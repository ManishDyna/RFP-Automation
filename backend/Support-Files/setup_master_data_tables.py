"""
Setup script to create the 3 Master Data Dataverse tables via the Web API.

Tables created:
  1. cr673_bahra_material_master  - Material master codes
  2. cr673_bahra_keywords         - Unique matching keywords
  3. cr673_bahra_rfp_team         - RFP team assignment members

Usage:
  python setup_master_data_tables.py

Run this once before starting the application. Safe to re-run (skips existing tables/columns).
After running, check the printed EntitySetName values and update config/config.py accordingly.
"""

import sys
import json
import time
import requests
from helpers.dataverse_helper import DataverseClient
from config.config import TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL


# ---------------------------------------------------------------------------
# Helpers  (identical to setup_rbac_tables.py)
# ---------------------------------------------------------------------------

def make_label(text: str) -> dict:
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


def memo_column(schema_name: str, display: str, max_length: int = 2000) -> dict:
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
        "schema_name": "cr673_bahra_material_master",
        "display_name": "Bahra Material Master",
        "display_name_plural": "Bahra Material Masters",
        "description": "Master material codes for RFP matching",
        "primary_attribute": primary_name_column("cr673_material_code", "material_code", 100),
        "extra_columns": [
            memo_column("cr673_description", "description", 2000),
            string_column("cr673_is_active", "is_active", 10),
            string_column("cr673_created_date", "created_date", 100),
            string_column("cr673_updated_date", "updated_date", 100),
        ],
    },
    {
        "schema_name": "cr673_bahra_keywords",
        "display_name": "Bahra Keywords",
        "display_name_plural": "Bahra Keywords",
        "description": "Unique keywords for RFP content matching",
        "primary_attribute": primary_name_column("cr673_keyword", "keyword", 500),
        "extra_columns": [
            string_column("cr673_is_active", "is_active", 10),
            string_column("cr673_created_date", "created_date", 100),
            string_column("cr673_updated_date", "updated_date", 100),
        ],
    },
    {
        "schema_name": "cr673_bahra_rfp_team",
        "display_name": "Bahra RFP Team",
        "display_name_plural": "Bahra RFP Team Members",
        "description": "RFP team assignment members for product-based email routing",
        "primary_attribute": primary_name_column("cr673_product", "product", 200),
        "extra_columns": [
            string_column("cr673_name", "name", 200),
            string_column("cr673_email", "email", 300),
            string_column("cr673_is_active", "is_active", 10),
            string_column("cr673_created_date", "created_date", 100),
            string_column("cr673_updated_date", "updated_date", 100),
        ],
    },
]


# ---------------------------------------------------------------------------
# Table check & creation  (identical logic to setup_rbac_tables.py)
# ---------------------------------------------------------------------------

def table_exists(client: DataverseClient, logical_name: str) -> bool:
    url = f"{client.api_url}EntityDefinitions(LogicalName='{logical_name}')?$select=LogicalName"
    resp = requests.get(url, headers=client._headers())
    return resp.status_code == 200


def get_entity_set_name(client: DataverseClient, logical_name: str) -> str:
    """Query Dataverse for the actual EntitySetName (pluralized API path)."""
    url = f"{client.api_url}EntityDefinitions(LogicalName='{logical_name}')?$select=EntitySetName"
    resp = requests.get(url, headers=client._headers())
    if resp.status_code == 200:
        return resp.json().get("EntitySetName", "")
    return ""


def create_table(client: DataverseClient, table_def: dict) -> bool:
    schema = table_def["schema_name"]

    already_existed = table_exists(client, schema)
    if already_existed:
        print(f"  [SKIP] Table '{schema}' already exists, checking columns...")

    if not already_existed:
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

    if not already_existed:
        print(f"  [WAIT] Waiting for entity propagation...")
        time.sleep(10)

    # Fetch MetadataId
    entity_id = None
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

        for retry in range(3):
            col_resp = requests.post(col_url, json=col_def, headers=client._headers())
            if col_resp.status_code in (200, 201, 204):
                print(f"         + Column '{col_name}' added.")
                break
            elif col_resp.status_code == 409:
                print(f"         ~ Column '{col_name}' already exists.")
                break
            elif col_resp.status_code == 400:
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

    # Publish
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
    print("  Master Data Dataverse Table Setup")
    print("=" * 60)
    print(f"\nDataverse: {RESOURCE_URL}\n")

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

    # Print EntitySetName for each table so config.py can be updated
    print("=" * 60)
    print("  Confirmed API names (update config/config.py if different):")
    print("=" * 60)
    for table_def in TABLE_DEFINITIONS:
        schema = table_def["schema_name"]
        api_name = get_entity_set_name(client, schema)
        print(f"  {schema}")
        print(f"    EntitySetName (API path): {api_name or '(could not fetch)'}")
    print()

    print("=" * 60)
    print(f"  Result: {success_count}/{len(TABLE_DEFINITIONS)} tables ready.")
    print("=" * 60)

    if success_count == len(TABLE_DEFINITIONS):
        print("\nAll tables are ready!")

        # Seed RFP Team table from static config
        try:
            from services.master_data_service import bulk_import_rfp_team
            from config.config import _PROD_RFP_TEAM_TABLE
            print("\nSeeding RFP Team from static config...")
            result = bulk_import_rfp_team(_PROD_RFP_TEAM_TABLE)
            print(f"  Created: {result['created']}, Skipped: {result['skipped']}, Failed: {result['failed']}")
        except Exception as e:
            print(f"\n[WARN] Could not seed RFP Team: {e}")

        print("\nNext steps:")
        print("  1. Update MATERIAL_MASTER_TABLE_API, KEYWORDS_TABLE_API, and RFP_TEAM_TABLE_API")
        print("     in config/config.py using the EntitySetName values printed above.")
        print("  2. Start the server:  python dashboard_main.py")
        print("  3. Navigate to /admin/master-data in the portal.")
    else:
        print("\nSome tables failed. Check errors above and retry.")
        sys.exit(1)


if __name__ == "__main__":
    main()
