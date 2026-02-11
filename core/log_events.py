from core.common_imports import *
from helpers.dataverse_helper import DataverseClient
import pandas as pd
import os
import uuid
from datetime import datetime
import csv
from contextvars import ContextVar
from config.config import *

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
                        RFP_ACTIVITY_LOG_TABLE_API,
                        filter_expr=f"RFP_ID eq '{rfp_id_str}'",
                        top=1,
                        table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL,
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
                AUTOMATION_LOG_TABLE_API,  # pluralized API endpoint
                dv_row,
                table_logical_name=AUTOMATION_LOG_TABLE_LOGICAL,  # singular logical name for metadata
                use_display_names=True
            )
        except Exception as e:
            print(f"⚠ Could not insert automation log into Dataverse: {e}")

    print(f"📝 Log: {row}")

def log_event(category, action, status, message=None, rfp_id=None, run_id=None, insert_to_dataverse=True):
    write_log_row(category, action, status, message or "", rfp_id or "", run_id or get_current_run_id(), insert_to_dataverse)
# ---------------- RFP activity log ----------------

def log_rfp_activity(rfp_id, Downloaded_At, RFP_End_Date=None,
                     Matched_Data=None, email_sent_at=None,
                     email_to=None, email_status=None,
                     owner_name=None, publish_time=None,
                     participated=None, link=None,
                     company_name=None,
                     run_id=None, insert_to_dataverse=True):

    if isinstance(Matched_Data, pd.DataFrame) and not Matched_Data.empty:
        Matched_Data_str = Matched_Data.to_json(orient="records")
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
    
    # Only add date fields if they have valid values
    if safe_date_field(RFP_End_Date) is not None:
        row_data["RFP_End_Date"] = safe_date_field(RFP_End_Date)
    if safe_date_field(email_sent_at) is not None:
        row_data["Email_Sent_At"] = safe_date_field(email_sent_at)
    if safe_date_field(publish_time) is not None:
        row_data["publish_time"] = safe_date_field(publish_time)
    if participated is not None:
        row_data["participated"] = participated
    if owner_name is not None:
        row_data["owner_name"] = owner_name
    if publish_time is not None:
        row_data["publish_time"] = publish_time
    if link is not None and link.strip():
        row_data["Link"] = link.strip()
    if company_name is not None and company_name.strip():
        row_data["Company_Name"] = company_name.strip()


    print("Row Data:", row_data)
    if insert_to_dataverse:
        try:
            # Check for existing record
            existing_result = DATAVERSE.query_rows(
                RFP_ACTIVITY_LOG_TABLE_API,
                filter_expr=f"RFP_ID eq '{rfp_id}'",
                top=1,
                table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL,
                use_display_names=True
            )
            
            if existing_result and "value" in existing_result and len(existing_result["value"]) > 0:
                # Existing record found
                existing_row = existing_result["value"][0]
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
                    
                    # Check if matched data is being added (and wasn't there before)
                    if Matched_Data_str and Matched_Data_str.strip():
                        existing_matched_data = existing_row.get("Matched_Data", "")
                        if not existing_matched_data or not existing_matched_data.strip():
                            has_meaningful_updates = True
                            print(f"🔄 Adding matched data for previously downloaded RFP: {rfp_id}")
                    
                    # Only update if there are meaningful changes
                    if has_meaningful_updates:
                        record_id = existing_row[f"{RFP_ACTIVITY_LOG_TABLE_LOGICAL}id"]
                        # Merge: only update fields provided in row_data (don't update Downloaded_At for re-downloads)
                        update_data = {}
                        
                        # Only include fields that have meaningful updates
                        if participated is not None and existing_row.get("participated", "") != participated:
                            update_data["participated"] = participated
                        if email_status and email_status.strip() and existing_row.get("Email_Status", "") != email_status:
                            update_data["Email_Status"] = email_status
                        if email_to and email_to.strip():
                            update_data["Email_To"] = email_to
                        if Matched_Data_str and Matched_Data_str.strip():
                            existing_matched = existing_row.get("Matched_Data", "")
                            if not existing_matched or not existing_matched.strip():
                                update_data["Matched_Data"] = Matched_Data_str
                        if link is not None and link.strip():
                            existing_link = existing_row.get("Link", "")
                            if not existing_link or existing_link.strip() != link.strip():
                                update_data["Link"] = link.strip()
                        
                        # Don't update Downloaded_At for re-downloads
                        # Only update other meaningful fields
                        if update_data:
                            DATAVERSE.update_row(
                                RFP_ACTIVITY_LOG_TABLE_API,
                                record_id,
                                update_data,
                                table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL
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
                    record_id = existing_row[f"{RFP_ACTIVITY_LOG_TABLE_LOGICAL}id"]
                    update_data = {k: v for k, v in row_data.items() if v not in [None, ""]}
                    DATAVERSE.update_row(
                        RFP_ACTIVITY_LOG_TABLE_API,
                        record_id,
                        update_data,
                        table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL
                    )
                    print(f"✅ Updated RFP log with Downloaded_At: {rfp_id}")
            else:
                # Insert new record - this is a new RFP
                DATAVERSE.insert_row(
                    RFP_ACTIVITY_LOG_TABLE_API,
                    row_data,
                    table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL
                )
                print(f"✅ New RFP Log Inserted: {rfp_id}")

        except Exception as e:
            print(f"⚠ Could not upsert RFP log into Dataverse: {e}")

    print(f"📝 RFP Log Processed: {rfp_id}")
