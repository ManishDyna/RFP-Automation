import email
import os

# ===== Common CONFIG =====
URL = "https://service.ariba.com/Sourcing.aw/109582016/aw?awh=r&awssk=u9fNiSxN&dard=1#b0"


# USERNAME = "Loai.Albar@bahra-cables.com"
# PASSWORD = "Albar@2020"
COMPANY_NAME = "Saudi Electricity Company"
COMPANY_OPTIONS = [
    "Aramco e-Marketplace",
    "Saudi Electricity Company",
    # "SABIC - Saudi Basic Industries Corp.",
    # "Rabigh Refining and Petrochemical Company (Petro Rabigh)",
    # "MARAFIQ",
    # "Economic group general trading company LLC",
    "HADEED - RAJHI STEEL",
]

# Mapping from frontend short names to full portal names
COMPANY_NAME_MAP = {
    "SEC": "Saudi Electricity Company",
    "Aramco": "Aramco e-Marketplace",
    "HADEED": "HADEED - RAJHI STEEL",
    "SABIC": "SABIC - Saudi Basic Industries Corp.",
    # Add more mappings as needed
}

def resolve_company_name(short_name: str) -> str:
    """Resolve frontend short name to full portal name"""
    if not short_name:
        return COMPANY_NAME
    # Check if it's already a full name
    if short_name in COMPANY_OPTIONS:
        return short_name
    # Try to map from short name
    return COMPANY_NAME_MAP.get(short_name, short_name)

# ===== SharePoint / Graph API Config =====
CLIENT_ID = "ab1ad5df-98f4-4fdf-8a9d-072ffebfec4a"
CLIENT_SECRET = "lu~8Q~yVL4us3qrdrmKtR6BUU7PGRkVYDN36Oc.o"
TENANT_ID = "d39f97da-dbb2-40a0-9651-829e92444131"
SHAREPOINT_HOSTNAME = "dynatechconsultancy.sharepoint.com"
SITE_PATH = "/sites/Test-AI-ML"
DRIVE_NAME = "Documents"
SP_BASE_FOLDER = "RFP-logs"
TDS_FILE_PATH = "https://dynatechconsultancy.sharepoint.com/sites/Test-AI-ML/Shared%20Documents/RFP-logs/TDS-files/"
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = ["https://graph.microsoft.com/.default"]
SP_BASE_FOLDER_RFP_UPLOAD_FILES = "RFP-logs/RFP-upload-files" # This is the folder where the RFP filled files are uploaded


# Dataverse Configurations
RESOURCE_URL = "https://orga7d8c4fd.api.crm.dynamics.com/"
# Use the singular logical name for metadata
AUTOMATION_LOG_TABLE_LOGICAL = "cr673_bahra_automation_log1"
RFP_ACTIVITY_LOG_TABLE_LOGICAL = "cr673_requestforproposal"

# Use pluralized endpoint for inserts
AUTOMATION_LOG_TABLE_API = "cr673_bahra_automation_log1s"
RFP_ACTIVITY_LOG_TABLE_API = "cr673_requestforproposals"

# ===== Users (Dataverse) =====
USERS_TABLE_LOGICAL = "cr673_bahra_users"     # logical name of your table (example)
USERS_TABLE_API = "cr673_bahra_userses"       # pluralized API path (example)

# ===== SAP Password (Dataverse) =====
# Update these if your table logical/API names differ
SAP_PASSWORD_TABLE_LOGICAL = "cr673_bahra_sap_infomation"
SAP_PASSWORD_TABLE_API = "cr673_bahra_sap_infomations"

# ===== Automation Schedules (Dataverse) =====
# Logical and API plural names for table: bahra_automation_schedules
AUTOMATION_SCHEDULE_TABLE_LOGICAL = "cr673_bahra_automation_schedules"  # update if different
AUTOMATION_SCHEDULE_TABLE_API = "cr673_bahra_automation_scheduleses"     # Dataverse plural name

