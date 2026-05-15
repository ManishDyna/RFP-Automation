"""
DEPRECATED — DO NOT RUN
=======================
This script normalised the publish_time TEXT column to 'M/D/YYYY H:MM AM/PM'.
That column no longer exists as TEXT — it is now a DateTime column on
cr673_bahra_rfps_v2 (see Support-Files/migrate_publish_time_to_datetime.py).

The migration script has already populated every row with proper DateTime
values, so this normaliser has nothing to do. Running it would only confuse
the DateTime values.

Kept in the repo as a historical reference for the text-era backfill logic.
The original docstring follows.

---
Normalize publish_time format in Dataverse  (HISTORICAL — TEXT-ERA SCRIPT)
==========================================
One-time backfill that scans the cr673_bahra_rfps_v2 table and converts any
publish_time value that is NOT already in the locked DB standard
'M/D/YYYY H:MM AM/PM' to that format.

The bug being fixed
-------------------
core/log_events.py used to write the raw scraped portal value (often ISO
8601 like '2019-08-27T16:00:00Z') directly to the publish_time text column.
That writer has been patched, but existing rows still hold the old non-MDY
values. This script normalises them in place.

Two-phase approval-gated flow (same pattern as master_rfp_sync.py):
  Phase A (no --apply): scan + write preview CSV. NO DB writes.
  Phase B (--apply):    read approved preview rows and update Dataverse.

Usage:
  Phase A:
    python Support-Files\\normalize_publish_time_format.py
    python Support-Files\\normalize_publish_time_format.py --company "Saudi Energy" --limit 5

  Edit the preview CSV in Excel: type "NO" in user_approve on any row to veto.

  Phase B:
    python Support-Files\\normalize_publish_time_format.py --apply
    python Support-Files\\normalize_publish_time_format.py --apply --preview path\\to\\preview.csv

Out of scope
------------
  * Owner_name, RFP_End_Date, rfp_type, Link, participated — untouched.
  * Portal access — none. Pure DB normalisation.
"""

import sys as _sys

_DEPRECATION_MESSAGE = (
    "\n" + "=" * 72 + "\n"
    "  DEPRECATED — normalize_publish_time_format.py will not run.\n"
    "  Reason: publish_time is now a DateTime column on cr673_bahra_rfps_v2.\n"
    "  See Support-Files/migrate_publish_time_to_datetime.py for the migration\n"
    "  that converted it from TEXT to DateTime. Existing rows are already\n"
    "  populated correctly — there is nothing for this script to do.\n"
    + "=" * 72 + "\n"
)

if __name__ == "__main__":
    print(_DEPRECATION_MESSAGE)
    _sys.exit(0)

# Anything below this point is preserved for historical reference and is not
# executed when the file is run directly (the __main__ guard above exits first).
# The original module-level code is left intact in case it's referenced by
# documentation; importing this module is a no-op past this point.

import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# Path bootstrap so helpers/ and config/ resolve when run from Support-Files/
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from helpers.dataverse_helper import DataverseClient
from config.config import (
    TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL,
    RFP_ACTIVITY_LOG_TABLE_API, RFP_ACTIVITY_LOG_TABLE_LOGICAL,
    COMPANY_OPTIONS,
)

# Reuse the locked date formatter (fixed in this same edit to handle ISO 8601)
from sync_rfp_publish_date import normalize_date  # noqa: E402


PRIMARY_KEY_LOGICAL = f"{RFP_ACTIVITY_LOG_TABLE_LOGICAL}id"  # cr673_bahra_rfps_v2id

PROGRESS_FILE = HERE / ".normalize_publish_time_progress.json"
OUTPUT_DIR = HERE / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

PREVIEW_HEADERS = [
    "timestamp", "rfp_id", "company_name", "record_id",
    "current_value", "normalized_value", "status", "user_approve", "notes",
]

APPLIED_HEADERS = [
    "timestamp", "rfp_id", "record_id",
    "old_value", "new_value", "result",
]

# Regex for the canonical format M/D/YYYY H:MM AM/PM (no leading zeros)
CANONICAL_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}\s+(AM|PM)$")


# ─── Progress file ───────────────────────────────────────────────────────────

