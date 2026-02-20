"""
Creates the cr673_bahra_system_settings Dataverse table with all required
columns and then seeds it with every configuration value from config/config.py.

Run from the project root:
    python scripts/create_settings_table.py

What it does:
  1. Creates the entity  : cr673_bahra_system_settings
  2. Adds custom columns : cr673_value, cr673_data_type, cr673_section,
                           cr673_label, cr673_description,
                           cr673_is_sensitive, cr673_is_editable
  3. Seeds all rows from config/config.py (skips keys that already exist)

If the table already exists, step 1 is skipped and the script proceeds to
column creation (also idempotent) and seeding.
"""

import sys
import os
import json
import time
import logging
import requests

# Allow imports from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

from helpers.core_helper import DATAVERSE
from helpers.settings_helper import SETTINGS_TABLE_API, SETTINGS_TABLE_LOGICAL
import config.config as cfg

# ─── Dataverse API helpers ────────────────────────────────────────────────────

API_URL = DATAVERSE.api_url  # e.g. https://…/api/data/v9.2/
ENTITY_DEFS_URL = f"{API_URL}EntityDefinitions"

SCHEMA_NAME = "cr673_bahra_system_settings"
DISPLAY_NAME = "Bahra System Settings"
DISPLAY_PLURAL = "Bahra System Settings"
DESCRIPTION = "Stores application-level configuration for the RFP Automation system."
PRIMARY_NAME_ATTR = "cr673_key"


def _label(text: str) -> dict:
    """Build a Dataverse Label object."""
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.Label",
        "LocalizedLabels": [
            {
                "@odata.type": "Microsoft.Dynamics.CRM.LocalizedLabel",
                "Label": text,
                "LanguageCode": 1033,
            }
        ],
    }


def _headers(content_type="application/json"):
    return DATAVERSE._headers(content_type)


# ─── Step 1: Create the entity ───────────────────────────────────────────────

def _table_exists() -> bool:
    """Check whether the table already exists in Dataverse."""
    url = f"{ENTITY_DEFS_URL}(LogicalName='{SCHEMA_NAME}')"
    resp = requests.get(url, headers=_headers())
    return resp.status_code == 200


def create_table():
    """Create the cr673_bahra_system_settings entity."""
    if _table_exists():
        logger.info(f"Table '{SCHEMA_NAME}' already exists — skipping creation.")
        return True

    body = {
        "@odata.type": "Microsoft.Dynamics.CRM.EntityMetadata",
        "SchemaName": SCHEMA_NAME,
        "DisplayName": _label(DISPLAY_NAME),
        "DisplayCollectionName": _label(DISPLAY_PLURAL),
        "Description": _label(DESCRIPTION),
        "OwnershipType": "UserOwned",
        "IsActivity": False,
        "HasActivities": False,
        "HasNotes": False,
        "PrimaryNameAttribute": PRIMARY_NAME_ATTR,
        "Attributes": [
            {
                "AttributeType": "String",
                "@odata.type": "Microsoft.Dynamics.CRM.StringAttributeMetadata",
                "SchemaName": PRIMARY_NAME_ATTR,
                "DisplayName": _label("Key"),
                "Description": _label("Unique configuration key (maps to config.py variable name)."),
                "RequiredLevel": {
                    "Value": "ApplicationRequired",
                    "CanBeChanged": False,
                },
                "MaxLength": 250,
                "IsPrimaryName": True,
            }
        ],
    }

    resp = requests.post(ENTITY_DEFS_URL, json=body, headers=_headers())
    if resp.status_code in (200, 201, 204):
        logger.info(f"Table '{SCHEMA_NAME}' created successfully.")
        return True
    else:
        logger.error(f"Failed to create table: {resp.status_code} {resp.text[:500]}")
        return False


# ─── Step 2: Add custom columns ──────────────────────────────────────────────

ATTRS_URL = f"{ENTITY_DEFS_URL}(LogicalName='{SCHEMA_NAME}')/Attributes"


def _attr_exists(logical_name: str) -> bool:
    url = f"{ATTRS_URL}(LogicalName='{logical_name}')"
    resp = requests.get(url, headers=_headers())
    return resp.status_code == 200


