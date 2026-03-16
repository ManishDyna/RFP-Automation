"""
Seed System Settings - Populates the cr673_bahra_system_settings Dataverse table
from current config.py values. Idempotent: skips existing keys.

Usage:
    python seed_system_settings.py
    python seed_system_settings.py --update   # Update sections, sub_sections, descriptions
"""

import json
import sys
import os

# Add project root to path so imports work from Support-Files/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from helpers.dataverse_helper import DataverseClient
from config.config import (
    TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL,
    SYSTEM_SETTINGS_TABLE_API, SYSTEM_SETTINGS_TABLE_LOGICAL,
)
import config.config as config

# ─────────────────────────────────────────────────────
# Seed Data: one dict per config key
# Only Admin-facing settings remain in Dataverse/portal.
# Developer settings are managed via config/config.py only.
# All email values use _PROD_* directly — independent of EMAIL_MODE.
# ─────────────────────────────────────────────────────
SEED_DATA = [
    # ═══════════════════════════════════════════════════
    # SECTION: Admin  ►  Email Configurations
    # Only email recipient settings are managed via portal.
    # All other settings (URL, credentials, etc.) are in config/config.py.
    # ═══════════════════════════════════════════════════

    {"key": "EMAIL_TO_NEW_RFP", "value": "loai.albar@bahra-cables.com;theeb.alsamrah@bahra-cables.com;faiq.natto@bahra-cables.com;hossam.ahmed@bahra-cables.com;renad.jastaniah@bahra-cables.com;sec.tenderteam@bahra-cables.com;abdullah.rawah@bahra-cables.com;Manish.soni@dynatechconsultancy.com",
     "label": "Email: New RFP Found", "section": "Admin", "sub_section": "Email", "data_type": "email",
     "description": "Recipient when a NEW RFP is found on the portal. Used by: RFP download automation. Sent once per new RFP with the RFP file attached and matched materials.",
     "is_editable": True, "is_sensitive": False},

    {"key": "EMAIL_TO_NO_NEW_RFP", "value": "abdullah.rawah@bahra-cables.com;Manish.soni@dynatechconsultancy.com",
     "label": "Email: No New RFP", "section": "Admin", "sub_section": "Email", "data_type": "email",
     "description": "Recipient when automation runs but finds NO new RFP on the portal. Used by: RFP download automation. Sent as a status update so admins know the bot ran successfully.",
     "is_editable": True, "is_sensitive": False},

    {"key": "EMAIL_TO_RFP_DECLINED", "value": "abdullah.rawah@bahra-cables.com",
     "label": "Email: RFP Declined", "section": "Admin", "sub_section": "Email", "data_type": "email",
     "description": "Recipient when an RFP is declined via the portal. Used by: RFP decline automation. Confirms the decline action was completed.",
     "is_editable": True, "is_sensitive": False},

    {"key": "EMAIL_TO_RFP_ERROR_IN_SUBMISSION", "value": "Manish.soni@dynatechconsultancy.com",
     "label": "Email: Submission Error", "section": "Admin", "sub_section": "Email", "data_type": "email",
     "description": "Recipient when an RFP submission fails with an error. Used by: RFP submit automation. Contains error details so the team can investigate and retry.",
     "is_editable": True, "is_sensitive": False},

    {"key": "EMAIL_TO_RFP_ERROR_IN_DECLINE", "value": "Manish.soni@dynatechconsultancy.com",
     "label": "Email: Decline Error", "section": "Admin", "sub_section": "Email", "data_type": "email",
     "description": "Recipient when an RFP decline fails with an error. Used by: RFP decline automation. Contains error details for investigation.",
     "is_editable": True, "is_sensitive": False},

    {"key": "EMAIL_TO_AUTOMATION_FAILURE", "value": "Manish.soni@dynatechconsultancy.com",
     "label": "Email: Automation Failure", "section": "Admin", "sub_section": "Email", "data_type": "email",
     "description": "Recipient when the automation bot crashes or encounters a critical failure. Used by: automation error handler. This is the most important alert email -- ensure it reaches someone who can respond quickly.",
     "is_editable": True, "is_sensitive": False},

    {"key": "EMAIL_TO_RFP_SUBMITTED", "value": "abdullah.rawah@bahra-cables.com",
     "label": "Email: RFP Submitted", "section": "Admin", "sub_section": "Email", "data_type": "email",
     "description": "Recipient when an RFP is successfully submitted on the portal. Used by: RFP submit automation. Confirms the submission was completed.",
     "is_editable": True, "is_sensitive": False},

    {"key": "EMAIL_TO_RFP_SAVED_DRAFT", "value": "arawah@bahra-cables.com",
     "label": "Email: RFP Saved Draft", "section": "Admin", "sub_section": "Email", "data_type": "email",
     "description": "Recipient when an RFP is saved as draft on the portal. Used by: RFP draft automation. Notifies the team that a draft is ready for review.",
     "is_editable": True, "is_sensitive": False},

    {"key": "EMAIL_TO_RFP_REMINDER", "value": "abdullah.rawah@bahra-cables.com",
     "label": "Email: RFP Reminder", "section": "Admin", "sub_section": "Email", "data_type": "email",
     "description": "Recipient for RFP deadline reminder notifications. Used by: RFP reminder scheduler. Sent before RFP deadlines to prompt action.",
     "is_editable": True, "is_sensitive": False},

    {"key": "EMAIL_TO_NEW_RFP_WITH_MATCH", "value": "loai.albar@bahra-cables.com;theeb.alsamrah@bahra-cables.com;faiq.natto@bahra-cables.com;hossam.ahmed@bahra-cables.com;renad.jastaniah@bahra-cables.com;sec.tenderteam@bahra-cables.com;abdullah.rawah@bahra-cables.com",
     "label": "Email: New RFP With Match", "section": "Admin", "sub_section": "Email", "data_type": "email",
     "description": "Recipient when a new RFP is found AND has material matches in master data. Used by: RFP download automation with material matching. Contains the matched materials summary.",
     "is_editable": True, "is_sensitive": False},

    {"key": "EMAIL_TO_NO_MATCHED_DATA", "value": "loai.albar@bahra-cables.com;theeb.alsamrah@bahra-cables.com;faiq.natto@bahra-cables.com;hossam.ahmed@bahra-cables.com;renad.jastaniah@bahra-cables.com;sec.tenderteam@bahra-cables.com;abdullah.rawah@bahra-cables.com",
     "label": "Email: No Matched Data", "section": "Admin", "sub_section": "Email", "data_type": "email",
     "description": "Recipient when material matching runs but finds no matches in master data. Used by: material matching service. Alerts the team to review material master data.",
     "is_editable": True, "is_sensitive": False},

    {"key": "EMAIL_TO_NEW_RFP_NO_MATCH", "value": "loai.albar@bahra-cables.com;theeb.alsamrah@bahra-cables.com;faiq.natto@bahra-cables.com;hossam.ahmed@bahra-cables.com;renad.jastaniah@bahra-cables.com;sec.tenderteam@bahra-cables.com;abdullah.rawah@bahra-cables.com",
     "label": "Email: New RFP No Match", "section": "Admin", "sub_section": "Email", "data_type": "email",
     "description": "Recipient when a new RFP is found but has NO material matches. Used by: RFP download automation. Alerts the team that manual material review is needed.",
     "is_editable": True, "is_sensitive": False},

    {"key": "DECLINE_BUTTON_EMAILS", "value": json.dumps(config.DECLINE_BUTTON_EMAILS),
     "label": "Decline Button Emails", "section": "Admin", "sub_section": "Email", "data_type": "json",
     "description": "Email addresses authorized to see the 'Decline RFP' button in consolidated response emails. Used by: actionable card email builder. Only these users will see the decline option. Must be a valid JSON array of email strings.",
     "is_editable": True, "is_sensitive": False},
]

