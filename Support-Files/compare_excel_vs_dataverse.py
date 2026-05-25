"""
Compare an Excel file of RFPs against the Dataverse RFP Activity Log table
(cr673_bahra_rfps_v2) and write a multi-sheet Excel report of the differences.

Fields compared: Company_Name, Link, Owner, Publish_Date, End_Date,
Event_Type, Status, Participated.

Output sheets:
  - Summary
  - Differences          (one row per RFP/field that mismatches)
  - Differences_Pivot    (one row per RFP, columns = fields with diffs)
  - Missing_In_DB        (RFPs in Excel but not in Dataverse)
  - Missing_In_Excel     (RFPs in Dataverse but not in Excel)
"""

import argparse
import os
import sys
from datetime import datetime

import pandas as pd
import pytz

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from helpers.dataverse_helper import DataverseClient
from config.config import (
    TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL,
    RFP_ACTIVITY_LOG_TABLE_API, RFP_ACTIVITY_LOG_TABLE_LOGICAL,
)

DEFAULT_INPUT = r"C:\Users\Manish.Soni\Downloads\RFP-Data.xlsx"
DEFAULT_SHEET = "Sheet1"

KSA_TZ = pytz.timezone("Asia/Riyadh")

# Excel column -> Dataverse display-name column. is_date marks fields that
# need date normalization before string compare.
FIELD_MAP = [
    # (label,         excel_col,     dv_col,        is_date)
    ("Company_Name",  "Company_Name", "Company_Name", False),
    ("Link",          "Link",         "Link",         False),
    ("Owner",         "Owner",        "owner_name",   False),
    ("Publish_Date",  "Publish_Date", "publish_time", True),
    ("End_Date",      "End_Date",     "RFP_End_Date", True),
    ("Event_Type",    "Event_Type",   "rfp_type",     False),
    ("Status",        "Status",       "Status",       False),
    ("Participated",  "Participated", "participated", False),
]


def clean_str(val) -> str:
    if val is None:
        return ""
    if isinstance(val, float) and pd.isna(val):
        return ""
    s = str(val).strip()
    return "" if s.lower() in ("nan", "none", "nat") else s


def normalize_date(val) -> str:
    """Parse any date format and return 'M/D/YYYY H:MM AM/PM' in KSA time.
    Excel serial numbers (e.g. 46084.64583) are also handled."""
    s = clean_str(val)
    if not s:
        return ""
    # Excel serial number?
    try:
        f = float(s)
        if 20000 < f < 80000:  # reasonable date-serial range
            dt = pd.to_datetime("1899-12-30") + pd.to_timedelta(f, unit="D")
            return dt.strftime("%#m/%#d/%Y %#I:%M %p")
    except (ValueError, TypeError):
        pass

    try:
        if "-" in s and "/" not in s:
            parts = s.split(" ", 1)
            date_part = parts[0]
            time_part = parts[1] if len(parts) > 1 else "00:00:00"
            chunks = date_part.split("-")
            if len(chunks) == 3 and len(chunks[0]) == 4:
                # ISO-like YYYY-MM-DD
                dt = pd.to_datetime(f"{chunks[0]}-{chunks[1]}-{chunks[2]} {time_part}")
            else:
                dt = pd.to_datetime(s)
        else:
            dt = pd.to_datetime(s)
        if dt.tzinfo is not None:
            dt = dt.astimezone(KSA_TZ)
        return dt.strftime("%#m/%#d/%Y %#I:%M %p")
    except Exception:
        return s


def norm_str(val) -> str:
    """Case- and whitespace-insensitive normalization for non-date string compare."""
    return clean_str(val).lower()


def read_excel_sheet(path: str, sheet: str) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=sheet, dtype=str)
    # Drop fully-empty unnamed columns
    drop_cols = [c for c in df.columns if str(c).startswith("Unnamed") and df[c].isna().all()]
    if drop_cols:
        df = df.drop(columns=drop_cols)
    if "RFP_ID" not in df.columns:
        raise ValueError(f"Sheet '{sheet}' missing RFP_ID column. Found: {list(df.columns)}")
    # De-dupe by RFP_ID (keep first non-empty row)
    df["RFP_ID"] = df["RFP_ID"].map(clean_str)
    df = df[df["RFP_ID"] != ""].drop_duplicates(subset=["RFP_ID"], keep="first").reset_index(drop=True)
    print(f"  Excel '{sheet}': {len(df)} unique RFP rows")
    return df


def fetch_dataverse(client: DataverseClient) -> dict:
    select_cols = ["RFP_ID"] + [m[2] for m in FIELD_MAP]
    rows = client.get_all_rows(
        table_api_name=RFP_ACTIVITY_LOG_TABLE_API,
        select_columns=select_cols,
        table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL,
        use_display_names=True,
    )
    lookup = {}
    for row in rows:
        rfp_id = clean_str(row.get("RFP_ID", ""))
        if not rfp_id:
            continue
        lookup[rfp_id] = {m[2]: clean_str(row.get(m[2], "")) for m in FIELD_MAP}
    print(f"  Dataverse: {len(lookup)} unique RFP rows")
    return lookup