def _add_string_column(schema_name: str, label: str, description: str, max_length: int = 200):
    if _attr_exists(schema_name.lower()):
        logger.info(f"  Column '{schema_name}' already exists — skip.")
        return True

    body = {
        "@odata.type": "Microsoft.Dynamics.CRM.StringAttributeMetadata",
        "AttributeType": "String",
        "SchemaName": schema_name,
        "DisplayName": _label(label),
        "Description": _label(description),
        "MaxLength": max_length,
        "RequiredLevel": {"Value": "None", "CanBeChanged": True},
    }
    resp = requests.post(ATTRS_URL, json=body, headers=_headers())
    if resp.status_code in (200, 201, 204):
        logger.info(f"  Column '{schema_name}' created.")
        return True
    logger.error(f"  Failed to create '{schema_name}': {resp.status_code} {resp.text[:300]}")
    return False


def _add_memo_column(schema_name: str, label: str, description: str, max_length: int = 100000):
    if _attr_exists(schema_name.lower()):
        logger.info(f"  Column '{schema_name}' already exists — skip.")
        return True

    body = {
        "@odata.type": "Microsoft.Dynamics.CRM.MemoAttributeMetadata",
        "AttributeType": "Memo",
        "SchemaName": schema_name,
        "DisplayName": _label(label),
        "Description": _label(description),
        "MaxLength": max_length,
        "RequiredLevel": {"Value": "None", "CanBeChanged": True},
    }
    resp = requests.post(ATTRS_URL, json=body, headers=_headers())
    if resp.status_code in (200, 201, 204):
        logger.info(f"  Column '{schema_name}' created.")
        return True
    logger.error(f"  Failed to create '{schema_name}': {resp.status_code} {resp.text[:300]}")
    return False


def _add_boolean_column(schema_name: str, label: str, description: str, default_value: bool = False):
    if _attr_exists(schema_name.lower()):
        logger.info(f"  Column '{schema_name}' already exists — skip.")
        return True

    body = {
        "@odata.type": "Microsoft.Dynamics.CRM.BooleanAttributeMetadata",
        "AttributeType": "Boolean",
        "SchemaName": schema_name,
        "DisplayName": _label(label),
        "Description": _label(description),
        "RequiredLevel": {"Value": "None", "CanBeChanged": True},
        "DefaultValue": default_value,
        "OptionSet": {
            "@odata.type": "Microsoft.Dynamics.CRM.BooleanOptionSetMetadata",
            "TrueOption": {
                "Value": 1,
                "Label": _label("Yes"),
            },
            "FalseOption": {
                "Value": 0,
                "Label": _label("No"),
            },
        },
    }
    resp = requests.post(ATTRS_URL, json=body, headers=_headers())
    if resp.status_code in (200, 201, 204):
        logger.info(f"  Column '{schema_name}' created.")
        return True
    logger.error(f"  Failed to create '{schema_name}': {resp.status_code} {resp.text[:300]}")
    return False


def create_columns():
    """Add all custom columns to the table."""
    logger.info("Creating custom columns …")

    _add_memo_column(
        "cr673_value", "Value",
        "Setting value (plain string or serialized JSON).", 100000,
    )
    _add_string_column(
        "cr673_data_type", "Data Type",
        "Value type: string, integer, boolean, json_list, json_table.", 50,
    )
    _add_string_column(
        "cr673_section", "Section",
        "UI grouping section: general, email, sharepoint, dataverse, flow_urls, rfp_team.", 100,
    )
    _add_string_column(
        "cr673_label", "Label",
        "Human-readable display label shown in the Settings page.", 250,
    )
    _add_memo_column(
        "cr673_description", "Description",
        "Help text displayed under the label in the Settings page.", 2000,
    )
    _add_boolean_column(
        "cr673_is_sensitive", "Is Sensitive",
        "If true, the value is masked in the UI (e.g. passwords, secrets).", False,
    )
    _add_boolean_column(
        "cr673_is_editable", "Is Editable",
        "If true, the value can be edited from the Settings page.", True,
    )

    logger.info("Column creation complete.")


