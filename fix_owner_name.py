"""
Fix owner_name in Dataverse where values are incorrectly set to 'Yes' or 'No'.

For ALL companies (SEC, Aramco, Hadeed, etc.):
  - If the CSV has a real owner name for the RFP → update DB with it
  - If the RFP is NOT in the CSV → clear to blank (remove the bad 'Yes'/'No')

Supports resume: tracks progress in a JSON file.

Usage:
  python fix_owner_name.py                              # uses default CSV
  python fix_owner_name.py --file path/to/file.csv      # custom file
  python fix_owner_name.py --dry-run                     # preview without updating
  python fix_owner_name.py --reset                       # clear progress and start fresh
"""

import argparse
import json
import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers.dataverse_helper import DataverseClient
from config.config import (
    TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL,
    RFP_ACTIVITY_LOG_TABLE_API, RFP_ACTIVITY_LOG_TABLE_LOGICAL,
)

DEFAULT_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "RFP_Info_All-RFPs_wirh_ownerandpublich.csv",
)
PROGRESS_FILE = os.path.join(os.getcwd(), ".fix_owner_progress.json")

BAD_VALUES = {"Yes", "No"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clean_str(val) -> str:
    if pd.isna(val) or val is None:
        return ""
    s = str(val).strip()
    return "" if s.lower() == "nan" else s


def normalize_key(val: str) -> str:
    """Normalize RFP_ID for matching: lowercase + collapse all whitespace.
    e.g. 'SEC  RFP - C001482827' -> 'sec rfp - c001482827'
    """
    return re.sub(r"\s+", " ", val.strip().lower())


def load_progress() -> set:
    if not os.path.exists(PROGRESS_FILE):
        return set()
    try:
        with open(PROGRESS_FILE, "r") as f:
            return set(json.load(f).get("completed", []))
    except Exception:
        return set()


def save_progress(completed: set):
    with open(PROGRESS_FILE, "w") as f:
        json.dump({"completed": list(completed)}, f)


def clear_progress():
    if os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)
        print("  Progress file cleared.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def fix_owners(file_path: str, dry_run: bool = False):
    # Read CSV
    ext = os.path.splitext(file_path)[1].lower()
    if ext in (".xls", ".xlsx"):
        csv_df = pd.read_excel(file_path, dtype=str)
    else:
        csv_df = pd.read_csv(file_path, dtype=str)
    print(f"  Read {len(csv_df)} rows from {file_path}")

    # Build CSV lookup: {normalized_rfp_id: owner}
    csv_lookup = {}
    for _, row in csv_df.iterrows():
        rfp_id = clean_str(row.get("RFP_ID", ""))
        owner = clean_str(row.get("Owner", ""))
        if rfp_id and owner and owner not in BAD_VALUES:
            csv_lookup[normalize_key(rfp_id)] = owner

    print(f"  CSV entries with real owner names: {len(csv_lookup)}")

    # Connect to Dataverse
    dv = DataverseClient(TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL)

    # Fetch all DB rows
    print("  Fetching all RFP records from Dataverse...")
    db_rows = dv.get_all_rows(
        table_api_name=RFP_ACTIVITY_LOG_TABLE_API,
        select_columns=["RFP_ID", "owner_name"],
        table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL,
        use_display_names=True,
    )
    print(f"  Fetched {len(db_rows)} records from Dataverse")

    # Get primary key column
    try:
        colmap = dv.get_column_mapping(RFP_ACTIVITY_LOG_TABLE_LOGICAL)
        logical_to_display = {v: k for k, v in colmap.items()}
    except Exception:
        logical_to_display = {}
    pk_logical = f"{RFP_ACTIVITY_LOG_TABLE_LOGICAL}id"
    pk_display = logical_to_display.get(pk_logical, pk_logical)

    # Find ALL bad rows (Yes/No) — fix from CSV if available, otherwise clear to blank
    fixable = []
    for row in db_rows:
        rfp_id = row.get("RFP_ID", "")
        db_owner = str(row.get("owner_name", "") or "").strip()
        if db_owner not in BAD_VALUES:
            continue
        csv_owner = csv_lookup.get(normalize_key(rfp_id), "")
        record_id = row.get(pk_display) or row.get(pk_logical)
        fixable.append({
            "rfp_id": rfp_id,
            "record_id": record_id,
            "old_owner": db_owner,
            "new_owner": csv_owner if csv_owner else "",  # real name from CSV or blank
        })

    # Load resume progress (track by record_id since multiple records per RFP)
    completed = load_progress() if not dry_run else set()

    fix_from_csv = sum(1 for f in fixable if f["new_owner"])
    fix_to_blank = sum(1 for f in fixable if not f["new_owner"])

    print(f"\n{'='*60}")
    print(f"  FIX OWNER NAME (Yes/No -> Real Names or Blank)")
    print(f"{'='*60}")
    print(f"  Total bad (Yes/No) in DB:     {len(fixable)}")
    print(f"  Will fix from CSV:            {fix_from_csv}")
    print(f"  Will clear to blank:          {fix_to_blank}")
    print(f"  Already done (resume):        {len(completed)}")
    print(f"  Mode:                         {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"{'='*60}\n")

    updated = 0
    skipped = 0
    failed = 0

    for item in fixable:
        rfp_id = item["rfp_id"]
        record_id = item["record_id"]

        if record_id in completed:
            skipped += 1
            continue

        if dry_run:
            new_display = item["new_owner"] if item["new_owner"] else "(blank)"
            print(f'  [DRY] {rfp_id[:55]}  "{item["old_owner"]}" -> "{new_display}"')
            updated += 1
            continue

        try:
            success = dv.update_row(
                RFP_ACTIVITY_LOG_TABLE_API,
                record_id,
                {"owner_name": item["new_owner"]},
                table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL,
            )
            if success:
                updated += 1
                new_display = item["new_owner"] if item["new_owner"] else "(blank)"
                print(f'  [{updated}] {rfp_id[:55]}  "{item["old_owner"]}" -> "{new_display}"')
                completed.add(record_id)
                save_progress(completed)
            else:
                failed += 1
                print(f"  [FAIL] {rfp_id[:55]}")
        except Exception as e:
            failed += 1
            print(f"  [FAIL] {rfp_id[:55]}: {e}")

    print(f"\n{'='*60}")
    print(f"  FIX COMPLETE {'(DRY RUN)' if dry_run else ''}")
    print(f"{'='*60}")
    print(f"  Total fixed:      {updated}")
    print(f"  Skipped (resume): {skipped}")
    print(f"  Failed:           {failed}")
    print(f"{'='*60}\n")

    if not dry_run and failed == 0:
        clear_progress()
        print("  All done. Progress file removed.")


def main():
    parser = argparse.ArgumentParser(
        description="Fix owner_name where values are 'Yes'/'No' in Dataverse"
    )
    parser.add_argument(
        "--file", "-f", default=DEFAULT_FILE,
        help=f"Path to CSV file with Owner column. Default: {DEFAULT_FILE}",
    )
    parser.add_argument(
        "--dry-run", "-d", action="store_true",
        help="Preview changes without updating Dataverse",
    )
    parser.add_argument(
        "--reset", "-r", action="store_true",
        help="Clear progress and start fresh",
    )
    args = parser.parse_args()

    if args.reset:
        clear_progress()

    if not os.path.exists(args.file):
        print(f"  File not found: {args.file}")
        sys.exit(1)

    fix_owners(args.file, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
