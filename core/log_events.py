from core.common_imports import *
from helpers.dataverse_helper import DataverseClient
import pandas as pd
import pytz
import os
import uuid
from datetime import datetime
import csv
from contextvars import ContextVar
from config.config import *
from services.system_settings_service import get_setting


def normalize_date_format(val) -> str:
    """Convert any date string to ISO 8601 format for Dataverse datetime column.

    Handles:
      - Slash format: 'MM/DD/YYYY HH:MM AM/PM'
      - Dash format:  'YYYY-DD-MM HH:MM:SS' (Excel locale swap)
      - Portal format: 'MM-DD-YYYY HH:MM'
      - ISO format: '2026-03-15T18:30:00Z' (pass through)

    Returns ISO 8601 string: 'YYYY-MM-DDTHH:MM:SSZ'
    """
    if not val or str(val).strip() in ("", "-"):
        return ""
    val = str(val).strip()

    # Already ISO format — pass through
    if "T" in val and (val.endswith("Z") or "+" in val[10:]):
        return val

    try:
        if "-" in val and "/" not in val:
            parts = val.split(" ", 1)
            date_part = parts[0]
            time_part = parts[1] if len(parts) > 1 else "00:00:00"
            chunks = date_part.split("-")

            if len(chunks) == 3 and len(chunks[0]) == 4:
                # YYYY-DD-MM format (Excel swapped day/month)
                y, d, m = chunks
                fixed = f"{y}-{m}-{d} {time_part}"
                dt = pd.to_datetime(fixed)
            else:
                # MM-DD-YYYY portal format
                dt = pd.to_datetime(val)
        else:
            # Slash format: MM/DD/YYYY HH:MM AM/PM
            dt = pd.to_datetime(val)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return str(val).strip()


def normalize_publish_time(val) -> str:
    """Return ISO 8601 string ('YYYY-MM-DDTHH:MM:SSZ') for the publish_time
    DateTime column (cr673_bahra_rfps_v2). This is the wire format Dataverse
    requires; the column is configured with TimeZoneIndependent behavior, so
    the wall-clock value we send is stored literally without UTC conversion
    and Power Apps still displays it as 'M/D/YYYY H:MM AM/PM' to users.

    Handles:
      * ISO 8601 with T-separator: '2019-08-27T16:00:00Z' (kept as-is)
      * Excel locale-swapped: 'YYYY-DD-MM HH:MM:SS'
      * MDY slash format: '10/6/2025 4:33 AM'
      * Other pandas-parseable formats

    Returns '' for blank/None input. Returns the raw stripped input on parse
    failure so we never silently mangle a value we can't understand.
    """
    if val is None or pd.isna(val) or str(val).strip() in ("", "-"):
        return ""
    val = str(val).strip()
    try:
        if "T" in val or val.endswith("Z"):
            dt = pd.to_datetime(val)
        elif "-" in val and "/" not in val:
            parts = val.split(" ", 1)
            date_part = parts[0]
            time_part = parts[1] if len(parts) > 1 else "00:00:00"
            y, d, m = date_part.split("-")
            fixed = f"{y}-{m}-{d} {time_part}"
            dt = pd.to_datetime(fixed)
        else:
            dt = pd.to_datetime(val)
        # Drop any tz so we emit naive wall-clock numbers. Column behavior is
        # TimeZoneIndependent → stored literally, no UTC conversion.
        if hasattr(dt, "tzinfo") and dt.tzinfo is not None:
            dt = dt.tz_localize(None) if hasattr(dt, "tz_localize") else dt.replace(tzinfo=None)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return str(val).strip()


# ==== CONFIGURE DATAVERSE ====
DATAVERSE = DataverseClient(
    tenant_id=TENANT_ID,
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    resource_url=RESOURCE_URL
)

# Current run ID - per async task using ContextVar (fixes concurrency overlap)
# Each concurrent automation process will have its own isolated run ID
_current_run_id: ContextVar[str | None] = ContextVar("run_id", default=None)

def start_new_run():
    """Generate a new unique RUN_ID for each automation run"""
    run_id = str(uuid.uuid4())
    _current_run_id.set(run_id)
    print(f"🆕 New RUN_ID generated: {run_id}")
    return run_id

