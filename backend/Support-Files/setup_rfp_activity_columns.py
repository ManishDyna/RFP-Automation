"""
Setup script to add new analytics columns to the existing cr673_requestforproposal table.

New columns added:
  1. rfp_type           - RFP event type from portal (RFQ, RFP, Tender, etc.)
  2. total_line_items   - Total rows in the RFP Excel file
  3. match_rate_pct     - Percentage of materials matched
  4. exact_match_count  - Count of exact material code matches
  5. keyword_match_count - Count of keyword-based matches
  6. file_size_bytes    - Size of downloaded RFP file
  7. first_response_at  - Timestamp of first team member response
  8. all_responses_at   - Timestamp when all team members responded
  9. response_count     - Number of team members who have responded

Usage:
  python setup_rfp_activity_columns.py

Safe to re-run (skips existing columns).
"""

import sys
import json
import time
import requests
from helpers.dataverse_helper import DataverseClient
from config.config import (
    TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL,
    RFP_ACTIVITY_LOG_TABLE_LOGICAL,
)


# ---------------------------------------------------------------------------
# Helpers (same as setup_master_data_tables.py)
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


# ---------------------------------------------------------------------------
# Column definitions to add
# ---------------------------------------------------------------------------

NEW_COLUMNS = [
    string_column("cr673_rfp_type", "rfp_type", 100),
    string_column("cr673_total_line_items", "total_line_items", 50),
    string_column("cr673_match_rate_pct", "match_rate_pct", 10),
    string_column("cr673_exact_match_count", "exact_match_count", 10),
    string_column("cr673_keyword_match_count", "keyword_match_count", 10),
    string_column("cr673_file_size_bytes", "file_size_bytes", 50),
    string_column("cr673_first_response_at", "first_response_at", 100),
    string_column("cr673_all_responses_at", "all_responses_at", 100),
    string_column("cr673_response_count", "response_count", 10),
]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    table_logical = RFP_ACTIVITY_LOG_TABLE_LOGICAL

    print("=" * 60)
    print("  Add Analytics Columns to RFP Activity Log")
    print("=" * 60)
    print(f"\nDataverse: {RESOURCE_URL}")
    print(f"Table:     {table_logical}\n")

    client = DataverseClient(
        tenant_id=TENANT_ID,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        resource_url=RESOURCE_URL,
    )
    print("[AUTH] Token acquired successfully.\n")

    # Verify table exists
    check_url = f"{client.api_url}EntityDefinitions(LogicalName='{table_logical}')?$select=LogicalName"
    check_resp = requests.get(check_url, headers=client._headers())
    if check_resp.status_code != 200:
        print(f"[FAIL] Table '{table_logical}' not found (HTTP {check_resp.status_code})")
        sys.exit(1)
    print(f"[OK]   Table '{table_logical}' exists.\n")

    # Fetch MetadataId
    entity_id = None
    for attempt in range(5):
        meta_url = f"{client.api_url}EntityDefinitions(LogicalName='{table_logical}')?$select=MetadataId"
        meta_resp = requests.get(meta_url, headers=client._headers())
        if meta_resp.status_code == 200:
            entity_id = meta_resp.json().get("MetadataId")
            if entity_id:
                break
        print(f"  [WAIT] MetadataId not ready yet, retrying ({attempt + 1}/5)...")
        time.sleep(5)

    if not entity_id:
        print("[FAIL] Could not get MetadataId. Aborting.")
        sys.exit(1)

    print(f"[OK]   MetadataId: {entity_id}\n")

    # Add each column
    added = skipped = failed = 0
    for col_def in NEW_COLUMNS:
        col_name = col_def.get("SchemaName", "?")
        col_url = f"{client.api_url}EntityDefinitions({entity_id})/Attributes"

        for retry in range(3):
            col_resp = requests.post(col_url, json=col_def, headers=client._headers())
            if col_resp.status_code in (200, 201, 204):
                print(f"  + Column '{col_name}' added.")
                added += 1
                break
            elif col_resp.status_code == 409:
                print(f"  ~ Column '{col_name}' already exists.")
                skipped += 1
                break
            elif col_resp.status_code == 400:
                err_msg = ""
                try:
                    err_msg = col_resp.json().get("error", {}).get("message", "")
                except Exception:
                    pass
                if "already exists" in err_msg.lower():
                    print(f"  ~ Column '{col_name}' already exists.")
                    skipped += 1
                    break
                else:
                    print(f"  ! Column '{col_name}' FAILED (HTTP 400): {err_msg[:300]}")
                    failed += 1
                    break
            elif col_resp.status_code == 404 and retry < 2:
                print(f"  ? Column '{col_name}' got 404, re-fetching MetadataId...")
                time.sleep(5)
                meta_resp2 = requests.get(
                    f"{client.api_url}EntityDefinitions(LogicalName='{table_logical}')?$select=MetadataId",
                    headers=client._headers(),
                )
                if meta_resp2.status_code == 200:
                    new_id = meta_resp2.json().get("MetadataId")
                    if new_id:
                        entity_id = new_id
                        col_url = f"{client.api_url}EntityDefinitions({entity_id})/Attributes"
            else:
                print(f"  ! Column '{col_name}' FAILED (HTTP {col_resp.status_code})")
                try:
                    err = col_resp.json()
                    print(f"    {err.get('error', {}).get('message', '')[:300]}")
                except Exception:
                    print(f"    {col_resp.text[:300]}")
                failed += 1
                break

    # Publish
    print()
    publish_url = f"{client.api_url}PublishXml"
    publish_payload = {
        "ParameterXml": f"<importexportxml><entities><entity>{table_logical}</entity></entities></importexportxml>"
    }
    pub_resp = requests.post(publish_url, json=publish_payload, headers=client._headers())
    if pub_resp.status_code in (200, 204):
        print(f"[OK]   Published '{table_logical}'.")
    else:
        print(f"[WARN] Publish returned HTTP {pub_resp.status_code}")

    print()
    print("=" * 60)
    print(f"  Result: {added} added, {skipped} skipped, {failed} failed")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