# Keys removed from Dataverse (managed via config/config.py only).
# Running --update will delete these from Dataverse.
REMOVED_KEYS = [
    # ── Previously removed keys ──
    "LOGS_FETCH_TOP_MAX", "LOGS_FETCH_AHEAD_FACTOR",
    "DEFAULT_PAGE_SIZE", "MIN_PAGE_SIZE", "MAX_PAGE_SIZE",
    "DASHBOARD_HTTP_MAX_AGE",
    "SESSION_WARNING_SECONDS", "SESSION_REFRESH_INTERVAL", "IDLE_TIMEOUT_SECONDS",
    "TDS_FILE_PATH", "SP_BASE_FOLDER_RFP_UPLOAD_FILES", "RFP_TEAM_TABLE",

    # ── Moved to config.py only (Admin > General) ──
    "URL", "COMPANY_NAME", "COMPANY_OPTIONS", "VALID_RFP_STATUSES",
    "DASHBOARD_TTL_SECONDS", "LOGS_TTL_SECONDS", "SAP_LOGS_TTL_SECONDS",

    # ── Moved to config.py only (Admin > Email) ──
    "EMAIL_MODE", "DEV_EMAIL",

    # ── Moved to config.py only (Admin > Security & Access) ──
    "SESSION_TIMEOUT_SECONDS", "RBAC_CACHE_TTL_SECONDS",
    "ACCOUNT_LOCKOUT_THRESHOLD", "ACCOUNT_LOCKOUT_DURATION_MINUTES",
    "PASSWORD_MIN_LENGTH", "PASSWORD_REQUIRE_UPPERCASE",
    "PASSWORD_REQUIRE_NUMBER", "PASSWORD_MAX_AGE_DAYS",

    # ── Moved to config.py only (Developer > Azure & Auth) ──
    "TENANT_ID", "CLIENT_ID", "CLIENT_SECRET", "RESOURCE_URL",
    "FORGOT_PASSWORD_FLOW_URL",

    # ── Moved to config.py only (Developer > Automation) ──
    "FLOW_URL", "ACTIONABLE_CARD_ORIGINATOR_ID", "ACTIONABLE_CARD_CALLBACK_URL",

    # ── Moved to config.py only (Developer > SharePoint) ──
    "SHAREPOINT_HOSTNAME", "SITE_PATH", "DRIVE_NAME", "SP_BASE_FOLDER",

    # ── Moved to config.py only (Developer > File Paths) ──
    "OUTPUT_DIR", "FAILURE_LOGS_DIR", "SP_FAILURE_LOGS_FOLDER",

    # ── Moved to config.py only (Developer > Dataverse Tables) ──
    "AUTOMATION_LOG_TABLE_LOGICAL", "AUTOMATION_LOG_TABLE_API",
    "RFP_ACTIVITY_LOG_TABLE_LOGICAL", "RFP_ACTIVITY_LOG_TABLE_API",
    "USERS_TABLE_LOGICAL", "USERS_TABLE_API",
    "SAP_PASSWORD_TABLE_LOGICAL", "SAP_PASSWORD_TABLE_API",
    "AUTOMATION_SCHEDULE_TABLE_LOGICAL", "AUTOMATION_SCHEDULE_TABLE_API",
    "RFP_STATUS_TABLE_LOGICAL", "RFP_STATUS_TABLE_API",
    "ROLES_TABLE_LOGICAL", "ROLES_TABLE_API",
    "ROLE_PERMISSIONS_TABLE_LOGICAL", "ROLE_PERMISSIONS_TABLE_API",
    "AUDIT_LOG_TABLE_LOGICAL", "AUDIT_LOG_TABLE_API",
    "USER_STATUS_TABLE_LOGICAL", "USER_STATUS_TABLE_API",
    "SYSTEM_SETTINGS_TABLE_LOGICAL", "SYSTEM_SETTINGS_TABLE_API",
    "MATERIAL_MASTER_TABLE_LOGICAL", "MATERIAL_MASTER_TABLE_API",
    "KEYWORDS_TABLE_LOGICAL", "KEYWORDS_TABLE_API",
    "RFP_TEAM_DV_TABLE_LOGICAL", "RFP_TEAM_DV_TABLE_API",
    "RFP_TEAM_COLUMNS_TABLE_LOGICAL", "RFP_TEAM_COLUMNS_TABLE_API",
    "RFP_RESPONSE_TABLE_LOGICAL", "RFP_RESPONSE_TABLE_API",

    # ── Incorrectly seeded with _PROD_/_DEV_ prefixed keys — delete these junk rows ──
    "_PROD_EMAIL_TO_NEW_RFP", "_PROD_EMAIL_TO_NO_NEW_RFP",
    "_PROD_EMAIL_TO_RFP_DECLINED", "_PROD_EMAIL_TO_RFP_ERROR_IN_SUBMISSION",
    "_PROD_EMAIL_TO_RFP_ERROR_IN_DECLINE", "_PROD_EMAIL_TO_AUTOMATION_FAILURE",
    "_PROD_EMAIL_TO_RFP_SUBMITTED", "_PROD_EMAIL_TO_RFP_SAVED_DRAFT",
    "_PROD_EMAIL_TO_RFP_REMINDER", "_PROD_EMAIL_TO_NEW_RFP_WITH_MATCH",
    "_PROD_EMAIL_TO_NO_MATCHED_DATA", "_PROD_EMAIL_TO_NEW_RFP_NO_MATCH",
    "_PROD_RFP_TEAM_TABLE", "_DEV_RFP_TEAM_TABLE",
]


