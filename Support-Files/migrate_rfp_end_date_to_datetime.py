"""
Migration script: Convert RFP_End_Date from STRING to DATETIME in Dataverse.

Steps:
  1. Add backup column 'bck_rfp_end_date' (string)
  2. Copy all RFP_End_Date values to backup column
  3. Delete original 'cr673_RFP_End_Date' column
  4. Create new 'cr673_RFP_End_Date' as DateTimeAttributeMetadata
  5. Parse dates from backup → write as ISO datetime to new column
  6. Publish entity

Usage:
  python -m Support-Files.migrate_rfp_end_date_to_datetime
"""

import sys
import json
import time
import requests
import pandas as pd
from datetime import datetime
from dateutil import parser as du_parser

from helpers.dataverse_helper import DataverseClient
from config.config import TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL

TABLE_LOGICAL = "cr673_bahra_rfps_v2"
TABLE_API = "cr673_bahra_rfps_v2s"


def make_label(text):
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.Label",
        "LocalizedLabels": [{"@odata.type": "Microsoft.Dynamics.CRM.LocalizedLabel", "Label": text, "LanguageCode": 1033}],
    }


def get_entity_id(client, logical_name):
    resp = requests.get(
        f"{client.api_url}EntityDefinitions(LogicalName='{logical_name}')?$select=MetadataId",
        headers=client._headers(),
    )
    if resp.status_code == 200:
        return resp.json().get("MetadataId")
    return None


def publish_entity(client, logical_name):
    resp = requests.post(
        f"{client.api_url}PublishXml",
        json={"ParameterXml": f"<importexportxml><entities><entity>{logical_name}</entity></entities></importexportxml>"},
        headers=client._headers(),
    )
    return resp.status_code in (200, 204)


def add_string_column(client, entity_id, schema_name, display_name, max_length=200):
    col_def = {
        "@odata.type": "Microsoft.Dynamics.CRM.StringAttributeMetadata",
        "AttributeType": "String",
        "AttributeTypeName": {"Value": "StringType"},
        "SchemaName": schema_name,
        "DisplayName": make_label(display_name),
        "MaxLength": max_length,
        "RequiredLevel": {"Value": "None", "CanBeChanged": True},
        "FormatName": {"Value": "Text"},
    }
    resp = requests.post(
        f"{client.api_url}EntityDefinitions({entity_id})/Attributes",
        json=col_def, headers=client._headers(),
    )
    if resp.status_code in (200, 201, 204):
        return True
    if resp.status_code in (400, 409):
        err = resp.json().get("error", {}).get("message", "")
        if "already exists" in err.lower():
            return True
    print(f"  [FAIL] Add column {schema_name}: HTTP {resp.status_code} - {resp.text[:300]}")
    return False


def add_datetime_column(client, entity_id, schema_name, display_name):
    col_def = {
        "@odata.type": "Microsoft.Dynamics.CRM.DateTimeAttributeMetadata",
        "AttributeType": "DateTime",
        "AttributeTypeName": {"Value": "DateTimeType"},
        "SchemaName": schema_name,
        "DisplayName": make_label(display_name),
        "RequiredLevel": {"Value": "None", "CanBeChanged": True},
        "Format": "DateAndTime",
        "DateTimeBehavior": {"Value": "UserLocal"},
    }
    resp = requests.post(
        f"{client.api_url}EntityDefinitions({entity_id})/Attributes",
        json=col_def, headers=client._headers(),
    )
    if resp.status_code in (200, 201, 204):
        return True
    if resp.status_code in (400, 409):
        err = resp.json().get("error", {}).get("message", "")
        if "already exists" in err.lower():
            return True
    print(f"  [FAIL] Add datetime column {schema_name}: HTTP {resp.status_code} - {resp.text[:300]}")
    return False


def delete_column(client, entity_id, logical_col_name):
    # Get attribute metadata ID first
    resp = requests.get(
        f"{client.api_url}EntityDefinitions({entity_id})/Attributes?$filter=LogicalName eq '{logical_col_name}'&$select=MetadataId",
        headers=client._headers(),
    )
    if resp.status_code != 200:
        print(f"  [WARN] Could not find attribute {logical_col_name}")
        return False

    attrs = resp.json().get("value", [])
    if not attrs:
        print(f"  [INFO] Column {logical_col_name} does not exist (already deleted?)")
        return True

    attr_id = attrs[0]["MetadataId"]
    del_resp = requests.delete(
        f"{client.api_url}EntityDefinitions({entity_id})/Attributes({attr_id})",
        headers=client._headers(),
    )
    if del_resp.status_code in (200, 204):
        return True
    print(f"  [FAIL] Delete {logical_col_name}: HTTP {del_resp.status_code} - {del_resp.text[:300]}")
    return False


def parse_date_string(val):
    """Parse various date string formats to ISO 8601 datetime string."""
    if not val or str(val).strip() in ("", "-"):
        return None
    val = str(val).strip()
    try:
        # Try dateutil parser (handles most formats)
        dt = du_parser.parse(val)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        pass
    try:
        # Try pandas
        dt = pd.to_datetime(val)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        pass
    return None


