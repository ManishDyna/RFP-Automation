"""
Setup script to create the 4 RBAC Dataverse tables via the Web API.

Tables created:
  1. cr673_bahra_roles          - Dynamic roles
  2. cr673_bahra_role_permissions - Role-permission mappings
  3. cr673_bahra_audit_logs     - Audit trail
  4. cr673_bahra_user_status    - User lifecycle tracking

Usage:
  python setup_rbac_tables.py

Run this once before starting the application. Safe to re-run (skips existing tables).
"""

import sys
import json
import time
import requests
from helpers.dataverse_helper import DataverseClient
from config.config import TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_label(text: str) -> dict:
    """Create a Dataverse LocalizedLabel structure."""
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


def string_column(schema_name: str, display: str, max_length: int = 200) -> dict:
    """Define a String attribute for entity creation."""
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.StringAttributeMetadata",
        "AttributeType": "String",
        "AttributeTypeName": {"Value": "StringType"},
        "SchemaName": schema_name,
        "DisplayName": make_label(display),
        "MaxLength": max_length,
        "RequiredLevel": {"Value": "None", "CanBeChanged": True},
        "FormatName": {"Value": "Text"},
    }


def memo_column(schema_name: str, display: str, max_length: int = 4000) -> dict:
    """Define a Memo (multiline text) attribute for large text fields."""
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.MemoAttributeMetadata",
        "AttributeType": "Memo",
        "AttributeTypeName": {"Value": "MemoType"},
        "SchemaName": schema_name,
        "DisplayName": make_label(display),
        "MaxLength": max_length,
        "RequiredLevel": {"Value": "None", "CanBeChanged": True},
        "Format": "TextArea",
    }


def primary_name_column(schema_name: str, display: str, max_length: int = 200) -> dict:
    """Define the primary name attribute (included in entity creation body)."""
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.StringAttributeMetadata",
        "AttributeType": "String",
        "AttributeTypeName": {"Value": "StringType"},
        "SchemaName": schema_name,
        "DisplayName": make_label(display),
        "Description": make_label("Primary name field"),
        "MaxLength": max_length,
        "RequiredLevel": {"Value": "ApplicationRequired", "CanBeChanged": True},
        "FormatName": {"Value": "Text"},
        "IsPrimaryName": True,
    }


# ---------------------------------------------------------------------------
# Table definitions
# ---------------------------------------------------------------------------

TABLE_DEFINITIONS = [
    {
        "schema_name": "cr673_bahra_roles",
        "display_name": "Bahra Roles",
        "display_name_plural": "Bahra Roles",
        "description": "Dynamic RBAC roles for the RFP Portal",
        "primary_attribute": primary_name_column("cr673_name", "name"),
        "extra_columns": [
            string_column("cr673_description", "description", 500),
            string_column("cr673_is_system", "is_system", 10),
            string_column("cr673_is_active", "is_active", 10),
            string_column("cr673_created_date", "created_date", 100),
            string_column("cr673_update_date", "update_date", 100),
        ],
    },
    {
        "schema_name": "cr673_bahra_role_permissions",
        "display_name": "Bahra Role Permissions",
        "display_name_plural": "Bahra Role Permissions",
        "description": "Maps roles to granular permission keys",
        "primary_attribute": primary_name_column("cr673_name", "name"),
        "extra_columns": [
            string_column("cr673_role_id", "role_id", 100),
            string_column("cr673_role_name", "role_name", 200),
            string_column("cr673_permission_key", "permission_key", 200),
            string_column("cr673_created_date", "created_date", 100),
        ],
    },
    {
        "schema_name": "cr673_bahra_audit_logs",
        "display_name": "Bahra Audit Logs",
        "display_name_plural": "Bahra Audit Logs",
        "description": "Audit trail for authentication, user management, and system events",
        "primary_attribute": primary_name_column("cr673_name", "name"),
        "extra_columns": [
            string_column("cr673_action", "action", 100),
            string_column("cr673_category", "category", 50),
            string_column("cr673_actor_email", "actor_email", 200),
            string_column("cr673_actor_name", "actor_name", 200),
            string_column("cr673_target_type", "target_type", 100),
            string_column("cr673_target_id", "target_id", 200),
            memo_column("cr673_details", "details", 4000),
            string_column("cr673_ip_address", "ip_address", 100),
            string_column("cr673_created_date", "created_date", 100),
        ],
    },
    {
        "schema_name": "cr673_bahra_user_status",
        "display_name": "Bahra User Status",
        "display_name_plural": "Bahra User Statuses",
        "description": "User lifecycle tracking: activation, lockout, password expiry",
        "primary_attribute": primary_name_column("cr673_name", "name"),
        "extra_columns": [
            string_column("cr673_user_id", "user_id", 100),
            string_column("cr673_is_active", "is_active", 10),
            string_column("cr673_failed_attempts", "failed_attempts", 10),
            string_column("cr673_locked_until", "locked_until", 100),
            string_column("cr673_last_login", "last_login", 100),
            string_column("cr673_password_changed_at", "password_changed_at", 100),
            string_column("cr673_deactivated_by", "deactivated_by", 200),
            string_column("cr673_deactivated_at", "deactivated_at", 100),
            string_column("cr673_created_date", "created_date", 100),
            string_column("cr673_update_date", "update_date", 100),
        ],
    },
]