def seed_settings():
    """Seed system settings from SEED_DATA into Dataverse. Idempotent."""
    print("=" * 60)
    print("Seeding System Settings to Dataverse")
    print("=" * 60)

    client = DataverseClient(TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL)

    existing_rows = client.get_all_rows(
        SYSTEM_SETTINGS_TABLE_API,
        table_logical_name=SYSTEM_SETTINGS_TABLE_LOGICAL,
        use_display_names=True,
    )
    existing_keys = {row.get("Key", row.get("cr673_key", "")) for row in existing_rows}
    print(f"Found {len(existing_keys)} existing settings in Dataverse\n")

    created = 0
    skipped = 0

    for item in SEED_DATA:
        key = item["key"]
        if key in existing_keys:
            print(f"  [SKIP] {key} (already exists)")
            skipped += 1
            continue

        row_data = {
            "Key": key,
            "Value": str(item["value"]),
            "Label": item["label"],
            "Section": item["section"],
            "Sub Section": item.get("sub_section", ""),
            "Data Type": item["data_type"],
            "Description": item.get("description", ""),
            "Is Editable": True if item.get("is_editable", True) else False,
            "Is Sensitive": True if item.get("is_sensitive", False) else False,
        }

        try:
            client.insert_row(
                SYSTEM_SETTINGS_TABLE_API,
                row_data,
                table_logical_name=SYSTEM_SETTINGS_TABLE_LOGICAL,
                use_display_names=True,
            )
            print(f"  [CREATE] {key}")
            created += 1
        except Exception as e:
            print(f"  [ERROR] {key}: {e}")

    print(f"\nDone! Created: {created}, Skipped: {skipped}, Total: {len(SEED_DATA)}")


