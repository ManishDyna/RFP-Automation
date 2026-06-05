"""
Setup script to create the RFP Delegation Dataverse table via the Web API.

Table created:
  cr673_bahra_rfp_delegations - Per-RFP product-line delegation records

Each row maps an "original recipient" to a "new recipient" for ONE specific
RFP + product combination. The master cr673_bahra_rfp_team table is NEVER
touched - delegation is on-the-fly and scoped to a single RFP.

Usage:
  python Support-Files/setup_delegation_table.py

Run once. Safe to re-run - skips existing table and adds missing columns.
After publish, prints the resolved EntitySetName for pasting into config.py
(Dataverse pluralization is unpredictable - see project memory).
"""

import sys
import json
import time
from pathlib import Path

# Allow running as a script from project root (python Support-Files/setup_delegation_table.py).
_PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import requests
from helpers.dataverse_helper import DataverseClient
from config.config import TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL


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


TABLE_DEFINITIONS = [
    {
        "schema_name": "cr673_bahra_rfp_delegations",
        "display_name": "Bahra RFP Delegations",
        "display_name_plural": "Bahra RFP Delegations",
        "description": "Per-RFP product-line delegation records (original recipient -> new recipient)",
        "primary_attribute": primary_name_column("cr673_name", "name", 500),
        "extra_columns": [
            string_column("cr673_rfp_id", "rfp_id", 100),
            string_column("cr673_product", "product", 200),
            string_column("cr673_original_email", "original_email", 200),
            string_column("cr673_original_name", "original_name", 200),
            string_column("cr673_new_email", "new_email", 200),
            string_column("cr673_new_name", "new_name", 200),
            string_column("cr673_delegated_by_email", "delegated_by_email", 200),
            string_column("cr673_delegated_by_name", "delegated_by_name", 200),
            string_column("cr673_delegated_at", "delegated_at", 100),
            string_column("cr673_is_active", "is_active", 10),
        ],
    },
]


def table_exists(client: DataverseClient, logical_name: str) -> bool:
    url = f"{client.api_url}EntityDefinitions(LogicalName='{logical_name}')?$select=LogicalName"
    resp = requests.get(url, headers=client._headers())
    return resp.status_code == 200


def resolve_entity_set_name(client: DataverseClient, logical_name: str) -> str:
    """Look up the actual EntitySetName (the API URL segment) for a table.
    Dataverse pluralization is unpredictable - +es, +s, or replaces 'status'->'statuses'."""
    url = f"{client.api_url}EntityDefinitions(LogicalName='{logical_name}')?$select=EntitySetName"
    resp = requests.get(url, headers=client._headers())
    if resp.status_code == 200:
        return resp.json().get("EntitySetName", "") or ""
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
                print(f"         ! Column '{col_name}' FAILED (HTTP 400)")
                print(f"           {err_msg[:300]}")
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


def main():
    print("=" * 60)
    print("  RFP Delegation Dataverse Table Setup")
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

    print("=" * 60)
    print(f"  Result: {success_count}/{len(TABLE_DEFINITIONS)} table(s) ready.")
    print("=" * 60)

    # Resolve and print EntitySetName for config.py - Dataverse pluralization is unpredictable
    print("\n--- Resolved EntitySetNames (paste into config/config.py) ---")
    for table_def in TABLE_DEFINITIONS:
        logical = table_def["schema_name"]
        api_name = resolve_entity_set_name(client, logical)
        if api_name:
            print(f"  {logical}")
            print(f"    -> EntitySetName: {api_name}")
            print(f"    RFP_DELEGATION_TABLE_LOGICAL = \"{logical}\"")
            print(f"    RFP_DELEGATION_TABLE_API     = \"{api_name}\"")
        else:
            print(f"  {logical} -> [WARN] could not resolve EntitySetName")

    if success_count < len(TABLE_DEFINITIONS):
        sys.exit(1)


if __name__ == "__main__":
    main()
