from fastapi import APIRouter, Body, HTTPException, UploadFile, File, Form, Query
from automation_logic import run_automation_download, run_automation_submit, run_automation_decline, run_automation_reminder, run_automation_sync_portal

# Export helper functions for use in other routes
__all__ = ['_RUN_STATE', '_set_state', '_add_submitting_rfp', '_remove_submitting_rfp', '_is_rfp_submitting']
from config.config import (
    SP_BASE_FOLDER_RFP_UPLOAD_FILES,
    CLIENT_ID,
    CLIENT_SECRET,
    TENANT_ID,
    SHAREPOINT_HOSTNAME,
    SITE_PATH,
    DRIVE_NAME,
    COMPANY_NAME,
)
from helpers.sharepoint_helper import GraphClient
import tempfile
import os
import sys
import asyncio
import threading
from datetime import datetime
from fastapi.responses import JSONResponse
import pandas as pd
from io import BytesIO
from helpers.core_helper import (
    find_column_name,
    normalize_filename,
    clean_rfp_title,
    get_sharepoint_rfp_material_path,
    get_sharepoint_rfp_tds_path,
    get_rfp_tds_folder_path
)


def _run_async_in_thread(coro_func, *args, **kwargs):
    """
    Run an async function in a separate thread with its own ProactorEventLoop.
    This is required on Windows because Playwright needs ProactorEventLoop for subprocess support,
    but uvicorn uses SelectorEventLoop which doesn't support subprocesses.
    """
    def _thread_target():
        # Create a new event loop for this thread
        if sys.platform == "win32":
            # Use ProactorEventLoop on Windows for subprocess support
            loop = asyncio.ProactorEventLoop()
        else:
            loop = asyncio.new_event_loop()

        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(coro_func(*args, **kwargs))
        finally:
            loop.close()

    thread = threading.Thread(target=_thread_target, daemon=True)
    thread.start()

router = APIRouter( tags=["Automation"]) 

# In-memory run-state flags for UI reflection
_RUN_STATE = {
    "download": False,
    "submit": False,
    "decline": False,
    "sync": False,
    "last": None,
    "submitting_rfps": set(),  # Track specific RFP IDs being submitted
}

def _set_state(key: str, value: bool):
    _RUN_STATE[key] = value
    if value:
        _RUN_STATE["last"] = key

def _add_submitting_rfp(rfp_id: str):
    """Add RFP ID to submitting set"""
    _RUN_STATE["submitting_rfps"].add(rfp_id)

def _remove_submitting_rfp(rfp_id: str):
    """Remove RFP ID from submitting set"""
    _RUN_STATE["submitting_rfps"].discard(rfp_id)

def _is_rfp_submitting(rfp_id: str) -> bool:
    """Check if specific RFP is being submitted"""
    return rfp_id in _RUN_STATE["submitting_rfps"]

@router.get("/automation/status")
async def automation_status():
    # Determine overall status for frontend
    is_running = (
        _RUN_STATE.get("download") or
        _RUN_STATE.get("submit") or
        _RUN_STATE.get("decline") or
        _RUN_STATE.get("sync")
    )
    status = "Running" if is_running else "Ready"

    return {
        "ok": True,
        "status": status,
        "progress": 50 if is_running else 0,  # Simplified progress indicator
        "download_running": bool(_RUN_STATE.get("download")),
        "submit_running": bool(_RUN_STATE.get("submit")),
        "decline_running": bool(_RUN_STATE.get("decline")),
        "sync_running": bool(_RUN_STATE.get("sync")),
        "last": _RUN_STATE.get("last"),
        "submitting_rfps": list(_RUN_STATE.get("submitting_rfps", set())),
    }

@router.get("/download-rfp")
async def download_rfp_endpoint(company: str = Query("", alias="company")):
    selected_company = (company or "").strip()
    if _RUN_STATE.get("download"):
        return JSONResponse({"ok": False, "message": "Download already running"}, status_code=409)

    async def _task():
        try:
            _set_state("download", True)
            await run_automation_download(selected_company or None)
        finally:
            _set_state("download", False)

    # Run in separate thread with ProactorEventLoop for Windows Playwright compatibility
    _run_async_in_thread(_task)
    return JSONResponse({"ok": True, "started": True}, status_code=202)