def update_existing_rows():
    """Update section, sub_section, and description for existing rows. Delete removed keys."""
    print("=" * 60)
    print("Updating existing settings (sections + sub_sections + descriptions)")
    print("=" * 60)

    client = DataverseClient(TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL)

    seed_lookup = {item["key"]: item for item in SEED_DATA}

    existing_rows = client.get_all_rows(
        SYSTEM_SETTINGS_TABLE_API,
        table_logical_name=SYSTEM_SETTINGS_TABLE_LOGICAL,
        use_display_names=True,
    )

    updated = 0
    deleted = 0

    for row in existing_rows:
        key = row.get("Key", row.get("cr673_key", ""))
        record_id = row.get("Bahra System Settings", row.get("cr673_bahra_system_settingsid", ""))
        if not key or not record_id:
            continue

        # Delete removed keys
        if key in REMOVED_KEYS:
            try:
                client.delete_row(SYSTEM_SETTINGS_TABLE_API, record_id)
                print(f"  [DELETE] {key}")
                deleted += 1
            except Exception as e:
                print(f"  [ERROR deleting] {key}: {e}")
            continue

        # Update section/sub_section/description if changed
        if key in seed_lookup:
            seed = seed_lookup[key]
            current_section = row.get("Section", row.get("cr673_section", ""))
            current_sub = row.get("Sub Section", row.get("cr6db_sub_section", ""))
            current_desc = row.get("Description", row.get("cr673_description", ""))

            new_section = seed["section"]
            new_sub = seed.get("sub_section", "")
            new_desc = seed.get("description", "")

            # Build update payload only for changed fields
            updates = {}
            if current_section != new_section:
                updates["Section"] = new_section
            if current_sub != new_sub:
                updates["Sub Section"] = new_sub
            if current_desc != new_desc:
                updates["Description"] = new_desc

            if updates:
                try:
                    client.update_row(
                        SYSTEM_SETTINGS_TABLE_API,
                        record_id,
                        updates,
                        table_logical_name=SYSTEM_SETTINGS_TABLE_LOGICAL,
                        use_display_names=True,
                    )
                    changed = ", ".join(updates.keys())
                    print(f"  [UPDATE] {key}: {changed}")
                    updated += 1
                except Exception as e:
                    print(f"  [ERROR updating] {key}: {e}")

    print(f"\nDone! Updated: {updated}, Deleted: {deleted}")


