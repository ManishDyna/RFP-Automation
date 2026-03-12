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
  python compare_rfp_dates.py --file path/to/file.xls
"""

import argparse
import os
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


def normalize_date(val) -> str:
    """Parse any date format and return 'MM/DD/YYYY HH:MM AM/PM' string."""
    if pd.isna(val) or str(val).strip() == "":
        return ""
    val = str(val).strip()
    try:
        if "-" in val and "/" not in val:
            # Dash format: YYYY-DD-MM HH:MM:SS (day/month swapped by Excel)
            parts = val.split(" ", 1)
            date_part = parts[0]
            time_part = parts[1] if len(parts) > 1 else "00:00:00"
            y, d, m = date_part.split("-")
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


def fetch_db_dates(dataverse: DataverseClient) -> dict:
    """Fetch all RFP_End_Date values from Dataverse. Returns {rfp_id: end_date_str}."""
    logger.info("Fetching RFP end dates from Dataverse...")
    rows = dataverse.get_all_rows(
        table_api_name=RFP_ACTIVITY_LOG_TABLE_API,
        select_columns=["RFP_ID", "RFP_End_Date"],
        table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL,
        use_display_names=True,
    )
    logger.info(f"Fetched {len(rows)} records from Dataverse")

    lookup = {}
    for row in rows:
        rfp_id = row.get("RFP_ID", "")
        if rfp_id:
            lookup[rfp_id] = row.get("RFP_End_Date", "") or ""
    return lookup


def run(file_path: str):
    """Main logic: read Excel, normalize, fetch DB, compare, save."""
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

    # Map DB dates into a column using Title → RFP_ID
    df["db_end_date"] = df["Title"].apply(lambda t: db_lookup.get(str(t).strip(), ""))

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


def main():
    parser = argparse.ArgumentParser(
        description="Compare RFP End Dates: Excel vs Dataverse"
    )
    parser.add_argument(
        "--file", "-f",
        default=DEFAULT_FILE,
        help=f"Path to ALL-RFPs file. Default: {DEFAULT_FILE}",
    )
    args = parser.parse_args()

    if not os.path.exists(args.file):
        logger.error(f"File not found: {args.file}")
        sys.exit(1)

    run(args.file)


if __name__ == "__main__":
    main()
