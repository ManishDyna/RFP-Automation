"""
Fix script for cr673_bahra_rfps_v2 table.

Actions:
  1. Clear corrupted owner_name (where value is a status like "Declined")
  2. For ALL rows, compare v2 vs old table and update any column where
     the old table has a better/non-empty value that v2 is missing or
     where v2 has a clearly wrong value.

Usage:
  python -m Support-Files.fix_rfps_v2
"""

import re
import sys
import time
from helpers.dataverse_helper import DataverseClient
from config.config import TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL

# ---------------------------------------------------------------------------
# Table names
# ---------------------------------------------------------------------------
OLD_TABLE_LOGICAL = "cr673_requestforproposal"
OLD_TABLE_API = "cr673_requestforproposals"

NEW_TABLE_LOGICAL = "cr673_bahra_rfps_v2"
NEW_TABLE_API = "cr673_bahra_rfps_v2s"

# Display-name key for the record GUID (mapped from cr673_bahra_rfps_v2id)
RECORD_ID_KEY = "Bahra RFPs V2"

# Columns that can be corrected from old table (excluding Matched_Data — large JSON)
CORRECTABLE_COLUMNS = [
    "Company_Name", "RFP_End_Date", "owner_name", "publish_time",
    "participated", "Link", "Email_Status", "Email_To", "Email_Sent_At",
    "Downloaded_At", "Reminder_1Day_Sent", "Reminder_3Day_Sent",
    "response_count", "first_response_at", "all_responses_at", "rfp_type",
]

# ---------------------------------------------------------------------------
# Validation helpers (same as audit script)
# ---------------------------------------------------------------------------
STATUS_KEYWORDS = {
    "declined", "submitted", "participated", "yes", "no", "no bid",
    "not participated", "open", "sent", "sent (actionable)",
}

DATE_PATTERNS = [
    re.compile(r"^\d{4}-\d{2}-\d{2}T"),
    re.compile(r"^\d{1,2}/\d{1,2}/\d{4}"),
    re.compile(r"^\d{1,2}-\d{1,2}-\d{4}"),
    re.compile(r"^\d{4}-\d{2}-\d{2}"),
]

OWNER_NAME_RE = re.compile(r"^[A-Za-z\s\.\,\'\-]+$")


def _val(row, col):
    v = row.get(col)
    if v is None:
        return ""
    return str(v).strip()


def _looks_like_date(s):
    return any(p.match(s) for p in DATE_PATTERNS)


def _is_corrupt_owner(name):
    """Return True if owner_name is corrupted (contains status value, digits, etc.)."""
    if not name:
        return False  # empty is fine
    if len(name) < 3:
        return True
    if name.lower() in STATUS_KEYWORDS:
        return True
    if _looks_like_date(name):
        return True
    if re.search(r"\d", name):
        return True
    if not OWNER_NAME_RE.match(name):
        return True
    return False


