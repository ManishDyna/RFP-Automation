"""
Duplicate RFP Cleanup — EXECUTE (writes to Dataverse)
======================================================
For each duplicate pair in cr673_bahra_rfps_v2:
  1. Append the duplicate's full row data to a backup CSV (flushed before any DB change)
  2. Compute merged field values using the same merge rules as the analysis script
  3. PATCH the keeper row with merged values (only fields that need changing)
  4. DELETE the duplicate row
  5. Append progress to a resume-able CSV

If the script is interrupted, re-run with `--resume <progress_csv>` to skip already-completed pairs.

SAFETY:
  - Update happens BEFORE delete. If the script dies between them, the keeper has the merged
    data and the duplicate still exists — re-running cleans it up.
  - Every duplicate's full row data is written to a backup CSV before deletion.
  - --limit N processes only the first N pairs (use this for the initial smoke test).
  - --dry-run echoes intended actions without performing any write.

Usage:
    python Support-Files/cleanup_duplicate_rfps.py --limit 5             # smoke test
    python Support-Files/cleanup_duplicate_rfps.py --resume <progress>   # continue after stop
    python Support-Files/cleanup_duplicate_rfps.py                       # full run
"""

import argparse
import csv
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "Support-Files"))

from config.config import (                                          # noqa: E402
    TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL,
    RFP_ACTIVITY_LOG_TABLE_API, RFP_ACTIVITY_LOG_TABLE_LOGICAL,
)
from helpers.dataverse_helper import DataverseClient                 # noqa: E402

# Re-use the merge logic / field tiers we built in the analysis script
from analyze_duplicate_rfps import (                                 # noqa: E402
    normalize_rfp_id, match_key, _is_blank, _val, pick_keeper,
    merge_field, ALL_FIELDS,
)


OUTPUT_DIR = os.path.join(PROJECT_ROOT, "Support-Files", "output")

# Display name <-> logical name we need for the PATCH payload.
# The execute script fetches with use_display_names=False so we get raw logical
# names + the GUID PK in one shot. For PATCH we send logical names.
DISPLAY_TO_LOGICAL = {}    # populated at startup from column metadata


def _to_logical(display_name):
    return DISPLAY_TO_LOGICAL.get(display_name, display_name)


def _from_logical(logical_name):
    # Reverse map for reading rows back into display-name space (used by merge_field)
    return LOGICAL_TO_DISPLAY.get(logical_name, logical_name)


LOGICAL_TO_DISPLAY = {}


def fetch_all_with_pk(client):
    """Fetch every row using logical names so we always get cr673_bahra_rfps_v2id."""
    return client.get_all_rows(
        table_api_name=RFP_ACTIVITY_LOG_TABLE_API,
        table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL,
        use_display_names=False,
    )


def logical_row_to_display(row):
    """Convert a logical-name row dict into a display-name row dict our merge logic understands."""
    out = {}
    for lk, v in row.items():
        if lk.startswith("@"):
            continue
        out[_from_logical(lk)] = v
    return out


def compute_merged_payload(keeper_disp, dup_disp):
    """Return:
       merged_payload  - dict of {logical_name: value} to PATCH the keeper, ONLY for
                         fields whose merged value differs from the keeper's current value.
       changes         - human-readable list of "field: old -> new" strings for logging.
    """
    merged_payload = {}
    changes = []
    for fld in ALL_FIELDS:
        kv = _val(keeper_disp, fld)
        dv = _val(dup_disp, fld)
        merged, src = merge_field(fld, kv, dv)
        if str(merged) != str(kv):
            # Only patch when the merge actually changes the keeper
            logical = _to_logical(fld)
            merged_payload[logical] = merged
            changes.append(f"{fld}: '{kv[:60]}' -> '{str(merged)[:60]}' (from {src})")
    return merged_payload, changes


