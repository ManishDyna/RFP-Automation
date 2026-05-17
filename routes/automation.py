from fastapi import APIRouter, Body, HTTPException, UploadFile, File, Form, Query
from automation_logic import run_automation_download, run_automation_download_open_rfps, run_automation_submit, run_automation_decline, run_automation_reminder, run_automation_sync_portal, run_sync_sharepoint_dataverse

# Import shared progress helper
from helpers.progress_helper import update_progress as _update_progress, get_progress as _get_progress, reset_progress as _reset_progress

# Export helper functions for use in other routes
__all__ = [
    '_RUN_STATE', '_STATE_LOCK', '_set_state', '_try_start_operation', '_finish_operation',
    '_add_submitting_rfp', '_remove_submitting_rfp', '_is_rfp_submitting', '_get_state_snapshot',
    '_run_async_in_thread', '_update_progress', '_get_progress'
]
from services.system_settings_service import get_setting
from services.dashboard_service import invalidate_dashboard_caches
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
    get_sharepoint_rfp_savedrfp_path,
    get_rfp_tds_folder_path,
    get_rfp_savedrfp_folder_path
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

# Thread-safe lock for concurrent operation protection
_STATE_LOCK = threading.Lock()

# In-memory run-state flags for UI reflection
_RUN_STATE = {
    "download": False,
    "submit": False,
    "decline": False,
    "sync": False,
    "sync_sp_dv": False,  # SharePoint-Dataverse sync
    "sync_all": False,    # 3-way sync (Dataverse + SharePoint + Local)
    "last": None,
    "submitting_rfps": set(),  # Track specific RFP IDs being submitted
}

def _set_state(key: str, value: bool):
    """Thread-safe state setter"""
    with _STATE_LOCK:
        _RUN_STATE[key] = value
        if value:
            _RUN_STATE["last"] = key
        else:
            # Reset progress when operation completes
            _reset_progress(key)

def _try_start_operation(key: str) -> bool:
    """
    Thread-safe atomic check-and-set for starting an operation.
    Returns True if operation can start (was not already running).
    Returns False if operation is already running.
    """
    with _STATE_LOCK:
        if _RUN_STATE.get(key):
            return False  # Already running
        _RUN_STATE[key] = True
        _RUN_STATE["last"] = key
        return True

def _finish_operation(key: str):
    """Thread-safe operation completion handler"""
    with _STATE_LOCK:
        _RUN_STATE[key] = False
        _reset_progress(key)

def _add_submitting_rfp(rfp_id: str):
    """Thread-safe: Add RFP ID to submitting set"""
    with _STATE_LOCK:
        _RUN_STATE["submitting_rfps"].add(rfp_id)

def _remove_submitting_rfp(rfp_id: str):
    """Thread-safe: Remove RFP ID from submitting set"""
    with _STATE_LOCK:
        _RUN_STATE["submitting_rfps"].discard(rfp_id)

def _is_rfp_submitting(rfp_id: str) -> bool:
    """Thread-safe: Check if specific RFP is being submitted"""
    with _STATE_LOCK:
        return rfp_id in _RUN_STATE["submitting_rfps"]

def _get_state_snapshot() -> dict:
    """Thread-safe: Get a copy of current state for reading"""
    with _STATE_LOCK:
        return {
            "download": _RUN_STATE.get("download", False),
            "submit": _RUN_STATE.get("submit", False),
            "decline": _RUN_STATE.get("decline", False),
            "sync": _RUN_STATE.get("sync", False),
            "sync_sp_dv": _RUN_STATE.get("sync_sp_dv", False),
            "sync_all": _RUN_STATE.get("sync_all", False),
            "last": _RUN_STATE.get("last"),
            "submitting_rfps": list(_RUN_STATE.get("submitting_rfps", set())),
        }

@router.get("/automation/status")
async def automation_status():
    # Get thread-safe snapshot of current state
    state = _get_state_snapshot()

    # Determine overall status for frontend
    is_running = (
        state["download"] or
        state["submit"] or
        state["decline"] or
        state["sync"] or
        state["sync_sp_dv"] or
        state["sync_all"]
    )
    status = "Running" if is_running else "Ready"

    # Calculate overall progress based on running operation
    overall_progress = 0
    if state["download"]:
        overall_progress = _get_progress("download")["percentage"]
    elif state["submit"]:
        overall_progress = _get_progress("submit")["percentage"]
    elif state["decline"]:
        overall_progress = _get_progress("decline")["percentage"]
    elif state["sync"]:
        overall_progress = _get_progress("sync")["percentage"]
    elif state["sync_sp_dv"]:
        overall_progress = _get_progress("sync_sp_dv")["percentage"]
    elif state["sync_all"]:
        overall_progress = _get_progress("sync_all")["percentage"]

    return {
        "ok": True,
        "status": status,
        "progress": overall_progress,
        "download_running": state["download"],
        "submit_running": state["submit"],
        "decline_running": state["decline"],
        "sync_running": state["sync"],
        "sync_sp_dv_running": state["sync_sp_dv"],
        "sync_all_running": state["sync_all"],
        "last": state["last"],
        "submitting_rfps": state["submitting_rfps"],
        # Detailed progress for each operation
        "progress_details": {
            "download": _get_progress("download") if state["download"] else None,
            "submit": _get_progress("submit") if state["submit"] else None,
            "decline": _get_progress("decline") if state["decline"] else None,
            "sync": _get_progress("sync") if state["sync"] else None,
            "sync_sp_dv": _get_progress("sync_sp_dv") if state["sync_sp_dv"] else None,
            "sync_all": _get_progress("sync_all") if state["sync_all"] else None,
        }
    }

