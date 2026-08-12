"""
Example config — copy to `config.py` and fill in every value.
"""

import logging
import os

# ── 1. AZURE AD & AUTHENTICATION ─────────────────────────────────────────────
TENANT_ID = ""
CLIENT_ID = ""
CLIENT_SECRET = ""
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = ["https://graph.microsoft.com/.default"]

# ── 2. DATAVERSE ─────────────────────────────────────────────────────────────
RESOURCE_URL = ""

AUTOMATION_LOG_TABLE_LOGICAL = ""
AUTOMATION_LOG_TABLE_API = ""

RFP_ACTIVITY_LOG_TABLE_LOGICAL = ""
RFP_ACTIVITY_LOG_TABLE_API = ""

USERS_TABLE_LOGICAL = ""
USERS_TABLE_API = ""

SAP_PASSWORD_TABLE_LOGICAL = ""
SAP_PASSWORD_TABLE_API = ""

AUTOMATION_SCHEDULE_TABLE_LOGICAL = ""
AUTOMATION_SCHEDULE_TABLE_API = ""

RFP_STATUS_TABLE_LOGICAL = ""
RFP_STATUS_TABLE_API = ""

ROLES_TABLE_LOGICAL = ""
ROLES_TABLE_API = ""

ROLE_PERMISSIONS_TABLE_LOGICAL = ""
ROLE_PERMISSIONS_TABLE_API = ""

AUDIT_LOG_TABLE_LOGICAL = ""
AUDIT_LOG_TABLE_API = ""

USER_STATUS_TABLE_LOGICAL = ""
USER_STATUS_TABLE_API = ""

SYSTEM_SETTINGS_TABLE_LOGICAL = ""
SYSTEM_SETTINGS_TABLE_API = ""

MATERIAL_MASTER_TABLE_LOGICAL = ""
MATERIAL_MASTER_TABLE_API = ""

KEYWORDS_TABLE_LOGICAL = ""
KEYWORDS_TABLE_API = ""

RFP_TEAM_DV_TABLE_LOGICAL = ""
RFP_TEAM_DV_TABLE_API = ""

RFP_TEAM_COLUMNS_TABLE_LOGICAL = ""
RFP_TEAM_COLUMNS_TABLE_API = ""

RFP_RESPONSE_TABLE_LOGICAL = ""
RFP_RESPONSE_TABLE_API = ""

BAHRA_RFP_REMINDER_LOGICAL = ""
BAHRA_RFP_REMINDER_API = ""

RFP_DELEGATION_TABLE_LOGICAL = ""
RFP_DELEGATION_TABLE_API = ""

# ── 3. SHAREPOINT / GRAPH API ────────────────────────────────────────────────
SHAREPOINT_HOSTNAME = ""
SITE_PATH = ""
DRIVE_NAME = ""
SP_BASE_FOLDER = ""
SP_BASE_FOLDER_RFP_UPLOAD_FILES = ""
SP_FAILURE_LOGS_FOLDER = ""
TDS_FILE_PATH = ""

# ── 4. POWER AUTOMATE & ACTIONABLE CARDS ─────────────────────────────────────
FLOW_URL = ""
FORGOT_PASSWORD_FLOW_URL = ""

ACTIONABLE_CARD_ORIGINATOR_ID = ""
ACTIONABLE_CARD_CALLBACK_URL = ""
ACTIONABLE_CARD_ACTIONS_APP_ID = "48af08dc-f6d2-435f-b2a7-069abd99c086"  # fixed by Microsoft
ACTIONABLE_CARD_APP_ID_URI = ""

UPLOAD_BASE_URL = ""        # must end with "/"
UPLOAD_TOKEN_SECRET = ""
FRONTEND_URL = ""           # no trailing slash

# ── 5. ARIBA PORTAL & RFP SETTINGS ───────────────────────────────────────────
URL = ""

COMPANY_NAME = ""
COMPANY_OPTIONS = []

_DEFAULT_RFP_DETAIL_SELECTORS = [
    'div.wideLabels table td',
    'table.wideLabels td',
    'table td',
    'div.wideLabels td',
    '.w-tbl-cell',
    'div[class*="label"] table td',
]
# {"<company>": {"preferred_selectors": list(_DEFAULT_RFP_DETAIL_SELECTORS)}}
COMPANY_RFP_SELECTORS = {}

VALID_RFP_STATUSES = ["no", "saved_draft", "submitted", "declined"]

# ── 6. EMAIL CONFIGURATION ───────────────────────────────────────────────────
EMAIL_MODE = "dev"          # "dev" | "prod"
DEV_EMAIL = ""

_DEV_RFP_TEAM_TABLE = [
    {"product": "", "name": "", "email": ""},
]

EMAIL_TO_NEW_RFP = DEV_EMAIL
EMAIL_TO_NO_NEW_RFP = DEV_EMAIL
EMAIL_TO_RFP_DECLINED = DEV_EMAIL
EMAIL_TO_RFP_ERROR_IN_SUBMISSION = DEV_EMAIL
EMAIL_TO_RFP_ERROR_IN_DECLINE = DEV_EMAIL
EMAIL_TO_AUTOMATION_FAILURE = DEV_EMAIL
EMAIL_TO_RFP_SUBMITTED = DEV_EMAIL
EMAIL_TO_RFP_SAVED_DRAFT = DEV_EMAIL
EMAIL_TO_RFP_REMINDER = DEV_EMAIL
EMAIL_TO_NO_MATCHED_DATA = DEV_EMAIL
RFP_TEAM_TABLE = _DEV_RFP_TEAM_TABLE

DECLINE_BUTTON_EMAILS = []

# ── 7. SECURITY & SESSION MANAGEMENT ─────────────────────────────────────────
SESSION_TIMEOUT_SECONDS = 7200
IDLE_TIMEOUT_SECONDS = 1800
SESSION_WARNING_SECONDS = 300
SESSION_REFRESH_INTERVAL = 300

RBAC_CACHE_TTL_SECONDS = 300
ACCOUNT_LOCKOUT_THRESHOLD = 5
ACCOUNT_LOCKOUT_DURATION_MINUTES = 30

PASSWORD_MIN_LENGTH = 8
PASSWORD_REQUIRE_UPPERCASE = True
PASSWORD_REQUIRE_NUMBER = True
PASSWORD_MAX_AGE_DAYS = 90

# ── 8. CACHING & PAGINATION ──────────────────────────────────────────────────
DASHBOARD_TTL_SECONDS = 300
LOGS_TTL_SECONDS = 300
SAP_LOGS_TTL_SECONDS = 300
DASHBOARD_HTTP_MAX_AGE = 30

LOGS_FETCH_TOP_MAX = 2000
LOGS_FETCH_AHEAD_FACTOR = 10

DEFAULT_PAGE_SIZE = 50
MIN_PAGE_SIZE = 10
MAX_PAGE_SIZE = 500

# ── 9. LOCAL FILE PATHS ──────────────────────────────────────────────────────
DOWNLOAD_DIR = os.path.expanduser("~/Downloads")

OUTPUT_DIR = os.path.join(os.getcwd(), "ALLRFPs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

FAILURE_LOGS_DIR = os.path.join(os.getcwd(), "LOGS")
os.makedirs(FAILURE_LOGS_DIR, exist_ok=True)


# ── 10. HELPER FUNCTIONS ─────────────────────────────────────────────────────
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
