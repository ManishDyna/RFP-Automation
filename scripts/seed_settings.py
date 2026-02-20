"""
One-time seed script: populates the cr673_bahra_system_settings Dataverse table
with all configuration values from config/config.py.

Run once from the project root:
    python scripts/seed_settings.py

Existing rows (matching cr673_key) are skipped to avoid overwriting live edits.
"""

import sys
import os
import json
import logging

# Allow imports from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

from helpers.core_helper import DATAVERSE
from helpers.settings_helper import SETTINGS_TABLE_API, SETTINGS_TABLE_LOGICAL
import config.config as cfg


def _jl(v) -> str:
    """Serialize a list to JSON string."""
    return json.dumps(v, ensure_ascii=False)


# ──────────────────────────────────────────────────────────────────────────────
# Full definition of every setting to seed
# Fields: key, label, description, value (as string), data_type, section,
#         is_sensitive, is_editable
# ──────────────────────────────────────────────────────────────────────────────
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
        logger.warning(f"Could not fetch existing keys: {e}")
        return set()


def seed():
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


if __name__ == "__main__":
    seed()
