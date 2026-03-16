from core.common_imports import *
from helpers.dataverse_helper import DataverseClient
from config.config import *
from services.system_settings_service import get_setting
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def sanitize_filter_value(value: str) -> str:
    """
    Sanitize a value for use in OData filter expressions to prevent injection.
    Escapes single quotes by doubling them.
    """
    if value is None:
        return ""
    return str(value).replace("'", "''")
# ==== CONFIGURE DATAVERSE ====
DATAVERSE = DataverseClient(
    tenant_id=TENANT_ID,
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    resource_url=RESOURCE_URL
)
# ===== HELPERS =====
async def click_if_visible(page, selector, timeout=5000, max_attempts=3):
    """Click element if visible, retry up to max_attempts"""
    for attempt in range(max_attempts):
        try:
            await page.wait_for_selector(selector, timeout=timeout, state="visible")
            await page.click(selector)
            return True
        except Exception:
            if attempt < max_attempts - 1:
                await asyncio.sleep(1)
            else:
                return False

async def safe_navigate(page, url):
    """Navigate and wait for network idle"""
    await page.goto(url, wait_until="networkidle")
    await page.wait_for_load_state('domcontentloaded')


def clean_rfp_title(title: str) -> str:
    return re.sub(r'\s+', ' ', title).strip()

def normalize_filename(name: str) -> str:
    return re.sub(r'[^a-z0-9]', '', name.lower())

def find_column_name(cols, target="name"):
    for col in cols:
        if target.lower() in col.lower().replace(" ", "").replace("_", ""):
            return col
    return None
def get_all_excel_files(folder):
    """Get all Excel files from folder, including nested structure (ALLRFPs/RFP_title/downloaded-rfp/)"""
    excel_files = []
    if not os.path.exists(folder):
        return excel_files
    
    # Check if it's the new nested structure (ALLRFPs with subfolders)
    for item in os.listdir(folder):
        item_path = os.path.join(folder, item)
        if os.path.isdir(item_path):
            # Check for downloaded-rfp subfolder
            material_folder = os.path.join(item_path, "downloaded-rfp")
            if os.path.exists(material_folder):
                # Get Excel files from downloaded-rfp folder
                for file in os.listdir(material_folder):
                    if file.endswith((".xls", ".xlsx")):
                        excel_files.append(os.path.join(material_folder, file))
            else:
                # Fallback: check if Excel files are directly in RFP folder (old structure)
                for file in os.listdir(item_path):
                    if file.endswith((".xls", ".xlsx")):
                        excel_files.append(os.path.join(item_path, file))
        elif item.endswith((".xls", ".xlsx")):
            # Old flat structure: Excel files directly in ALLRFPs
            excel_files.append(item_path)
    
    return excel_files

def get_rfp_folder_path(rfp_title: str, company_name: str) -> str:
    """Get the RFP folder path: ALLRFPs/CompanyName/RFP_title"""
    clean_title = clean_rfp_title(rfp_title)
    safe_company_name = re.sub(r'[<>:"/\\|?*]', '_', company_name).strip().rstrip('.')
    return os.path.join(get_setting("OUTPUT_DIR", os.path.join(os.getcwd(), "ALLRFPs")), safe_company_name, clean_title)

def get_rfp_material_file_path(rfp_title: str, company_name: str, filename: str = None) -> str:
    """Get the downloaded-rfp folder path for an RFP: ALLRFPs/CompanyName/RFP_title/downloaded-rfp/"""
    rfp_folder = get_rfp_folder_path(rfp_title, company_name)
    material_folder = os.path.join(rfp_folder, "downloaded-rfp")
    os.makedirs(material_folder, exist_ok=True)
    if filename:
        return os.path.join(material_folder, filename)
    return material_folder

def get_rfp_tds_folder_path(rfp_title: str, company_name: str) -> str:
    """Get the TDS-files folder path for an RFP: ALLRFPs/CompanyName/RFP_title/TDS-files/"""
    rfp_folder = get_rfp_folder_path(rfp_title, company_name)
    tds_folder = os.path.join(rfp_folder, "TDS-files")
    os.makedirs(tds_folder, exist_ok=True)
    return tds_folder

