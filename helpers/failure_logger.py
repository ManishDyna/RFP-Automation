import json
import os
import traceback
import uuid
import asyncio
from datetime import datetime
from typing import Any, Dict, Optional

from services.system_settings_service import get_setting
from helpers.core_helper import DATAVERSE


def _timestamp_slug() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def _unique_slug() -> str:
    return f"{_timestamp_slug()}_{uuid.uuid4().hex[:6]}"


def _normalize_automation_label(name: Optional[str]) -> str:
    safe = (name or "automation").strip().replace(" ", "_").replace("/", "_")
    return safe or "automation"


def _create_error_folder(folder_name: str) -> str:
    """Create a unique error folder locally and return its path."""
    folder_path = os.path.join(get_setting("FAILURE_LOGS_DIR", os.path.join(os.getcwd(), "LOGS")), folder_name)
    os.makedirs(folder_path, exist_ok=True)
    return folder_path


async def capture_screenshot(page, save_path: str) -> Optional[str]:
    """
    Capture a screenshot from a Playwright page object.
    Returns the saved screenshot path, or None on failure.
    """
    if page is None:
        return None
    try:
        await page.screenshot(path=save_path, full_page=True)
        print(f"📸 Screenshot saved: {save_path}")
        return save_path
    except Exception as e:
        print(f"⚠️  Could not capture screenshot: {e}")
        return None


def capture_screenshot_sync(page, save_path: str) -> Optional[str]:
    """
    Synchronous wrapper to capture a screenshot.
    Only works when no event loop is running. For async contexts, use capture_screenshot directly.
    """
    if page is None:
        return None
    try:
        return asyncio.run(capture_screenshot(page, save_path))
    except Exception as e:
        print(f"⚠️  Could not capture screenshot (sync): {e}")
        return None


def _upload_folder_to_sharepoint(graph_client, local_folder: str, sp_folder: str) -> list:
    """Upload all files from a local folder to a SharePoint folder. Returns list of uploaded file names."""
    uploaded = []
    if not graph_client or not os.path.isdir(local_folder):
        return uploaded
    for fname in os.listdir(local_folder):
        fpath = os.path.join(local_folder, fname)
        if os.path.isfile(fpath):
            try:
                graph_client.upload_file_as(fpath, sp_folder, fname)
                uploaded.append(fname)
            except Exception as e:
                print(f"⚠️  Could not upload {fname} to SharePoint: {e}")
    return uploaded


def _extract_exception_details(exc: Exception) -> Dict[str, Any]:
    frames = []
    tb = exc.__traceback__
    if tb:
        for frame in traceback.extract_tb(tb):
            frames.append(
                {
                    "file": frame.filename,
                    "line": frame.lineno,
                    "function": frame.name,
                    "code": frame.line,
                }
            )
    primary = frames[-1] if frames else {}
    return {
        "error_type": exc.__class__.__name__,
        "error_message": str(exc),
        "file": primary.get("file"),
        "line": primary.get("line"),
        "function": primary.get("function"),
        "stack": frames,
        "formatted_traceback": "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        ),
    }


