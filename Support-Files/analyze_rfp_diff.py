"""
Analyze differences between RFP_Info CSV and Dataverse RFP Activity Log.

Compares three fields: Owner Name, Publish Date, and Due Date.
Generates a CSV report showing missing values and mismatches.

Supports resume: tracks progress in a JSON file so if the script is
interrupted, it restarts from where it stopped.

Usage:
  python analyze_rfp_diff.py                          # uses default CSV
  python analyze_rfp_diff.py --file path/to/file.csv  # custom file
  python analyze_rfp_diff.py --output report.csv      # custom output path
  python analyze_rfp_diff.py --reset                   # clear progress and start fresh
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

DEFAULT_FILE = os.path.join(os.getcwd(), "RFP_Info_All-RFPs.csv")
DEFAULT_OUTPUT = os.path.join(os.getcwd(), "rfp_diff_report.csv")
PROGRESS_FILE = os.path.join(os.getcwd(), ".analyze_rfp_progress.json")

# CSV column names
CSV_COL_RFP_ID = "RFP_ID"
CSV_COL_PUBLISH_DATE = "Publish_Date"
CSV_COL_OWNER = "Owner"
CSV_COL_DUE_DATE = "End Time"

# Dataverse display-name columns
DB_COL_PUBLISH = "publish_time"
DB_COL_OWNER = "owner_name"
DB_COL_DUE_DATE = "RFP_End_Date"

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
    """Return cleaned string or empty string for NaN/None."""
    if pd.isna(val) or val is None:
        return ""
    s = str(val).strip()
    return "" if s.lower() == "nan" else s


def read_rfp_file(file_path: str) -> pd.DataFrame:
    """Read an RFP info file (Excel or CSV) as strings."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext in (".xls", ".xlsx"):
        df = pd.read_excel(file_path, dtype=str)
    elif ext == ".csv":
        df = pd.read_csv(file_path, dtype=str)
    else:
        raise ValueError(f"Unsupported file format: {ext}. Use .xls, .xlsx, or .csv")

    if CSV_COL_RFP_ID not in df.columns:
        raise ValueError(f"File is missing required column: {CSV_COL_RFP_ID}. Found: {list(df.columns)}")

    print(f"  Read {len(df)} rows from {file_path}")
    return df


def load_progress() -> dict:
    """Load progress: completed RFP IDs and their result rows."""
    if not os.path.exists(PROGRESS_FILE):
        return {"completed": [], "rows": []}
    try:
        with open(PROGRESS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"completed": [], "rows": []}


def save_progress(completed: list, rows: list):
    """Save completed RFP IDs and their result rows to progress file."""
    with open(PROGRESS_FILE, "w") as f:
        json.dump({"completed": completed, "rows": rows}, f)


def clear_progress():
    """Remove the progress file to start fresh."""
    if os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)
        print("  Progress file cleared.")


def fetch_db_records(dataverse: DataverseClient) -> dict:
    """Fetch all RFP records from Dataverse. Returns {rfp_id: {field: value}}."""
    print("  Fetching all RFP records from Dataverse...")
    rows = dataverse.get_all_rows(
        table_api_name=RFP_ACTIVITY_LOG_TABLE_API,
        select_columns=["RFP_ID", DB_COL_PUBLISH, DB_COL_OWNER, DB_COL_DUE_DATE],
        table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL,
        use_display_names=True,
    )
    print(f"  Fetched {len(rows)} records from Dataverse")

    lookup = {}
    for row in rows:
        rfp_id = row.get("RFP_ID", "")
        if not rfp_id:
            continue
        lookup[rfp_id] = {
            DB_COL_OWNER: clean_str(row.get(DB_COL_OWNER, "")),
            DB_COL_PUBLISH: clean_str(row.get(DB_COL_PUBLISH, "")),
            DB_COL_DUE_DATE: clean_str(row.get(DB_COL_DUE_DATE, "")),
        }
    return lookup


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

FIELD_MAP = [
    # (label, csv_column, db_column, is_date)
    ("Owner Name", CSV_COL_OWNER, DB_COL_OWNER, False),
    ("Publish Date", CSV_COL_PUBLISH_DATE, DB_COL_PUBLISH, True),
    ("Due Date", CSV_COL_DUE_DATE, DB_COL_DUE_DATE, True),
]