def get_rfp_savedrfp_folder_path(rfp_title: str, company_name: str) -> str:
    """Get the savedrfp folder path for an RFP: ALLRFPs/CompanyName/RFP_title/rfp-upload-file/"""
    rfp_folder = get_rfp_folder_path(rfp_title, company_name)
    rfp_upload_file_folder = os.path.join(rfp_folder, "rfp-upload-file")
    os.makedirs(rfp_upload_file_folder, exist_ok=True)
    return rfp_upload_file_folder

def get_rfp_saved_excel_file_path(rfp_title: str, company_name: str) -> str:
    """Get the saved Excel file path: ALLRFPs/CompanyName/RFP_title/rfp-upload-file/RFP_title.xls"""
    clean_title = clean_rfp_title(rfp_title)
    savedrfp_folder = get_rfp_savedrfp_folder_path(rfp_title, company_name)
    # Use same extension as original file
    original_path = get_rfp_excel_file_path(rfp_title, company_name)
    ext = os.path.splitext(original_path)[1] or '.xls'
    return os.path.join(savedrfp_folder, f"{clean_title}{ext}")

def get_rfp_company_name(rfp_id: str) -> str | None:
    """Get company name for an RFP from database. Returns None if not found."""
    if not rfp_id:
        return None

    try:
        rfp_rows = get_rfp_activity_data_from_db()
        for row in rfp_rows:
            if row.get("RFP_ID") == rfp_id:
                company = row.get("Company_Name")
                if company:
                    return company
    except Exception as e:
        logger.warning(f"Could not get company name for RFP {rfp_id}: {e}")
    return None

def find_rfp_file_across_companies(rfp_id: str) -> tuple[str | None, str | None]:
    """
    Search for RFP file across all company folders.
    Returns (file_path, company_name) or (None, None) if not found.
    """
    clean_title = clean_rfp_title(rfp_id)
    _output_dir = get_setting("OUTPUT_DIR", os.path.join(os.getcwd(), "ALLRFPs"))
    if not os.path.exists(_output_dir):
        return None, None

    # Try to get company from database first
    company_name = get_rfp_company_name(rfp_id)
    if company_name:
        file_path = get_rfp_excel_file_path(rfp_id, company_name)
        if os.path.exists(file_path):
            return file_path, company_name

    # Search through all company folders
    for company_folder in os.listdir(_output_dir):
        company_path = os.path.join(_output_dir, company_folder)
        if not os.path.isdir(company_path):
            continue
        
        try:
            file_path = get_rfp_excel_file_path(rfp_id, company_folder)
            if os.path.exists(file_path):
                return file_path, company_folder
        except Exception:
            continue
    
    return None, None

def get_rfp_excel_file_path(rfp_title: str, company_name: str) -> str:
    """Get the Excel file path for an RFP: ALLRFPs/CompanyName/RFP_title/downloaded-rfp/RFP_title.xls"""
    clean_title = clean_rfp_title(rfp_title)
    # Try to find existing file with any extension
    material_folder = get_rfp_material_file_path(rfp_title, company_name)
    for ext in ['.xls', '.xlsx']:
        file_path = os.path.join(material_folder, f"{clean_title}{ext}")
        if os.path.exists(file_path):
            return file_path
    # Return default path
    return os.path.join(material_folder, f"{clean_title}.xls")

def get_sharepoint_rfp_path(rfp_title: str, company_name: str) -> str:
    """Get SharePoint base path for RFP: RFP-logs/ALLRFPs/CompanyName/RFP_title"""
    clean_title = clean_rfp_title(rfp_title)
    safe_company_name = re.sub(r'[<>:"/\\|?*]', '_', company_name).strip().rstrip('.')
    return f"{get_setting('SP_BASE_FOLDER', 'RFP-logs')}/ALLRFPs/{safe_company_name}/{clean_title}"

def get_sharepoint_rfp_material_path(rfp_title: str, company_name: str, filename: str = None) -> str:
    """Get SharePoint downloaded-rfp path: RFP-logs/ALLRFPs/CompanyName/RFP_title/downloaded-rfp/"""
    base_path = get_sharepoint_rfp_path(rfp_title, company_name)
    material_path = f"{base_path}/downloaded-rfp"
    if filename:
        return f"{material_path}/{filename}"
    return material_path