## moved /dashboard/rfp-preview endpoint to routes/dashboard.py

@router.post("/dashboard/submit-rfp")
async def dashboard_submit_rfp_endpoint(
    rfp_id: str = Form(...),
    excel_file: UploadFile = File(...),
    technical_files: list[UploadFile] = File(default=[]),
    company: str = Form("")
 ):
    """
    Dashboard-specific endpoint: Upload file to SharePoint, then run automation
    """
    selected_company = (company or "").strip()
    print(f"📝 Dashboard Submit RFP - RFP ID: {rfp_id} - Company: {selected_company or COMPANY_NAME}")
    print(f"📄 File received: {excel_file.filename}")
    
    if not rfp_id or not excel_file:
        raise HTTPException(status_code=400, detail="Both rfp_id and excel_file are required")
    
    # Validate file extension
    allowed_extensions = ['.xls', '.xlsx']
    file_ext = os.path.splitext(excel_file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"Invalid file type. Only {', '.join(allowed_extensions)} files are allowed")
    
    temp_file_path = None
    temp_pdf_paths = []
    try:
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
            content = await excel_file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        print(f"💾 Temporary file saved: {temp_file_path}")
        
        # Initialize SharePoint client and upload file
        graph_client = GraphClient(
            CLIENT_ID, CLIENT_SECRET, TENANT_ID,
            SHAREPOINT_HOSTNAME, SITE_PATH, DRIVE_NAME
        )
        graph_client.auth()
        graph_client.resolve_site_and_drive()
        
        # Rename the temporary file to match RFP ID before upload
        renamed_file_path = os.path.join(os.path.dirname(temp_file_path), f"{rfp_id}{file_ext}")
        # Delete the target file if it already exists (Windows issue)
        if os.path.exists(renamed_file_path):
            os.unlink(renamed_file_path)

        os.rename(temp_file_path, renamed_file_path)
        temp_file_path = renamed_file_path
        
        # Upload file to SharePoint using new folder structure
        clean_title = clean_rfp_title(rfp_id)
        target_company = selected_company or COMPANY_NAME
        sp_material_path = get_sharepoint_rfp_material_path(rfp_id, target_company)
        print(f"☁️ Uploading to SharePoint: {sp_material_path}/{clean_title}{file_ext}")
        graph_client.upload_file_as(
            temp_file_path, 
            sp_material_path,
            f"{clean_title}{file_ext}"
        )
        
        print(f"✅ File uploaded to SharePoint successfully")

        # ==== Upload technical PDF files (if provided) to new folder structure ====
        # New structure: RFP-logs/ALLRFPs/CompanyName/RFP_title/TDS-files/
        # Also save locally: ALLRFPs/CompanyName/RFP_title/TDS-files/
        try:
            if technical_files:
                sp_tds_folder = get_sharepoint_rfp_tds_path(rfp_id, target_company)
                local_tds_folder = get_rfp_tds_folder_path(rfp_id, target_company)  # Get local TDS folder path
                
                for uf in technical_files:
                    if not uf:  # safety
                        continue
                    pdf_ext = os.path.splitext(uf.filename or "")[1].lower()
                    if pdf_ext != ".pdf":
                        continue
                    
                    # Read file content
                    content = await uf.read()
                    if not content:
                        continue
                    
                    # Build remote name keeping original
                    remote_name = os.path.basename(uf.filename or "").strip()
                    if not remote_name:
                        # Generate a name if not provided
                        remote_name = f"TDS_{datetime.now().strftime('%Y%m%d_%H%M%S')}{pdf_ext}"
                    
                    # Save to temp file for SharePoint upload
                    with tempfile.NamedTemporaryFile(delete=False, suffix=pdf_ext) as tpdf:
                        tpdf.write(content)
                        temp_pdf_paths.append(tpdf.name)
                    
                    # Upload to SharePoint
                    print(f"☁️ Uploading technical PDF to SharePoint: {sp_tds_folder}/{remote_name}")
                    graph_client.upload_file_as(
                        temp_pdf_paths[-1],
                        sp_tds_folder,
                        remote_name
                    )
                    
                    # Save to local folder structure: ALLRFPs/RFP_title/TDS-files/
                    local_tds_path = os.path.join(local_tds_folder, remote_name)
                    with open(local_tds_path, "wb") as local_file:
                        local_file.write(content)
                    print(f"💾 Saved TDS file locally: {local_tds_path}")
                    
                print("✅ Technical PDFs uploaded to SharePoint and saved locally")
        except Exception as e:
            print(f"⚠️ Technical PDFs upload/save error: {e}")
        
        # Now trigger the automation in background
        if _RUN_STATE.get("submit"):
            return JSONResponse({"ok": False, "message": "Submit already running"}, status_code=409)

        async def _task():
            try:
                _set_state("submit", True)
                await run_automation_submit(rfp_id, selected_company or None)
            finally:
                _set_state("submit", False)

        # Run in separate thread with ProactorEventLoop for Windows Playwright compatibility
        _run_async_in_thread(_task)
        return JSONResponse({
            "ok": True,
            "started": True,
            "message": f"File uploaded and RFP '{rfp_id}' automation started"
        }, status_code=202)
        
    except Exception as e:
        print(f"❌ Error in dashboard submit RFP: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Submit RFP failed: {str(e)}")
        
    finally:
        # Clean up temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
                print(f"🗑️ Temporary file deleted: {temp_file_path}")
            except Exception as e:
                print(f"⚠️ Could not delete temp file: {e}")
        # Clean up temp PDFs
        for p in temp_pdf_paths:
            try:
                if p and os.path.exists(p):
                    os.unlink(p)
            except Exception:
                pass