def get_current_run_id():
    """Get the current RUN_ID, or generate a new one if not set"""
    run_id = _current_run_id.get()
    if run_id is None:
        run_id = str(uuid.uuid4())
        _current_run_id.set(run_id)
    return run_id

# ---------------- Automation log ----------------
def write_log_row(category, action, status, message="", rfp_id="", run_id=None, insert_to_dataverse=True):
    _act_api = get_setting("RFP_ACTIVITY_LOG_TABLE_API", "cr673_bahra_rfps_v2s")
    _act_logical = get_setting("RFP_ACTIVITY_LOG_TABLE_LOGICAL", "cr673_bahra_rfps_v2")
    _auto_api = get_setting("AUTOMATION_LOG_TABLE_API", "cr673_bahra_automation_log1s")
    _auto_logical = get_setting("AUTOMATION_LOG_TABLE_LOGICAL", "cr673_bahra_automation_log1")
    header = ["RunID", "Timestamp", "Category", "Action", "automation_status", "Message", "RFP_ID"]
    row = [
        run_id or get_current_run_id(),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        category,
        action,
        status,
        message,
        rfp_id,
    ]

    # Dataverse
    if insert_to_dataverse:
        # Check if this is an RFP-related log for an already-downloaded RFP
        # Skip ALL automation logs for RFPs that were already downloaded before
        if rfp_id and category == "RFP":
            # Handle both string and list types for rfp_id
            # If it's a list, skip the duplicate check (usually used for summary logs)
            # Or check the first item if you want
            rfp_id_str = None
            if isinstance(rfp_id, list):
                # For lists, skip the duplicate check (usually used for summary/multi-RFP logs)
                # Or check the first item if you want to apply logic to lists
                if len(rfp_id) > 0 and isinstance(rfp_id[0], str):
                    rfp_id_str = rfp_id[0]  # Check first RFP in list
                else:
                    rfp_id_str = None  # Skip check for empty lists or non-string items
            elif isinstance(rfp_id, str) and rfp_id.strip():
                rfp_id_str = rfp_id
            
            if rfp_id_str:
                try:
                    # Check if RFP already exists in RFP activity log with Downloaded_At
                    existing_result = DATAVERSE.query_rows(
                        _act_api,
                        filter_expr=f"RFP_ID eq '{rfp_id_str}'",
                        top=1,
                        table_logical_name=_act_logical,
                        use_display_names=True
                    )
                    
                    if existing_result and "value" in existing_result and len(existing_result["value"]) > 0:
                        existing_row = existing_result["value"][0]
                        existing_downloaded_at = existing_row.get("Downloaded_At", "")
                        
                        # If RFP was already downloaded, skip ALL automation logs for this RFP
                        if existing_downloaded_at and existing_downloaded_at.strip():
                            print(f"⏩ Skipping automation log for already-downloaded RFP: {rfp_id_str} (category: {category}, action: {action}, status: {status})")
                            return  # Exit early without logging - don't create any automation log for this RFP
                except Exception as e:
                    # If check fails, continue with normal logging to avoid breaking the flow
                    print(f"⚠ Could not check RFP activity log: {e}, proceeding with log insertion")
        
        # Normal insertion for new RFPs or non-RFP category logs
        dv_row = {k: str(v) for k, v in zip(header, row)}
        try:
            DATAVERSE.insert_row(
                _auto_api,  # pluralized API endpoint
                dv_row,
                table_logical_name=_auto_logical,  # singular logical name for metadata
                use_display_names=True
            )
        except Exception as e:
            print(f"⚠ Could not insert automation log into Dataverse: {e}")
            # Fallback: write to local JSONL so the log is not lost
            from core.local_log import write_local_event
            write_local_event(category, action, status, message, rfp_id,
                              extra={"run_id": run_id or "", "dataverse_error": str(e)})

    print(f"📝 Log: {row}")

def log_event(category, action, status, message=None, rfp_id=None, run_id=None, insert_to_dataverse=True):
    write_log_row(category, action, status, message or "", rfp_id or "", run_id or get_current_run_id(), insert_to_dataverse)
# ---------------- RFP activity log ----------------