def get_sharepoint_rfp_tds_path(rfp_title: str, company_name: str, material_code: str = None) -> str:
    """Get SharePoint TDS-files path: RFP-logs/ALLRFPs/CompanyName/RFP_title/TDS-files/"""
    base_path = get_sharepoint_rfp_path(rfp_title, company_name)
    tds_path = f"{base_path}/TDS-files"
    if material_code:
        return f"{tds_path}/{material_code}_TDS.pdf"
    return tds_path

def get_sharepoint_rfp_savedrfp_path(rfp_title: str, company_name: str, filename: str = None) -> str:
    """Get SharePoint rfp-upload-file path: RFP-logs/ALLRFPs/CompanyName/RFP_title/rfp-upload-file/"""
    base_path = get_sharepoint_rfp_path(rfp_title, company_name)
    rfp_upload_file_path = f"{base_path}/rfp-upload-file"
    if filename:
        return f"{rfp_upload_file_path}/{filename}"
    return rfp_upload_file_path

def get_latest_file(download_dir, title):
    norm_title = normalize_filename(title)
    try:
        candidates = [
            os.path.join(download_dir, f)
            for f in os.listdir(download_dir)
            if normalize_filename(f).startswith(norm_title)
        ]
        return max(candidates, key=os.path.getmtime) if candidates else None
    except Exception:
        return None

def get_rfp_activity_data_from_db(top: int = 5000, skip: int = 0):
    """
    Get ALL RFP activity data from Dataverse using automatic pagination.

    Args:
        top: Ignored (kept for backward compatibility). All rows are fetched.
        skip: Ignored (kept for backward compatibility).

    Returns:
        List of dicts with display names as keys
    """
    return DATAVERSE.get_all_rows(
        table_api_name=get_setting("RFP_ACTIVITY_LOG_TABLE_API", "cr673_requestforproposals"),
        select_columns=["RFP_ID", "Email_Status", "RFP_End_Date", "owner_name", "publish_time", "Company_Name", "participated", "Link", "Material_Matched", "Keyword_Matched", "Matched_Data", "Material_Code", "Material_Description", "Matched_Keywords"],
        table_logical_name=get_setting("RFP_ACTIVITY_LOG_TABLE_LOGICAL", "cr673_requestforproposal"),
        use_display_names=True
    )