# ─── Step 2b: Publish entity customizations ──────────────────────────────────

def publish_entity():
    """
    Publish entity customizations so newly created columns become available
    to the OData data endpoint. Without this, inserts may fail with
    'property does not exist' errors.
    """
    logger.info("Publishing entity customizations …")
    url = f"{API_URL}PublishXml"
    body = {
        "ParameterXml": (
            "<importexportxml>"
            "<entities>"
            f"<entity>{SCHEMA_NAME}</entity>"
            "</entities>"
            "</importexportxml>"
        )
    }
    resp = requests.post(url, json=body, headers=_headers())
    if resp.status_code in (200, 204):
        logger.info("Entity published successfully.")
        return True
    else:
        logger.error(f"Publish failed: {resp.status_code} {resp.text[:500]}")
        return False


def _wait_for_columns(required_columns: list[str], max_wait: int = 60, interval: int = 5) -> bool:
    """
    Poll the entity metadata until all required columns are visible,
    or until max_wait seconds have elapsed.
    """
    logger.info(f"Waiting for columns to become available (up to {max_wait}s) …")
    elapsed = 0
    while elapsed < max_wait:
        try:
            url = (
                f"{ENTITY_DEFS_URL}(LogicalName='{SCHEMA_NAME}')/Attributes"
                f"?$select=LogicalName&$filter="
                + " or ".join(f"LogicalName eq '{c}'" for c in required_columns)
            )
            resp = requests.get(url, headers=_headers())
            if resp.status_code == 200:
                found = {a["LogicalName"] for a in resp.json().get("value", [])}
                missing = set(required_columns) - found
                if not missing:
                    logger.info("All columns are available.")
                    return True
                logger.info(f"  Still waiting … missing: {missing}")
        except Exception as e:
            logger.warning(f"  Check failed: {e}")

        time.sleep(interval)
        elapsed += interval

    logger.warning("Timed out waiting for columns. Proceeding anyway …")
    return False


# ─── Step 3: Seed all rows ───────────────────────────────────────────────────

def _jl(v) -> str:
    return json.dumps(v, ensure_ascii=False)


