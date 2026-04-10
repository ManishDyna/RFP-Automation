"""
Backfill script to migrate data from old cr673_requestforproposal table
to the new cr673_bahra_rfps_v2 table.

Flow:
  1. Read ALL rows from old table
  2. Deduplicate by RFP_ID (keep latest Downloaded_At)
  3. Copy the 19 relevant columns to the new table
  4. Idempotent: skips RFP_IDs that already exist in new table

Usage:
  python -m Support-Files.backfill_rfps_v2

NOTE: Run setup_rfps_v2_table.py first to create the new table.
      Update NEW_TABLE_API below after confirming the EntitySetName.
"""

import sys
import time
from helpers.dataverse_helper import DataverseClient
from config.config import TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL

# ---------------------------------------------------------------------------
# Table names
# ---------------------------------------------------------------------------

# Old table (source)
OLD_TABLE_LOGICAL = "cr673_requestforproposal"
OLD_TABLE_API = "cr673_requestforproposals"

# New table (destination) — UPDATE API name after running setup script
NEW_TABLE_LOGICAL = "cr673_bahra_rfps_v2"
NEW_TABLE_API = "cr673_bahra_rfps_v2s"

# The 19 columns to copy (display names, matching both tables)
COLUMNS_TO_COPY = [
    "RunID",
    "RFP_ID",
    "Company_Name",
    "RFP_End_Date",
    "owner_name",
    "publish_time",
    "participated",
    "Link",
    "Matched_Data",
    "Email_Status",
    "Email_To",
    "Email_Sent_At",
    "Downloaded_At",
    "Reminder_1Day_Sent",
    "Reminder_3Day_Sent",
    "response_count",
    "first_response_at",
    "all_responses_at",
    "rfp_type",
]


def main():
    print("=" * 60)
    print("  Backfill: Old RFPs -> cr673_bahra_rfps_v2")
    print("=" * 60)

    client = DataverseClient(
        tenant_id=TENANT_ID,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        resource_url=RESOURCE_URL,
    )
    print("[AUTH] Token acquired.\n")

    # -----------------------------------------------------------------------
    # 1. Read all rows from old table
    # -----------------------------------------------------------------------
    print("[1/4] Reading all rows from old table...")
    old_rows = client.get_all_rows(
        table_api_name=OLD_TABLE_API,
        table_logical_name=OLD_TABLE_LOGICAL,
        use_display_names=True,
    )
    print(f"       Total rows in old table: {len(old_rows)}")

    if not old_rows:
        print("       No rows found. Nothing to backfill.")
        return

    # -----------------------------------------------------------------------
    # 2. Deduplicate by RFP_ID (keep latest Downloaded_At)
    # -----------------------------------------------------------------------
    print("[2/4] Deduplicating by RFP_ID...")
    rfp_map = {}  # RFP_ID -> best row
    for row in old_rows:
        rfp_id = (row.get("RFP_ID") or "").strip()
        if not rfp_id:
            continue

        if rfp_id not in rfp_map:
            rfp_map[rfp_id] = row
        else:
            # Keep the one with the latest Downloaded_At (or the one that has it)
            existing_dl = (rfp_map[rfp_id].get("Downloaded_At") or "").strip()
            new_dl = (row.get("Downloaded_At") or "").strip()
            if new_dl and (not existing_dl or new_dl > existing_dl):
                rfp_map[rfp_id] = row

    unique_rows = list(rfp_map.values())
    print(f"       Unique RFP_IDs: {len(unique_rows)}")

    # -----------------------------------------------------------------------
    # 3. Check which RFP_IDs already exist in new table (idempotent)
    # -----------------------------------------------------------------------
    print("[3/4] Checking existing rows in new table...")
    existing_new_rows = client.get_all_rows(
        table_api_name=NEW_TABLE_API,
        select_columns=["RFP_ID"],
        table_logical_name=NEW_TABLE_LOGICAL,
        use_display_names=True,
    )
    existing_rfp_ids = {
        (r.get("RFP_ID") or "").strip()
        for r in existing_new_rows
        if (r.get("RFP_ID") or "").strip()
    }
    print(f"       Already in new table: {len(existing_rfp_ids)}")

    # -----------------------------------------------------------------------
    # 4. Insert missing rows into new table
    # -----------------------------------------------------------------------
    print("[4/4] Inserting rows into new table...")
    inserted = 0
    skipped = 0
    failed = 0

    for i, row in enumerate(unique_rows, 1):
        rfp_id = (row.get("RFP_ID") or "").strip()

        if rfp_id in existing_rfp_ids:
            skipped += 1
            continue

        # Build new row with only the 19 columns
        new_row = {}
        for col in COLUMNS_TO_COPY:
            val = row.get(col)
            # Also try stripped key (Dataverse sometimes has trailing spaces)
            if val is None:
                for k, v in row.items():
                    if k.strip() == col:
                        val = v
                        break
            if val is not None and str(val).strip():
                new_row[col] = str(val).strip() if not isinstance(val, str) else val

        # Must have at least RFP_ID and RunID
        if not new_row.get("RFP_ID"):
            failed += 1
            continue
        if not new_row.get("RunID"):
            new_row["RunID"] = f"backfill-{rfp_id[:50]}"

        try:
            client.insert_row(
                NEW_TABLE_API,
                new_row,
                table_logical_name=NEW_TABLE_LOGICAL,
                use_display_names=True,
            )
            inserted += 1
            if inserted % 25 == 0:
                print(f"       ... inserted {inserted} rows")
        except Exception as e:
            failed += 1
            print(f"       [FAIL] RFP_ID={rfp_id}: {e}")

    print(f"\n{'=' * 60}")
    print(f"  Backfill complete!")
    print(f"  Inserted: {inserted}")
    print(f"  Skipped (already exists): {skipped}")
    print(f"  Failed: {failed}")
    print(f"  Total unique RFPs: {len(unique_rows)}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
