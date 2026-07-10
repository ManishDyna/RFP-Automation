"""
Setup script to create the RFP Team Column Definitions table in Dataverse
and add extra_data / response_data columns to existing tables.

Tables created:
  1. cr673_bahra_rfp_team_columns - Column definitions for dynamic RFP team table

Tables modified:
  2. cr673_bahra_rfp_team         - adds 'extra_data' Memo column
  3. cr6db_cr673_bahra_rfp_response - adds 'response_data' Memo column

Usage:
  python setup_dynamic_columns_table.py

Safe to re-run (skips existing tables/columns).
After running, check printed EntitySetName and update config/config.py.
"""

import sys
import json
import time
import requests
from helpers.dataverse_helper import DataverseClient
from config.config import (
    TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL,
    RFP_TEAM_DV_TABLE_LOGICAL,
    RFP_RESPONSE_TABLE_LOGICAL,
)


# ---------------------------------------------------------------------------
# Helpers  (identical to setup_master_data_tables.py)
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


def memo_column(schema_name: str, display: str, max_length: int = 4000) -> dict:
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
# New table definition: RFP Team Column Definitions
# ---------------------------------------------------------------------------

COLUMN_DEF_TABLE = {
    "schema_name": "cr673_bahra_rfp_team_columns",
    "display_name": "Bahra RFP Team Columns",
    "display_name_plural": "Bahra RFP Team Column Definitions",
    "description": "Dynamic column definitions for RFP team table, emails, and adaptive cards",
    "primary_attribute": primary_name_column("cr673_column_key", "column_key", 100),
    "extra_columns": [
        string_column("cr673_column_label", "column_label", 200),
        string_column("cr673_column_type", "column_type", 20),       # text, dropdown, yes_no
        string_column("cr673_column_category", "column_category", 20),  # display, input
        string_column("cr673_sort_order", "sort_order", 10),
        memo_column("cr673_dropdown_options", "dropdown_options", 2000),  # JSON array
        string_column("cr673_is_required", "is_required", 10),
        string_column("cr673_is_team_field", "is_team_field", 10),
        string_column("cr673_is_protected", "is_protected", 10),
        string_column("cr673_is_active", "is_active", 10),
        string_column("cr673_created_date", "created_date", 100),
        string_column("cr673_updated_date", "updated_date", 100),
    ],
}

# Columns to add to existing tables
EXTRA_COLUMNS_FOR_RFP_TEAM = [
    memo_column("cr673_extra_data", "extra_data", 4000),
]

EXTRA_COLUMNS_FOR_RFP_RESPONSE = [
    memo_column("cr673_response_data", "response_data", 4000),
]

# Default seed data matching current hardcoded columns
DEFAULT_COLUMN_DEFS = [
    {
        "column_key": "product",
        "column_label": "Products",
        "column_type": "text",
        "column_category": "display",
        "sort_order": "1",
        "dropdown_options": "",
        "is_required": "true",
        "is_team_field": "true",
        "is_protected": "false",
        "is_active": "true",
    },
    {
        "column_key": "name",
        "column_label": "Name",
        "column_type": "text",
        "column_category": "display",
        "sort_order": "2",
        "dropdown_options": "",
        "is_required": "true",
        "is_team_field": "true",
        "is_protected": "false",
        "is_active": "true",
    },
    {
        "column_key": "email",
        "column_label": "Email",
        "column_type": "text",
        "column_category": "display",
        "sort_order": "3",
        "dropdown_options": "",
        "is_required": "true",
        "is_team_field": "true",
        "is_protected": "true",
        "is_active": "true",
    },
    {
        "column_key": "results",
        "column_label": "Results",
        "column_type": "text",
        "column_category": "input",
        "sort_order": "4",
        "dropdown_options": "",
        "is_required": "false",
        "is_team_field": "false",
        "is_protected": "false",
        "is_active": "true",
    },
    {
        "column_key": "remarks",
        "column_label": "Remarks",
        "column_type": "text",
        "column_category": "input",
        "sort_order": "5",
        "dropdown_options": "",
        "is_required": "false",
        "is_team_field": "false",
        "is_protected": "false",
        "is_active": "true",
    },
]


# ---------------------------------------------------------------------------
# Table check & creation  (same logic as setup_master_data_tables.py)
# ---------------------------------------------------------------------------

def table_exists(client: DataverseClient, logical_name: str) -> bool:
    url = f"{client.api_url}EntityDefinitions(LogicalName='{logical_name}')?$select=LogicalName"
    resp = requests.get(url, headers=client._headers())
    return resp.status_code == 200


def get_entity_set_name(client: DataverseClient, logical_name: str) -> str:
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

    _add_columns(client, schema, entity_id, table_def.get("extra_columns", []))
    _publish_entity(client, schema)
    return True


def _add_columns(client: DataverseClient, schema: str, entity_id: str, columns: list):
    """Add columns to a table, handling retries and duplicates."""
    for col_def in columns:
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