def main():
    print("=" * 70)
    print("  FIX: cr673_bahra_rfps_v2 Data Cleanup")
    print("=" * 70)

    client = DataverseClient(
        tenant_id=TENANT_ID,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        resource_url=RESOURCE_URL,
    )
    print("[AUTH] Token acquired.\n")

    # ----- Fetch both tables -----
    print("[1/4] Fetching all rows from NEW table (v2)...")
    new_rows = client.get_all_rows(
        table_api_name=NEW_TABLE_API,
        table_logical_name=NEW_TABLE_LOGICAL,
        use_display_names=True,
    )
    print(f"       Total rows in v2: {len(new_rows)}\n")

    print("[2/4] Fetching all rows from OLD table...")
    old_rows = client.get_all_rows(
        table_api_name=OLD_TABLE_API,
        table_logical_name=OLD_TABLE_LOGICAL,
        use_display_names=True,
    )
    print(f"       Total rows in old table: {len(old_rows)}\n")

    # Build lookup: RFP_ID -> best old row (latest Downloaded_At)
    old_map = {}
    for row in old_rows:
        rfp_id = _val(row, "RFP_ID")
        if not rfp_id:
            continue
        if rfp_id not in old_map:
            old_map[rfp_id] = row
        else:
            existing_dl = _val(old_map[rfp_id], "Downloaded_At")
            new_dl = _val(row, "Downloaded_At")
            if new_dl and (not existing_dl or new_dl > existing_dl):
                old_map[rfp_id] = row

    # ----- Build updates -----
    print("[3/4] Analyzing rows and building update list...")
    updates = []  # list of (record_id, rfp_id, patch_data, reasons)

    for row in new_rows:
        rfp_id = _val(row, "RFP_ID")
        if not rfp_id:
            continue

        record_id = row.get(RECORD_ID_KEY)
        if not record_id:
            print(f"  [WARN] No record ID for RFP_ID={rfp_id}, skipping")
            continue

        old_row = old_map.get(rfp_id, {})
        patch = {}
        reasons = []

        # --- Fix 1: Clear corrupted owner_name ---
        owner = _val(row, "owner_name")
        if _is_corrupt_owner(owner):
            # Check if old table has a valid owner
            old_owner = _val(old_row, "owner_name")
            if old_owner and not _is_corrupt_owner(old_owner):
                patch["owner_name"] = old_owner
                reasons.append(f"owner_name: '{owner}' -> '{old_owner}' (from old table)")
            else:
                patch["owner_name"] = ""
                reasons.append(f"owner_name: '{owner}' -> '' (cleared, old table also bad)")

        # --- Fix 2: Fill missing columns from old table ---
        for col in CORRECTABLE_COLUMNS:
            if col == "owner_name":
                continue  # already handled above
            v2_val = _val(row, col)
            old_val = _val(old_row, col)

            # If v2 is empty but old has a value, fill it
            if not v2_val and old_val:
                patch[col] = old_val
                reasons.append(f"{col}: '' -> '{old_val[:60]}' (filled from old table)")

        if patch:
            updates.append((record_id, rfp_id, patch, reasons))

    print(f"       Rows to update: {len(updates)}\n")

    if not updates:
        print("  Nothing to fix! All data looks good.")
        return

    # ----- Print summary before applying -----
    owner_fixes = sum(1 for _, _, p, _ in updates if "owner_name" in p)
    fill_fixes = sum(1 for _, _, p, _ in updates if len(p) > (1 if "owner_name" in p else 0))
    print(f"  Summary:")
    print(f"    owner_name fixes   : {owner_fixes}")
    print(f"    Rows with fills    : {fill_fixes}")
    print(f"    Total rows to patch: {len(updates)}")
    print()

    # Show first 10 examples
    print("  First 10 updates preview:")
    for i, (rec_id, rfp_id, patch, reasons) in enumerate(updates[:10], 1):
        print(f"    {i}. {rfp_id}")
        for r in reasons:
            print(f"       - {r}")
    if len(updates) > 10:
        print(f"    ... and {len(updates) - 10} more")
    print()

    # ----- Apply updates -----
    print("[4/4] Applying updates...")
    updated = 0
    failed = 0

    for i, (record_id, rfp_id, patch, reasons) in enumerate(updates, 1):
        try:
            client.update_row(
                NEW_TABLE_API,
                record_id,
                patch,
                table_logical_name=NEW_TABLE_LOGICAL,
                use_display_names=True,
            )
            updated += 1
            if updated % 50 == 0:
                print(f"       ... updated {updated}/{len(updates)} rows")
        except Exception as e:
            failed += 1
            print(f"  [FAIL] RFP_ID={rfp_id}: {e}")

    print(f"\n{'=' * 70}")
    print(f"  Fix complete!")
    print(f"  Updated : {updated}")
    print(f"  Failed  : {failed}")
    print(f"  Total   : {len(updates)}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