def load_progress() -> dict:
    if not PROGRESS_FILE.exists():
        return {"started_at": None, "completed": set()}
    try:
        with open(PROGRESS_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return {
            "started_at": data.get("started_at"),
            "completed":  set(data.get("completed", [])),
        }
    except Exception:
        return {"started_at": None, "completed": set()}


def save_progress(progress: dict) -> None:
    payload = {
        "started_at": progress.get("started_at"),
        "completed":  sorted(progress.get("completed", set())),
    }
    tmp = PROGRESS_FILE.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    os.replace(tmp, PROGRESS_FILE)


def reset_progress() -> None:
    if PROGRESS_FILE.exists():
        PROGRESS_FILE.unlink()
        print(f"  Progress file removed: {PROGRESS_FILE}")


# ─── Helpers ─────────────────────────────────────────────────────────────────

def clean_id(rfp_id: str) -> str:
    return re.sub(r"\s+", " ", str(rfp_id or "")).strip()


def _is_blank(val) -> bool:
    if val is None:
        return True
    s = str(val).strip()
    return s == "" or s.lower() in ("nan", "none", "-")


# ─── Phase A: scan + preview ─────────────────────────────────────────────────

def phase_a_scan(args) -> None:
    print("[INIT] Connecting to Dataverse...")
    dv = DataverseClient(TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL)

    # Resolve PK display name
    try:
        colmap = dv.get_column_mapping(RFP_ACTIVITY_LOG_TABLE_LOGICAL)
        logical_to_display = {v: k for k, v in colmap.items()}
        pk_display = logical_to_display.get(PRIMARY_KEY_LOGICAL, PRIMARY_KEY_LOGICAL)
    except Exception as exc:
        print(f"[WARN] Could not load column mapping: {exc}")
        pk_display = PRIMARY_KEY_LOGICAL

    print("[INIT] Fetching RFPs from Dataverse...")
    rows = dv.get_all_rows(
        table_api_name=RFP_ACTIVITY_LOG_TABLE_API,
        select_columns=["RFP_ID", "Company_Name", "publish_time"],
        table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL,
        use_display_names=True,
    )
    print(f"[INIT] Fetched {len(rows)} RFP rows.")

    if args.company:
        rows = [r for r in rows if (r.get("Company_Name") or "").strip() == args.company]
        print(f"[FILTER] --company={args.company!r}: {len(rows)} rows.")

    # Drop rows with no publish_time at all — nothing to normalize
    before = len(rows)
    rows = [r for r in rows if not _is_blank(r.get("publish_time"))]
    print(f"[FILTER] non-empty publish_time: {len(rows)} rows (dropped {before - len(rows)} blank rows).")

    if args.limit:
        rows = rows[: args.limit]
        print(f"[FILTER] --limit={args.limit}: {len(rows)} rows.")

    if not rows:
        print("[INIT] Nothing to process.")
        return

    if args.reset:
        reset_progress()
    progress = load_progress()
    if not progress["started_at"]:
        progress["started_at"] = datetime.now().isoformat()
    save_progress(progress)

    pending = []
    for r in rows:
        rid = clean_id(r.get("RFP_ID", ""))
        if not rid:
            continue
        if rid in progress["completed"]:
            continue
        pending.append(r)
    skipped = len(rows) - len(pending)
    print(f"[INIT] {skipped} already done; {len(pending)} pending.")
    if not pending:
        print("[INIT] Nothing pending. Use --reset to start over.")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    preview_path = OUTPUT_DIR / f"normalize_publish_time_preview_{timestamp}.csv"
    fh_csv = open(preview_path, "w", newline="", encoding="utf-8-sig")
    writer = csv.DictWriter(fh_csv, fieldnames=PREVIEW_HEADERS)
    writer.writeheader()
    fh_csv.flush()
    print(f"[INIT] Preview CSV: {preview_path}")

    counters = {"OK": 0, "WILL_FIX": 0, "ERROR": 0}

    for idx, row in enumerate(pending, 1):
        rfp_id = clean_id(row.get("RFP_ID", ""))
        company = (row.get("Company_Name") or "").strip()
        record_id = row.get(pk_display) or row.get(PRIMARY_KEY_LOGICAL) or ""
        current = str(row.get("publish_time") or "").strip()

        normalized = normalize_date(current)

        if normalized and normalized != current and CANONICAL_RE.match(normalized):
            status = "WILL_FIX"
            note = ""
        elif normalized == current and CANONICAL_RE.match(current):
            status = "OK"
            note = "already canonical"
        elif not CANONICAL_RE.match(normalized):
            status = "ERROR"
            note = "could not parse to canonical format"
        else:
            status = "OK"
            note = ""

        writer.writerow({
            "timestamp":        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "rfp_id":           rfp_id,
            "company_name":     company,
            "record_id":        record_id,
            "current_value":    current,
            "normalized_value": normalized,
            "status":           status,
            "user_approve":     "",
            "notes":            note,
        })
        fh_csv.flush()
        counters[status] = counters.get(status, 0) + 1
        progress["completed"].add(rfp_id)

        # Save progress every 100 rows (frequent enough for resume, not too chatty)
        if idx % 100 == 0:
            save_progress(progress)
            print(f"  [{idx}/{len(pending)}] processed (OK={counters['OK']} WILL_FIX={counters['WILL_FIX']} ERROR={counters['ERROR']})")

    save_progress(progress)
    fh_csv.close()

    print(f"\n{'=' * 65}")
    print("  PHASE A COMPLETE")
    print(f"{'=' * 65}")
    print(f"  OK (already canonical) : {counters['OK']}")
    print(f"  WILL_FIX               : {counters['WILL_FIX']}")
    print(f"  ERROR (unparseable)    : {counters['ERROR']}")
    print(f"\n  Preview CSV : {preview_path}")
    print(f"  Progress    : {PROGRESS_FILE}")
    print("\n  Open the preview CSV in Excel. Set user_approve=NO on any rows")
    print("  you do NOT want applied. Blank / YES = approved.")
    print(f"\n  Then run:  python {Path(__file__).name} --apply --preview \"{preview_path}\"")
    print(f"{'=' * 65}")


# ─── Phase B: apply ──────────────────────────────────────────────────────────

def phase_b_apply(args) -> None:
    if args.preview:
        preview_path = Path(args.preview)
    else:
        candidates = sorted(OUTPUT_DIR.glob("normalize_publish_time_preview_*.csv"))
        if not candidates:
            print("[ERROR] No preview CSV found in Support-Files\\output\\. Run Phase A first.")
            sys.exit(1)
        preview_path = candidates[-1]
        print(f"[INIT] Using newest preview: {preview_path.name}")

    if not preview_path.exists():
        print(f"[ERROR] Preview not found: {preview_path}")
        sys.exit(1)

    to_apply = []
    vetoed = 0
    with open(preview_path, "r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            status = (row.get("status") or "").strip().upper()
            if status != "WILL_FIX":
                continue
            approve = (row.get("user_approve") or "").strip().upper()
            if approve == "NO":
                vetoed += 1
                continue
            record_id = (row.get("record_id") or "").strip()
            if not record_id:
                continue
            to_apply.append({
                "rfp_id":           (row.get("rfp_id") or "").strip(),
                "record_id":        record_id,
                "current_value":    row.get("current_value", ""),
                "normalized_value": row.get("normalized_value", ""),
            })

    print(f"[INIT] {len(to_apply)} rows to update | {vetoed} vetoed (user_approve=NO).")
    if not to_apply:
        print("[DONE] Nothing approved to apply.")
        return

    print("[INIT] Connecting to Dataverse...")
    dv = DataverseClient(TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    applied_path = OUTPUT_DIR / f"normalize_publish_time_applied_{timestamp}.csv"
    fh_applied = open(applied_path, "w", newline="", encoding="utf-8-sig")
    writer = csv.DictWriter(fh_applied, fieldnames=APPLIED_HEADERS)
    writer.writeheader()

    applied = 0
    failed = 0
    for r in to_apply:
        # Re-normalize for safety — guarantees canonical form lands in DB
        new_val = normalize_date(r["normalized_value"]) or r["normalized_value"]
        try:
            ok = dv.update_row(
                table_api_name=RFP_ACTIVITY_LOG_TABLE_API,
                record_id=r["record_id"],
                data={"publish_time": new_val},
                table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL,
                use_display_names=True,
            )
            result = "OK" if ok else "FAIL"
            if ok:
                applied += 1
                print(f"  [OK] {r['rfp_id']}: '{r['current_value']}' -> '{new_val}'")
            else:
                failed += 1
                print(f"  [FAIL] {r['rfp_id']}")
        except Exception as exc:
            result = f"ERROR: {exc}"
            failed += 1
            print(f"  [ERROR] {r['rfp_id']}: {exc}")

        writer.writerow({
            "timestamp":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "rfp_id":     r["rfp_id"],
            "record_id":  r["record_id"],
            "old_value":  r["current_value"],
            "new_value":  new_val,
            "result":     result,
        })
        fh_applied.flush()

    fh_applied.close()

    print(f"\n{'=' * 65}")
    print("  PHASE B COMPLETE")
    print(f"{'=' * 65}")
    print(f"  Applied: {applied}")
    print(f"  Failed : {failed}")
    print(f"  Vetoed : {vetoed}")
    print(f"  Applied log: {applied_path}")
    print(f"{'=' * 65}")


# ─── CLI ─────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill: convert publish_time values in Dataverse to the locked "
            "M/D/YYYY H:MM AM/PM format. Two-pass: preview, then --apply."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Phase B: read preview CSV and apply approved updates to Dataverse.",
    )
    parser.add_argument(
        "--company", default=None,
        help=f"Filter to one company. Must be one of: {COMPANY_OPTIONS}",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Process at most N rows (handy for smoke testing).",
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="Delete the progress file before starting Phase A.",
    )
    parser.add_argument(
        "--preview", default=None,
        help="Phase B only: path to a specific preview CSV. "
             "Default: newest normalize_publish_time_preview_*.csv in Support-Files\\output\\.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.company and args.company not in COMPANY_OPTIONS:
        print(f"[ERROR] --company {args.company!r} is not in COMPANY_OPTIONS.")
        print(f"        Valid values: {COMPANY_OPTIONS}")
        sys.exit(1)

    if args.apply:
        phase_b_apply(args)
    else:
        phase_a_scan(args)


if __name__ == "__main__":
    main()