def log_rfp_status_change(rfp_id: str, from_status: str, to_status: str, category: str = "Status Change"):
    """
    Log RFP status change to bhara_rfp_status table.
    
    Args:
        rfp_id: The RFP identifier
        from_status: Previous status (can be empty string if new)
        to_status: New status
        category: Category of the change (e.g., "submit", "draft", "declined", "status_change")
                   Will be converted to lowercase and matched to choice field options
    """
    try:
        now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Get column mapping to use correct display names
        _rfp_status_logical = get_setting("RFP_STATUS_TABLE_LOGICAL", "cr673_bhara_rfp_status")
        _rfp_status_api = get_setting("RFP_STATUS_TABLE_API", "cr673_bhara_rfp_statuses")
        column_map = DATAVERSE.get_column_mapping(_rfp_status_logical)
        
        # Check if category is a choice field and get its integer value
        category_value = None
        try:
            # Try to get choice options for category field
            # Common logical names for category field
            category_logical_names = ["category", "cr673_category", "submissioncategory", "cr673_submissioncategory"]
            category_logical = None
            
            # Find the actual logical name
            for display_name, logical_name in column_map.items():
                if logical_name.lower() in [name.lower() for name in category_logical_names]:
                    category_logical = logical_name
                    break
            
            if category_logical:
                choice_options = DATAVERSE.get_choice_options(_rfp_status_logical, category_logical)
                # Convert category to lowercase for matching
                category_lower = category.lower().strip()
                # Map common category names to potential choice labels
                category_mapping = {
                    "draft saved": "submit",
                    "saved draft": "submit", 
                    "submitted": "submit",
                    "declined": "submit",
                    "status change": "submit",
                    "synced from portal": "submit",
                    "initial status": "submit"
                }
                
                # Try to find matching label
                search_label = category_mapping.get(category_lower, category_lower)
                label_to_value = choice_options.get("label_to_value", {})
                
                # Try exact match first
                if search_label in label_to_value:
                    category_value = label_to_value[search_label]
                else:
                    # Try case-insensitive match
                    for label, value in label_to_value.items():
                        if label.lower() == search_label.lower():
                            category_value = value
                            break
                
                if category_value is None:
                    # If no match found, try using the first option or default
                    if label_to_value:
                        # Use first available option as fallback
                        category_value = list(label_to_value.values())[0]
                        logger.warning(f"Category '{category}' not found in choice options, using first option: {category_value}")
                    else:
                        logger.warning("No choice options found for category field, will try without choice value")
        except Exception as e:
            logger.warning(f"Could not get choice options for category field: {e}")
            # Continue without choice value - will try as string
        
        # Prepare data for status change log - only use columns that exist in the table
        # From error log, we know these columns exist:
        # - rfp_id -> cr673_rfpreference
        # - datetime -> cr673_submissioncode  
        # - to_this -> cr673_currentstatus
        # - category -> cr673_submissioncategory
        # - from_this does NOT exist, so we skip it
        
        status_data = {}
        
        # Find and add rfp_id field
        rfp_id_display = None
        for display_name, logical_name in column_map.items():
            if logical_name.lower() in ["rfpreference", "cr673_rfpreference", "rfp_id"]:
                rfp_id_display = display_name
                break
        if rfp_id_display:
            status_data[rfp_id_display] = str(rfp_id)
        else:
            # Fallback
            status_data["rfp_id"] = str(rfp_id)
        
        # Find and add datetime field
        datetime_display = None
        for display_name, logical_name in column_map.items():
            if logical_name.lower() in ["submissioncode", "cr673_submissioncode", "datetime"]:
                datetime_display = display_name
                break
        if datetime_display:
            status_data[datetime_display] = now_iso
        else:
            # Fallback
            status_data["datetime"] = now_iso
        
        # Find and add to_this field (current status)
        to_this_display = None
        for display_name, logical_name in column_map.items():
            if logical_name.lower() in ["currentstatus", "cr673_currentstatus", "to_this", "to this"]:
                to_this_display = display_name
                break
        if to_this_display:
            status_data[to_this_display] = str(to_status) if to_status else ""
        else:
            # Fallback
            status_data["to_this"] = str(to_status) if to_status else ""
        
        # Find and add from_this field (previous status)
        from_this_display = None
        for display_name, logical_name in column_map.items():
            if logical_name.lower() in ["from_this", "fromthis", "previousstatus", "cr673_from_this", "cr673_fromthis", "cr673_previousstatus"]:
                from_this_display = display_name
                break
        
        if from_this_display:
            status_data[from_this_display] = str(from_status) if from_status else ""
        else:
            # Fallback: try common display names
            status_data["from_this"] = str(from_status) if from_status else ""
        
        # Add category field - use integer value if found, otherwise try string
        if category_value is not None:
            # Use the display name for the category field
            category_display_name = None
            for display_name, logical_name in column_map.items():
                if logical_name.lower() in ["submissioncategory", "cr673_submissioncategory", "category"]:
                    category_display_name = display_name
                    break
            
            if category_display_name:
                status_data[category_display_name] = category_value
            else:
                # Fallback: try common display names
                status_data["category"] = category_value
        else:
            # Fallback: try as string (might fail if it's a choice field)
            category_display_name = None
            for display_name, logical_name in column_map.items():
                if logical_name.lower() in ["submissioncategory", "cr673_submissioncategory", "category"]:
                    category_display_name = display_name
                    break
            if category_display_name:
                status_data[category_display_name] = category.lower() if category else "submit"
            else:
                status_data["category"] = category.lower() if category else "submit"
        
        # Insert into status tracking table
        success = DATAVERSE.insert_row(
            table_api_name=_rfp_status_api,
            data=status_data,
            table_logical_name=_rfp_status_logical,
            use_display_names=True
        )
        if success:
            logger.info(f"Logged status change for RFP {rfp_id}: {from_status} -> {to_status} ({category})")
        else:
            logger.warning(f"Failed to log status change for RFP {rfp_id}")
        
        return success
        
    except Exception as e:
        logger.error(f"Error logging RFP status change: {e}")
        return False

