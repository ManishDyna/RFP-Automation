"""
Fix missing publish_time in Dataverse RFP Activity Log.

Finds all RFPs where publish_time is empty in Dataverse and fills them
from the CSV file's Publish_Date column. Only updates empty values,
never overwrites existing dates.

Supports resume: tracks progress in a JSON file.

Usage:
  python fix_missing_publish_date.py                              # uses default CSV
  python fix_missing_publish_date.py --file path/to/file.csv      # custom file
  python fix_missing_publish_date.py --dry-run                     # preview without updating
  python fix_missing_publish_date.py --reset                       # clear progress and start fresh
"""

import argparse
import json
import os
import sys

import pandas as pd
import pytz

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
PROGRESS_FILE = os.path.join(os.getcwd(), ".fix_publish_progress.json")
KSA_TZ = pytz.timezone("Asia/Riyadh")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_date(val) -> str:
    """Parse any date format and return consistent 'M/D/YYYY H:MM AM/PM' string in KSA time."""
    if pd.isna(val) or str(val).strip() == "":
        return ""
    val = str(val).strip()
    try:
        if "-" in val and "/" not in val:
            parts = val.split(" ", 1)
            date_part = parts[0]
            time_part = parts[1] if len(parts) > 1 else "00:00:00"
            y, d, m = date_part.split("-")
            fixed = f"{y}-{m}-{d} {time_part}"
            dt = pd.to_datetime(fixed)
        else:
            dt = pd.to_datetime(val)
        if dt.tzinfo is not None:
            dt = dt.astimezone(KSA_TZ)
        return dt.strftime("%#m/%#d/%Y %#I:%M %p")
    except Exception:
        return str(val).strip()


def clean_str(val) -> str:
    if pd.isna(val) or val is None:
        return ""
    s = str(val).strip()
    return "" if s.lower() == "nan" else s


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

def fix_publish_dates(file_path: str, dry_run: bool = False):
    # Read CSV
    ext = os.path.splitext(file_path)[1].lower()
    if ext in (".xls", ".xlsx"):
        csv_df = pd.read_excel(file_path, dtype=str)
    else:
        csv_df = pd.read_csv(file_path, dtype=str)
    print(f"  Read {len(csv_df)} rows from {file_path}")

    # Build CSV lookup: {rfp_id: normalized_publish_date}
    csv_lookup = {}
    for _, row in csv_df.iterrows():
        rfp_id = clean_str(row.get("RFP_ID", ""))
        pub_val = clean_str(row.get("Publish_Date", ""))
        if rfp_id and pub_val:
            normalized = normalize_date(pub_val)
            if normalized:
                csv_lookup[rfp_id] = normalized

    print(f"  CSV entries with Publish_Date: {len(csv_lookup)}")

    # Connect to Dataverse
    dv = DataverseClient(TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL)

    # Fetch all DB rows
    print("  Fetching all RFP records from Dataverse...")
    db_rows = dv.get_all_rows(
        table_api_name=RFP_ACTIVITY_LOG_TABLE_API,
        select_columns=["RFP_ID", "publish_time"],
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

    # Find rows with empty publish_time that have a CSV value
    fixable = []
    for row in db_rows:
        rfp_id = row.get("RFP_ID", "")
        db_publish = str(row.get("publish_time", "") or "").strip()
        if db_publish:
            continue  # already has a value, skip
        csv_date = csv_lookup.get(rfp_id, "")
        if not csv_date:
            continue  # no CSV value either
        record_id = row.get(pk_display) or row.get(pk_logical)
        fixable.append({
            "rfp_id": rfp_id,
            "record_id": record_id,
            "new_date": csv_date,
        })

    # Load resume progress (track by record_id since multiple records per RFP)
    completed = load_progress() if not dry_run else set()

    total_empty = sum(1 for r in db_rows if not str(r.get("publish_time", "") or "").strip())

    print(f"\n{'='*60}")
    print(f"  FIX MISSING PUBLISH DATES")
    print(f"{'='*60}")
    print(f"  Total RFPs in DB:              {len(db_rows)}")
    print(f"  Missing publish_time:          {total_empty}")
    print(f"  Fixable records from CSV:      {len(fixable)}")
    print(f"  Already done (resume):         {len(completed)}")
    print(f"  Mode:                          {'DRY RUN' if dry_run else 'LIVE'}")
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
            print(f'  [DRY] {rfp_id[:55]}  -> "{item["new_date"]}"')
            updated += 1
            continue

        try:
            success = dv.update_row(
                RFP_ACTIVITY_LOG_TABLE_API,
                record_id,
                {"publish_time": item["new_date"]},
                table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL,
            )
            if success:
                updated += 1
                print(f'  [{updated}] {rfp_id[:55]}  -> "{item["new_date"]}"')
                completed.add(record_id)
                save_progress(completed)
            else:
                failed += 1
                print(f"  [FAIL] {rfp_id[:55]}")
        except Exception as e:
            failed += 1
            print(f"  [FAIL] {rfp_id[:55]}: {e}")

    print(f"\n{'='*60}")
    print(f"  COMPLETE {'(DRY RUN)' if dry_run else ''}")
    print(f"{'='*60}")
    print(f"  Updated:          {updated}")
    print(f"  Skipped (resume): {skipped}")
    print(f"  Failed:           {failed}")
    print(f"{'='*60}\n")

    if not dry_run and failed == 0:
        clear_progress()
        print("  All done. Progress file removed.")


def main():
    parser = argparse.ArgumentParser(
        description="Fix missing publish_time in Dataverse from CSV"
    )
    parser.add_argument(
        "--file", "-f", default=DEFAULT_FILE,
        help=f"Path to CSV file. Default: {DEFAULT_FILE}",
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

    fix_publish_dates(args.file, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