def analyze(file_path: str, output_path: str):
    """Compare CSV with Dataverse and write a diff report CSV. Supports resume."""
    df = read_rfp_file(file_path)
    dataverse = DataverseClient(
        tenant_id=TENANT_ID,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        resource_url=RESOURCE_URL,
    )
    db_lookup = fetch_db_records(dataverse)

    available_csv_cols = set(df.columns)

    # Load resume progress
    progress = load_progress()
    completed_set = set(progress["completed"])
    rows_out = progress["rows"]

    # Counters (recount from saved rows)
    total_csv = 0
    not_in_db = sum(1 for r in rows_out if r["Status"] == "NOT IN DATABASE")
    match_count = sum(1 for r in rows_out if r["Status"] == "MATCH")
    diff_count = sum(1 for r in rows_out if r["Status"] == "DIFFERENT")
    missing_in_db_field = sum(1 for r in rows_out if r["Status"] == "MISSING IN DB")
    missing_in_csv_field = sum(1 for r in rows_out if r["Status"] == "MISSING IN CSV")
    skipped_resume = 0

    print(f"\n{'='*60}")
    print(f"  Analyzing RFP differences...")
    print(f"  File:           {file_path}")
    print(f"  Already done:   {len(completed_set)} (resume)")
    print(f"{'='*60}\n")

    for _, row in df.iterrows():
        rfp_id = clean_str(row.get(CSV_COL_RFP_ID, ""))
        if not rfp_id:
            continue
        total_csv += 1

        # Resume: skip already processed
        if rfp_id in completed_set:
            skipped_resume += 1
            continue

        db_entry = db_lookup.get(rfp_id)

        new_rows = []

        # RFP not found in Dataverse at all
        if not db_entry:
            not_in_db += 1
            new_rows.append({
                "RFP_ID": rfp_id,
                "Field": "ALL",
                "CSV_Value": "-",
                "DB_Value": "-",
                "Status": "NOT IN DATABASE",
            })
        else:
            for label, csv_col, db_col, is_date in FIELD_MAP:
                if csv_col not in available_csv_cols:
                    continue

                csv_val = clean_str(row.get(csv_col, ""))
                db_val = db_entry.get(db_col, "")

                # Normalize dates for fair comparison
                if is_date:
                    csv_norm = normalize_date(csv_val) if csv_val else ""
                    db_norm = normalize_date(db_val) if db_val else ""
                else:
                    csv_norm = csv_val
                    db_norm = db_val

                # Determine status
                if not csv_norm and not db_norm:
                    status = "BOTH EMPTY"
                elif csv_norm and not db_norm:
                    status = "MISSING IN DB"
                    missing_in_db_field += 1
                elif not csv_norm and db_norm:
                    status = "MISSING IN CSV"
                    missing_in_csv_field += 1
                elif csv_norm == db_norm:
                    status = "MATCH"
                    match_count += 1
                else:
                    status = "DIFFERENT"
                    diff_count += 1

                new_rows.append({
                    "RFP_ID": rfp_id,
                    "Field": label,
                    "CSV_Value": csv_norm or "(empty)",
                    "DB_Value": db_norm or "(empty)",
                    "Status": status,
                })

        # Save progress after each RFP
        rows_out.extend(new_rows)
        completed_set.add(rfp_id)
        save_progress(list(completed_set), rows_out)
        print(f"  [{len(completed_set)}] Analyzed {rfp_id}")

    # Write final report
    report_df = pd.DataFrame(rows_out)
    report_df.to_csv(output_path, index=False)

    # Print summary
    print(f"\n{'='*60}")
    print(f"  RFP DIFF ANALYSIS REPORT")
    print(f"{'='*60}")
    print(f"  Total RFPs in CSV:            {total_csv}")
    print(f"  Total RFPs in Dataverse:      {len(db_lookup)}")
    print(f"  Skipped (resume):             {skipped_resume}")
    print(f"  NOT in Database at all:       {not_in_db}")
    print(f"  Field-level matches:          {match_count}")
    print(f"  Field-level differences:      {diff_count}")
    print(f"  Missing in DB (has in CSV):   {missing_in_db_field}")
    print(f"  Missing in CSV (has in DB):   {missing_in_csv_field}")
    print(f"{'='*60}")
    print(f"  Report saved to: {output_path}")
    print(f"{'='*60}\n")

    # Clean up progress on full completion
    clear_progress()
    print("  All done. Progress file removed.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Analyze differences between RFP CSV file and Dataverse"
    )
    parser.add_argument(
        "--file", "-f",
        default=DEFAULT_FILE,
        help=f"Path to RFP info file. Default: {DEFAULT_FILE}",
    )
    parser.add_argument(
        "--output", "-o",
        default=DEFAULT_OUTPUT,
        help=f"Output CSV report path. Default: {DEFAULT_OUTPUT}",
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

    analyze(args.file, args.output)


if __name__ == "__main__":
    main()
