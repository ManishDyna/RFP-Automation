import json
import os
import traceback
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from config.config import FAILURE_LOGS_DIR, SP_FAILURE_LOGS_FOLDER, AUTOMATION_LOG_TABLE_API, AUTOMATION_LOG_TABLE_LOGICAL
from helpers.core_helper import DATAVERSE


def _timestamp_slug() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def _normalize_automation_label(name: Optional[str]) -> str:
    safe = (name or "automation").strip().replace(" ", "_").replace("/", "_")
    return safe or "automation"


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
) -> Dict[str, Any]:
    """
    Create a JSON log describing the exception, persist locally, and optionally upload to SharePoint.
    Returns metadata about the created artifacts.
    """
    os.makedirs(FAILURE_LOGS_DIR, exist_ok=True)

    context = context or {}
    details = _extract_exception_details(exc)
    details.update(
        {
            "timestamp": datetime.utcnow().isoformat(),
            "context": context,
        }
    )

    automation_label = _normalize_automation_label(context.get("automation"))
    file_name = f"{automation_label}_failure_{_timestamp_slug()}_{uuid.uuid4().hex[:6]}.json"
    local_path = os.path.join(FAILURE_LOGS_DIR, file_name)

    with open(local_path, "w", encoding="utf-8") as fp:
        json.dump(details, fp, indent=2, ensure_ascii=False)

    sharepoint_path = None
    sharepoint_full_path = None
    upload_error = None

    if graph_client:
        try:
            graph_client.upload_file_as(local_path, SP_FAILURE_LOGS_FOLDER, file_name)
            sharepoint_path = f"{SP_FAILURE_LOGS_FOLDER}/{file_name}"
            sharepoint_full_path = f"/Shared Documents/{sharepoint_path}"
        except Exception as upload_exc:  # noqa: BLE001
            upload_error = str(upload_exc)

    return {
        "file_name": file_name,
        "local_path": local_path,
        "sharepoint_path": sharepoint_path,
        "sharepoint_full_path": sharepoint_full_path,
        "details": details,
        "upload_error": upload_error,
    }


def create_rfp_error_log_file(
    rfp_id: str,
    context: Optional[Dict[str, Any]] = None,
    graph_client: Any = None,
) -> Dict[str, Any]:
    """
    Create an enhanced error log file for a specific RFP by fetching automation logs from Dataverse.
    Uses enhanced error analysis to identify exactly where automation failed.
    Returns metadata about the created log file.
    """
    os.makedirs(FAILURE_LOGS_DIR, exist_ok=True)
    
    context = context or {}
    
    # Fetch automation logs for this RFP from Dataverse
    logs = []
    try:
        rows = DATAVERSE.get_rows_from_dataverse(
            table_api_name=AUTOMATION_LOG_TABLE_API,
            filter_by={"RFP_ID": rfp_id},
            select_columns=["RunID", "Timestamp", "Category", "Action", "automation_status", "Message", "RFP_ID"],
            top=500,  # Get up to 500 log entries for this RFP
            order_by="Timestamp desc",  # Most recent first
            table_logical_name=AUTOMATION_LOG_TABLE_LOGICAL,
            use_display_names=True
        )
        logs = rows if rows else []
    except Exception as e:
        print(f"⚠️  Could not fetch automation logs for RFP {rfp_id}: {e}")
        logs = []
    
    # Use enhanced error analysis
    try:
        from helpers.enhanced_error_logger import create_enhanced_error_report, format_error_report_for_display
        
        # Create enhanced error report with analysis
        log_data = create_enhanced_error_report(rfp_id, logs, context)
        
        # Print formatted report to console for debugging
        print("\n" + "=" * 80)
        print("📊 ENHANCED ERROR REPORT GENERATED")
        print("=" * 80)
        print(format_error_report_for_display(log_data))
        print("=" * 80 + "\n")
        
    except Exception as e:
        # Fallback to basic log structure if enhanced logger fails
        print(f"⚠️  Could not create enhanced error report: {e}")
        log_data = {
            "rfp_id": rfp_id,
            "timestamp": datetime.utcnow().isoformat(),
            "context": context,
            "automation_logs": logs,
            "total_log_entries": len(logs),
            "enhanced_analysis_error": str(e)
        }
    
    # Generate filename
    safe_rfp_id = _normalize_automation_label(rfp_id)
    file_name = f"rfp_error_{safe_rfp_id}_{_timestamp_slug()}_{uuid.uuid4().hex[:6]}.json"
    local_path = os.path.join(FAILURE_LOGS_DIR, file_name)
    
    # Write log file
    with open(local_path, "w", encoding="utf-8") as fp:
        json.dump(log_data, fp, indent=2, ensure_ascii=False)
    
    # Also create a human-readable text version
    try:
        txt_file_name = file_name.replace('.json', '.txt')
        txt_local_path = os.path.join(FAILURE_LOGS_DIR, txt_file_name)
        
        with open(txt_local_path, "w", encoding="utf-8") as fp:
            fp.write(format_error_report_for_display(log_data))
        
        print(f"✅ Human-readable report saved: {txt_local_path}")
    except Exception as e:
        print(f"⚠️  Could not create text report: {e}")
    
    sharepoint_path = None
    sharepoint_full_path = None
    upload_error = None
    
    # Upload to SharePoint if graph_client is provided
    if graph_client:
        try:
            graph_client.upload_file_as(local_path, SP_FAILURE_LOGS_FOLDER, file_name)
            sharepoint_path = f"{SP_FAILURE_LOGS_FOLDER}/{file_name}"
            sharepoint_full_path = f"/Shared Documents/{sharepoint_path}"
            
            # Also upload the text version if it exists
            try:
                if os.path.exists(txt_local_path):
                    graph_client.upload_file_as(txt_local_path, SP_FAILURE_LOGS_FOLDER, txt_file_name)
            except:
                pass
                
        except Exception as upload_exc:
            upload_error = str(upload_exc)
            print(f"⚠️  Could not upload error log to SharePoint: {upload_error}")
    
    return {
        "file_name": file_name,
        "local_path": local_path,
        "sharepoint_path": sharepoint_path,
        "sharepoint_full_path": sharepoint_full_path,
        "log_data": log_data,
        "upload_error": upload_error,
        "error_summary": log_data.get("error_summary", ""),
        "automation_status": log_data.get("automation_status", "UNKNOWN")
    }