def _dataframe_to_categorized_json(df, rfp_id, rfp_end_date=None):
    """Convert a matched materials DataFrame to the categorized JSON format."""
    import json, math

    exact_matches = []
    keyword_matches = []
    not_matched = []

    source_file = ""
    if "SourceFile" in df.columns and not df["SourceFile"].dropna().empty:
        source_file = str(df["SourceFile"].dropna().iloc[0])

    for _, row in df.iterrows():
        is_matched = bool(row.get("is_matched", False))
        match_method = row.get("MatchMethod")
        mat_code = str(row.get("ExtractedMaterial") or row.get("Material") or "").strip()

        # Get description from master (handle NaN)
        mat_desc_raw = row.get("Material Description", "")
        mat_desc = "" if (isinstance(mat_desc_raw, float) and math.isnan(mat_desc_raw)) else str(mat_desc_raw or "")

        excel_name_raw = row.get("ExcelName", "")
        excel_name = "" if (isinstance(excel_name_raw, float) and math.isnan(excel_name_raw)) else str(excel_name_raw or "")

        excel_desc_raw = row.get("ExcelDescription", "")
        excel_desc = "" if (isinstance(excel_desc_raw, float) and math.isnan(excel_desc_raw)) else str(excel_desc_raw or "")

        row_num = row.get("RowNumber", 0)
        col_name = str(row.get("ColumnName", "") or "")

        qty_raw = row.get("Quantity", "")
        if isinstance(qty_raw, float) and math.isnan(qty_raw):
            qty = ""
        elif hasattr(qty_raw, "item"):
            qty = qty_raw.item()  # numpy.int64/float64 → Python int/float
        else:
            qty = qty_raw
        uom_raw = row.get("UnitOfMeasurement", "")
        uom = "" if (isinstance(uom_raw, float) and math.isnan(uom_raw)) else str(uom_raw or "")

        item = {
            "material_code": mat_code,
            "excel_name": excel_name,
            "excel_description": excel_desc,
            "row_number": int(row_num) if not (isinstance(row_num, float) and math.isnan(row_num)) else 0,
            "column_name": col_name,
            "quantity": qty,
            "unit_of_measurement": uom,
        }

        if is_matched and match_method and str(match_method).lower() == "keyword":
            item["material_description"] = mat_desc
            item["matched_keyword"] = ""  # Not captured in DataFrame flow
            keyword_matches.append(item)
        elif is_matched:
            item["material_description"] = mat_desc
            exact_matches.append(item)
        else:
            not_matched.append(item)

    total = len(exact_matches) + len(keyword_matches) + len(not_matched)
    matched_total = len(exact_matches) + len(keyword_matches)
    match_pct = round((matched_total / total * 100) if total > 0 else 0, 1)

    categorized = {
        "rfp_id": rfp_id or "",
        "source_file": source_file,
        "rfp_end_date": str(rfp_end_date or ""),
        "total_items": total,
        "summary": {
            "exact_match_count": len(exact_matches),
            "keyword_match_count": len(keyword_matches),
            "not_matched_count": len(not_matched),
            "match_percentage": match_pct,
        },
        "exact_matches": exact_matches,
        "keyword_matches": keyword_matches,
        "not_matched": not_matched,
    }
    return json.dumps(categorized)


