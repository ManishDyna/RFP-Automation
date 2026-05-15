"""
Sync RFP Publish Date & Owner Name from RFP_Info CSV to Dataverse.

Reads the RFP_Info_All-RFPs.csv file and updates both 'publish_time' and
'owner_name' fields in the Dataverse RFP Activity Log table.

Matches file rows by RFP_ID.
Supports resume: tracks progress in a JSON file so if the script is
interrupted, it restarts from where it stopped.

Usage:
  python sync_rfp_publish_date.py                              # uses default CSV
  python sync_rfp_publish_date.py --file path/to/file.csv      # custom file
  python sync_rfp_publish_date.py --dry-run                     # preview without updating
  python sync_rfp_publish_date.py --reset                       # clear progress and start fresh
"""

import argparse
import json
import os
import re
import sys

import pandas as pd
import pytz

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers.dataverse_helper import DataverseClient
from config.config import (
    TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL,
    RFP_ACTIVITY_LOG_TABLE_API, RFP_ACTIVITY_LOG_TABLE_LOGICAL,
)

DEFAULT_FILE = os.path.join(os.getcwd(), "RFP_Info_All-RFPs.csv")

# Source column names in the CSV
SRC_COL_PUBLISH_DATE = "Publish_Date"
SRC_COL_OWNER = "Owner"
SRC_COL_RFP_ID = "RFP_ID"

# Dataverse display-name columns to update
DB_FIELD_PUBLISH = "publish_time"
DB_FIELD_OWNER = "owner_name"

# Progress tracking file (for resume support)
PROGRESS_FILE = os.path.join(os.getcwd(), ".sync_rfp_progress.json")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_key(val: str) -> str:
    """Normalize RFP_ID for matching: lowercase + collapse all whitespace.
    e.g. 'SEC  RFP - C001482827' -> 'sec rfp - c001482827'
    """
    return re.sub(r"\s+", " ", val.strip().lower())


def normalize_date(val) -> str:
    """Parse any date format and return ISO 8601 ('YYYY-MM-DDTHH:MM:SSZ').

    The publish_time column is now a DateTime field with TimeZoneIndependent
    behavior; Dataverse stores the wall-clock value literally so what we
    send is what users see in Power Apps (formatted as M/D/YYYY h:MM AM/PM).

    Handles:
      * ISO 8601 with T-separator: '2019-08-27T16:00:00Z'
      * Excel locale-swapped: 'YYYY-DD-MM HH:MM:SS'
      * MDY slash format: '10/6/2025 4:33 AM'
      * Other pandas-parseable formats
    """
    if pd.isna(val) or str(val).strip() == "":
        return ""
    val = str(val).strip()
    try:
        if "T" in val or val.endswith("Z"):
            dt = pd.to_datetime(val)
        elif "-" in val and "/" not in val:
            parts = val.split(" ", 1)
            date_part = parts[0]
            time_part = parts[1] if len(parts) > 1 else "00:00:00"
            y, d, m = date_part.split("-")
            fixed = f"{y}-{m}-{d} {time_part}"
            dt = pd.to_datetime(fixed)
        else:
            dt = pd.to_datetime(val)
        # Strip any tz so wall-clock numbers go out verbatim. The column's
        # TimeZoneIndependent behavior stores the value as-is (no UTC shift).
        if hasattr(dt, "tzinfo") and dt.tzinfo is not None:
            dt = dt.tz_localize(None) if hasattr(dt, "tz_localize") else dt.replace(tzinfo=None)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return str(val).strip()