def compare(excel_df: pd.DataFrame, db_lookup: dict):
    diff_rows = []          # long format: one row per (RFP_ID, Field)
    pivot_rows = []         # wide format: one row per RFP with at least one diff
    missing_in_db = []
    only_in_db = []
    match_count = 0

    excel_ids = set(excel_df["RFP_ID"].tolist())
    db_ids = set(db_lookup.keys())

    for _, row in excel_df.iterrows():
        rfp_id = row["RFP_ID"]
        db = db_lookup.get(rfp_id)
        if not db:
            missing_in_db.append({"RFP_ID": rfp_id, **{m[0]: clean_str(row.get(m[1], "")) for m in FIELD_MAP}})
            continue

        per_rfp_diffs = {}
        had_diff = False
        for label, ex_col, db_col, is_date in FIELD_MAP:
            ex_raw = clean_str(row.get(ex_col, ""))
            db_raw = db.get(db_col, "")
            if is_date:
                ex_n = normalize_date(ex_raw)
                db_n = normalize_date(db_raw)
                equal = ex_n == db_n
            else:
                equal = norm_str(ex_raw) == norm_str(db_raw)
                ex_n, db_n = ex_raw, db_raw

            if not ex_n and not db_n:
                status = "BOTH EMPTY"
            elif ex_n and not db_n:
                status = "MISSING IN DB"
            elif db_n and not ex_n:
                status = "MISSING IN EXCEL"
            elif equal:
                status = "MATCH"
                match_count += 1
            else:
                status = "DIFFERENT"

            if status in ("DIFFERENT", "MISSING IN DB", "MISSING IN EXCEL"):
                diff_rows.append({
                    "RFP_ID": rfp_id,
                    "Field": label,
                    "Excel_Value": ex_n or "(empty)",
                    "DB_Value": db_n or "(empty)",
                    "Status": status,
                })
                per_rfp_diffs[f"{label}_Excel"] = ex_n
                per_rfp_diffs[f"{label}_DB"] = db_n
                per_rfp_diffs[f"{label}_Status"] = status
                had_diff = True

        if had_diff:
            pivot_rows.append({"RFP_ID": rfp_id, **per_rfp_diffs})

    for rfp_id in sorted(db_ids - excel_ids):
        only_in_db.append({"RFP_ID": rfp_id, **{m[0]: db_lookup[rfp_id].get(m[2], "") for m in FIELD_MAP}})

    summary = {
        "Total RFPs in Excel": len(excel_ids),
        "Total RFPs in Dataverse": len(db_ids),
        "RFPs in Excel but not in DB": len(missing_in_db),
        "RFPs in DB but not in Excel": len(only_in_db),
        "RFPs with at least one diff": len(pivot_rows),
        "Field-level matches": match_count,
        "Field-level diff rows": len(diff_rows),
    }
    return summary, diff_rows, pivot_rows, missing_in_db, only_in_db


def write_report(output_path: str, summary, diff_rows, pivot_rows, missing_in_db, only_in_db):
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        pd.DataFrame(
            [{"Metric": k, "Value": v} for k, v in summary.items()]
        ).to_excel(writer, sheet_name="Summary", index=False)

        pd.DataFrame(diff_rows).to_excel(writer, sheet_name="Differences", index=False)
        pd.DataFrame(pivot_rows).to_excel(writer, sheet_name="Differences_Pivot", index=False)
        pd.DataFrame(missing_in_db).to_excel(writer, sheet_name="Missing_In_DB", index=False)
        pd.DataFrame(only_in_db).to_excel(writer, sheet_name="Missing_In_Excel", index=False)

    print(f"  Report written: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Compare Excel RFPs vs Dataverse RFP table")
    parser.add_argument("--file", "-f", default=DEFAULT_INPUT, help=f"Input Excel (default: {DEFAULT_INPUT})")
    parser.add_argument("--sheet", "-s", default=DEFAULT_SHEET, help=f"Sheet name (default: {DEFAULT_SHEET})")
    parser.add_argument("--output", "-o", default=None, help="Output Excel path (default: alongside input)")
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"Input file not found: {args.file}")
        sys.exit(1)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = args.output or os.path.join(
        os.path.dirname(args.file),
        f"RFP-Data_vs_Dataverse_DIFF_{ts}.xlsx",
    )

    print(f"  Reading Excel: {args.file} (sheet: {args.sheet})")
    excel_df = read_excel_sheet(args.file, args.sheet)

    print("  Connecting to Dataverse...")
    client = DataverseClient(
        tenant_id=TENANT_ID,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        resource_url=RESOURCE_URL,
    )
    db_lookup = fetch_dataverse(client)

    print("  Comparing rows...")
    summary, diff_rows, pivot_rows, missing_in_db, only_in_db = compare(excel_df, db_lookup)

    print("\n" + "=" * 60)
    for k, v in summary.items():
        print(f"  {k}: {v}")
    print("=" * 60 + "\n")

    write_report(output_path, summary, diff_rows, pivot_rows, missing_in_db, only_in_db)


if __name__ == "__main__":
    main()