def log_rfp_activity(rfp_id, Downloaded_At, RFP_End_Date=None,
                     Matched_Data=None, email_sent_at=None,
                     email_to=None, email_status=None,
                     owner_name=None, publish_time=None,
                     participated=None, link=None,
                     company_name=None,
                     run_id=None, insert_to_dataverse=True,
                     rfp_type=None):
    _act_api = get_setting("RFP_ACTIVITY_LOG_TABLE_API", "cr673_bahra_rfps_v2s")
    _act_logical = get_setting("RFP_ACTIVITY_LOG_TABLE_LOGICAL", "cr673_bahra_rfps_v2")

    if isinstance(Matched_Data, pd.DataFrame) and not Matched_Data.empty:
        Matched_Data_str = _dataframe_to_categorized_json(Matched_Data, rfp_id, RFP_End_Date)
    elif isinstance(Matched_Data, str) and Matched_Data.strip():
        Matched_Data_str = Matched_Data
    else:
        Matched_Data_str = ""

    # Helper function to handle date fields properly
    def safe_date_field(date_value):
        if not date_value or date_value == "" or date_value == "-":
            return None  # Return None instead of empty string for date fields
        return date_value

    row_data = {
        "RunID": run_id or get_current_run_id(),
        "RFP_ID": rfp_id,
        "Downloaded_At": Downloaded_At,
        "Matched_Data": Matched_Data_str,
        "Email_To": email_to or "",
        "Email_Status": email_status or "",
        
    }
    
    # Only add date fields if they have valid values (normalize to MM/DD/YYYY HH:MM AM/PM)
    if safe_date_field(RFP_End_Date) is not None:
        row_data["RFP_End_Date"] = normalize_date_format(RFP_End_Date)
    if safe_date_field(email_sent_at) is not None:
        row_data["Email_Sent_At"] = safe_date_field(email_sent_at)
    if safe_date_field(publish_time) is not None:
        row_data["publish_time"] = normalize_publish_time(publish_time)
    if participated is not None:
        row_data["participated"] = participated
    if owner_name is not None:
        row_data["owner_name"] = owner_name
    if link is not None and link.strip():
        row_data["Link"] = link.strip()
    if company_name is not None and company_name.strip():
        row_data["Company_Name"] = company_name.strip()

    if rfp_type is not None and str(rfp_type).strip():
        row_data["rfp_type"] = str(rfp_type).strip()

    print("Row Data:", row_data)
    if insert_to_dataverse:
        try:
            # Check for existing record
            existing_result = DATAVERSE.query_rows(
                _act_api,
                filter_expr=f"RFP_ID eq '{rfp_id}'",
                top=1,
                table_logical_name=_act_logical,
                use_display_names=True
            )

            if existing_result and "value" in existing_result and len(existing_result["value"]) > 0:
                # Existing record found
                existing_row = existing_result["value"][0]
                # Row keys are display names (use_display_names=True) — resolve primary key via reverse map
                try:
                    _colmap = DATAVERSE.get_column_mapping(_act_logical)
                    _logical_to_display = {v: k for k, v in _colmap.items()}
                except Exception:
                    _logical_to_display = {}
                _pk_logical = f"{_act_logical}id"
                _pk_display = _logical_to_display.get(_pk_logical)
                existing_record_id = (existing_row.get(_pk_display) if _pk_display else None) or existing_row.get(_pk_logical)
                existing_downloaded_at = existing_row.get("Downloaded_At", "")
                
                # If RFP was already downloaded before, skip re-logging unless there are meaningful updates
                if existing_downloaded_at and existing_downloaded_at.strip():
                    # Check if there are meaningful updates (not just re-download)
                    has_meaningful_updates = False
                    
                    # Check if participation status changed
                    if participated is not None:
                        existing_participated = existing_row.get("participated", "")
                        if existing_participated != participated:
                            has_meaningful_updates = True
                            print(f"🔄 Participation status changed from '{existing_participated}' to '{participated}' for: {rfp_id}")
                    
                    # Check if email status changed
                    if email_status and email_status.strip():
                        existing_email_status = existing_row.get("Email_Status", "")
                        if existing_email_status != email_status:
                            has_meaningful_updates = True
                            print(f"🔄 Email status changed from '{existing_email_status}' to '{email_status}' for: {rfp_id}")

                    # Always update when email was just sent (timestamp changes every run)
                    if email_sent_at and email_sent_at.strip():
                        has_meaningful_updates = True
                        print(f"🔄 Email sent — updating Email_Sent_At for: {rfp_id}")

                    # Check if rfp_type is being provided
                    if rfp_type is not None and str(rfp_type).strip():
                        has_meaningful_updates = True

                    # Check if matched data is being added (and wasn't there before)
                    if Matched_Data_str and Matched_Data_str.strip():
                        existing_matched_data = existing_row.get("Matched_Data", "")
                        if not existing_matched_data or not existing_matched_data.strip():
                            has_meaningful_updates = True
                            print(f"🔄 Adding matched data for previously downloaded RFP: {rfp_id}")

                    # Check if owner_name is being added where it was missing
                    if owner_name is not None and str(owner_name).strip():
                        existing_owner = existing_row.get("owner_name", "")
                        if not existing_owner or not existing_owner.strip():
                            has_meaningful_updates = True
                            print(f"🔄 Adding missing owner_name for RFP: {rfp_id}")

                    # Check if publish_time is being added where it was missing
                    if publish_time is not None and str(publish_time).strip():
                        existing_publish = existing_row.get("publish_time", "")
                        if not existing_publish or not existing_publish.strip():
                            has_meaningful_updates = True
                            print(f"🔄 Adding missing publish_time for RFP: {rfp_id}")

                    # Only update if there are meaningful changes
                    if has_meaningful_updates:
                        record_id = existing_record_id
                        # Merge: only update fields provided in row_data (don't update Downloaded_At for re-downloads)
                        update_data = {}
                        
                        # Only include fields that have meaningful updates
                        if participated is not None and existing_row.get("participated", "") != participated:
                            update_data["participated"] = participated
                        if email_status and email_status.strip() and existing_row.get("Email_Status", "") != email_status:
                            update_data["Email_Status"] = email_status
                        if email_to and email_to.strip():
                            update_data["Email_To"] = email_to
                        if email_sent_at and email_sent_at.strip():
                            update_data["Email_Sent_At"] = email_sent_at
                        if Matched_Data_str and Matched_Data_str.strip():
                            existing_matched = existing_row.get("Matched_Data", "")
                            if not existing_matched or not existing_matched.strip():
                                update_data["Matched_Data"] = Matched_Data_str
                        if link is not None and link.strip():
                            existing_link = existing_row.get("Link", "")
                            if not existing_link or existing_link.strip() != link.strip():
                                update_data["Link"] = link.strip()

                        if rfp_type is not None and str(rfp_type).strip():
                            update_data["rfp_type"] = str(rfp_type).strip()

                        # Fill missing owner_name / publish_time if now available.
                        # Policy (Fix 5): treat "", None, and "-" as "unset" — a successful
                        # rescrape may overwrite them. Real non-empty values are kept (this
                        # protects manual corrections from being clobbered by a bad scrape).
                        def _is_unset(v):
                            if v is None:
                                return True
                            s = str(v).strip()
                            return s == "" or s == "-"

                        if owner_name is not None and str(owner_name).strip():
                            if _is_unset(existing_row.get("owner_name")):
                                update_data["owner_name"] = str(owner_name).strip()

                        if publish_time is not None and str(publish_time).strip():
                            if _is_unset(existing_row.get("publish_time")):
                                update_data["publish_time"] = normalize_publish_time(publish_time)

                        # Don't update Downloaded_At for re-downloads
                        # Only update other meaningful fields
                        if update_data:
                            DATAVERSE.update_row(
                                _act_api,
                                record_id,
                                update_data,
                                table_logical_name=_act_logical
                            )
                            print(f"✅ Updated existing RFP log with meaningful changes: {rfp_id}")
                        else:
                            print(f"⏩ Skipping re-log for RFP already downloaded: {rfp_id} (no meaningful updates)")
                    else:
                        # No meaningful updates, skip logging
                        print(f"⏩ Skipping re-log for RFP already downloaded: {rfp_id} (already logged on {existing_downloaded_at})")
                        print(f"📝 RFP Log Skipped (Already Exists): {rfp_id}")
                        return  # Exit early without logging
                else:
                    # Record exists but no Downloaded_At, treat as new download
                    record_id = existing_record_id
                    update_data = {k: v for k, v in row_data.items() if v not in [None, ""]}
                    DATAVERSE.update_row(
                        _act_api,
                        record_id,
                        update_data,
                        table_logical_name=_act_logical
                    )
                    print(f"✅ Updated RFP log with Downloaded_At: {rfp_id}")
            else:
                # Insert new record - this is a new RFP
                DATAVERSE.insert_row(
                    _act_api,
                    row_data,
                    table_logical_name=_act_logical
                )
                print(f"✅ New RFP Log Inserted: {rfp_id}")

        except Exception as e:
            log_event("DB", "RFPLog", "Fail", f"Could not upsert RFP log for {rfp_id}: {e}")
            print(f"⚠ Could not upsert RFP log into Dataverse: {e}")

    print(f"📝 RFP Log Processed: {rfp_id}")
