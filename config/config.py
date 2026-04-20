"""
Application Configuration
=========================
Central configuration for the RFP Automation system.
All developer/technical settings are managed here (not in the portal).
Only email recipient addresses are managed via the portal's System Settings page.
"""

import logging
import os

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# 1. AZURE AD & AUTHENTICATION
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

TENANT_ID = "46aa82d0-1a4b-4b08-b520-514ccbe1e7ca"
CLIENT_ID = "97312492-991a-46be-91de-62430026f72d"
CLIENT_SECRET = "pDN8Q~kLKXRoOmEB5PvLRDo-zVH2o91IjRtaJagr"
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = ["https://graph.microsoft.com/.default"]

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# 2. DATAVERSE
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

RESOURCE_URL = "https://operations-bahrauat-1.crm11.dynamics.com"

# Dataverse tables: (logical_name, api_plural_name)
# Logical names are used for metadata; API names for CRUD operations.

AUTOMATION_LOG_TABLE_LOGICAL = "cr673_bahra_automation_log1"
AUTOMATION_LOG_TABLE_API = "cr673_bahra_automation_log1s"

RFP_ACTIVITY_LOG_TABLE_LOGICAL = "cr673_requestforproposal"
RFP_ACTIVITY_LOG_TABLE_API = "cr673_requestforproposals"

USERS_TABLE_LOGICAL = "cr673_bahra_users"
USERS_TABLE_API = "cr673_bahra_userses"

SAP_PASSWORD_TABLE_LOGICAL = "cr673_bahra_sap_infomation"
SAP_PASSWORD_TABLE_API = "cr673_bahra_sap_infomations"

AUTOMATION_SCHEDULE_TABLE_LOGICAL = "cr673_bahra_automation_schedules"
AUTOMATION_SCHEDULE_TABLE_API = "cr673_bahra_automation_scheduleses"

RFP_STATUS_TABLE_LOGICAL = "cr673_bhara_rfp_status"
RFP_STATUS_TABLE_API = "cr673_bhara_rfp_statuses"

ROLES_TABLE_LOGICAL = "cr673_bahra_roles"
ROLES_TABLE_API = "cr673_bahra_roleses"

ROLE_PERMISSIONS_TABLE_LOGICAL = "cr673_bahra_role_permissions"
ROLE_PERMISSIONS_TABLE_API = "cr673_bahra_role_permissionses"

AUDIT_LOG_TABLE_LOGICAL = "cr673_bahra_audit_logs"
AUDIT_LOG_TABLE_API = "cr673_bahra_audit_logses"

USER_STATUS_TABLE_LOGICAL = "cr673_bahra_user_status"
USER_STATUS_TABLE_API = "cr673_bahra_user_statuses"

SYSTEM_SETTINGS_TABLE_LOGICAL = "cr673_bahra_system_settings"
SYSTEM_SETTINGS_TABLE_API = "cr673_bahra_system_settingses"

MATERIAL_MASTER_TABLE_LOGICAL = "cr673_bahra_material_master"
MATERIAL_MASTER_TABLE_API = "cr673_bahra_material_masters"

KEYWORDS_TABLE_LOGICAL = "cr673_bahra_keywords"
KEYWORDS_TABLE_API = "cr673_bahra_keywordses"

RFP_TEAM_DV_TABLE_LOGICAL = "cr673_bahra_rfp_team"
RFP_TEAM_DV_TABLE_API = "cr673_bahra_rfp_teams"

RFP_TEAM_COLUMNS_TABLE_LOGICAL = "cr673_bahra_rfp_team_columns"
RFP_TEAM_COLUMNS_TABLE_API = "cr673_bahra_rfp_team_columnses"

RFP_RESPONSE_TABLE_LOGICAL = "cr6db_cr673_bahra_rfp_response"
RFP_RESPONSE_TABLE_API = "cr6db_cr673_bahra_rfp_responses"

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# 3. SHAREPOINT / GRAPH API
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

SHAREPOINT_HOSTNAME = "bahracables.sharepoint.com"
SITE_PATH = "/sites/LiveSite/RFPAutomation"
DRIVE_NAME = "Documents"
SP_BASE_FOLDER = "RFP-logs"
SP_BASE_FOLDER_RFP_UPLOAD_FILES = "RFP-logs/RFP-upload-files"
SP_FAILURE_LOGS_FOLDER = "RFP-logs/automation-error-logs"
TDS_FILE_PATH = "https://bahracables.sharepoint.com/sites/Test-AI-ML/Shared%20Documents/RFP-logs/TDS-files/"

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# 4. POWER AUTOMATE
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

FLOW_URL = (
    "https://dab4cde858caeaa0b535f6dbd4b6cf.a6.environment.api.powerplatform.com:443"
    "/powerautomate/automations/direct/workflows/8b59f8e17de8493ab5f575461aa92133"
    "/triggers/manual/paths/invoke?api-version=1"
    "&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0"
    "&sig=bG4Z-fghyYpzFZHxsyu8yzsrSlPlNEkzgMCQeKvS9VI"
)

FORGOT_PASSWORD_FLOW_URL = (
    "https://dab4cde858caeaa0b535f6dbd4b6cf.a6.environment.api.powerplatform.com:443"
    "/powerautomate/automations/direct/workflows/326c08241613446da0e9cd6235d4e666"
    "/triggers/manual/paths/invoke?api-version=1"
    "&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0"
    "&sig=r3S5vKCYj3BQ0ymdc-qsBY2fPgzbsM67EDzfIiQcQFQ"
)