def _publish_entity(client: DataverseClient, schema: str):
    """Publish a Dataverse entity to make columns usable."""
    publish_url = f"{client.api_url}PublishXml"
    publish_payload = {
        "ParameterXml": f"<importexportxml><entities><entity>{schema}</entity></entities></importexportxml>"
    }
    pub_resp = requests.post(publish_url, json=publish_payload, headers=client._headers())
    if pub_resp.status_code in (200, 204):
        print(f"  [OK]   Published '{schema}'.")
    else:
        print(f"  [WARN] Publish for '{schema}' returned HTTP {pub_resp.status_code}")


def _get_entity_id(client: DataverseClient, logical_name: str) -> str:
    """Fetch MetadataId for an existing entity."""
    for attempt in range(5):
        resp = requests.get(
            f"{client.api_url}EntityDefinitions(LogicalName='{logical_name}')?$select=MetadataId",
            headers=client._headers(),
        )
        if resp.status_code == 200:
            eid = resp.json().get("MetadataId")
            if eid:
                return eid
        print(f"  [WAIT] MetadataId for '{logical_name}' not ready ({attempt + 1}/5)...")
        time.sleep(3)
    return ""


def _seed_default_columns(client: DataverseClient, table_api: str, table_logical: str):
    """Seed the default column definitions if table is empty."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    # Check if table already has data
    try:
        existing = client.query_rows(
            table_api_name=table_api,
            filter_expr="is_active eq 'true'",
            select="column_key",
            top=1,
            table_logical_name=table_logical,
            use_display_names=True,
        )
        if existing and existing.get("value"):
            print("  [SKIP] Column definitions already seeded.")
            return
    except Exception:
        pass

    print("  [SEED] Inserting default column definitions...")
    for col_def in DEFAULT_COLUMN_DEFS:
        data = {**col_def, "created_date": now, "updated_date": now}
        try:
            ok = client.insert_row(
                table_api_name=table_api,
                data=data,
                table_logical_name=table_logical,
                use_display_names=True,
            )
            status = "OK" if ok else "FAIL"
            print(f"         {status}: {col_def['column_key']} ({col_def['column_label']})")
        except Exception as e:
            print(f"         ERROR: {col_def['column_key']}: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("  Dynamic Columns Dataverse Table Setup")
    print("=" * 60)
    print(f"\nDataverse: {RESOURCE_URL}\n")

    client = DataverseClient(
        tenant_id=TENANT_ID,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        resource_url=RESOURCE_URL,
    )
    print("[AUTH] Token acquired successfully.\n")

    # Step 1: Create the column definitions table
    print("--- Step 1: Create Column Definitions Table ---")
    if not create_table(client, COLUMN_DEF_TABLE):
        print("\n[FAIL] Could not create column definitions table. Aborting.")
        sys.exit(1)
    print()

    # Step 2: Add extra_data column to existing RFP Team table
    print("--- Step 2: Add 'extra_data' to RFP Team table ---")
    entity_id = _get_entity_id(client, RFP_TEAM_DV_TABLE_LOGICAL)
    if entity_id:
        _add_columns(client, RFP_TEAM_DV_TABLE_LOGICAL, entity_id, EXTRA_COLUMNS_FOR_RFP_TEAM)
        _publish_entity(client, RFP_TEAM_DV_TABLE_LOGICAL)
    else:
        print(f"  [WARN] Could not find RFP Team table '{RFP_TEAM_DV_TABLE_LOGICAL}'")
    print()

    # Step 3: Add response_data column to existing RFP Response table
    print("--- Step 3: Add 'response_data' to RFP Response table ---")
    entity_id = _get_entity_id(client, RFP_RESPONSE_TABLE_LOGICAL)
    if entity_id:
        _add_columns(client, RFP_RESPONSE_TABLE_LOGICAL, entity_id, EXTRA_COLUMNS_FOR_RFP_RESPONSE)
        _publish_entity(client, RFP_RESPONSE_TABLE_LOGICAL)
    else:
        print(f"  [WARN] Could not find RFP Response table '{RFP_RESPONSE_TABLE_LOGICAL}'")
    print()

    # Step 4: Print EntitySetName for the new table
    schema = COLUMN_DEF_TABLE["schema_name"]
    api_name = get_entity_set_name(client, schema)
    print("=" * 60)
    print("  Confirmed API name (update config/config.py):")
    print("=" * 60)
    print(f"  {schema}")
    print(f"    EntitySetName (API path): {api_name or '(could not fetch)'}")
    print()

    # Step 5: Seed default column definitions
    print("--- Step 5: Seed default column definitions ---")
    if api_name:
        _seed_default_columns(client, api_name, schema)
    else:
        print("  [WARN] Cannot seed — EntitySetName unknown. Run script again after updating config.")
    print()

    print("=" * 60)
    print("  Setup complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Update RFP_TEAM_COLUMNS_TABLE_API in config/config.py")
    print(f"     with the EntitySetName: {api_name or '(check above)'}")
    print("  2. Restart the server:  python dashboard_main.py")


if __name__ == "__main__":
    main()
