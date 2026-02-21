"""
Sync RFP End Date from ALL-RFPs File to Dataverse.

Reads an ALL-RFPs file (Excel .xls/.xlsx or CSV) and updates the
'RFP_End_Date' field in the Dataverse RFP Activity Log table.

Matches file rows by Title → DB RFP_ID.
Updates only the RFP_End_Date field, nothing else.

Usage:
  python sync_rfp_end_date.py                           # uses default All-RFPs.xls
  python sync_rfp_end_date.py --file path/to/file.xls   # custom file
  python sync_rfp_end_date.py --dry-run                  # preview without updating
"""

import argparse
import os
import sys
import logging

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers.dataverse_helper import DataverseClient
from config.config import (
    TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL,
    RFP_ACTIVITY_LOG_TABLE_API, RFP_ACTIVITY_LOG_TABLE_LOGICAL,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

DEFAULT_FILE = os.path.join(os.getcwd(), "ALLRFPs", "Portal-Rfps", "All-RFPs.xls")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_date(val) -> str:
    """Parse any date format from the Excel file and return consistent 'MM/DD/YYYY HH:MM AM/PM' string.

    Handles two formats found in portal Excel files:
      - Slash format: 'MM/DD/YYYY HH:MM AM/PM' → parse directly (already correct)
      - Dash format:  'YYYY-DD-MM HH:MM:SS'    → day and month are swapped by Excel
        (portal uses DD/MM but Excel with US locale stored them as MM/DD datetime,
         so the YYYY-MM-DD string actually has day in month position and vice-versa)
    """
    if pd.isna(val) or str(val).strip() == "":
        return ""
    val = str(val).strip()
    try:
        if "-" in val and "/" not in val:
            # Dash format: YYYY-DD-MM HH:MM:SS (day/month swapped by Excel)
            parts = val.split(" ", 1)
            date_part = parts[0]                        # e.g. 2026-04-02
            time_part = parts[1] if len(parts) > 1 else "00:00:00"
            y, d, m = date_part.split("-")              # swap: treat as YYYY-DD-MM
            fixed = f"{y}-{m}-{d} {time_part}"          # → YYYY-MM-DD HH:MM:SS
            dt = pd.to_datetime(fixed)
        else:
            # Slash format: MM/DD/YYYY HH:MM AM/PM → already correct
            dt = pd.to_datetime(val)
        return dt.strftime("%m/%d/%Y %I:%M %p")
    except Exception:
        return str(val).strip()


def read_rfp_file(file_path: str) -> pd.DataFrame:
    """Read an ALL-RFPs file (Excel or CSV). Read all columns as strings to preserve date format."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext in (".xls", ".xlsx"):
        df = pd.read_excel(file_path, dtype=str)
    elif ext == ".csv":
        df = pd.read_csv(file_path, dtype=str)
    else:
        raise ValueError(f"Unsupported file format: {ext}. Use .xls, .xlsx, or .csv")

    required = {"Title", "End Time"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"File is missing required columns: {missing}. Found: {list(df.columns)}")

    logger.info(f"Read {len(df)} rows from {file_path}")
    return df


def build_db_lookup(dataverse: DataverseClient) -> dict:
    """
    Fetch all RFP activity rows and build lookup.
    Returns: {rfp_id: {"record_id": ..., "RFP_End_Date": ...}}
    """
    logger.info("Fetching all RFP records from Dataverse...")
    rows = dataverse.get_all_rows(
        table_api_name=RFP_ACTIVITY_LOG_TABLE_API,
        select_columns=["RFP_ID", "RFP_End_Date"],
        table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL,
        use_display_names=True,
    )
    logger.info(f"Fetched {len(rows)} RFP records from Dataverse")

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
        end_date = row.get("RFP_End_Date", "") or ""

        lookup[rfp_id] = {
            "record_id": record_id,
            "RFP_End_Date": end_date,
        }

    return lookup


# ---------------------------------------------------------------------------
# Main sync
# ---------------------------------------------------------------------------

def sync_end_dates(file_path: str, dry_run: bool = False):
    """Read file, compare with DB, update RFP_End_Date where needed."""
    df = read_rfp_file(file_path)

    dataverse = DataverseClient(
        tenant_id=TENANT_ID,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        resource_url=RESOURCE_URL,
    )

    db_lookup = build_db_lookup(dataverse)

    total = len(df)
    skipped_not_found = 0
    updated = 0
    failed = 0

    logger.info(f"{'DRY RUN - ' if dry_run else ''}Starting sync of {total} RFPs...")
    print(f"\n{'='*70}")
    print(f"  Sync RFP End Date to Dataverse")
    print(f"  File: {file_path}")
    print(f"  Mode: {'DRY RUN (no changes)' if dry_run else 'LIVE'}")
    print(f"  Total RFPs in file: {total}")
    print(f"  Total RFPs in DB:   {len(db_lookup)}")
    print(f"{'='*70}\n")

    for idx, row in df.iterrows():
        rfp_id = str(row.get("Title", "")).strip()
        file_end_time = row.get("End Time", "")

        if not rfp_id:
            continue

        new_date = normalize_date(file_end_time)
        if not new_date:
            continue

        db_entry = db_lookup.get(rfp_id)
        if not db_entry:
            skipped_not_found += 1
            logger.debug(f"  [{idx+1}/{total}] {rfp_id} — NOT FOUND in DB, skipping")
            continue

        old_date = db_entry["RFP_End_Date"] or ""
        record_id = db_entry["record_id"]

        if dry_run:
            print(f"  [DRY] {rfp_id}: '{old_date}' -> '{new_date}'")
            updated += 1
            continue

        # Update only RFP_End_Date field
        try:
            update_data = {"RFP_End_Date": new_date}
            success = dataverse.update_row(
                RFP_ACTIVITY_LOG_TABLE_API,
                record_id,
                update_data,
                table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL,
            )
            if success:
                updated += 1
                logger.info(f"  [{idx+1}/{total}] {rfp_id}: '{old_date}' -> '{new_date}'")
            else:
                failed += 1
                logger.error(f"  [{idx+1}/{total}] {rfp_id}: UPDATE FAILED")
        except Exception as e:
            failed += 1
            logger.error(f"  [{idx+1}/{total}] {rfp_id}: ERROR — {e}")

    print(f"\n{'='*70}")
    print(f"  SYNC COMPLETE {'(DRY RUN)' if dry_run else ''}")
    print(f"{'='*70}")
    print(f"  Total in file:           {total}")
    print(f"  Updated:                 {updated}")
    print(f"  Skipped (not in DB):     {skipped_not_found}")
    print(f"  Failed:                  {failed}")
    print(f"{'='*70}\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Sync RFP End Date from ALL-RFPs file to Dataverse"
    )
    parser.add_argument(
        "--file", "-f",
        default=DEFAULT_FILE,
        help=f"Path to ALL-RFPs file (.xls, .xlsx, or .csv). Default: {DEFAULT_FILE}",
    )
    parser.add_argument(
        "--dry-run", "-d",
        action="store_true",
        help="Preview changes without actually updating Dataverse",
    )
    args = parser.parse_args()

    if not os.path.exists(args.file):
        logger.error(f"File not found: {args.file}")
        sys.exit(1)

    sync_end_dates(args.file, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