# Check if RFP IDs match
def update_rfp_participation_status(rfp_id: str, status: str, category: str = None):
    """
    Update participation status for a specific RFP in the rfp_activity_log table and log the change.

    Args:
        rfp_id: The RFP identifier
        status: New status to set
        category: Optional category for the status change log. If not provided, will be auto-determined.

    Returns:
        bool: True if update was successful, False otherwise

    Raises:
        ValueError: If rfp_id or status is empty/invalid
    """
    # Validate inputs
    if not rfp_id or not rfp_id.strip():
        logger.error("update_rfp_participation_status: rfp_id is required")
        raise ValueError("rfp_id is required")

    if not status or not status.strip():
        logger.error("update_rfp_participation_status: status is required")
        raise ValueError("status is required")

    rfp_id = rfp_id.strip()
    status = status.strip()

    # Validate status against allowed values
    from config.config import validate_rfp_status
    if not validate_rfp_status(status):
        logger.warning(f"Status '{status}' is not in VALID_RFP_STATUSES, but proceeding anyway")

    try:
        # Sanitize rfp_id to prevent injection
        safe_rfp_id = sanitize_filter_value(rfp_id)
        _act_api = get_setting("RFP_ACTIVITY_LOG_TABLE_API", "cr673_requestforproposals")
        _act_logical = get_setting("RFP_ACTIVITY_LOG_TABLE_LOGICAL", "cr673_requestforproposal")

        # Check for existing record
        existing_result = DATAVERSE.query_rows(
            _act_api,
            filter_expr=f"RFP_ID eq '{safe_rfp_id}'",
            top=1,
            table_logical_name=_act_logical,
            use_display_names=True
        )
        old_status = ""
        if existing_result and "value" in existing_result and len(existing_result["value"]) > 0:
            # Existing record found
            existing_row = existing_result["value"][0]
            # NOTE: query used use_display_names=True, so row keys are DISPLAY names, not logical
            # Build reverse map (logical -> display) to look up primary key and participated field
            try:
                colmap = DATAVERSE.get_column_mapping(_act_logical)  # display -> logical
            except Exception:
                colmap = {}
            logical_to_display = {v: k for k, v in colmap.items()}

            # Get record_id: primary key may have been remapped to its display name
            pk_logical = f"{_act_logical}id"
            pk_display = logical_to_display.get(pk_logical)
            record_id = (existing_row.get(pk_display) if pk_display else None) or existing_row.get(pk_logical)
            if not record_id:
                logger.error(f"Could not find primary key for RFP {rfp_id} (tried '{pk_display}' and '{pk_logical}')")
                return False

            # Get old status using display name key (row uses display names)
            participated_display = next(
                (k for k in colmap if "participated" in k.lower().replace(" ", "").replace("_", "")),
                "participated"  # last resort
            )
            old_status = existing_row.get(participated_display, "") or ""
            # Update only the participated field
            update_data = {
                "participated": status
            }

            # Perform update with error handling
            try:
                update_success = DATAVERSE.update_row(
                    _act_api,
                    record_id,
                    update_data,
                    table_logical_name=_act_logical
                )
                if not update_success:
                    logger.error(f"Failed to update RFP {rfp_id} participation status")
                    return False
            except Exception as update_error:
                logger.error(f"Database error updating RFP {rfp_id}: {update_error}")
                raise

            logger.info(f"Updated RFP {rfp_id} participation status to: {status}")
            
            # Log status change if status actually changed
            if old_status.lower() != status.lower():
                # Determine category if not provided - use lowercase "submit" to match table
                if not category:
                    # All status changes map to "submit" category based on table structure
                    category = "submit"
                
                log_rfp_status_change(rfp_id, old_status, status, category)
            
            return True
        else:
            logger.warning(f"No RFP record found with ID: {rfp_id}")
            # Log initial status if this is a new record
            if status:
                initial_category = category or "submit"
                log_rfp_status_change(rfp_id, "", status, initial_category)
            return False

    except ValueError:
        # Re-raise validation errors
        raise
    except Exception as e:
        logger.error(f"Error updating RFP participation status for {rfp_id}: {e}")
        return False

