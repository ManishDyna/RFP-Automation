"""
Sync Participant Status from ALL-RFPs File to Dataverse.

Reads an ALL-RFPs file (Excel .xls/.xlsx or CSV) and updates the
'participated' field in the Dataverse RFP Activity Log table.

Logic:
  - File "Yes"      → DB "submitted"
  - File "Declined" → DB "declined"
  - File "No"       → DB "no"  (blank in DB is also treated as "no")
  - Skip if DB already has the same normalized status.
  - Update if different (including DB blank → file has a real status).

Usage:
  python sync_participant_status.py                           # uses default All-RFPs.xls
  python sync_participant_status.py --file path/to/file.xls   # custom file
  python sync_participant_status.py --file path/to/file.csv   # CSV also supported
  python sync_participant_status.py --dry-run                  # preview without updating
"""

import argparse
import os
import sys
import logging
from datetime import datetime

import pandas as pd

# Add project root to path
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

# Default file path
DEFAULT_FILE = os.path.join(os.getcwd(), "ALLRFPs", "Portal-Rfps", "All-RFPs.xls")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_participated(val) -> str:
    """Normalize participated value for comparison (mirrors automation_logic._normalize_participated)."""
    v = (str(val) if pd.notna(val) else "").strip().lower()
    if v in ("no", "not participated", "open", ""):
        return "no"
    if v in ("yes", "submitted", "participated"):
        return "submitted"
    if v in ("declined", "no bid"):
        return "declined"
    if v in ("saved_draft", "saved draft", "draft"):
        return "saved_draft"
    return v or "no"


def read_rfp_file(file_path: str) -> pd.DataFrame:
    """Read an ALL-RFPs file (Excel or CSV). Returns DataFrame with columns: Title, Participated."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext in (".xls", ".xlsx"):
        df = pd.read_excel(file_path)
    elif ext == ".csv":
        df = pd.read_csv(file_path)
    else:
        raise ValueError(f"Unsupported file format: {ext}. Use .xls, .xlsx, or .csv")

    # Validate required columns — Title is the RFP identifier that matches DB RFP_ID
    required = {"Title", "Participated"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"File is missing required columns: {missing}. Found: {list(df.columns)}")

    logger.info(f"Read {len(df)} rows from {file_path}")
    return df


def build_db_lookup(dataverse: DataverseClient) -> dict:
    """
    Fetch all RFP activity rows from Dataverse and build a lookup dict.
    Returns: {rfp_id: {"record_id": ..., "participated": ...}}
    """
    logger.info("Fetching all RFP records from Dataverse...")
    rows = dataverse.get_all_rows(
        table_api_name=RFP_ACTIVITY_LOG_TABLE_API,
        select_columns=["RFP_ID", "participated"],
        table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL,
        use_display_names=True,
    )
    logger.info(f"Fetched {len(rows)} RFP records from Dataverse")

    # Build reverse map for primary key lookup
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
        participated = row.get("participated", "") or ""

        lookup[rfp_id] = {
            "record_id": record_id,
            "participated": participated,
        }

    return lookup


# ---------------------------------------------------------------------------
# Main sync logic
# ---------------------------------------------------------------------------

def sync_statuses(file_path: str, dry_run: bool = False):
    """Main sync: read file, compare with DB, update where needed."""
    # Read file
    df = read_rfp_file(file_path)

    # Connect to Dataverse
    dataverse = DataverseClient(
        tenant_id=TENANT_ID,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        resource_url=RESOURCE_URL,
    )

    # Build DB lookup
    db_lookup = build_db_lookup(dataverse)

    # Get column mapping for status change logging
    from helpers.core_helper import log_rfp_status_change

    # Counters
    total = len(df)
    skipped_not_found = 0
    updated = 0
    failed = 0

    logger.info(f"{'DRY RUN - ' if dry_run else ''}Starting sync of {total} RFPs...")
    print(f"\n{'='*70}")
    print(f"  Sync Participant Status to Dataverse")
    print(f"  File: {file_path}")
    print(f"  Mode: {'DRY RUN (no changes)' if dry_run else 'LIVE'}")
    print(f"  Total RFPs in file: {total}")
    print(f"  Total RFPs in DB:   {len(db_lookup)}")
    print(f"{'='*70}\n")

    for idx, row in df.iterrows():
        rfp_id = str(row.get("Title", "")).strip()
        file_status_raw = row.get("Participated", "")

        if not rfp_id:
            continue

        # Normalize file status for DB (Yes→submitted, No→no, Declined→declined)
        new_status = normalize_participated(file_status_raw)

        # Look up in DB
        db_entry = db_lookup.get(rfp_id)
        if not db_entry:
            skipped_not_found += 1
            logger.debug(f"  [{idx+1}/{total}] {rfp_id} — NOT FOUND in DB, skipping")
            continue

        old_status = db_entry["participated"] or ""
        record_id = db_entry["record_id"]

        if dry_run:
            print(f"  [DRY] {rfp_id}: '{old_status}' → '{new_status}'")
            updated += 1
            continue

        # Update DB with file status — no comparison, always overwrite
        try:
            update_data = {"participated": new_status}
            success = dataverse.update_row(
                RFP_ACTIVITY_LOG_TABLE_API,
                record_id,
                update_data,
                table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL,
            )
            if success:
                updated += 1
                logger.info(f"  [{idx+1}/{total}] {rfp_id}: '{old_status}' → '{new_status}'")

                # Log status change if status actually changed
                if old_status.lower().strip() != new_status.lower().strip():
                    try:
                        log_rfp_status_change(rfp_id, old_status, new_status, "synced from portal")
                    except Exception as e:
                        logger.warning(f"  Could not log status change for {rfp_id}: {e}")
            else:
                failed += 1
                logger.error(f"  [{idx+1}/{total}] {rfp_id}: UPDATE FAILED")
        except Exception as e:
            failed += 1
            logger.error(f"  [{idx+1}/{total}] {rfp_id}: ERROR — {e}")

    # Summary
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
        description="Sync participant status from ALL-RFPs file to Dataverse"
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

    sync_statuses(args.file, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