@router.get("/download-rfp")
async def download_rfp_endpoint(company: str = Query("", alias="company")):
    selected_company = (company or "").strip()

    # Thread-safe atomic check-and-set
    if not _try_start_operation("download"):
        return JSONResponse({"ok": False, "message": "Download already running"}, status_code=409)

    async def _task():
        try:
            await run_automation_download(selected_company or None)
        finally:
            _finish_operation("download")

    # Run in separate thread with ProactorEventLoop for Windows Playwright compatibility
    _run_async_in_thread(_task)
    return JSONResponse({"ok": True, "started": True}, status_code=202)

@router.get("/download-rfps-automation")
async def download_rfps_automation_endpoint():
    """Download RFPs automation for ALL companies (iterates through all configured companies)."""
    # Thread-safe atomic check-and-set
    if not _try_start_operation("download"):
        return JSONResponse({"ok": False, "message": "Download already running"}, status_code=409)

    async def _task():
        try:
            await run_automation_download_open_rfps()
        finally:
            _finish_operation("download")

    # Run in separate thread with ProactorEventLoop for Windows Playwright compatibility
    _run_async_in_thread(_task)
    return JSONResponse({"ok": True, "started": True, "mode": "all_companies"}, status_code=202)

## moved /dashboard/rfp-preview endpoint to routes/dashboard.py

