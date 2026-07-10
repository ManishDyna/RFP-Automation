"""
Setup script to create the cr673_bahra_rfps_v2 Dataverse table via the Web API.

This is a clean replacement for the old cr673_requestforproposal table,
with only the 19 columns actually used by the system.

Usage:
  python -m Support-Files.setup_rfps_v2_table

Safe to re-run (skips existing table/columns).
"""

import sys
import json
import time
import requests
from helpers.dataverse_helper import DataverseClient
from config.config import TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL


# ---------------------------------------------------------------------------
# Helpers (same pattern as setup_rbac_tables.py)
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
# Table definition
# ---------------------------------------------------------------------------

TABLE_DEF = {
    "schema_name": "cr673_bahra_rfps_v2",
    "display_name": "Bahra RFPs V2",
    "display_name_plural": "Bahra RFPs V2",
    "description": "Clean RFP activity log with 19 columns. Matched_Data JSON is the single source of truth for material matches.",
    "primary_attribute": primary_name_column("cr673_RunID", "RunID"),
    "extra_columns": [
        string_column("cr673_RFP_ID", "RFP_ID", 500),
        string_column("cr673_Company_Name", "Company_Name", 200),
        string_column("cr673_RFP_End_Date", "RFP_End_Date", 200),
        string_column("cr673_owner_name", "owner_name", 200),
        string_column("cr673_publish_time", "publish_time", 200),
        string_column("cr673_participated", "participated", 50),
        string_column("cr673_Link", "Link", 2000),
        memo_column("cr673_Matched_Data", "Matched_Data", 1048576),
        string_column("cr673_Email_Status", "Email_Status", 200),
        string_column("cr673_Email_To", "Email_To", 500),
        string_column("cr673_Email_Sent_At", "Email_Sent_At", 200),
        string_column("cr673_Downloaded_At", "Downloaded_At", 200),
        string_column("cr673_Reminder_1Day_Sent", "Reminder_1Day_Sent", 10),
        string_column("cr673_Reminder_3Day_Sent", "Reminder_3Day_Sent", 10),
        string_column("cr673_response_count", "response_count", 50),
        string_column("cr673_first_response_at", "first_response_at", 200),
        string_column("cr673_all_responses_at", "all_responses_at", 200),
        string_column("cr673_rfp_type", "rfp_type", 200),
    ],
}


# ---------------------------------------------------------------------------
# Table check & creation
# ---------------------------------------------------------------------------

def table_exists(client: DataverseClient, logical_name: str) -> bool:
    url = f"{client.api_url}EntityDefinitions(LogicalName='{logical_name}')?$select=LogicalName"
    resp = requests.get(url, headers=client._headers())
    return resp.status_code == 200


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

    # Add extra columns one by one
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


def get_entity_set_name(client: DataverseClient, logical_name: str) -> str:
    """Query Dataverse for the actual EntitySetName (API plural name)."""
    url = f"{client.api_url}EntityDefinitions(LogicalName='{logical_name}')?$select=EntitySetName"
    resp = requests.get(url, headers=client._headers())
    if resp.status_code == 200:
        return resp.json().get("EntitySetName", "")
    return ""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("  RFPs V2 Dataverse Table Setup")
    print("=" * 60)
    print(f"\nDataverse: {RESOURCE_URL}\n")

    client = DataverseClient(
        tenant_id=TENANT_ID,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        resource_url=RESOURCE_URL,
    )
    print("[AUTH] Token acquired successfully.\n")

    print(f"--- {TABLE_DEF['display_name']} ({TABLE_DEF['schema_name']}) ---")
    success = create_table(client, TABLE_DEF)

    if success:
        # Confirm the actual API name
        api_name = get_entity_set_name(client, TABLE_DEF["schema_name"])
        print(f"\n{'=' * 60}")
        print(f"  Table ready!")
        print(f"  Logical Name: {TABLE_DEF['schema_name']}")
        print(f"  API Name (EntitySetName): {api_name}")
        print(f"{'=' * 60}")
        print(f"\n  *** UPDATE config.py with: ***")
        print(f'  RFP_ACTIVITY_LOG_TABLE_LOGICAL = "{TABLE_DEF["schema_name"]}"')
        print(f'  RFP_ACTIVITY_LOG_TABLE_API = "{api_name}"')
    else:
        print("\nTable creation failed. Check errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
