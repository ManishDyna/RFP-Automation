"""
Delete rows from cr673_bhara_rfp_status where to_this='declined'.

These rows were inserted by automation/sync paths before the fix landed.
Going forward only user-driven status changes write to this table, so the
historical decline rows are stale and inflate the dashboard's
"Declined by System" count.

Usage:
    # DRY RUN — counts and shows samples, deletes nothing:
    python Support-Files/cleanup_declined_status_rows.py

    # LIVE — actually deletes:
    python Support-Files/cleanup_declined_status_rows.py --confirm
"""

import sys
import io
import argparse
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from helpers.dataverse_helper import DataverseClient
from config.config import TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL

STATUS_TABLE_API = "cr673_bhara_rfp_statuses"
STATUS_TABLE_LOGICAL = "cr673_bhara_rfp_status"
PK_LOGICAL = f"{STATUS_TABLE_LOGICAL}id"
BATCH_SIZE = 100


def _find_key(row: dict, candidates: list[str]) -> str | None:
    """Look up a column by any of the candidate names, normalized."""
    keys_lower = {
        k.lower().replace(" ", "").replace("_", ""): k for k in row.keys()
    }
    for c in candidates:
        norm = c.lower().replace(" ", "").replace("_", "")
        if norm in keys_lower:
            return keys_lower[norm]
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Actually delete the rows. Without this flag the script is dry-run.",
    )
    args = parser.parse_args()

    dv = DataverseClient(
        tenant_id=TENANT_ID,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        resource_url=RESOURCE_URL,
    )

    print(f"\n{'=' * 70}")
    print(f"  Cleanup: {STATUS_TABLE_LOGICAL} rows where to_this='declined'")
    print(f"  Mode: {'LIVE (will delete)' if args.confirm else 'DRY RUN (no changes)'}")
    print(f"{'=' * 70}\n")

    # Resolve PK display name (we query with use_display_names=True, so the row
    # keys are display names, not logical names).
    try:
        column_map = dv.get_column_mapping(STATUS_TABLE_LOGICAL)  # display -> logical
    except Exception as e:
        print(f"[ERROR] Could not read column mapping: {e}")
        return 1
    logical_to_display = {v: k for k, v in column_map.items()}
    pk_display = logical_to_display.get(PK_LOGICAL)

    rows = dv.get_all_rows(
        table_api_name=STATUS_TABLE_API,
        table_logical_name=STATUS_TABLE_LOGICAL,
        use_display_names=True,
    )
    print(f"Total status rows in table: {len(rows)}")

    if not rows:
        print("Nothing to do — table is empty.")
        return 0

    to_key = _find_key(rows[0], ["to_this", "tothis", "currentstatus", "CurrentStatus"])
    rfp_key = _find_key(rows[0], ["RFP_ID", "rfp_id", "rfpreference", "RFP Reference"])
    if not to_key:
        print(f"[ERROR] Could not find a 'to_this' column. Available keys: {list(rows[0].keys())}")
        return 1

    # Collect record IDs to delete
    targets = []
    sample_rfp_ids = []
    for r in rows:
        to_val = (r.get(to_key) or "")
        if isinstance(to_val, str) and to_val.strip().lower() == "declined":
            rec_id = (r.get(pk_display) if pk_display else None) or r.get(PK_LOGICAL)
            if not rec_id:
                continue
            targets.append(rec_id)
            if rfp_key and len(sample_rfp_ids) < 10:
                sample_rfp_ids.append(r.get(rfp_key) or "?")

    print(f"Rows matching to_this='declined': {len(targets)}")
    if sample_rfp_ids:
        print("Sample RFP IDs from those rows:")
        for rid in sample_rfp_ids:
            print(f"  - {rid}")

    if not targets:
        print("Nothing to delete.")
        return 0

    if not args.confirm:
        print("\n[DRY RUN] Re-run with --confirm to actually delete these rows.")
        return 0

    # LIVE DELETE — batch in chunks
    print(f"\nDeleting {len(targets)} rows in batches of {BATCH_SIZE}...")
    deleted = 0
    for i in range(0, len(targets), BATCH_SIZE):
        chunk = targets[i : i + BATCH_SIZE]
        try:
            n = dv.batch_delete(STATUS_TABLE_API, chunk)
            deleted += n
            print(f"  Batch {i // BATCH_SIZE + 1}: deleted {n}/{len(chunk)} (running total: {deleted})")
        except Exception as e:
            print(f"  Batch {i // BATCH_SIZE + 1}: FAILED — {e}")

    print(f"\n{'=' * 70}")
    print(f"  DONE. Deleted {deleted}/{len(targets)} rows.")
    print(f"{'=' * 70}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
