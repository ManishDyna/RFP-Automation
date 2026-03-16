"""
Compare RFP End Dates: Excel (Portal) vs Dataverse Database.

Steps:
  1. Normalize "End Time" column → "normalized_dates" (MM/DD/YYYY HH:MM AM/PM)
  2. Fetch RFP_End_Date from Dataverse
  3. Compare normalized_dates with DB → "check_with_normalize_date" (match / not match)
  4. Add 2h30m to normalized_dates → "converted_dates"
  5. Compare converted_dates with DB → "check_with_converted_date" (match / not match)

Usage:
  python compare_rfp_dates.py
  python compare_rfp_dates.py --file path/to/file.csv
  python compare_rfp_dates.py --file path/to/file.csv --update            # dry-run
  python compare_rfp_dates.py --file path/to/file.csv --update --confirm  # actual update
"""

import argparse
import json
import os
import re
import sys
import logging
from datetime import timedelta

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
PROGRESS_FILE = os.path.join(os.getcwd(), "ALLRFPs", "Portal-Rfps", "update_progress.json")


def load_progress() -> set:
    """Load set of already-updated record IDs from progress file."""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            data = json.load(f)
        logger.info(f"Resuming: {len(data)} records already updated (from {PROGRESS_FILE})")
        return set(data)
    return set()


def save_progress(updated_ids: set):
    """Save updated record IDs to progress file."""
    with open(PROGRESS_FILE, "w") as f:
        json.dump(list(updated_ids), f)


def clear_progress():
    """Remove progress file after successful completion."""
    if os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)
        logger.info("Progress file cleared — all updates complete.")


def normalize_date(val) -> str:
    """Parse any date format and return 'MM/DD/YYYY HH:MM AM/PM' string."""
    if pd.isna(val) or str(val).strip() == "":
        return ""
    val = str(val).strip()
    try:
        if "-" in val and "/" not in val:
            # Dash format: MM-DD-YYYY HH:MM (24h) from portal export
            parts = val.split(" ", 1)
            date_part = parts[0]
            time_part = parts[1] if len(parts) > 1 else "00:00"
            m, d, y = date_part.split("-")
            fixed = f"{y}-{m}-{d} {time_part}"
            dt = pd.to_datetime(fixed)
        else:
            dt = pd.to_datetime(val)
        return dt.strftime("%m/%d/%Y %I:%M %p")
    except Exception:
        return str(val).strip()


def parse_to_datetime(date_str: str):
    """Parse a date string to datetime object, return None on failure."""
    if not date_str or not date_str.strip():
        return None
    try:
        return pd.to_datetime(date_str.strip())
    except Exception:
        return None


def add_time(date_str: str, hours: int, minutes: int) -> str:
    """Add hours and minutes to a date string, return formatted string."""
    dt = parse_to_datetime(date_str)
    if dt is None:
        return ""
    dt = dt + timedelta(hours=hours, minutes=minutes)
    return dt.strftime("%m/%d/%Y %I:%M %p")


def dates_match(date_str_a: str, date_str_b: str) -> bool:
    """Compare two date strings as datetime objects (ignoring formatting differences)."""
    dt_a = parse_to_datetime(date_str_a)
    dt_b = parse_to_datetime(date_str_b)
    if dt_a is None or dt_b is None:
        return False
    return dt_a == dt_b


GUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)