def record_failure_log(
    exc: Exception,
    context: Optional[Dict[str, Any]] = None,
    graph_client: Any = None,
    screenshot_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a dedicated error folder with JSON log and optional screenshot,
    persist locally, and optionally upload the entire folder to SharePoint.
    Returns metadata about the created artifacts.
    """
    os.makedirs(get_setting("FAILURE_LOGS_DIR", os.path.join(os.getcwd(), "LOGS")), exist_ok=True)

    context = context or {}
    details = _extract_exception_details(exc)
    details.update(
        {
            "timestamp": datetime.utcnow().isoformat(),
            "context": context,
        }
    )

    automation_label = _normalize_automation_label(context.get("automation"))
    slug = _unique_slug()
    folder_name = f"{automation_label}_error_{slug}"

    # Create dedicated error folder
    error_folder = _create_error_folder(folder_name)

    # Write JSON log inside the folder
    file_name = f"{automation_label}_failure_{slug}.json"
    local_path = os.path.join(error_folder, file_name)
    with open(local_path, "w", encoding="utf-8") as fp:
        json.dump(details, fp, indent=2, ensure_ascii=False)

    # Copy screenshot into the error folder if provided
    if screenshot_path and os.path.isfile(screenshot_path):
        import shutil
        screenshot_dest = os.path.join(error_folder, "screenshot.png")
        if os.path.abspath(screenshot_path) != os.path.abspath(screenshot_dest):
            shutil.copy2(screenshot_path, screenshot_dest)
        details["screenshot"] = "screenshot.png"
        print(f"📸 Screenshot included in error folder: {folder_name}")

    sharepoint_path = None
    sharepoint_full_path = None
    upload_error = None

    # Upload entire error folder to SharePoint
    if graph_client:
        try:
            sp_error_folder = f"{get_setting('SP_FAILURE_LOGS_FOLDER', 'RFP-logs/automation-error-logs')}/{folder_name}"
            uploaded = _upload_folder_to_sharepoint(graph_client, error_folder, sp_error_folder)
            if uploaded:
                sharepoint_path = sp_error_folder
                sharepoint_full_path = f"/Shared Documents/{sp_error_folder}"
                print(f"✅ Error folder uploaded to SharePoint: {sp_error_folder} ({len(uploaded)} files)")
        except Exception as upload_exc:  # noqa: BLE001
            upload_error = str(upload_exc)

    return {
        "file_name": file_name,
        "local_path": local_path,
        "error_folder": error_folder,
        "folder_name": folder_name,
        "sharepoint_path": sharepoint_path,
        "sharepoint_full_path": sharepoint_full_path,
        "details": details,
        "upload_error": upload_error,
    }


def create_rfp_error_log_file(
    rfp_id: str,
    context: Optional[Dict[str, Any]] = None,
    graph_client: Any = None,
    screenshot_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a dedicated error folder with enhanced error log (JSON + TXT) and optional screenshot
    for a specific RFP by fetching automation logs from Dataverse.
    Uses enhanced error analysis to identify exactly where automation failed.
    Returns metadata about the created log file.
    """
    os.makedirs(get_setting("FAILURE_LOGS_DIR", os.path.join(os.getcwd(), "LOGS")), exist_ok=True)

    context = context or {}

    # Fetch automation logs for this RFP from Dataverse
    logs = []
    try:
        rows = DATAVERSE.get_rows_from_dataverse(
            table_api_name=get_setting("AUTOMATION_LOG_TABLE_API", "cr673_bahra_automation_log1s"),
            filter_by={"RFP_ID": rfp_id},
            select_columns=["RunID", "Timestamp", "Category", "Action", "automation_status", "Message", "RFP_ID"],
            top=500,
            order_by="Timestamp desc",
            table_logical_name=get_setting("AUTOMATION_LOG_TABLE_LOGICAL", "cr673_bahra_automation_log1"),
            use_display_names=True
        )
        logs = rows if rows else []
    except Exception as e:
        print(f"⚠️  Could not fetch automation logs for RFP {rfp_id}: {e}")
        logs = []

    # Use enhanced error analysis
    format_error_report_for_display = None
    try:
        from helpers.enhanced_error_logger import create_enhanced_error_report, format_error_report_for_display as _fmt
        format_error_report_for_display = _fmt

        log_data = create_enhanced_error_report(rfp_id, logs, context)

        print("\n" + "=" * 80)
        print("📊 ENHANCED ERROR REPORT GENERATED")
        print("=" * 80)
        print(format_error_report_for_display(log_data))
        print("=" * 80 + "\n")

    except Exception as e:
        print(f"⚠️  Could not create enhanced error report: {e}")
        log_data = {
            "rfp_id": rfp_id,
            "timestamp": datetime.utcnow().isoformat(),
            "context": context,
            "automation_logs": logs,
            "total_log_entries": len(logs),
            "enhanced_analysis_error": str(e)
        }

    # Create dedicated error folder
    safe_rfp_id = _normalize_automation_label(rfp_id)
    slug = _unique_slug()
    folder_name = f"rfp_error_{safe_rfp_id}_{slug}"
    error_folder = _create_error_folder(folder_name)

    # Write JSON log inside the folder
    file_name = f"rfp_error_{safe_rfp_id}_{slug}.json"
    local_path = os.path.join(error_folder, file_name)
    with open(local_path, "w", encoding="utf-8") as fp:
        json.dump(log_data, fp, indent=2, ensure_ascii=False)

    # Create human-readable text version inside the folder
    txt_file_name = file_name.replace('.json', '.txt')
    txt_local_path = os.path.join(error_folder, txt_file_name)
    try:
        if format_error_report_for_display:
            with open(txt_local_path, "w", encoding="utf-8") as fp:
                fp.write(format_error_report_for_display(log_data))
            print(f"✅ Human-readable report saved: {txt_local_path}")
    except Exception as e:
        print(f"⚠️  Could not create text report: {e}")

    # Copy screenshot into the error folder if provided
    if screenshot_path and os.path.isfile(screenshot_path):
        import shutil
        screenshot_dest = os.path.join(error_folder, "screenshot.png")
        if os.path.abspath(screenshot_path) != os.path.abspath(screenshot_dest):
            shutil.copy2(screenshot_path, screenshot_dest)
        log_data["screenshot"] = "screenshot.png"
        print(f"📸 Screenshot included in error folder: {folder_name}")

    sharepoint_path = None
    sharepoint_full_path = None
    upload_error = None

    # Upload entire error folder to SharePoint
    if graph_client:
        try:
            sp_error_folder = f"{get_setting('SP_FAILURE_LOGS_FOLDER', 'RFP-logs/automation-error-logs')}/{folder_name}"
            uploaded = _upload_folder_to_sharepoint(graph_client, error_folder, sp_error_folder)
            if uploaded:
                sharepoint_path = sp_error_folder
                sharepoint_full_path = f"/Shared Documents/{sp_error_folder}"
                print(f"✅ Error folder uploaded to SharePoint: {sp_error_folder} ({len(uploaded)} files)")
        except Exception as upload_exc:
            upload_error = str(upload_exc)
            print(f"⚠️  Could not upload error log to SharePoint: {upload_error}")

    return {
        "file_name": file_name,
        "local_path": local_path,
        "error_folder": error_folder,
        "folder_name": folder_name,
        "sharepoint_path": sharepoint_path,
        "sharepoint_full_path": sharepoint_full_path,
        "log_data": log_data,
        "upload_error": upload_error,
        "error_summary": log_data.get("error_summary", ""),
        "automation_status": log_data.get("automation_status", "UNKNOWN")
    }

