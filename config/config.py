import email
import os

# ===== Common CONFIG =====
URL = "https://service.ariba.com/Sourcing.aw/109582016/aw?awh=r&awssk=u9fNiSxN&dard=1#b0"


# USERNAME = "Loai.Albar@bahra-cables.com"
# PASSWORD = "Albar@2020"
COMPANY_NAME = "Saudi Electricity Company"

# All supported company options - single source of truth
COMPANY_OPTIONS = [
    "Saudi Electricity Company",
    "Aramco e-Marketplace",
    "SABIC - Saudi Basic Industries Corp.",
    "HADEED - RAJHI STEEL",
    # "Rabigh Refining and Petrochemical Company (Petro Rabigh)",
    # "MARAFIQ",
    # "Economic group general trading company LLC",
]

# Valid RFP participation statuses
VALID_RFP_STATUSES = ["saved_draft", "submitted", "declined"]


class InvalidCompanyError(ValueError):
    """Raised when an invalid company name is provided"""
    pass


def resolve_company_name(name: str, strict: bool = False) -> str:
    """
    Resolve company name, defaulting to COMPANY_NAME if empty.

    Args:
        name: Company name to resolve
        strict: If True, raises InvalidCompanyError for invalid names.
                If False, returns the name as-is (for backward compatibility).

    Returns:
        Resolved company name

    Raises:
        InvalidCompanyError: If strict=True and company name is not in COMPANY_OPTIONS
    """
    if not name:
        return COMPANY_NAME

    name = name.strip()

    # Check if it's a valid company name
    if name in COMPANY_OPTIONS:
        return name

    # If strict mode, raise error for invalid names
    if strict:
        raise InvalidCompanyError(
            f"Invalid company name: '{name}'. "
            f"Valid options are: {', '.join(COMPANY_OPTIONS)}"
        )

    # For backward compatibility, return the name as-is with a warning
    import logging
    logging.warning(f"Company name '{name}' not in COMPANY_OPTIONS. Consider using strict=True.")
    return name


def validate_rfp_status(status: str) -> bool:
    """Validate if the given status is a valid RFP participation status"""
    return status.lower() in [s.lower() for s in VALID_RFP_STATUSES]

# ===== SharePoint / Graph API Config =====
TENANT_ID = "46aa82d0-1a4b-4b08-b520-514ccbe1e7ca"
CLIENT_ID = "97312492-991a-46be-91de-62430026f72d"
CLIENT_SECRET = "pDN8Q~kLKXRoOmEB5PvLRDo-zVH2o91IjRtaJagr"



SHAREPOINT_HOSTNAME = "bahracables.sharepoint.com"
SITE_PATH = "/sites/LiveSite/RFPAutomation"
DRIVE_NAME = "Documents"
SP_BASE_FOLDER = "RFP-logs"
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = ["https://graph.microsoft.com/.default"]
SP_BASE_FOLDER_RFP_UPLOAD_FILES = "RFP-logs/RFP-upload-files" # This is the folder where the RFP filled files are uploaded   ## Review


# Dataverse Configurations
RESOURCE_URL = "https://operations-bahrauat-1.crm11.dynamics.com"   # get this from the environment variable click details
# Use the singular logical name for metadata
AUTOMATION_LOG_TABLE_LOGICAL = "cr673_bahra_automation_log1"
RFP_ACTIVITY_LOG_TABLE_LOGICAL = "cr673_requestforproposal"

# Use pluralized endpoint for inserts
AUTOMATION_LOG_TABLE_API = "cr673_bahra_automation_log1s"
RFP_ACTIVITY_LOG_TABLE_API = "cr673_requestforproposals"

# ===== Users (Dataverse) =====
USERS_TABLE_LOGICAL = "cr673_bahra_users"     # logical name of your table (example)
USERS_TABLE_API = "cr673_bahra_userses"       # pluralized API path (example)
TDS_FILE_PATH = "https://bahracables.sharepoint.com/sites/Test-AI-ML/Shared%20Documents/RFP-logs/TDS-files/"   ## Review

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
# FLOW_URL = "https://prod-44.westus.logic.azure.com:443/workflows/0ecbe93dd4cb4235ab019270aa024405/triggers/manual/paths/invoke?api-version=2016-06-01&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=pZOCiQeonvszlw8n81uS2SHglLLNoM_dGW9DYioNdrE"
FLOW_URL = "https://8250a9bfeb76ef4cba38b14a0bb011.0c.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/0ecbe93dd4cb4235ab019270aa024405/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=A1nhkrQ4Ip6hp6nKwK08lrMqC5y1BKA_esFHGkpGx4U"
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