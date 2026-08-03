"""
Update RFP rows in Dataverse from RFP_Info_Clean.xlsx
=====================================================
Source : Support-Files/Analysis-Files/RFP_Info_Clean.xlsx
Target : Dataverse table cr673_bahra_rfps_v2

Columns updated (matched on RFP ID):
  Excel "Owner"         -> owner_name      (string)
  Excel "Publish Date"  -> publish_time    (DateTime, TimeZoneIndependent)
  Excel "End Date"      -> RFP_End_Date    (DateTime, TimeZoneIndependent)
  Excel "Participated"  -> participated    (string)

Behaviour
---------
- Default = DRY RUN. Prints a preview of what would change. No writes.
- Pass --apply to actually update Dataverse.
- Pass --limit N to only process the first N Excel rows (for a smoke test).
- Pass --file <path> to override the input workbook.
- Pass --sheet <name> to override the sheet (default = first sheet).
- Idempotent: rows whose 4 fields already match are skipped.

Usage
-----
  python -m Support-Files.update_rfp_from_excel
  python -m Support-Files.update_rfp_from_excel --limit 10
  python -m Support-Files.update_rfp_from_excel --apply
"""

import argparse
import sys
from pathlib import Path

import pandas as pd
from dateutil import parser as du_parser

# Path bootstrap so the script can be run directly OR as a module
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from helpers.dataverse_helper import DataverseClient
from config.config import (
    TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL,
    RFP_ACTIVITY_LOG_TABLE_LOGICAL, RFP_ACTIVITY_LOG_TABLE_API,
)


DEFAULT_EXCEL = REPO_ROOT / "Support-Files" / "Analysis-Files" / "RFP_Info_Clean.xlsx"