# ---------------------------------------------------------------------------
# Table check & creation
# ---------------------------------------------------------------------------

def table_exists(client: DataverseClient, logical_name: str) -> bool:
    """Check if a Dataverse entity already exists."""
    url = f"{client.api_url}EntityDefinitions(LogicalName='{logical_name}')?$select=LogicalName"
    resp = requests.get(url, headers=client._headers())
    return resp.status_code == 200


def create_table(client: DataverseClient, table_def: dict) -> bool:
    """Create a Dataverse custom entity with its columns."""
    schema = table_def["schema_name"]

    # Check if already exists - if so, skip creation but still add missing columns
    already_existed = table_exists(client, schema)
    if already_existed:
        print(f"  [SKIP] Table '{schema}' already exists, checking columns...")

    if not already_existed:
        # Build entity metadata payload
        payload = {
            "@odata.type": "Microsoft.Dynamics.CRM.EntityMetadata",
            "SchemaName": schema,
            "DisplayName": make_label(table_def["display_name"]),
            "DisplayCollectionName": make_label(table_def["display_name_plural"]),
            "Description": make_label(table_def["description"]),
            "OwnershipType": "UserOwned",
            "IsActivity": False,
            "HasActivities": False,
            "HasNotes": False,
            "Attributes": [table_def["primary_attribute"]],
        }

        url = f"{client.api_url}EntityDefinitions"
        resp = requests.post(url, json=payload, headers=client._headers())

        if resp.status_code in (200, 201, 204):
            print(f"  [OK]   Table '{schema}' created.")
        elif resp.status_code == 409:
            print(f"  [SKIP] Table '{schema}' already exists (409).")
            already_existed = True
        else:
            print(f"  [FAIL] Table '{schema}' - HTTP {resp.status_code}")
            try:
                err = resp.json()
                print(f"         {json.dumps(err.get('error', {}).get('message', err), indent=2)[:500]}")
            except Exception:
                print(f"         {resp.text[:500]}")
            return False

    # Wait for Dataverse to propagate the new entity before adding columns
    if not already_existed:
        print(f"  [WAIT] Waiting for entity propagation...")
        time.sleep(10)

    # Add extra columns one by one
    entity_id = None
    # Fetch the entity ID - retry a few times
    for attempt in range(5):
        meta_resp = requests.get(
            f"{client.api_url}EntityDefinitions(LogicalName='{schema}')?$select=MetadataId",
            headers=client._headers(),
        )
        if meta_resp.status_code == 200:
            entity_id = meta_resp.json().get("MetadataId")
            if entity_id:
                break
        print(f"  [WAIT] MetadataId not ready yet, retrying ({attempt + 1}/5)...")
        time.sleep(5)

    if not entity_id:
        print(f"  [WARN] Could not get MetadataId for '{schema}', skipping extra columns.")
        return True

    for col_def in table_def.get("extra_columns", []):
        col_name = col_def.get("SchemaName", "?")
        col_url = f"{client.api_url}EntityDefinitions({entity_id})/Attributes"

        # Retry column creation up to 3 times with delay
        for retry in range(3):
            col_resp = requests.post(col_url, json=col_def, headers=client._headers())
            if col_resp.status_code in (200, 201, 204):
                print(f"         + Column '{col_name}' added.")
                break
            elif col_resp.status_code == 409:
                print(f"         ~ Column '{col_name}' already exists.")
                break
            elif col_resp.status_code == 400:
                # Dataverse returns 400 for "already exists" instead of 409
                err_msg = ""
                try:
                    err_msg = col_resp.json().get("error", {}).get("message", "")
                except Exception:
                    pass
                if "already exists" in err_msg.lower():
                    print(f"         ~ Column '{col_name}' already exists.")
                    break
            elif col_resp.status_code == 404 and retry < 2:
                print(f"         ? Column '{col_name}' got 404, retrying in 5s...")
                time.sleep(5)
                # Re-fetch entity ID in case it changed
                meta_resp2 = requests.get(
                    f"{client.api_url}EntityDefinitions(LogicalName='{schema}')?$select=MetadataId",
                    headers=client._headers(),
                )
                if meta_resp2.status_code == 200:
                    new_id = meta_resp2.json().get("MetadataId")
                    if new_id:
                        entity_id = new_id
                        col_url = f"{client.api_url}EntityDefinitions({entity_id})/Attributes"
            else:
                print(f"         ! Column '{col_name}' FAILED (HTTP {col_resp.status_code})")
                try:
                    err = col_resp.json()
                    print(f"           {err.get('error', {}).get('message', '')[:300]}")
                except Exception:
                    print(f"           {col_resp.text[:300]}")
                break

    # Publish the entity so columns become usable
    publish_url = f"{client.api_url}PublishXml"
    publish_payload = {
        "ParameterXml": f"<importexportxml><entities><entity>{schema}</entity></entities></importexportxml>"
    }
    pub_resp = requests.post(publish_url, json=publish_payload, headers=client._headers())
    if pub_resp.status_code in (200, 204):
        print(f"  [OK]   Published '{schema}'.")
    else:
        print(f"  [WARN] Publish for '{schema}' returned HTTP {pub_resp.status_code}")

    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("  RBAC Dataverse Table Setup")
    print("=" * 60)
    print(f"\nDataverse: {RESOURCE_URL}\n")

    # Initialize client (handles auth automatically)
    client = DataverseClient(
        tenant_id=TENANT_ID,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        resource_url=RESOURCE_URL,
    )
    print("[AUTH] Token acquired successfully.\n")

    success_count = 0
    for table_def in TABLE_DEFINITIONS:
        print(f"--- {table_def['display_name']} ({table_def['schema_name']}) ---")
        if create_table(client, table_def):
            success_count += 1
        print()

    print("=" * 60)
    print(f"  Result: {success_count}/{len(TABLE_DEFINITIONS)} tables ready.")
    print("=" * 60)

    if success_count == len(TABLE_DEFINITIONS):
        print("\nAll tables are ready!")
        print("Next steps:")
        print("  1. Start the server:  python dashboard_main.py")
        print("  2. Login as Admin")
        print("  3. Seed default roles: POST /api/roles/seed")
        print("     (or use the Roles page in the admin UI)")
    else:
        print("\nSome tables failed. Check errors above and retry.")
        sys.exit(1)


if __name__ == "__main__":
    main()