def read_rfp_file(file_path: str) -> pd.DataFrame:
    """Read an RFP info file (Excel or CSV) as strings."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext in (".xls", ".xlsx"):
        df = pd.read_excel(file_path, dtype=str)
    elif ext == ".csv":
        df = pd.read_csv(file_path, dtype=str)
    else:
        raise ValueError(f"Unsupported file format: {ext}. Use .xls, .xlsx, or .csv")

    required = {SRC_COL_RFP_ID}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"File is missing required columns: {missing}. Found: {list(df.columns)}")

    print(f"  Read {len(df)} rows from {file_path}")
    return df


def load_progress() -> set:
    """Load set of already-updated RFP IDs from progress file."""
    if not os.path.exists(PROGRESS_FILE):
        return set()
    try:
        with open(PROGRESS_FILE, "r") as f:
            data = json.load(f)
        return set(data.get("completed", []))
    except Exception:
        return set()


def save_progress(completed: set):
    """Save completed RFP IDs to progress file."""
    with open(PROGRESS_FILE, "w") as f:
        json.dump({"completed": list(completed)}, f)


def clear_progress():
    """Remove the progress file to start fresh."""
    if os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)
        print("  Progress file cleared.")


def build_db_lookup(dataverse: DataverseClient) -> dict:
    """
    Fetch all RFP activity rows and build lookup.
    Returns: {rfp_id: {"record_id": ..., "publish_time": ..., "owner_name": ...}}
    """
    print("  Fetching all RFP records from Dataverse...")
    rows = dataverse.get_all_rows(
        table_api_name=RFP_ACTIVITY_LOG_TABLE_API,
        select_columns=["RFP_ID", DB_FIELD_PUBLISH, DB_FIELD_OWNER],
        table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL,
        use_display_names=True,
    )
    print(f"  Fetched {len(rows)} RFP records from Dataverse")

    try:
        colmap = dataverse.get_column_mapping(RFP_ACTIVITY_LOG_TABLE_LOGICAL)
        logical_to_display = {v: k for k, v in colmap.items()}
    except Exception:
        logical_to_display = {}

    pk_logical = f"{RFP_ACTIVITY_LOG_TABLE_LOGICAL}id"
    pk_display = logical_to_display.get(pk_logical, pk_logical)

    lookup = {}
    for row in rows:
        rfp_id = row.get("RFP_ID", "")
        if not rfp_id:
            continue

        record_id = row.get(pk_display) or row.get(pk_logical)
        lookup[normalize_key(rfp_id)] = {
            "record_id": record_id,
            DB_FIELD_PUBLISH: row.get(DB_FIELD_PUBLISH, "") or "",
            DB_FIELD_OWNER: row.get(DB_FIELD_OWNER, "") or "",
        }

    return lookup


# ---------------------------------------------------------------------------
# Main sync
# ---------------------------------------------------------------------------

def sync_rfp_data(file_path: str, dry_run: bool = False):
    """Read file, compare with DB, update publish_time and owner_name where needed."""
    df = read_rfp_file(file_path)

    dataverse = DataverseClient(
        tenant_id=TENANT_ID,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        resource_url=RESOURCE_URL,
    )

    db_lookup = build_db_lookup(dataverse)

    # Load resume progress
    completed = load_progress() if not dry_run else set()

    total = len(df)
    skipped_not_found = 0
    skipped_already_done = 0
    skipped_no_change = 0
    updated = 0
    failed = 0

    has_publish_col = SRC_COL_PUBLISH_DATE in df.columns
    has_owner_col = SRC_COL_OWNER in df.columns

    print(f"\n{'='*70}")
    print(f"  Sync RFP Publish Date & Owner Name to Dataverse")
    print(f"  File:             {file_path}")
    print(f"  Publish col:      {SRC_COL_PUBLISH_DATE} {'(found)' if has_publish_col else '(NOT in file)'}")
    print(f"  Owner col:        {SRC_COL_OWNER} {'(found)' if has_owner_col else '(NOT in file)'}")
    print(f"  Mode:             {'DRY RUN (no changes)' if dry_run else 'LIVE'}")
    print(f"  Total in file:    {total}")
    print(f"  Total in DB:      {len(db_lookup)}")
    print(f"  Already done:     {len(completed)} (resume)")
    print(f"{'='*70}\n")

    for idx, row in df.iterrows():
        rfp_id = str(row.get(SRC_COL_RFP_ID, "")).strip()
        if not rfp_id:
            continue

        rfp_key = normalize_key(rfp_id)

        # Resume: skip already completed
        if rfp_key in completed:
            skipped_already_done += 1
            continue

        db_entry = db_lookup.get(rfp_key)
        if not db_entry:
            skipped_not_found += 1
            continue

        record_id = db_entry["record_id"]
        update_data = {}

        # Check publish_time. Both new_date and old_date are ISO 8601 now (DB
        # column is DateTime). Compare via parsed datetimes to avoid spurious
        # diffs from sub-second precision or differing 'Z' notations.
        if has_publish_col:
            file_publish = row.get(SRC_COL_PUBLISH_DATE, "")
            new_date = normalize_date(file_publish)
            old_date = db_entry[DB_FIELD_PUBLISH]
            if new_date:
                try:
                    new_dt = pd.to_datetime(new_date, errors="coerce")
                    old_dt = pd.to_datetime(old_date, errors="coerce") if old_date else None
                    # Compare wall-clock only (drop tz on both sides)
                    if new_dt is not None and hasattr(new_dt, "tzinfo") and new_dt.tzinfo is not None:
                        new_dt = new_dt.tz_localize(None)
                    if old_dt is not None and hasattr(old_dt, "tzinfo") and old_dt.tzinfo is not None:
                        old_dt = old_dt.tz_localize(None)
                    if old_dt is None or pd.isna(old_dt) or new_dt != old_dt:
                        update_data[DB_FIELD_PUBLISH] = new_date
                except Exception:
                    # Fallback to string compare if parsing somehow fails
                    if new_date != old_date:
                        update_data[DB_FIELD_PUBLISH] = new_date

        # Check owner_name
        if has_owner_col:
            file_owner = str(row.get(SRC_COL_OWNER, "") or "").strip()
            old_owner = db_entry[DB_FIELD_OWNER]
            if file_owner and file_owner != "nan" and file_owner != old_owner:
                update_data[DB_FIELD_OWNER] = file_owner

        if not update_data:
            skipped_no_change += 1
            # Mark as done even if no change needed (so resume skips it)
            if not dry_run:
                completed.add(rfp_key)
                save_progress(completed)
            continue

        if dry_run:
            changes = ", ".join(f"{k}: '{db_entry[k]}' -> '{v}'" for k, v in update_data.items())
            print(f"  [DRY] {rfp_id}: {changes}")
            updated += 1
            continue

        try:
            success = dataverse.update_row(
                RFP_ACTIVITY_LOG_TABLE_API,
                record_id,
                update_data,
                table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL,
            )
            if success:
                updated += 1
                changes = ", ".join(f"{k}: '{db_entry[k]}' -> '{v}'" for k, v in update_data.items())
                print(f"  [{updated}] {rfp_id}: {changes}")
                completed.add(rfp_key)
                save_progress(completed)
            else:
                failed += 1
                print(f"  [FAIL] {rfp_id}: UPDATE FAILED")
        except Exception as e:
            failed += 1
            print(f"  [FAIL] {rfp_id}: {e}")

    print(f"\n{'='*70}")
    print(f"  SYNC COMPLETE {'(DRY RUN)' if dry_run else ''}")
    print(f"{'='*70}")
    print(f"  Total in file:           {total}")
    print(f"  Updated:                 {updated}")
    print(f"  Skipped (not in DB):     {skipped_not_found}")
    print(f"  Skipped (no change):     {skipped_no_change}")
    print(f"  Skipped (already done):  {skipped_already_done}")
    print(f"  Failed:                  {failed}")
    print(f"{'='*70}\n")

    # Clean up progress file on full completion (no failures)
    if not dry_run and failed == 0:
        clear_progress()
        print("  All done. Progress file removed.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Sync RFP Publish Date & Owner Name from RFP_Info CSV to Dataverse"
    )
    parser.add_argument(
        "--file", "-f",
        default=DEFAULT_FILE,
        help=f"Path to RFP info file (.xls, .xlsx, or .csv). Default: {DEFAULT_FILE}",
    )
    parser.add_argument(
        "--dry-run", "-d",
        action="store_true",
        help="Preview changes without actually updating Dataverse",
    )
    parser.add_argument(
        "--reset", "-r",
        action="store_true",
        help="Clear progress file and start fresh from the beginning",
    )
    args = parser.parse_args()

    if args.reset:
        clear_progress()

    if not os.path.exists(args.file):
        print(f"  File not found: {args.file}")
        sys.exit(1)

    sync_rfp_data(args.file, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