# Excel column header -> Dataverse display name
COLUMN_MAP = {
    "Owner":        "owner_name",
    "Publish Date": "publish_time",
    "End Date":     "RFP_End_Date",
    "Participated": "participated",
}
DATE_COLUMNS = {"publish_time", "RFP_End_Date"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def to_iso(val) -> str | None:
    """Parse Excel cell value into ISO 8601 string ('YYYY-MM-DDTHH:MM:SSZ').
    Returns None for blanks / unparseable values.
    """
    if val is None:
        return None
    if isinstance(val, float) and pd.isna(val):
        return None
    if isinstance(val, pd.Timestamp):
        return val.strftime("%Y-%m-%dT%H:%M:%SZ")
    s = str(val).strip()
    if not s or s == "-":
        return None
    try:
        dt = du_parser.parse(s, dayfirst=False)  # MDY (project standard)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        pass
    try:
        dt = pd.to_datetime(s, errors="raise")
        if hasattr(dt, "to_pydatetime"):
            dt = dt.to_pydatetime()
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return None


def clean_str(val) -> str | None:
    """Strip + None-out blanks. Leaves real strings untouched."""
    if val is None:
        return None
    if isinstance(val, float) and pd.isna(val):
        return None
    s = str(val).strip()
    return s if s else None


def normalize_dataverse_iso(val) -> str | None:
    """Dataverse returns DateTime fields as ISO 8601 with milliseconds and 'Z'.
    Normalise to 'YYYY-MM-DDTHH:MM:SSZ' so we can compare with our parsed value."""
    if not val:
        return None
    s = str(val).strip()
    if not s:
        return None
    try:
        dt = du_parser.parse(s)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return s


def load_excel_rows(path: Path, sheet: str | None, limit: int | None) -> list[dict]:
    """Read the Excel file and return a list of normalised dicts keyed by RFP_ID."""
    if not path.exists():
        print(f"[FATAL] Excel file not found: {path}")
        sys.exit(1)

    read_kwargs = {"dtype": object}
    if sheet:
        read_kwargs["sheet_name"] = sheet
    df = pd.read_excel(path, **read_kwargs)

    print(f"[EXCEL] Loaded {len(df)} rows from {path.name} (sheet: {sheet or 'default'})")
    print(f"[EXCEL] Columns: {list(df.columns)}")

    required = ["RFP ID", *COLUMN_MAP.keys()]
    missing = [c for c in required if c not in df.columns]
    if missing:
        print(f"[FATAL] Excel is missing required columns: {missing}")
        sys.exit(1)

    out: list[dict] = []
    for _, raw in df.iterrows():
        rfp_id = clean_str(raw.get("RFP ID"))
        if not rfp_id:
            continue
        out.append({
            "RFP_ID":       rfp_id,
            "owner_name":   clean_str(raw.get("Owner")),
            "publish_time": to_iso(raw.get("Publish Date")),
            "RFP_End_Date": to_iso(raw.get("End Date")),
            "participated": clean_str(raw.get("Participated")),
        })
        if limit and len(out) >= limit:
            break

    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", default=str(DEFAULT_EXCEL), help="Path to source Excel file")
    ap.add_argument("--sheet", default=None, help="Sheet name (default = first sheet)")
    ap.add_argument("--limit", type=int, default=None, help="Process only the first N Excel rows")
    ap.add_argument("--apply", action="store_true", help="Actually write to Dataverse (otherwise dry-run)")
    args = ap.parse_args()

    print("=" * 70)
    print("  Update RFPs from Excel -> Dataverse")
    print(f"  Mode: {'APPLY (will write)' if args.apply else 'DRY RUN (no writes)'}")
    print("=" * 70)

    excel_rows = load_excel_rows(Path(args.file), args.sheet, args.limit)
    print(f"[EXCEL] {len(excel_rows)} usable rows after cleaning\n")
    if not excel_rows:
        print("Nothing to do.")
        return

    print("[AUTH] Acquiring Dataverse token...")
    client = DataverseClient(
        tenant_id=TENANT_ID,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        resource_url=RESOURCE_URL,
    )
    print("[AUTH] Token acquired.\n")

    # ----- Pull existing rows (just the 4 target columns + RFP_ID) -----
    print(f"[DV] Loading existing rows from {RFP_ACTIVITY_LOG_TABLE_LOGICAL}...")
    pk_logical = f"{RFP_ACTIVITY_LOG_TABLE_LOGICAL}id"
    dv_rows = client.get_all_rows(
        table_api_name=RFP_ACTIVITY_LOG_TABLE_API,
        select_columns=["RFP_ID", "owner_name", "publish_time", "RFP_End_Date", "participated"],
        table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL,
        use_display_names=True,
    )
    print(f"[DV] Loaded {len(dv_rows)} rows.\n")

    # query_rows renames the PK column from logical to its display label,
    # so resolve the display name via the reverse mapping (see MEMORY.md).
    colmap = client.get_column_mapping(RFP_ACTIVITY_LOG_TABLE_LOGICAL)
    logical_to_display = {v: k for k, v in colmap.items()}
    pk_display = logical_to_display.get(pk_logical)

    def _record_id(row: dict) -> str | None:
        if pk_display and row.get(pk_display):
            return row[pk_display]
        return row.get(pk_logical)

    # Build lookup: RFP_ID -> (record_id, existing_row)
    dv_index: dict[str, tuple[str, dict]] = {}
    for r in dv_rows:
        rid = _record_id(r)
        rfp_id = clean_str(r.get("RFP_ID"))
        if not rid or not rfp_id:
            continue
        dv_index[rfp_id] = (rid, r)

    # ----- Walk Excel rows, compare, update -----
    updated = 0
    skipped_match = 0
    not_found = 0
    failed = 0
    nothing_to_set = 0

    for i, src in enumerate(excel_rows, 1):
        rfp_id = src["RFP_ID"]
        match = dv_index.get(rfp_id)
        if not match:
            not_found += 1
            if not_found <= 10:
                print(f"  [MISS]   {rfp_id} - not found in Dataverse")
            continue

        rid, existing = match

        # Build the actual update payload — only include fields whose source
        # has a value AND whose current Dataverse value differs.
        payload: dict[str, str] = {}
        for excel_col, dv_col in COLUMN_MAP.items():
            new_val = src[dv_col]
            if new_val is None:
                continue  # don't overwrite with blank
            current = existing.get(dv_col)
            if dv_col in DATE_COLUMNS:
                current_norm = normalize_dataverse_iso(current)
                if current_norm == new_val:
                    continue
            else:
                if (clean_str(current) or "") == new_val:
                    continue
            payload[dv_col] = new_val

        if not payload:
            skipped_match += 1
            continue

        if not args.apply:
            nothing_to_set += 1
            print(f"  [WOULD]  {rfp_id} -> {payload}")
            continue

        try:
            client.update_row(
                RFP_ACTIVITY_LOG_TABLE_API,
                rid,
                payload,
                table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL,
                use_display_names=True,
            )
            updated += 1
            if updated % 25 == 0:
                print(f"       ... updated {updated} rows so far")
        except Exception as e:
            failed += 1
            if failed <= 10:
                print(f"  [FAIL]   {rfp_id}: {e}")

    print("\n" + "=" * 70)
    print("  Summary")
    print("=" * 70)
    print(f"  Excel rows processed       : {len(excel_rows)}")
    print(f"  Already in sync (skipped)  : {skipped_match}")
    print(f"  Not found in Dataverse     : {not_found}")
    if args.apply:
        print(f"  Updated                    : {updated}")
        print(f"  Failed                     : {failed}")
    else:
        print(f"  Would update               : {nothing_to_set}")
        print(f"  (dry-run only — re-run with --apply to write)")
    print("=" * 70)


if __name__ == "__main__":
    main()