def fetch_db_dates(dataverse: DataverseClient) -> dict:
    """Fetch all RFP_End_Date values from Dataverse. Returns {rfp_id: [{"end_date": str, "record_id": str}, ...]}."""
    logger.info("Fetching RFP end dates from Dataverse...")
    rows = dataverse.get_all_rows(
        table_api_name=RFP_ACTIVITY_LOG_TABLE_API,
        select_columns=["RFP_ID", "RFP_End_Date"],
        table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL,
        use_display_names=True,
    )
    logger.info(f"Fetched {len(rows)} records from Dataverse")

    # Log sample row keys for debugging
    if rows:
        logger.info(f"Sample row keys: {list(rows[0].keys())[:15]}")

    lookup = {}
    for row in rows:
        rfp_id = row.get("RFP_ID", "")
        if rfp_id:
            # Find the primary key GUID value in the row
            record_id = ""
            for key, val in row.items():
                if isinstance(val, str) and GUID_PATTERN.match(val) and key != "RFP_ID":
                    record_id = val
                    break
            entry = {
                "end_date": row.get("RFP_End_Date", "") or "",
                "record_id": record_id,
            }
            if rfp_id not in lookup:
                lookup[rfp_id] = []
            lookup[rfp_id].append(entry)
    return lookup


def run(file_path: str, update: bool = False, confirm: bool = False):
    """Main logic: read Excel, normalize, fetch DB, compare, save. Optionally update DB."""
    # --- Read Excel ---
    ext = os.path.splitext(file_path)[1].lower()
    if ext in (".xls", ".xlsx"):
        df = pd.read_excel(file_path)
    elif ext == ".csv":
        df = pd.read_csv(file_path)
    else:
        raise ValueError(f"Unsupported file format: {ext}")

    logger.info(f"Read {len(df)} rows from {file_path}")

    # --- Step 1: Normalize End Time → normalized_dates ---
    df["normalized_dates"] = df["End Time"].apply(normalize_date)
    logger.info("Step 1 done: normalized_dates column created")

    # --- Step 2: Fetch DB dates ---
    dataverse = DataverseClient(
        tenant_id=TENANT_ID,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        resource_url=RESOURCE_URL,
    )
    db_lookup = fetch_db_dates(dataverse)

    # Map DB dates and record IDs into columns using Title → RFP_ID
    # Use first record's end_date for comparison; store ALL record GUIDs for updates
    df["db_end_date"] = df["Title"].apply(
        lambda t: db_lookup.get(str(t).strip(), [{}])[0].get("end_date", "")
    )
    df["db_record_ids"] = df["Title"].apply(
        lambda t: [r["record_id"] for r in db_lookup.get(str(t).strip(), []) if r.get("record_id")]
    )

    # --- Step 3: Compare normalized_dates vs db_end_date → check_with_normalize_date ---
    df["check_with_normalize_date"] = df.apply(
        lambda row: "match" if dates_match(row["normalized_dates"], row["db_end_date"])
        else "not match",
        axis=1,
    )
    match_count_1 = (df["check_with_normalize_date"] == "match").sum()
    logger.info(f"Step 3 done: {match_count_1} match, {len(df) - match_count_1} not match")

    # --- Step 4: Add 2h30m to normalized_dates → converted_dates ---
    df["converted_dates"] = df["normalized_dates"].apply(
        lambda d: add_time(d, hours=2, minutes=30)
    )
    logger.info("Step 4 done: converted_dates column created (+2h30m)")

    # --- Step 5: Compare converted_dates vs db_end_date → check_with_converted_date ---
    df["check_with_converted_date"] = df.apply(
        lambda row: "match" if dates_match(row["converted_dates"], row["db_end_date"])
        else "not match",
        axis=1,
    )
    match_count_2 = (df["check_with_converted_date"] == "match").sum()
    logger.info(f"Step 5 done: {match_count_2} match, {len(df) - match_count_2} not match")

    # --- Save output ---
    output_dir = os.path.dirname(file_path)
    output_file = os.path.join(output_dir, "All-RFPs-compared.xlsx")
    df.to_excel(output_file, index=False)
    logger.info(f"Saved to {output_file}")

    # --- Summary ---
    print(f"\n{'='*70}")
    print(f"  RFP Date Comparison Complete")
    print(f"{'='*70}")
    print(f"  Total rows:                          {len(df)}")
    print(f"  Rows found in DB:                    {(df['db_end_date'] != '').sum()}")
    print(f"  Rows NOT in DB:                      {(df['db_end_date'] == '').sum()}")
    print(f"  ---")
    print(f"  Normalized vs DB — match:            {match_count_1}")
    print(f"  Normalized vs DB — not match:        {len(df) - match_count_1}")
    print(f"  ---")
    print(f"  Converted (+2h30m) vs DB — match:    {match_count_2}")
    print(f"  Converted (+2h30m) vs DB — not match:{len(df) - match_count_2}")
    print(f"{'='*70}")
    print(f"  Output: {output_file}")
    print(f"{'='*70}\n")

    # --- Step 6 (optional): Update mismatched dates in Dataverse ---
    if update:
        mismatched = df[
            (df["check_with_normalize_date"] == "not match") &
            (df["db_record_ids"].apply(len) > 0) &
            (df["normalized_dates"] != "")
        ].copy()

        if mismatched.empty:
            print("No mismatched rows with valid DB records to update.")
            return

        total_records = mismatched["db_record_ids"].apply(len).sum()
        print(f"\n{'='*70}")
        print(f"  {'DRY-RUN: ' if not confirm else ''}Update {len(mismatched)} RFPs ({total_records} total DB records)")
        print(f"{'='*70}")
        print(f"  {'Title':<50} {'Records':<8} {'DB Date':<22} {'New Date':<22}")
        print(f"  {'-'*50} {'-'*8} {'-'*22} {'-'*22}")
        for _, row in mismatched.iterrows():
            title = str(row["Title"])[:50]
            num_records = len(row["db_record_ids"])
            print(f"  {title:<50} {num_records:<8} {row['db_end_date']:<22} {row['normalized_dates']:<22}")
        print(f"{'='*70}")

        if not confirm:
            print("\n  This is a DRY-RUN. No changes were made.")
            print("  Add --confirm to actually update the database.\n")
            return

        # Actual update — update ALL duplicate records for each RFP
        # Load progress to skip already-updated records (resume support)
        already_updated = load_progress()
        success_count = 0
        skipped_count = 0
        fail_count = 0
        for _, row in mismatched.iterrows():
            title = str(row["Title"]).strip()
            new_date = row["normalized_dates"]
            for record_id in row["db_record_ids"]:
                if record_id in already_updated:
                    skipped_count += 1
                    continue
                try:
                    dataverse.update_row(
                        table_api_name=RFP_ACTIVITY_LOG_TABLE_API,
                        record_id=record_id,
                        data={"RFP_End_Date": new_date},
                        table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL,
                        use_display_names=True,
                    )
                    success_count += 1
                    already_updated.add(record_id)
                    save_progress(already_updated)
                    logger.info(f"Updated [{success_count + skipped_count}/{total_records}]: {title} -> {new_date}")
                except Exception as e:
                    fail_count += 1
                    logger.error(f"Failed to update {title} (record {record_id}): {e}")

        if skipped_count:
            print(f"\n  Skipped {skipped_count} already-updated records (resumed).")
        print(f"  Update complete: {success_count} succeeded, {fail_count} failed.\n")

        # Clear progress file if everything succeeded
        if fail_count == 0:
            clear_progress()


def main():
    parser = argparse.ArgumentParser(
        description="Compare RFP End Dates: Excel vs Dataverse"
    )
    parser.add_argument(
        "--file", "-f",
        default=DEFAULT_FILE,
        help=f"Path to ALL-RFPs file. Default: {DEFAULT_FILE}",
    )
    parser.add_argument(
        "--update", action="store_true",
        help="Update mismatched RFP_End_Date values in Dataverse (dry-run by default)",
    )
    parser.add_argument(
        "--confirm", action="store_true",
        help="Actually apply updates to Dataverse (requires --update)",
    )
    args = parser.parse_args()

    if args.confirm and not args.update:
        logger.error("--confirm requires --update")
        sys.exit(1)

    if not os.path.exists(args.file):
        logger.error(f"File not found: {args.file}")
        sys.exit(1)

    run(args.file, update=args.update, confirm=args.confirm)


if __name__ == "__main__":
    main()