@router.post("/dashboard/submit-rfp")
async def dashboard_submit_rfp_endpoint(
    rfp_id: str = Form(...),
    excel_file: UploadFile = File(...),
    technical_files: list[UploadFile] = File(default=[]),
    existing_tds_files: list[str] = Form(default=[]),
    company: str = Form("")
 ):
    """
    Dashboard-specific endpoint: Upload file to SharePoint, then run automation
    """
    selected_company = (company or "").strip()
    print(f"Dashboard Submit RFP - RFP ID: {rfp_id} - Company: {selected_company or get_setting('COMPANY_NAME', '')}")
    print(f"File received: {excel_file.filename}")
    
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
        
        print(f"[Saved] Temporary file saved: {temp_file_path}")
        
        # Initialize SharePoint client and upload file
        graph_client = GraphClient(
            get_setting("CLIENT_ID", ""), get_setting("CLIENT_SECRET", ""), get_setting("TENANT_ID", ""),
            get_setting("SHAREPOINT_HOSTNAME", ""), get_setting("SITE_PATH", ""), get_setting("DRIVE_NAME", "")
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
        target_company = selected_company or get_setting("COMPANY_NAME", "")
        sp_material_path = get_sharepoint_rfp_material_path(rfp_id, target_company)
        print(f"[Upload] Uploading to SharePoint: {sp_material_path}/{clean_title}{file_ext}")
        graph_client.upload_file_as(
            temp_file_path, 
            sp_material_path,
            f"{clean_title}{file_ext}"
        )
        
        print(f"[OK] File uploaded to SharePoint (downloaded-rfp) successfully")

        # ==== Also save the uploaded (filled) file to rfp-upload-file folder ====
        # This is the folder the automation checks FIRST when importing the Excel file
        try:
            sp_savedrfp_path = get_sharepoint_rfp_savedrfp_path(rfp_id, target_company)
            print(f"[Upload] Uploading to SharePoint (rfp-upload-file): {sp_savedrfp_path}/{clean_title}{file_ext}")
            graph_client.upload_file_as(
                temp_file_path,
                sp_savedrfp_path,
                f"{clean_title}{file_ext}"
            )
            print(f"[OK] File uploaded to SharePoint (rfp-upload-file) successfully")

            # Also save locally to rfp-upload-file folder
            local_savedrfp_folder = get_rfp_savedrfp_folder_path(rfp_id, target_company)
            local_savedrfp_path = os.path.join(local_savedrfp_folder, f"{clean_title}{file_ext}")
            with open(temp_file_path, "rb") as src:
                with open(local_savedrfp_path, "wb") as dst:
                    dst.write(src.read())
            print(f"[Saved] Saved uploaded file locally: {local_savedrfp_path}")
        except Exception as e:
            print(f"[WARN] Could not save to rfp-upload-file folder: {e}")

        # ==== Upload technical PDF files (if provided) to new folder structure ====
        # New structure: RFP-logs/ALLRFPs/CompanyName/RFP_title/TDS-files/
        # Also save locally: ALLRFPs/CompanyName/RFP_title/TDS-files/
        # Filter to actual PDF files only
        valid_tds_files = []
        for uf in technical_files:
            if not uf or not (uf.filename or "").strip():
                continue
            pdf_ext = os.path.splitext(uf.filename or "")[1].lower()
            if pdf_ext == ".pdf":
                valid_tds_files.append(uf)

        print(f"[Attachment] TDS files received: {len(valid_tds_files)} PDF(s) - {[uf.filename for uf in valid_tds_files]}")

        if valid_tds_files:
            sp_tds_folder = get_sharepoint_rfp_tds_path(rfp_id, target_company)
            local_tds_folder = get_rfp_tds_folder_path(rfp_id, target_company)
            uploaded_count = 0

            for uf in valid_tds_files:
                try:
                    content = await uf.read()
                    if not content:
                        print(f"[WARN] TDS file '{uf.filename}' has empty content, skipping")
                        continue

                    remote_name = os.path.basename(uf.filename or "").strip()
                    if not remote_name:
                        remote_name = f"TDS_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

                    # Save to temp file for SharePoint upload
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tpdf:
                        tpdf.write(content)
                        temp_pdf_paths.append(tpdf.name)

                    # Upload to SharePoint
                    print(f"[Upload] Uploading TDS to SharePoint: {sp_tds_folder}/{remote_name}")
                    graph_client.upload_file_as(
                        temp_pdf_paths[-1],
                        sp_tds_folder,
                        remote_name
                    )
                    print(f"[OK] TDS uploaded to SharePoint: {remote_name}")

                    # Save to local folder
                    local_tds_path = os.path.join(local_tds_folder, remote_name)
                    with open(local_tds_path, "wb") as local_file:
                        local_file.write(content)
                    print(f"[Saved] TDS saved locally: {local_tds_path}")
                    uploaded_count += 1

                except Exception as e:
                    print(f"[ERROR] Failed to upload TDS file '{uf.filename}': {e}")

            print(f"TDS upload complete: {uploaded_count}/{len(valid_tds_files)} files saved to TDS-files folder")

        # Build the allow-list of TDS filenames the automation should use.
        # Combines: (a) names user picked from existing SharePoint files,
        #           (b) names of files just uploaded in this submission.
        # If empty, the automation falls back to using every PDF in the TDS folder
        # (preserves prior behavior for callers that don't send the new field).
        selected_existing = [name.strip() for name in (existing_tds_files or []) if (name or "").strip()]
        uploaded_names = [os.path.basename((uf.filename or "").strip()) for uf in valid_tds_files if (uf.filename or "").strip()]
        allowed_tds_filenames = list({n for n in (selected_existing + uploaded_names) if n}) or None
        if allowed_tds_filenames:
            print(f"[TDS] Restricting automation to {len(allowed_tds_filenames)} TDS file(s): {allowed_tds_filenames}")

        # Now trigger the automation in background
        # Thread-safe atomic check-and-set
        if not _try_start_operation("submit"):
            return JSONResponse({"ok": False, "message": "Submit already running"}, status_code=409)

        async def _task():
            try:
                await run_automation_submit(rfp_id, selected_company or None, allowed_tds_filenames=allowed_tds_filenames)
            finally:
                _finish_operation("submit")
                invalidate_dashboard_caches()  # Flush cache so Draft tab reflects immediately

        # Run in separate thread with ProactorEventLoop for Windows Playwright compatibility
        _run_async_in_thread(_task)
        return JSONResponse({
            "ok": True,
            "started": True,
            "message": f"File uploaded and RFP '{rfp_id}' automation started"
        }, status_code=202)
        
    except Exception as e:
        print(f"[ERROR] Error in dashboard submit RFP: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Submit RFP failed: {str(e)}")
        
    finally:
        # Clean up temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
                print(f"[Deleted] Temporary file deleted: {temp_file_path}")
            except Exception as e:
                print(f"[WARN] Could not delete temp file: {e}")
        # Clean up temp PDFs
        for p in temp_pdf_paths:
            try:
                if p and os.path.exists(p):
                    os.unlink(p)
            except Exception:
                pass

@router.get("/dashboard/list-tds-files")
async def list_existing_tds_files(rfp_id: str = Query(...), company: str = Query("")):
    """
    List existing PDF files in the SharePoint TDS-files folder for a given RFP.
    Used by the Submit RFP dialog so users can pick already-uploaded files instead
    of re-uploading them.
    """
    if not rfp_id:
        raise HTTPException(status_code=400, detail="rfp_id is required")

    target_company = (company or "").strip() or get_setting("COMPANY_NAME", "")
    tds_folder = get_sharepoint_rfp_tds_path(rfp_id, target_company)

    try:
        graph_client = GraphClient(
            get_setting("CLIENT_ID", ""), get_setting("CLIENT_SECRET", ""), get_setting("TENANT_ID", ""),
            get_setting("SHAREPOINT_HOSTNAME", ""), get_setting("SITE_PATH", ""), get_setting("DRIVE_NAME", "")
        )
        graph_client.auth()
        graph_client.resolve_site_and_drive()
        files = graph_client.list_files_in_directory(tds_folder, ['.pdf']) or []
    except Exception as e:
        print(f"[WARN] Could not list TDS folder for {rfp_id}/{target_company}: {e}")
        files = []

    return JSONResponse({
        "ok": True,
        "rfp_id": rfp_id,
        "company": target_company,
        "folder": tds_folder,
        "files": [{"name": f.get("name", ""), "path": f.get("path", "")} for f in files],
    })


@router.post("/submit-rfp")
async def submit_rfp_endpoint(payload: dict = Body(...)):
    """Original endpoint for Postman - unchanged"""
    rfp_id = payload.get("rfp_id")
    selected_company = (payload.get("company") or "").strip()
    print("rfp_id:-",rfp_id)
    if not rfp_id:
        raise HTTPException(status_code=400, detail="rfp_id is required")

    # Thread-safe atomic check-and-set
    if not _try_start_operation("submit"):
        return JSONResponse({"ok": False, "message": "Submit already running"}, status_code=409)

    async def _task():
        try:
            await run_automation_submit(rfp_id, selected_company or None)
        finally:
            _finish_operation("submit")

    # Run in separate thread with ProactorEventLoop for Windows Playwright compatibility
    _run_async_in_thread(_task)
    return JSONResponse({"ok": True, "started": True}, status_code=202)

@router.get("/sync_portal_data")
async def dashboard_sync_portal_data(rfp_ids: str = Query("", alias="rfp_ids")):
    """
    Sync portal participation status.
    - If rfp_ids is provided (comma-separated), only sync those specific RFPs (dashboard mode).
    - If rfp_ids is empty, sync ALL RFPs (full sync from RFP Insights).
    """
    # Thread-safe atomic check-and-set
    if not _try_start_operation("sync"):
        return JSONResponse({"ok": False, "message": "Sync already running"}, status_code=409)

    # Parse rfp_ids if provided
    parsed_rfp_ids = None
    if rfp_ids and rfp_ids.strip():
        parsed_rfp_ids = [rid.strip() for rid in rfp_ids.split(",") if rid.strip()]

    async def _task():
        try:
            await run_automation_sync_portal(rfp_ids=parsed_rfp_ids)
        finally:
            _finish_operation("sync")

    # Run in separate thread with ProactorEventLoop for Windows Playwright compatibility
    _run_async_in_thread(_task)
    return JSONResponse({"ok": True, "started": True}, status_code=202)


@router.get("/sync-sharepoint-dataverse")
async def sync_sharepoint_dataverse_endpoint(company: str = Query("", alias="company")):
    """
    Sync RFP files between SharePoint and Dataverse.

    If Dataverse has an RFP entry but file is missing in SharePoint,
    download from portal and upload to SharePoint, then update timestamp.
    """
    selected_company = (company or "").strip()

    # Thread-safe atomic check-and-set
    if not _try_start_operation("sync_sp_dv"):
        return JSONResponse({"ok": False, "message": "SharePoint-Dataverse sync already running"}, status_code=409)

    async def _task():
        try:
            await run_sync_sharepoint_dataverse(selected_company or None)
        finally:
            _finish_operation("sync_sp_dv")

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

    # Thread-safe atomic check-and-set
    if not _try_start_operation("decline"):
        return JSONResponse({"ok": False, "message": "Decline already running"}, status_code=409)

    async def _task():
        try:
            await run_automation_decline(rfp_id, selected_company or None)
        finally:
            _finish_operation("decline")
    # Run in separate thread with ProactorEventLoop for Windows Playwright compatibility
    _run_async_in_thread(_task)
    return JSONResponse({"ok": True, "started": True}, status_code=202)

@router.get("/rfp-reminder")
async def rfp_reminder_endpoint():
    return await run_automation_reminder()