# ===== RFP Status Tracking (Dataverse) =====
# Table for tracking RFP status changes: bhara_rfp_status
RFP_STATUS_TABLE_LOGICAL = "cr673_bhara_rfp_status"  # singular logical name
RFP_STATUS_TABLE_API = "cr673_bhara_rfp_statuses"    # pluralized API name

# ===== All RFPs Storage (Dataverse) =====
#  # pluralized API name

# Power Automate Flow endpoint
# Legacy
FLOW_URL = "https://prod-44.westus.logic.azure.com:443/workflows/0ecbe93dd4cb4235ab019270aa024405/triggers/manual/paths/invoke?api-version=2016-06-01&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=pZOCiQeonvszlw8n81uS2SHglLLNoM_dGW9DYioNdrE"

# Power Automate Forgot Password (HTTP trigger URL)
FORGOT_PASSWORD_FLOW_URL = "https://8250a9bfeb76ef4cba38b14a0bb011.0c.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/d668e231abda4775a75d9983caada124/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=_LKAHUtU1ZLbm587mzjCCU4c5NusDrYFaPXCN1wBfFs"

# Local file path
DOWNLOAD_DIR = os.path.expanduser("~/Downloads")
OUTPUT_DIR = os.path.join(os.getcwd(), "ALLRFPs")
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

FAILURE_LOGS_DIR = os.path.join(os.getcwd(), "LOGS")
os.makedirs(FAILURE_LOGS_DIR, exist_ok=True)
SP_FAILURE_LOGS_FOLDER = "RFP-logs/automation-error-logs"


# Email Config
EMAIL_TO_RFP_SUBMITTED = "Manish.Soni@dynatechconsultancy.com"  # When RFP is submitted successfully
EMAIL_TO_RFP_DECLINED = "Manish.Soni@dynatechconsultancy.com"  # When RFP is declined successfully
EMAIL_TO_RFP_ERROR_IN_SUBMISSION = "Manish.Soni@dynatechconsultancy.com"  # When RFP is submission failed
EMAIL_TO_RFP_ERROR_IN_DECLINE = "Manish.Soni@dynatechconsultancy.com"  # When RFP is decline failed or error in decline
EMAIL_TO_AUTOMATION_FAILURE = "Manish.Soni@dynatechconsultancy.com"  # When Automation is failed

EMAIL_TO_RFP_SAVED_DRAFT = "Manish.Soni@dynatechconsultancy.com"  # When RFP is saved as draft successfully
EMAIL_TO_NO_MATCHED_DATA = "Manish.Soni@dynatechconsultancy.com"  # When No matched data IN DOWNLOAD RFP

EMAIL_TO_RFP_REMINDER = "Manish.Soni@dynatechconsultancy.com;shubham.kumbhar@dynatechconsultancy.com"
# RFP REMINDER EMAIL

# ===== Dashboard / Logs Settings =====
# Backend cache TTLs (seconds)
DASHBOARD_TTL_SECONDS = 300
LOGS_TTL_SECONDS = 300
SAP_LOGS_TTL_SECONDS = 300

# HTTP cache max-age for dashboard pages (seconds)
DASHBOARD_HTTP_MAX_AGE = 30

# Logs listing server-side fetch window settings
LOGS_FETCH_TOP_MAX = 2000
LOGS_FETCH_AHEAD_FACTOR = 10

# Pagination defaults/limits
DEFAULT_PAGE_SIZE = 50
MIN_PAGE_SIZE = 10
MAX_PAGE_SIZE = 500

# ===== Session Management Settings =====
# Session timeout in seconds (2 hours)
SESSION_TIMEOUT_SECONDS = 7200
# Idle timeout in seconds (30 minutes of inactivity)
IDLE_TIMEOUT_SECONDS = 1800
# Warning time before session expires (5 minutes)
SESSION_WARNING_SECONDS = 300
# Session refresh interval in seconds (5 minutes)
SESSION_REFRESH_INTERVAL = 300