def update_values():
    """Overwrite email Value fields in Dataverse with production values from SEED_DATA."""
    print("=" * 60)
    print("Updating email setting values to production recipients")
    print("=" * 60)

    client = DataverseClient(TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL)

    # Fetch rows WITHOUT display name translation to get raw logical column names
    existing_rows = client.get_all_rows(
        SYSTEM_SETTINGS_TABLE_API,
        table_logical_name=SYSTEM_SETTINGS_TABLE_LOGICAL,
        use_display_names=False,
    )

    # Print first row keys so we can see the actual column names
    if existing_rows:
        print(f"DEBUG - Raw column names from Dataverse: {list(existing_rows[0].keys())}\n")

    key_to_id = {
        row.get("cr673_key", ""): row.get("cr673_bahra_system_settingsid", "")
        for row in existing_rows
        if row.get("cr673_key", "")
    }
    print(f"Found {len(key_to_id)} existing settings in Dataverse\n")

    updated = 0
    not_found = 0

    for item in SEED_DATA:
        key = item["key"]
        new_value = item["value"]
        record_id = key_to_id.get(key)
        if not record_id:
            print(f"  [NOT FOUND] {key}")
            not_found += 1
            continue
        print(f"  [DEBUG] {key} → record_id={record_id}")
        try:
            client.update_row(
                SYSTEM_SETTINGS_TABLE_API,
                record_id,
                {"cr673_value": str(new_value)},
                table_logical_name=SYSTEM_SETTINGS_TABLE_LOGICAL,
                use_display_names=False,
            )
            print(f"  [UPDATE] {key} → {str(new_value)[:60]}")
            updated += 1
        except Exception as e:
            print(f"  [ERROR] {key}: {e}")

    print(f"\nDone! Updated: {updated}, Not found: {not_found}, Total: {len(SEED_DATA)}")


if __name__ == "__main__":
    if "--update-values" in sys.argv:
        update_values()
    elif "--update" in sys.argv:
        update_existing_rows()
    else:
        seed_settings()
        print("\nRun with --update to update sections/sub_sections/descriptions of existing rows")
        print("Run with --update-values to push production email recipients into Dataverse")
