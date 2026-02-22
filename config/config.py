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

# ===== Roles (Dataverse) =====
ROLES_TABLE_LOGICAL = "cr673_bahra_roles"
ROLES_TABLE_API = "cr673_bahra_roleses"

# ===== Role Permissions (Dataverse) =====
ROLE_PERMISSIONS_TABLE_LOGICAL = "cr673_bahra_role_permissions"
ROLE_PERMISSIONS_TABLE_API = "cr673_bahra_role_permissionses"

# ===== Audit Logs (Dataverse) =====
AUDIT_LOG_TABLE_LOGICAL = "cr673_bahra_audit_logs"
AUDIT_LOG_TABLE_API = "cr673_bahra_audit_logses"

# ===== User Status / Lifecycle (Dataverse) =====
USER_STATUS_TABLE_LOGICAL = "cr673_bahra_user_status"
USER_STATUS_TABLE_API = "cr673_bahra_user_statuses"

# ===== RBAC Settings =====
RBAC_CACHE_TTL_SECONDS = 300            # Cache role-permissions for 5 min
ACCOUNT_LOCKOUT_THRESHOLD = 5           # Failed attempts before lockout
ACCOUNT_LOCKOUT_DURATION_MINUTES = 30   # Lockout duration in minutes
PASSWORD_MIN_LENGTH = 8
PASSWORD_REQUIRE_UPPERCASE = True
PASSWORD_REQUIRE_NUMBER = True
PASSWORD_MAX_AGE_DAYS = 90              # Force password change after 90 days

# Power Automate Flow endpoint
# Legacy
# FLOW_URL = "https://prod-44.westus.logic.azure.com:443/workflows/0ecbe93dd4cb4235ab019270aa024405/triggers/manual/paths/invoke?api-version=2016-06-01&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=pZOCiQeonvszlw8n81uS2SHglLLNoM_dGW9DYioNdrE"

FLOW_URL = "https://dab4cde858caeaa0b535f6dbd4b6cf.a6.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/8b59f8e17de8493ab5f575461aa92133/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=bG4Z-fghyYpzFZHxsyu8yzsrSlPlNEkzgMCQeKvS9VI"
# Power Automate Forgot Password (HTTP trigger URL)
FORGOT_PASSWORD_FLOW_URL = "https://dab4cde858caeaa0b535f6dbd4b6cf.a6.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/326c08241613446da0e9cd6235d4e666/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=r3S5vKCYj3BQ0ymdc-qsBY2fPgzbsM67EDzfIiQcQFQ"

# Local file path
DOWNLOAD_DIR = os.path.expanduser("~/Downloads")
OUTPUT_DIR = os.path.join(os.getcwd(), "ALLRFPs")
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

FAILURE_LOGS_DIR = os.path.join(os.getcwd(), "LOGS") 
os.makedirs(FAILURE_LOGS_DIR, exist_ok=True)
SP_FAILURE_LOGS_FOLDER = "RFP-logs/automation-error-logs"


# Email Config

# ── Case 1: New RFP found on portal (one email per RFP with RFP file + matched materials) ──
# Combined recipients (previously EMAIL_TO_NEW_RFP + EMAIL_TO_NEW_RFP_WITH_MATCH)
# Add multiple recipients separated by semicolons: "a@x.com;b@x.com"
EMAIL_TO_NEW_RFP = "Manish.soni@dynatechconsultancy.com"

# ── Case 2: Automation ran but NO new RFP was found on portal ──
# Add multiple recipients separated by semicolons: "a@x.com;b@x.com"
EMAIL_TO_NO_NEW_RFP = "Manish.soni@dynatechconsultancy.com"

 # When RFP is submitted successfully
EMAIL_TO_RFP_DECLINED = "Manish.soni@dynatechconsultancy.com"  # When RFP is declined successfully
EMAIL_TO_RFP_ERROR_IN_SUBMISSION = "Manish.soni@dynatechconsultancy.com"  # When RFP is submission failed
EMAIL_TO_RFP_ERROR_IN_DECLINE = "Manish.soni@dynatechconsultancy.com"  # When RFP is decline failed or error in decline
EMAIL_TO_AUTOMATION_FAILURE = "Manish.soni@dynatechconsultancy.com"  # When Automation is failed
EMAIL_TO_NEW_RFP_NO_MATCH = "Manish.soni@dynatechconsultancy.com"
# When a new RFP is found AND materials are matched — receives the RFP file itself (in addition to
# Sales/Technical who receive the matched materials CSV)
# Add multiple recipients separated by semicolons: "a@x.com;b@x.com"
EMAIL_TO_RFP_SUBMITTED = "Manish.soni@dynatechconsultancy.com" 
EMAIL_TO_RFP_SAVED_DRAFT = "Manish.soni@dynatechconsultancy.com"  # Abdullah Alrawah(  When RFP is saved as draft successfully )


EMAIL_TO_RFP_REMINDER = "Manish.soni@dynatechconsultancy.com"
# RFP REMINDER EMAIL

# EMAIL_TO_NEW_RFP_WITH_MATCH = "sec.tenderteam@bahra-cables.com;ksatenders@bahra-cables.com"
# EMAIL_TO_NO_MATCHED_DATA = "sec.tenderteam@bahra-cables.com;ksatenders@bahra-cables.com"
# NOTE: EMAIL_TO_NEW_RFP_WITH_MATCH is now consolidated with EMAIL_TO_NEW_RFP (per-RFP email flow)
EMAIL_TO_NEW_RFP_WITH_MATCH = "Manish.soni@dynatechconsultancy.com"
EMAIL_TO_NO_MATCHED_DATA = "Manish.soni@dynatechconsultancy.com"  # When No matched data IN DOWNLOAD RFP"
# EMAIL_TO_RFP_SUBMITTED = "arawah@bahra-cables.com" 
# EMAIL_TO_RFP_SAVED_DRAFT = "arawah@bahra-cables.com"  # Abdullah Alrawah(  When RFP is saved as draft successfully )


# ===== RFP Notification Email — Team Assignment Table =====
# Shown in every new-RFP email so recipients know who handles each product.
# Each entry: {"product": "Category", "name": "Person Name"}
# A product can have multiple rows (one per person).
RFP_TEAM_TABLE = [
    {"product": "Cables",             "name": "Lotfy Idrees"},
    {"product": "Cable Accessories",  "name": "Ahmed Ebeed"},
    {"product": "Non-Cables",         "name": "Karim Nour"},
    {"product": "TBS and BED",        "name": "Intikhab Ali"},
    {"product": "TBS and BED",        "name": "Mohammad Ariff"},
]

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



# ===== Temp data for testing =====
# python download_from_csv.py --csv C:\python\RFP-automation\ALLRFPs\Portal-Rfps\cr673_requestforproposals.csv --username Loai.Albar@bahra-cables.com --password Bahra@2026



# python download_from_csv.py --file C:\python\RFP-automation\ALLRFPs\Portal-Rfps\cr673_requestforproposals.csv --username Loai.Albar@bahra-cables.com --password Bahra@2026


# python download_from_csv.py --file C:\python\RFP-automation\missing_rfps_20260220_182001.csv --username Loai.Albar@bahra-cables.com --password Bahra@2026