# Actionable Messages (Adaptive Cards in Outlook)
ACTIONABLE_CARD_ORIGINATOR_ID ="8dc8a969-5abf-4c49-828f-fbced5ae7570"   # orgnization Id Without MSEntra ID
ACTIONABLE_CARD_CALLBACK_URL = "https://0vv8220f-8000.inc1.devtunnels.ms/api/actionable-card/response" 

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# 5. ARIBA PORTAL & RFP SETTINGS
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

URL = "https://service.ariba.com/Sourcing.aw/109582016/aw?awh=r&awssk=u9fNiSxN&dard=1#b0"

COMPANY_NAME = "Saudi Electricity Company"

COMPANY_OPTIONS = [
    "Saudi Electricity Company",
    "Aramco e-Marketplace",
    # "SABIC - Saudi Basic Industries Corp.",
    # "HADEED - RAJHI STEEL",
]

VALID_RFP_STATUSES = ["no", "saved_draft", "submitted", "declined"]

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# 6. EMAIL CONFIGURATION
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# EMAIL_MODE controls routing for ALL outgoing emails:
#   "dev"  -> every email goes to DEV_EMAIL only
#   "prod" -> emails go to the production recipient lists below

EMAIL_MODE = "prod"
DEV_EMAIL = "KSAGov.tenders@bahra-cables.com;manish.soni@dynatechconsultancy.com"

# Dev RFP team assignment
_DEV_RFP_TEAM_TABLE = [
    {"product": "Cables", "name": "Lotfy Idrees", "email": "KSAGOV.tenders@bahra-cables.com"},
]

# Email fallback â€” only used if Dataverse is unreachable.
# Production recipients are managed in Dataverse system settings (cr673_bahra_system_settings).
EMAIL_TO_NEW_RFP = DEV_EMAIL
EMAIL_TO_NO_NEW_RFP = DEV_EMAIL
EMAIL_TO_RFP_DECLINED = DEV_EMAIL
EMAIL_TO_RFP_ERROR_IN_SUBMISSION = DEV_EMAIL
EMAIL_TO_RFP_ERROR_IN_DECLINE = DEV_EMAIL
EMAIL_TO_AUTOMATION_FAILURE = DEV_EMAIL
EMAIL_TO_RFP_SUBMITTED = DEV_EMAIL
EMAIL_TO_RFP_SAVED_DRAFT = DEV_EMAIL
EMAIL_TO_RFP_REMINDER = DEV_EMAIL
EMAIL_TO_NEW_RFP_WITH_MATCH = DEV_EMAIL
EMAIL_TO_NO_MATCHED_DATA = DEV_EMAIL
EMAIL_TO_NEW_RFP_NO_MATCH = DEV_EMAIL
RFP_TEAM_TABLE = _DEV_RFP_TEAM_TABLE

# Emails authorized to see the "Decline RFP" button in actionable card emails
DECLINE_BUTTON_EMAILS = [
    "abdullah.rawah@bahra-cables.com",
]

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# 7. SECURITY & SESSION MANAGEMENT
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

SESSION_TIMEOUT_SECONDS = 7200          # 2 hours
IDLE_TIMEOUT_SECONDS = 1800             # 30 minutes
SESSION_WARNING_SECONDS = 300           # 5 minutes before expiry
SESSION_REFRESH_INTERVAL = 300          # 5 minutes

RBAC_CACHE_TTL_SECONDS = 300            # 5 minutes
ACCOUNT_LOCKOUT_THRESHOLD = 5           # Failed attempts before lockout
ACCOUNT_LOCKOUT_DURATION_MINUTES = 30   # Lockout duration

PASSWORD_MIN_LENGTH = 8
PASSWORD_REQUIRE_UPPERCASE = True
PASSWORD_REQUIRE_NUMBER = True
PASSWORD_MAX_AGE_DAYS = 90

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# 8. CACHING & PAGINATION
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

DASHBOARD_TTL_SECONDS = 300
LOGS_TTL_SECONDS = 300
SAP_LOGS_TTL_SECONDS = 300
DASHBOARD_HTTP_MAX_AGE = 30

LOGS_FETCH_TOP_MAX = 2000
LOGS_FETCH_AHEAD_FACTOR = 10

DEFAULT_PAGE_SIZE = 50
MIN_PAGE_SIZE = 10
MAX_PAGE_SIZE = 500

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# 9. LOCAL FILE PATHS
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

DOWNLOAD_DIR = os.path.expanduser("~/Downloads")

OUTPUT_DIR = os.path.join(os.getcwd(), "ALLRFPs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

FAILURE_LOGS_DIR = os.path.join(os.getcwd(), "LOGS")
os.makedirs(FAILURE_LOGS_DIR, exist_ok=True)

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# 10. HELPER FUNCTIONS
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def resolve_company_name(name: str) -> str:
    """Resolve company name, defaulting to COMPANY_NAME if empty."""
    if not name:
        return COMPANY_NAME

    name = name.strip()

    if name in COMPANY_OPTIONS:
        return name

    logging.warning(f"Company name '{name}' not in COMPANY_OPTIONS.")
    return name


def validate_rfp_status(status: str) -> bool:
    """Validate if the given status is a valid RFP participation status."""
    return status.lower() in [s.lower() for s in VALID_RFP_STATUSES]