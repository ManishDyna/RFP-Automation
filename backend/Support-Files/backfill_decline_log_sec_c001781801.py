"""
One-off backfill: add a missing decline-log row for RFP 'SEC RFP-C001781801'.

This RFP was declined by automation BEFORE the logging fix landed, so no row
was written to cr673_bhara_rfp_status. The dashboard's "Declined by System"
count is therefore missing it. This script inserts the missing history row.

Prerequisites:
  - Run setup_rfp_status_category_options.py first so the 'decline' choice
    option exists on the category field.

Idempotent: if a row already exists with rfp_id='SEC RFP-C001781801' and
to_this='declined', the script does nothing.

Usage:
    python Support-Files/backfill_decline_log_sec_c001781801.py

Avoids importing helpers.core_helper to dodge the services.* circular import.
"""

import sys
import io
from datetime import datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from helpers.dataverse_helper import DataverseClient
from config.config import TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL

RFP_ID = "SEC RFP-C001781801"
FROM_STATUS = "no"
TO_STATUS = "declined"
CATEGORY_LABEL = "decline"

STATUS_TABLE_API = "cr673_bhara_rfp_statuses"
STATUS_TABLE_LOGICAL = "cr673_bhara_rfp_status"
CATEGORY_ATTR_LOGICAL = "cr673_submissioncategory"


def _find_key(row: dict, candidates: list[str]) -> str | None:
    keys_lower = {k.lower().replace(" ", "").replace("_", ""): k for k in row.keys()}
    for c in candidates:
        norm = c.lower().replace(" ", "").replace("_", "")
        if norm in keys_lower:
            return keys_lower[norm]
    return None


def already_logged(dv: DataverseClient) -> bool:
    rows = dv.get_all_rows(
        table_api_name=STATUS_TABLE_API,
        table_logical_name=STATUS_TABLE_LOGICAL,
        use_display_names=True,
    )
    if not rows:
        return False
    rfp_key = _find_key(rows[0], ["RFP_ID", "rfp_id", "rfpreference"])
    to_key = _find_key(rows[0], ["to_this", "tothis", "currentstatus"])
    if not rfp_key or not to_key:
        print(f"[WARN] Could not resolve columns (rfp_key={rfp_key}, to_key={to_key}); proceeding without dedupe check")
        return False
    for r in rows:
        raw_rid = r.get(rfp_key)
        rid = (raw_rid.strip() if isinstance(raw_rid, str) else str(raw_rid or "").strip())
        raw_to = r.get(to_key)
        to_val = (raw_to.strip().lower() if isinstance(raw_to, str) else str(raw_to or "").strip().lower())
        if rid == RFP_ID and to_val == TO_STATUS:
            return True
    return False


def find_display_name(column_map: dict, candidates: list[str]) -> str | None:
    """column_map is display_name -> logical_name. Find display name whose
    logical name matches any candidate."""
    for display_name, logical_name in column_map.items():
        if logical_name.lower() in [c.lower() for c in candidates]:
            return display_name
    return None


def main() -> int:
    print(f"\n{'=' * 70}")
    print(f"  Backfill decline log for: {RFP_ID}")
    print(f"  {FROM_STATUS!r} -> {TO_STATUS!r}  (category={CATEGORY_LABEL!r})")
    print(f"{'=' * 70}\n")

    dv = DataverseClient(
        tenant_id=TENANT_ID,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        resource_url=RESOURCE_URL,
    )

    if already_logged(dv):
        print(f"[SKIP] A row already exists for '{RFP_ID}' with to_this='{TO_STATUS}'. Nothing to do.")
        return 0

    # Resolve the integer value for the 'decline' choice option
    try:
        choice = dv.get_choice_options(STATUS_TABLE_LOGICAL, CATEGORY_ATTR_LOGICAL)
    except Exception as e:
        print(f"[ERROR] Could not read choice options for category field: {e}")
        return 1

    label_to_value = choice.get("label_to_value", {})
    category_value = None
    for label, value in label_to_value.items():
        if label.lower() == CATEGORY_LABEL.lower():
            category_value = value
            break
    if category_value is None:
        print(f"[ERROR] '{CATEGORY_LABEL}' is not a choice option on {CATEGORY_ATTR_LOGICAL}.")
        print(f"        Available: {list(label_to_value.keys())}")
        print(f"        Run setup_rfp_status_category_options.py first.")
        return 1
    print(f"Resolved category '{CATEGORY_LABEL}' -> {category_value}")

    # Resolve display names for the columns we need to write
    try:
        column_map = dv.get_column_mapping(STATUS_TABLE_LOGICAL)  # display -> logical
    except Exception as e:
        print(f"[ERROR] Could not read column mapping: {e}")
        return 1

    rfp_id_display = find_display_name(column_map, ["cr673_rfpreference"])
    datetime_display = find_display_name(column_map, ["cr673_submissioncode"])
    to_this_display = find_display_name(column_map, ["cr673_currentstatus"])
    from_this_display = find_display_name(
        column_map,
        ["cr673_from_this", "cr673_fromthis", "cr673_previousstatus"],
    )
    category_display = find_display_name(column_map, ["cr673_submissioncategory"])

    print(f"Column resolution:")
    print(f"  rfp_id    -> {rfp_id_display}")
    print(f"  datetime  -> {datetime_display}")
    print(f"  to_this   -> {to_this_display}")
    print(f"  from_this -> {from_this_display}")
    print(f"  category  -> {category_display}")

    now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    row = {}
    row[rfp_id_display or "rfp_id"] = str(RFP_ID)
    row[datetime_display or "datetime"] = now_iso
    row[to_this_display or "to_this"] = TO_STATUS
    if from_this_display:
        row[from_this_display] = FROM_STATUS
    row[category_display or "category"] = category_value

    print(f"\nInserting row: {row}")

    success = dv.insert_row(
        table_api_name=STATUS_TABLE_API,
        data=row,
        table_logical_name=STATUS_TABLE_LOGICAL,
        use_display_names=True,
    )

    if success:
        print(f"\n[OK] Inserted decline log row for {RFP_ID}")
        return 0
    print(f"\n[ERROR] Failed to insert decline log row for {RFP_ID}")
    return 1


if __name__ == "__main__":
    sys.exit(main() or 0)