def update_sync_timestamp(rfp_id: str, company_name: str = None) -> bool:
    """
    Update the Downloaded_At timestamp in Dataverse for a synced RFP.

    Args:
        rfp_id: The RFP identifier
        company_name: Optional company name for more precise matching

    Returns:
        bool: True if update successful, False otherwise
    """
    if not rfp_id or not rfp_id.strip():
        logger.error("update_sync_timestamp: rfp_id is required")
        return False

    rfp_id = rfp_id.strip()

    try:
        # Sanitize values to prevent injection
        safe_rfp_id = sanitize_filter_value(rfp_id)
        filter_expr = f"RFP_ID eq '{safe_rfp_id}'"
        _act_api = get_setting("RFP_ACTIVITY_LOG_TABLE_API", "cr673_requestforproposals")
        _act_logical = get_setting("RFP_ACTIVITY_LOG_TABLE_LOGICAL", "cr673_requestforproposal")

        if company_name:
            safe_company = sanitize_filter_value(company_name.strip())
            filter_expr += f" and Company_Name eq '{safe_company}'"

        # Query for existing record
        existing_result = DATAVERSE.query_rows(
            _act_api,
            filter_expr=filter_expr,
            top=1,
            table_logical_name=_act_logical,
            use_display_names=True
        )

        if existing_result and "value" in existing_result and len(existing_result["value"]) > 0:
            existing_row = existing_result["value"][0]
            # Row keys are display names (use_display_names=True) — resolve primary key via reverse map
            try:
                colmap = DATAVERSE.get_column_mapping(_act_logical)
                logical_to_display = {v: k for k, v in colmap.items()}
            except Exception:
                logical_to_display = {}
            pk_logical = f"{_act_logical}id"
            pk_display = logical_to_display.get(pk_logical)
            record_id = (existing_row.get(pk_display) if pk_display else None) or existing_row.get(pk_logical)
            if not record_id:
                logger.error(f"Could not find primary key for RFP {rfp_id} in update_sync_timestamp")
                return False

            # Update Downloaded_At timestamp
            update_data = {
                "Downloaded_At": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            update_success = DATAVERSE.update_row(
                _act_api,
                record_id,
                update_data,
                table_logical_name=_act_logical
            )

            if update_success:
                logger.info(f"Updated sync timestamp for RFP {rfp_id}")
                return True
            else:
                logger.error(f"Failed to update sync timestamp for RFP {rfp_id}")
                return False
        else:
            logger.warning(f"No RFP record found with ID: {rfp_id}")
            return False

    except Exception as e:
        logger.error(f"Error updating sync timestamp for RFP {rfp_id}: {e}")
        return False


def rfp_ids_match(search_id: str, title: str) -> bool:
    """
    Check if RFP IDs match using existing normalize_filename function
    """
    if not search_id or not title:
        return False
    
    # Use your existing normalize_filename function
    normalized_search = normalize_filename(search_id)
    normalized_title = normalize_filename(title)
    
    # Check if normalized search ID is contained in normalized title
    return normalized_search in normalized_title

def _find_other_content_sheet_name(excel_path: str):
    """
    Finds the 'Other Content' sheet (case/space-insensitive), or returns None.
    """
    try:
        import pandas as pd
        xl = pd.ExcelFile(excel_path)
        for name in xl.sheet_names:
            if name.replace(" ", "").lower() == "othercontent":
                return name
        # fallback: any sheet containing both words
        for name in xl.sheet_names:
            ln = name.lower()
            if "other" in ln and "content" in ln:
                return name
    except Exception as e:
        print(f"[WARN] Could not enumerate sheets: {e}")
    return None

def extract_keywords_from_text(
    text: str, 
    delimiter: str = ',', 
    to_upper: bool = True,
    strip_whitespace: bool = True
) -> list:
    """
    Extract keywords from delimited text.
    
    Args:
        text: Text containing delimited keywords
        delimiter: Delimiter to split on (default: comma)
        to_upper: Convert keywords to uppercase (default: True)
        strip_whitespace: Remove leading/trailing whitespace (default: True)
    
    Returns:
        List of extracted keywords
    
    Examples:
        >>> extract_keywords_from_text("CABLE,ELEC,CU")
        ['CABLE', 'ELEC', 'CU']
        
        >>> extract_keywords_from_text("cable;elec;cu", delimiter=';')
        ['CABLE', 'ELEC', 'CU']
    """
    import pandas as pd
    if not text or pd.isna(text):
        return []
    
    keywords = []
    for part in str(text).split(delimiter):
        kw = part.strip() if strip_whitespace else part
        if to_upper:
            kw = kw.upper()
        if kw:  # Only add non-empty keywords
            keywords.append(kw)
    
    return keywords

def extract_materials_from_excel(excel_path: str, include_details: bool = False, filter_by_intent: bool = True):
    """
    Extract materials from Excel 'Other Content' sheet.

    Args:
        excel_path: Path to Excel file
        include_details: If True, returns list of dicts with name/description.
                        If False, returns set of material codes only.
        filter_by_intent: If True, only include rows where 'Intend To Respond' = Yes.
                         If False, include ALL rows (used for match % calculation).

    Returns:
        If include_details=True: list[dict] with material_code, name, description
        If include_details=False: set[str] of material codes only
    """
    import pandas as pd
    import re

    sheet = _find_other_content_sheet_name(excel_path) or "Other Content"
    try:
        df = pd.read_excel(excel_path, sheet_name=sheet)
    except Exception as e:
        print(f"[WARN] Could not read sheet '{sheet}' from {excel_path}: {e}")
        return [] if include_details else set()

    name_col = find_column_name(df.columns, "name")
    if not name_col:
        print("[WARN] 'name' column not found; no materials extracted.")
        return [] if include_details else set()

    if filter_by_intent:
        # Try to find the intent column with tolerant matching
        intent_col = (
            find_column_name(df.columns, "intend to respond")
            or find_column_name(df.columns, "intend")
            or find_column_name(df.columns, "respond intend")
        )
        if not intent_col:
            print("[WARN] 'Intend To Respond' column not found; no materials selected.")
            return [] if include_details else set()

        def is_yes(v) -> bool:
            s = str(v).strip().lower()
            return s in {"yes", "y", "true", "1"}

        # Keep only rows where intent indicates Yes
        try:
            filtered = df[df[intent_col].map(is_yes)]
        except Exception as e:
            print(f"[WARN] Could not filter by intent column '{intent_col}': {e}")
            return [] if include_details else set()
    else:
        # Use ALL rows — no intent filtering
        filtered = df

    if include_details:
        # Return list of dicts with details
        desc_col = find_column_name(df.columns, "description")
        materials_data = []
        seen_codes = set()

        # Use to_dict('records') for better performance (faster than iterrows, safer with column names)
        for row in filtered.to_dict('records'):
            name_value = str(row.get(name_col, "")) if not pd.isna(row.get(name_col)) else ""
            desc_value = str(row.get(desc_col, "")) if desc_col and not pd.isna(row.get(desc_col)) else ""

            # Extract 9-digit material codes
            for mat_code in re.findall(r"\d{9}", name_value):
                if mat_code not in seen_codes:
                    seen_codes.add(mat_code)
                    materials_data.append({
                        "material_code": mat_code,
                        "name": name_value,
                        "description": desc_value
                    })

        print(f"Materials extracted (filter_by_intent={filter_by_intent}): {len(materials_data)}")
        return materials_data
    else:
        # Return set of material codes only
        materials = set()
        for _, value in filtered[name_col].items():
            if pd.isna(value):
                continue
            for mat in re.findall(r"\d{9}", str(value)):
                materials.add(mat)

        print(f"Materials extracted (filter_by_intent={filter_by_intent}): {sorted(materials)}")
        return materials