def load_resume_set(resume_path):
    done = set()
    if not resume_path or not os.path.exists(resume_path):
        return done
    with open(resume_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if (row.get("status") or "").strip() == "DELETED":
                done.add(row.get("group_match_key") or "")
    return done


def main():
    parser = argparse.ArgumentParser(description="Clean up duplicate RFPs in cr673_bahra_rfps_v2")
    parser.add_argument("--limit", type=int, default=0, help="Process only the first N pairs (0 = all)")
    parser.add_argument("--dry-run", action="store_true", help="Echo actions without writing")
    parser.add_argument("--resume", type=str, default=None, help="Path to a previous progress CSV; pairs marked DELETED are skipped")
    parser.add_argument("--pause", type=float, default=0.15, help="Seconds to sleep between pairs (rate-limit safety)")
    args = parser.parse_args()

    print("=" * 70)
    print("Duplicate RFP Cleanup  --  EXECUTE" + ("  (DRY RUN)" if args.dry_run else "  (LIVE)"))
    print("=" * 70)

    client = DataverseClient(TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL)

    # Build display<->logical mapping for the v2 table
    print("Resolving column metadata ...")
    col_map = client.get_column_mapping(RFP_ACTIVITY_LOG_TABLE_LOGICAL)
    DISPLAY_TO_LOGICAL.update(col_map)
    for disp, log in col_map.items():
        LOGICAL_TO_DISPLAY[log] = disp

    print("Fetching all rows ...")
    rows = fetch_all_with_pk(client)
    print(f"  Fetched {len(rows)} rows.")

    # Group into duplicate sets (logical row format)
    groups = defaultdict(list)
    for r in rows:
        rid_logical_key = "cr673_rfp_id"
        rid = (r.get(rid_logical_key) or "").strip()
        if rid:
            groups[match_key(rid)].append(r)
    dup_groups = {k: v for k, v in groups.items() if len(v) > 1}
    print(f"  Identified {len(dup_groups)} duplicate pairs.")

    # Apply --resume
    done_keys = load_resume_set(args.resume)
    if done_keys:
        print(f"  Resume mode: {len(done_keys)} pairs already completed in prior run, will skip.")

    work = [(k, items) for k, items in sorted(dup_groups.items()) if k not in done_keys]
    if args.limit:
        work = work[:args.limit]
    print(f"  Pairs to process this run: {len(work)}")
    print()

    # Output files
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    backup_path   = os.path.join(OUTPUT_DIR, f"executed_backup_{ts}.csv")
    progress_path = os.path.join(OUTPUT_DIR, f"executed_progress_{ts}.csv")
    changes_path  = os.path.join(OUTPUT_DIR, f"executed_changes_{ts}.csv")

    backup_headers = ["group_match_key", "dup_guid", "dup_runid", "dup_rfp_id"] + [f"col_{f}" for f in ALL_FIELDS]
    progress_headers = ["timestamp", "group_match_key", "keeper_guid", "dup_guid", "status", "detail"]
    changes_headers = ["group_match_key", "keeper_guid", "field", "old_value", "new_value"]

    backup_f   = open(backup_path,   "w", newline="", encoding="utf-8")
    progress_f = open(progress_path, "w", newline="", encoding="utf-8")
    changes_f  = open(changes_path,  "w", newline="", encoding="utf-8")
    backup_w   = csv.DictWriter(backup_f,   fieldnames=backup_headers); backup_w.writeheader()
    progress_w = csv.DictWriter(progress_f, fieldnames=progress_headers); progress_w.writeheader()
    changes_w  = csv.DictWriter(changes_f,  fieldnames=changes_headers); changes_w.writeheader()

    def log_progress(key, keeper_guid, dup_guid, status, detail=""):
        progress_w.writerow({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "group_match_key": key,
            "keeper_guid": keeper_guid,
            "dup_guid": dup_guid,
            "status": status,
            "detail": detail,
        })
        progress_f.flush()

    n_updated = n_deleted = n_skipped = n_failed = n_no_op = 0

    for idx, (key, items) in enumerate(work, 1):
        # Re-order so the canonical (single-space) row is the keeper.
        # We need to operate on the LOGICAL-format rows; convert to display only for merge logic.
        canonical_items_with_disp = [(it, logical_row_to_display(it)) for it in items]
        # Pass display-format rows to pick_keeper (uses RFP_ID display key)
        keeper_disp, dup_disps = pick_keeper([d for _, d in canonical_items_with_disp])
        # Map display rows back to their logical-format counterparts (by RunID, which is unique within a pair)
        keeper_logical = next(it for it, d in canonical_items_with_disp if d is keeper_disp)
        dup_logical    = next(it for it, d in canonical_items_with_disp if d is dup_disps[0])
        dup_disp = dup_disps[0]

        keeper_guid = keeper_logical.get("cr673_bahra_rfps_v2id") or ""
        dup_guid    = dup_logical.get("cr673_bahra_rfps_v2id") or ""
        dup_rfp     = dup_logical.get("cr673_rfp_id") or ""
        dup_runid   = dup_logical.get("cr673_runid") or ""

        print(f"[{idx}/{len(work)}] {key}  keeper={keeper_guid[:8]}  dup={dup_guid[:8]}")

        # 1. Backup the duplicate row BEFORE any change
        backup_record = {
            "group_match_key": key,
            "dup_guid": dup_guid,
            "dup_runid": dup_runid,
            "dup_rfp_id": dup_rfp,
        }
        for fld in ALL_FIELDS:
            backup_record[f"col_{fld}"] = dup_disp.get(fld, "")
        backup_w.writerow(backup_record)
        backup_f.flush()
        os.fsync(backup_f.fileno())

        # 2. Compute merged payload
        merged_payload, changes = compute_merged_payload(keeper_disp, dup_disp)

        # 3. PATCH the keeper if anything actually needs to change
        if merged_payload:
            for ch in changes:
                fld_name = ch.split(":", 1)[0]
                old_str = ch.split("'", 4)[1] if "'" in ch else ""
                new_str = ch.split("'", 4)[3] if ch.count("'") >= 4 else ""
                changes_w.writerow({
                    "group_match_key": key,
                    "keeper_guid": keeper_guid,
                    "field": fld_name,
                    "old_value": old_str,
                    "new_value": new_str,
                })
            changes_f.flush()

            if args.dry_run:
                print(f"    [DRY-RUN] would PATCH keeper with {len(merged_payload)} field(s): {list(merged_payload.keys())}")
            else:
                try:
                    client.update_row(
                        table_api_name=RFP_ACTIVITY_LOG_TABLE_API,
                        record_id=keeper_guid,
                        data=merged_payload,
                        use_display_names=False,
                    )
                    n_updated += 1
                except Exception as e:
                    err = str(e)[:200]
                    print(f"    [ERROR] UPDATE failed: {err}")
                    log_progress(key, keeper_guid, dup_guid, "UPDATE_FAILED", err)
                    n_failed += 1
                    continue
        else:
            n_no_op += 1
            print(f"    no keeper change needed")

        # 4. DELETE the duplicate
        if args.dry_run:
            print(f"    [DRY-RUN] would DELETE duplicate {dup_guid}")
            log_progress(key, keeper_guid, dup_guid, "DRY_RUN", f"merged_fields={len(merged_payload)}")
        else:
            try:
                client.delete_row(
                    table_api_name=RFP_ACTIVITY_LOG_TABLE_API,
                    record_id=dup_guid,
                )
                n_deleted += 1
                log_progress(key, keeper_guid, dup_guid, "DELETED", f"merged_fields={len(merged_payload)}")
            except Exception as e:
                err = str(e)[:200]
                print(f"    [ERROR] DELETE failed: {err}")
                log_progress(key, keeper_guid, dup_guid, "DELETE_FAILED", err)
                n_failed += 1
                continue

        if args.pause > 0:
            time.sleep(args.pause)

    backup_f.close()
    progress_f.close()
    changes_f.close()

    print()
    print("=" * 70)
    print("Done.")
    print("=" * 70)
    print(f"  Pairs processed         : {len(work)}")
    print(f"  Keepers updated         : {n_updated}")
    print(f"  Keepers needing no patch: {n_no_op}")
    print(f"  Duplicates deleted      : {n_deleted}")
    print(f"  Failures                : {n_failed}")
    print(f"  Skipped (resume)        : {len(done_keys)}")
    print()
    print(f"  Backup file   : {backup_path}")
    print(f"  Progress file : {progress_path}")
    print(f"  Changes file  : {changes_path}")
    print()
    if args.dry_run:
        print("  This was a DRY RUN. No Dataverse changes were made.")
    else:
        print("  LIVE RUN complete. Re-run analyze_duplicate_rfps.py to verify duplicate count = 0.")


if __name__ == "__main__":
    main()