# Every setting to seed — mirrors config/config.py
SETTINGS_SEED: list[dict] = [
    # ── General ──────────────────────────────────────────────────────────────
    {
        "key": "URL",
        "label": "Ariba Portal URL",
        "description": "Main Ariba sourcing portal URL used by the automation bot.",
        "value": cfg.URL,
        "data_type": "string",
        "section": "general",
        "is_sensitive": False,
        "is_editable": True,
    },
    {
        "key": "COMPANY_NAME",
        "label": "Default Company Name",
        "description": "The company name used when none is specified.",
        "value": cfg.COMPANY_NAME,
        "data_type": "string",
        "section": "general",
        "is_sensitive": False,
        "is_editable": True,
    },
    {
        "key": "COMPANY_OPTIONS",
        "label": "Supported Company Options",
        "description": "JSON list of company names available in the portal dropdown.",
        "value": _jl(cfg.COMPANY_OPTIONS),
        "data_type": "json_list",
        "section": "general",
        "is_sensitive": False,
        "is_editable": True,
    },

    # ── Email ─────────────────────────────────────────────────────────────────
    {
        "key": "EMAIL_TO_NEW_RFP",
        "label": "New RFP Email Recipients",
        "description": "Recipients when a new RFP is found. Separate multiple with semicolons.",
        "value": cfg.EMAIL_TO_NEW_RFP,
        "data_type": "string",
        "section": "email",
        "is_sensitive": False,
        "is_editable": True,
    },
    {
        "key": "EMAIL_TO_NO_NEW_RFP",
        "label": "No New RFP Email Recipients",
        "description": "Recipients when automation runs but no new RFP is found.",
        "value": cfg.EMAIL_TO_NO_NEW_RFP,
        "data_type": "string",
        "section": "email",
        "is_sensitive": False,
        "is_editable": True,
    },
    {
        "key": "EMAIL_TO_RFP_DECLINED",
        "label": "RFP Declined Email Recipients",
        "description": "Recipients when an RFP is declined successfully.",
        "value": cfg.EMAIL_TO_RFP_DECLINED,
        "data_type": "string",
        "section": "email",
        "is_sensitive": False,
        "is_editable": True,
    },
    {
        "key": "EMAIL_TO_RFP_ERROR_IN_SUBMISSION",
        "label": "RFP Submission Error Email Recipients",
        "description": "Recipients when RFP submission fails.",
        "value": cfg.EMAIL_TO_RFP_ERROR_IN_SUBMISSION,
        "data_type": "string",
        "section": "email",
        "is_sensitive": False,
        "is_editable": True,
    },
    {
        "key": "EMAIL_TO_RFP_ERROR_IN_DECLINE",
        "label": "RFP Decline Error Email Recipients",
        "description": "Recipients when RFP decline fails.",
        "value": cfg.EMAIL_TO_RFP_ERROR_IN_DECLINE,
        "data_type": "string",
        "section": "email",
        "is_sensitive": False,
        "is_editable": True,
    },
    {
        "key": "EMAIL_TO_AUTOMATION_FAILURE",
        "label": "Automation Failure Email Recipients",
        "description": "Recipients when the automation process itself fails.",
        "value": cfg.EMAIL_TO_AUTOMATION_FAILURE,
        "data_type": "string",
        "section": "email",
        "is_sensitive": False,
        "is_editable": True,
    },
    {
        "key": "EMAIL_TO_NEW_RFP_NO_MATCH",
        "label": "New RFP (No Match) Email Recipients",
        "description": "Recipients when a new RFP is found but no material matches.",
        "value": cfg.EMAIL_TO_NEW_RFP_NO_MATCH,
        "data_type": "string",
        "section": "email",
        "is_sensitive": False,
        "is_editable": True,
    },
    {
        "key": "EMAIL_TO_RFP_SUBMITTED",
        "label": "RFP Submitted Email Recipients",
        "description": "Recipients when an RFP is submitted successfully.",
        "value": cfg.EMAIL_TO_RFP_SUBMITTED,
        "data_type": "string",
        "section": "email",
        "is_sensitive": False,
        "is_editable": True,
    },
    {
        "key": "EMAIL_TO_RFP_SAVED_DRAFT",
        "label": "RFP Saved as Draft Email Recipients",
        "description": "Recipients when an RFP is saved as draft successfully.",
        "value": cfg.EMAIL_TO_RFP_SAVED_DRAFT,
        "data_type": "string",
        "section": "email",
        "is_sensitive": False,
        "is_editable": True,
    },
    {
        "key": "EMAIL_TO_RFP_REMINDER",
        "label": "RFP Reminder Email Recipients",
        "description": "Recipients for RFP reminder emails.",
        "value": cfg.EMAIL_TO_RFP_REMINDER,
        "data_type": "string",
        "section": "email",
        "is_sensitive": False,
        "is_editable": True,
    },
    {
        "key": "EMAIL_TO_NEW_RFP_WITH_MATCH",
        "label": "New RFP (With Match) Email Recipients",
        "description": "Recipients when a new RFP is found with material matches.",
        "value": cfg.EMAIL_TO_NEW_RFP_WITH_MATCH,
        "data_type": "string",
        "section": "email",
        "is_sensitive": False,
        "is_editable": True,
    },
    {
        "key": "EMAIL_TO_NO_MATCHED_DATA",
        "label": "No Matched Data Email Recipients",
        "description": "Recipients when no matched data is found during download.",
        "value": cfg.EMAIL_TO_NO_MATCHED_DATA,
        "data_type": "string",
        "section": "email",
        "is_sensitive": False,
        "is_editable": True,
    },

    # ── SharePoint / Graph API ────────────────────────────────────────────────
    {
        "key": "TENANT_ID",
        "label": "Azure Tenant ID",
        "description": "Microsoft Azure Active Directory Tenant ID.",
        "value": cfg.TENANT_ID,
        "data_type": "string",
        "section": "sharepoint",
        "is_sensitive": False,
        "is_editable": True,
    },
    {
        "key": "CLIENT_ID",
        "label": "Azure App Client ID",
        "description": "Microsoft Azure App Registration Client ID.",
        "value": cfg.CLIENT_ID,
        "data_type": "string",
        "section": "sharepoint",
        "is_sensitive": False,
        "is_editable": True,
    },
    {
        "key": "CLIENT_SECRET",
        "label": "Azure App Client Secret",
        "description": "Microsoft Azure App Registration Client Secret.",
        "value": cfg.CLIENT_SECRET,
        "data_type": "string",
        "section": "sharepoint",
        "is_sensitive": True,
        "is_editable": True,
    },
    {
        "key": "SHAREPOINT_HOSTNAME",
        "label": "SharePoint Hostname",
        "description": "SharePoint site hostname (e.g. yourcompany.sharepoint.com).",
        "value": cfg.SHAREPOINT_HOSTNAME,
        "data_type": "string",
        "section": "sharepoint",
        "is_sensitive": False,
        "is_editable": True,
    },
    {
        "key": "SITE_PATH",
        "label": "SharePoint Site Path",
        "description": "Path to the SharePoint site (e.g. /sites/MySite/RFP).",
        "value": cfg.SITE_PATH,
        "data_type": "string",
        "section": "sharepoint",
        "is_sensitive": False,
        "is_editable": True,
    },
    {
        "key": "DRIVE_NAME",
        "label": "SharePoint Drive Name",
        "description": "Document library name (e.g. Documents).",
        "value": cfg.DRIVE_NAME,
        "data_type": "string",
        "section": "sharepoint",
        "is_sensitive": False,
        "is_editable": True,
    },
    {
        "key": "SP_BASE_FOLDER",
        "label": "SharePoint Base Folder",
        "description": "Base folder path for RFP logs in SharePoint.",
        "value": cfg.SP_BASE_FOLDER,
        "data_type": "string",
        "section": "sharepoint",
        "is_sensitive": False,
        "is_editable": True,
    },
    {
        "key": "SP_BASE_FOLDER_RFP_UPLOAD_FILES",
        "label": "SharePoint RFP Upload Files Folder",
        "description": "Folder where filled RFP files are uploaded.",
        "value": cfg.SP_BASE_FOLDER_RFP_UPLOAD_FILES,
        "data_type": "string",
        "section": "sharepoint",
        "is_sensitive": False,
        "is_editable": True,
    },
    {
        "key": "SP_FAILURE_LOGS_FOLDER",
        "label": "SharePoint Failure Logs Folder",
        "description": "Folder path for automation error logs in SharePoint.",
        "value": cfg.SP_FAILURE_LOGS_FOLDER,
        "data_type": "string",
        "section": "sharepoint",
        "is_sensitive": False,
        "is_editable": True,
    },
    {
        "key": "TDS_FILE_PATH",
        "label": "TDS Files SharePoint URL",
        "description": "Full SharePoint URL to the TDS files folder.",
        "value": cfg.TDS_FILE_PATH,
        "data_type": "string",
        "section": "sharepoint",
        "is_sensitive": False,
        "is_editable": True,
    },

    # ── Dataverse ─────────────────────────────────────────────────────────────
    {
        "key": "RESOURCE_URL",
        "label": "Dataverse Resource URL",
        "description": "The Dynamics 365 / Dataverse environment URL.",
        "value": cfg.RESOURCE_URL,
        "data_type": "string",
        "section": "dataverse",
        "is_sensitive": False,
        "is_editable": True,
    },
    {
        "key": "AUTOMATION_LOG_TABLE_LOGICAL",
        "label": "Automation Log Table (Logical Name)",
        "description": "Logical name of the automation log Dataverse table.",
        "value": cfg.AUTOMATION_LOG_TABLE_LOGICAL,
        "data_type": "string",
        "section": "dataverse",
        "is_sensitive": False,
        "is_editable": True,
    },
    {
        "key": "AUTOMATION_LOG_TABLE_API",
        "label": "Automation Log Table (API Name)",
        "description": "Plural API name of the automation log Dataverse table.",
        "value": cfg.AUTOMATION_LOG_TABLE_API,
        "data_type": "string",
        "section": "dataverse",
        "is_sensitive": False,
        "is_editable": True,
    },
    {
        "key": "RFP_ACTIVITY_LOG_TABLE_LOGICAL",
        "label": "RFP Activity Log Table (Logical Name)",
        "description": "Logical name of the RFP activity log Dataverse table.",
        "value": cfg.RFP_ACTIVITY_LOG_TABLE_LOGICAL,
        "data_type": "string",
        "section": "dataverse",
        "is_sensitive": False,
        "is_editable": True,
    },
    {
        "key": "RFP_ACTIVITY_LOG_TABLE_API",
        "label": "RFP Activity Log Table (API Name)",
        "description": "Plural API name of the RFP activity log Dataverse table.",
        "value": cfg.RFP_ACTIVITY_LOG_TABLE_API,
        "data_type": "string",
        "section": "dataverse",
        "is_sensitive": False,
        "is_editable": True,
    },
    {
        "key": "USERS_TABLE_LOGICAL",
        "label": "Users Table (Logical Name)",
        "description": "Logical name of the users Dataverse table.",
        "value": cfg.USERS_TABLE_LOGICAL,
        "data_type": "string",
        "section": "dataverse",
        "is_sensitive": False,
        "is_editable": True,
    },
    {
        "key": "USERS_TABLE_API",
        "label": "Users Table (API Name)",
        "description": "Plural API name of the users Dataverse table.",
        "value": cfg.USERS_TABLE_API,
        "data_type": "string",
        "section": "dataverse",
        "is_sensitive": False,
        "is_editable": True,
    },
    {
        "key": "SAP_PASSWORD_TABLE_LOGICAL",
        "label": "SAP Password Table (Logical Name)",
        "description": "Logical name of the SAP password Dataverse table.",
        "value": cfg.SAP_PASSWORD_TABLE_LOGICAL,
        "data_type": "string",
        "section": "dataverse",
        "is_sensitive": False,
        "is_editable": True,
    },
    {
        "key": "SAP_PASSWORD_TABLE_API",
        "label": "SAP Password Table (API Name)",
        "description": "Plural API name of the SAP password Dataverse table.",
        "value": cfg.SAP_PASSWORD_TABLE_API,
        "data_type": "string",
        "section": "dataverse",
        "is_sensitive": False,
        "is_editable": True,
    },
    {
        "key": "AUTOMATION_SCHEDULE_TABLE_LOGICAL",
        "label": "Automation Schedule Table (Logical Name)",
        "description": "Logical name of the automation schedule Dataverse table.",
        "value": cfg.AUTOMATION_SCHEDULE_TABLE_LOGICAL,
        "data_type": "string",
        "section": "dataverse",
        "is_sensitive": False,
        "is_editable": True,
    },
    {
        "key": "AUTOMATION_SCHEDULE_TABLE_API",
        "label": "Automation Schedule Table (API Name)",
        "description": "Plural API name of the automation schedule Dataverse table.",
        "value": cfg.AUTOMATION_SCHEDULE_TABLE_API,
        "data_type": "string",
        "section": "dataverse",
        "is_sensitive": False,
        "is_editable": True,
    },
    {
        "key": "RFP_STATUS_TABLE_LOGICAL",
        "label": "RFP Status Table (Logical Name)",
        "description": "Logical name of the RFP status tracking Dataverse table.",
        "value": cfg.RFP_STATUS_TABLE_LOGICAL,
        "data_type": "string",
        "section": "dataverse",
        "is_sensitive": False,
        "is_editable": True,
    },
    {
        "key": "RFP_STATUS_TABLE_API",
        "label": "RFP Status Table (API Name)",
        "description": "Plural API name of the RFP status tracking Dataverse table.",
        "value": cfg.RFP_STATUS_TABLE_API,
        "data_type": "string",
        "section": "dataverse",
        "is_sensitive": False,
        "is_editable": True,
    },

    # ── Flow URLs ─────────────────────────────────────────────────────────────
    {
        "key": "FLOW_URL",
        "label": "Power Automate Flow URL (Main)",
        "description": "HTTP trigger URL for the main RFP submission/download Power Automate flow.",
        "value": cfg.FLOW_URL,
        "data_type": "string",
        "section": "flow_urls",
        "is_sensitive": True,
        "is_editable": True,
    },
    {
        "key": "FORGOT_PASSWORD_FLOW_URL",
        "label": "Power Automate Flow URL (Forgot Password)",
        "description": "HTTP trigger URL for the forgot password Power Automate flow.",
        "value": cfg.FORGOT_PASSWORD_FLOW_URL,
        "data_type": "string",
        "section": "flow_urls",
        "is_sensitive": True,
        "is_editable": True,
    },

    # ── RFP Team ──────────────────────────────────────────────────────────────
    {
        "key": "RFP_TEAM_TABLE",
        "label": "RFP Team Assignment Table",
        "description": "List of product-to-person assignments shown in RFP emails. JSON array of {product, name}.",
        "value": _jl(cfg.RFP_TEAM_TABLE),
        "data_type": "json_table",
        "section": "rfp_team",
        "is_sensitive": False,
        "is_editable": True,
    },
]