@router.post("/submit-rfp")
async def submit_rfp_endpoint(payload: dict = Body(...)):
    """Original endpoint for Postman - unchanged"""
    rfp_id = payload.get("rfp_id")
    selected_company = (payload.get("company") or "").strip()
    print("rfp_id:-",rfp_id)
    if not rfp_id:
        raise HTTPException(status_code=400, detail="rfp_id is required")
    if _RUN_STATE.get("submit"):
        return JSONResponse({"ok": False, "message": "Submit already running"}, status_code=409)
    async def _task():
        try:
            _set_state("submit", True)
            await run_automation_submit(rfp_id, selected_company or None)
        finally:
            _set_state("submit", False)
    # Run in separate thread with ProactorEventLoop for Windows Playwright compatibility
    _run_async_in_thread(_task)
    return JSONResponse({"ok": True, "started": True}, status_code=202)

@router.get("/sync_portal_data")
async def dashboard_sync_portal_data():
    if _RUN_STATE.get("sync"):
        return JSONResponse({"ok": False, "message": "Sync already running"}, status_code=409)

    async def _task():
        try:
            _set_state("sync", True)
            await run_automation_sync_portal()
        finally:
            _set_state("sync", False)

    # Run in separate thread with ProactorEventLoop for Windows Playwright compatibility
    _run_async_in_thread(_task)
    return JSONResponse({"ok": True, "started": True}, status_code=202)

@router.post("/decline-rfp")
async def decline_rfp_endpoint(payload: dict = Body(...)):
    # Accept both rfp_id and rfp_title for frontend compatibility
    rfp_id = payload.get("rfp_id") or payload.get("rfp_title")
    selected_company = (payload.get("company") or "").strip()
    if not rfp_id:
        raise HTTPException(status_code=400, detail="rfp_id or rfp_title is required")
    if _RUN_STATE.get("decline"):
        return JSONResponse({"ok": False, "message": "Decline already running"}, status_code=409)
    async def _task():
        try:
            _set_state("decline", True)
            await run_automation_decline(rfp_id, selected_company or None)
        finally:
            _set_state("decline", False)
    # Run in separate thread with ProactorEventLoop for Windows Playwright compatibility
    _run_async_in_thread(_task)
    return JSONResponse({"ok": True, "started": True}, status_code=202)

@router.get("/rfp-reminder")
async def rfp_reminder_endpoint():
    return await run_automation_reminder()