def main():
    print("=" * 60)
    print("  Migrate RFP_End_Date: STRING -> DATETIME")
    print("=" * 60)

    client = DataverseClient(TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL)
    print("[AUTH] Ready.\n")

    entity_id = get_entity_id(client, TABLE_LOGICAL)
    if not entity_id:
        print("[FATAL] Cannot find entity metadata!")
        sys.exit(1)
    print(f"[OK] Entity ID: {entity_id}")

    # --- Step 1: Add backup column ---
    print("\n[Step 1/6] Adding backup column 'bck_rfp_end_date'...")
    if not add_string_column(client, entity_id, "cr673_bck_rfp_end_date", "bck_rfp_end_date", 200):
        print("[FATAL] Could not add backup column!")
        sys.exit(1)
    publish_entity(client, TABLE_LOGICAL)
    print("  [OK] Backup column added and published.")
    time.sleep(5)

    # --- Step 2: Copy values to backup ---
    print("\n[Step 2/6] Copying RFP_End_Date values to backup column...")
    all_rows = client.get_all_rows(
        table_api_name=TABLE_API,
        select_columns=["RFP_ID", "RFP_End_Date"],
        table_logical_name=TABLE_LOGICAL,
        use_display_names=True,
    )
    print(f"  Total rows: {len(all_rows)}")

    # Resolve PK
    try:
        colmap = client.get_column_mapping(TABLE_LOGICAL)
        logical_to_display = {v: k for k, v in colmap.items()}
    except Exception:
        logical_to_display = {}
    pk_logical = f"{TABLE_LOGICAL}id"
    pk_display = logical_to_display.get(pk_logical)

    copied = 0
    for i, row in enumerate(all_rows, 1):
        end_date = (row.get("RFP_End_Date") or "").strip()
        if not end_date:
            continue
        record_id = (row.get(pk_display) if pk_display else None) or row.get(pk_logical)
        if not record_id:
            continue
        try:
            client.update_row(TABLE_API, record_id, {"bck_rfp_end_date": end_date}, table_logical_name=TABLE_LOGICAL)
            copied += 1
            if copied % 100 == 0:
                print(f"  Copied {copied} rows...")
        except Exception as e:
            print(f"  [WARN] Copy failed for row {i}: {e}")
    print(f"  [OK] Copied {copied} values to backup column.")

    # --- Step 3: Delete original column ---
    print("\n[Step 3/6] Deleting original 'cr673_rfp_end_date' column...")
    # Re-fetch entity_id (may have changed after publish)
    entity_id = get_entity_id(client, TABLE_LOGICAL)
    if delete_column(client, entity_id, "cr673_rfp_end_date"):
        print("  [OK] Original column deleted.")
        publish_entity(client, TABLE_LOGICAL)
        time.sleep(10)
    else:
        print("  [FAIL] Could not delete column. Aborting.")
        print("  Your backup data is safe in 'bck_rfp_end_date' column.")
        sys.exit(1)

    # --- Step 4: Create new datetime column ---
    print("\n[Step 4/6] Creating new 'RFP_End_Date' as DateTime column...")
    entity_id = get_entity_id(client, TABLE_LOGICAL)
    if not add_datetime_column(client, entity_id, "cr673_RFP_End_Date", "RFP_End_Date"):
        print("  [FAIL] Could not create datetime column!")
        sys.exit(1)
    publish_entity(client, TABLE_LOGICAL)
    time.sleep(10)
    print("  [OK] DateTime column created and published.")

    # Clear column mapping cache so new column type is recognized
    client.clear_column_mapping_cache(TABLE_LOGICAL)

    # --- Step 5: Migrate data from backup to new datetime column ---
    print("\n[Step 5/6] Migrating dates from backup to new DateTime column...")
    # Re-fetch all rows with backup column
    all_rows = client.get_all_rows(
        table_api_name=TABLE_API,
        select_columns=["RFP_ID", "bck_rfp_end_date"],
        table_logical_name=TABLE_LOGICAL,
        use_display_names=True,
    )

    # Re-resolve PK (column mapping may have changed)
    client.clear_column_mapping_cache(TABLE_LOGICAL)
    try:
        colmap = client.get_column_mapping(TABLE_LOGICAL)
        logical_to_display = {v: k for k, v in colmap.items()}
    except Exception:
        logical_to_display = {}
    pk_display = logical_to_display.get(pk_logical)

    migrated = 0
    failed_parse = 0
    for i, row in enumerate(all_rows, 1):
        bck_val = (row.get("bck_rfp_end_date") or "").strip()
        if not bck_val:
            continue
        record_id = (row.get(pk_display) if pk_display else None) or row.get(pk_logical)
        if not record_id:
            continue

        iso_date = parse_date_string(bck_val)
        if not iso_date:
            failed_parse += 1
            if failed_parse <= 5:
                print(f"  [WARN] Could not parse date: '{bck_val}'")
            continue

        try:
            client.update_row(TABLE_API, record_id, {"RFP_End_Date": iso_date}, table_logical_name=TABLE_LOGICAL)
            migrated += 1
            if migrated % 100 == 0:
                print(f"  Migrated {migrated} rows...")
        except Exception as e:
            failed_parse += 1
            if failed_parse <= 10:
                print(f"  [WARN] Update failed for '{bck_val}': {e}")

    print(f"  [OK] Migrated {migrated} dates. Failed to parse: {failed_parse}")

    # --- Step 6: Final publish ---
    print("\n[Step 6/6] Final publish...")
    publish_entity(client, TABLE_LOGICAL)

    print(f"\n{'=' * 60}")
    print(f"  Migration complete!")
    print(f"  Copied to backup: {copied}")
    print(f"  Migrated to datetime: {migrated}")
    print(f"  Parse failures: {failed_parse}")
    print(f"  Backup column 'bck_rfp_end_date' retained for safety.")
    print(f"{'=' * 60}")
    print(f"\n  Next: Update code to use ISO datetime format.")
    print(f"  Then: Add OData $filter for server-side date filtering.")


if __name__ == "__main__":
    main()