def _get_existing_keys() -> set:
    """Fetch all existing setting keys from Dataverse."""
    try:
        rows = DATAVERSE.get_all_rows(
            table_api_name=SETTINGS_TABLE_API,
            select_columns=["cr673_key"],
            table_logical_name=SETTINGS_TABLE_LOGICAL,
            use_display_names=False,
        )
        return {r.get("cr673_key") for r in rows if r.get("cr673_key")}
    except Exception as e:
        logger.warning(f"Could not fetch existing keys (table may be new): {e}")
        return set()


def seed_data():
    """Insert all settings rows that don't already exist."""
    logger.info("Seeding settings data …")

    existing_keys = _get_existing_keys()
    logger.info(f"Found {len(existing_keys)} existing settings in Dataverse.")

    inserted = 0
    skipped = 0
    failed = 0

    for item in SETTINGS_SEED:
        key = item["key"]
        if key in existing_keys:
            logger.info(f"  SKIP  {key} (already exists)")
            skipped += 1
            continue

        row = {
            "cr673_key": key,
            "cr673_value": item["value"],
            "cr673_data_type": item["data_type"],
            "cr673_section": item["section"],
            "cr673_label": item["label"],
            "cr673_description": item["description"],
            "cr673_is_sensitive": item["is_sensitive"],
            "cr673_is_editable": item["is_editable"],
        }

        try:
            ok = DATAVERSE.insert_row(
                table_api_name=SETTINGS_TABLE_API,
                data=row,
                table_logical_name=SETTINGS_TABLE_LOGICAL,
                use_display_names=False,
            )
            if ok:
                logger.info(f"  INSERT {key}")
                inserted += 1
            else:
                logger.error(f"  FAIL   {key} (insert returned False)")
                failed += 1
        except Exception as e:
            logger.error(f"  FAIL   {key}: {e}")
            failed += 1

    logger.info(
        f"\nSeed complete: {inserted} inserted, {skipped} skipped, {failed} failed."
    )


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    logger.info("=" * 60)
    logger.info("  cr673_bahra_system_settings — Create Table & Seed Data")
    logger.info("=" * 60)

    # Step 1: Create the table
    logger.info("\n[Step 1/4] Creating table …")
    if not create_table():
        logger.error("Table creation failed. Attempting columns & seed anyway …")

    # Brief pause to let Dataverse propagate the entity
    time.sleep(5)

    # Step 2: Add custom columns
    logger.info("\n[Step 2/4] Creating columns …")
    create_columns()

    # Step 3: Publish entity so OData recognises the new columns
    logger.info("\n[Step 3/4] Publishing entity customizations …")
    publish_entity()

    # Wait for all columns to become available in the OData layer
    _wait_for_columns([
        "cr673_value", "cr673_data_type", "cr673_section",
        "cr673_label", "cr673_description",
        "cr673_is_sensitive", "cr673_is_editable",
    ])

    # Step 4: Seed data
    logger.info("\n[Step 4/4] Seeding data …")
    seed_data()

    logger.info("\nDone.")


if __name__ == "__main__":
    main()
