"""
Migration script: Convert publish_time from STRING to DATETIME on
cr673_bahra_rfps_v2.

WHY
  publish_time is currently a TEXT column (max 200) holding values like
  "2/23/2026 8:10 PM" (KSA local). OData $orderby on text sorts
  lexicographically ("1/..." after "9/..."), so server-side sort/min/max
  queries are wrong. After this migration, the column becomes a real
  DateTime and Dataverse sorts it natively.

PHASES
  1. Add backup column 'bck_publish_time' (string, max 200).
  2. Copy publish_time -> bck_publish_time for every row (resumable).
  3. Drop the original cr673_publish_time column.
  4. Re-create cr673_publish_time as DateTime (TimeZoneIndependent).
  5. Parse bck_publish_time text -> write ISO datetime to the new column
     (resumable).
  6. Final PublishXml on the entity.

PROGRESS / RESUME
  Tracked in Support-Files/.migrate_publish_time_progress.json. The script
  auto-resumes from where it left off if you re-run it after Ctrl+C or a
  network failure. Phases 1/3/4/6 are recorded as boolean flags; phases 2
  and 5 (the per-row work) record completed record IDs and skip them on
  re-run. Progress is flushed every 50 rows.

  To start over from scratch, delete the progress file.

USAGE
  python -m Support-Files.migrate_publish_time_to_datetime

POST-MIGRATION
  This script ONLY changes Dataverse. Writer code that still produces
  "M/D/YYYY h:MM AM/PM" text strings (core/log_events.py, rfp/download_rfp.py,
  Support-Files/sync_rfp_publish_date.py, etc.) MUST be updated to send
  ISO 8601 datetimes after this script runs, otherwise new inserts will
  fail. The backup column 'bck_publish_time' is kept as a safety net.
"""

import sys
import json
import time
import argparse
import requests
import pandas as pd
from datetime import datetime
from pathlib import Path
from dateutil import parser as du_parser

from helpers.dataverse_helper import DataverseClient
from config.config import TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL


TABLE_LOGICAL = "cr673_bahra_rfps_v2"
TABLE_API = "cr673_bahra_rfps_v2s"
HERE = Path(__file__).resolve().parent
PROGRESS_FILE = HERE / ".migrate_publish_time_progress.json"
SAVE_EVERY = 50  # flush progress to disk every N rows


# ---------------------------------------------------------------- progress IO

def _now_iso() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")


def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        try:
            with PROGRESS_FILE.open("r", encoding="utf-8") as f:
                p = json.load(f)
            # Ensure new keys exist if file is from an earlier run
            p.setdefault("phase_1_done", False)
            p.setdefault("phase_2_completed_ids", [])
            p.setdefault("phase_3_done", False)
            p.setdefault("phase_4_done", False)
            p.setdefault("phase_5_completed_ids", [])
            p.setdefault("phase_6_done", False)
            p.setdefault("started_at", _now_iso())
            return p
        except Exception as e:
            print(f"[WARN] Could not read progress file ({e}); starting fresh.")
    return {
        "started_at": _now_iso(),
        "phase_1_done": False,
        "phase_2_completed_ids": [],
        "phase_3_done": False,
        "phase_4_done": False,
        "phase_5_completed_ids": [],
        "phase_6_done": False,
    }


def save_progress(p: dict) -> None:
    p["last_updated"] = _now_iso()
    tmp = PROGRESS_FILE.with_suffix(PROGRESS_FILE.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(p, f, indent=2)
    tmp.replace(PROGRESS_FILE)


# ---------------------------------------------------------------- DV helpers

def make_label(text: str) -> dict:
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.Label",
        "LocalizedLabels": [
            {"@odata.type": "Microsoft.Dynamics.CRM.LocalizedLabel",
             "Label": text, "LanguageCode": 1033},
        ],
    }


def get_entity_id(client: DataverseClient, logical_name: str) -> str | None:
    resp = requests.get(
        f"{client.api_url}EntityDefinitions(LogicalName='{logical_name}')?$select=MetadataId",
        headers=client._headers(),
    )
    return resp.json().get("MetadataId") if resp.status_code == 200 else None


def publish_entity(client: DataverseClient, logical_name: str) -> bool:
    resp = requests.post(
        f"{client.api_url}PublishXml",
        json={"ParameterXml": f"<importexportxml><entities><entity>{logical_name}</entity></entities></importexportxml>"},
        headers=client._headers(),
    )
    return resp.status_code in (200, 204)


def add_string_column(client, entity_id, schema_name, display_name, max_length=200) -> bool:
    col_def = {
        "@odata.type": "Microsoft.Dynamics.CRM.StringAttributeMetadata",
        "AttributeType": "String",
        "AttributeTypeName": {"Value": "StringType"},
        "SchemaName": schema_name,
        "DisplayName": make_label(display_name),
        "MaxLength": max_length,
        "RequiredLevel": {"Value": "None", "CanBeChanged": True},
        "FormatName": {"Value": "Text"},
    }
    resp = requests.post(
        f"{client.api_url}EntityDefinitions({entity_id})/Attributes",
        json=col_def, headers=client._headers(),
    )
    if resp.status_code in (200, 201, 204):
        return True
    if resp.status_code in (400, 409):
        err = resp.json().get("error", {}).get("message", "")
        if "already exists" in err.lower():
            return True
    print(f"  [FAIL] Add column {schema_name}: HTTP {resp.status_code} - {resp.text[:300]}")
    return False


def add_datetime_column(client, entity_id, schema_name, display_name) -> bool:
    """TimeZoneIndependent so values are stored literally as KSA-local moments
    (no UTC conversion) — preserves the user-facing "8:10 PM" exactly."""
    col_def = {
        "@odata.type": "Microsoft.Dynamics.CRM.DateTimeAttributeMetadata",
        "AttributeType": "DateTime",
        "AttributeTypeName": {"Value": "DateTimeType"},
        "SchemaName": schema_name,
        "DisplayName": make_label(display_name),
        "RequiredLevel": {"Value": "None", "CanBeChanged": True},
        "Format": "DateAndTime",
        "DateTimeBehavior": {"Value": "TimeZoneIndependent"},
    }
    resp = requests.post(
        f"{client.api_url}EntityDefinitions({entity_id})/Attributes",
        json=col_def, headers=client._headers(),
    )
    if resp.status_code in (200, 201, 204):
        return True
    if resp.status_code in (400, 409):
        err = resp.json().get("error", {}).get("message", "")
        if "already exists" in err.lower():
            return True
    print(f"  [FAIL] Add datetime column {schema_name}: HTTP {resp.status_code} - {resp.text[:300]}")
    return False


def delete_column(client, entity_id, logical_col_name) -> bool:
    resp = requests.get(
        f"{client.api_url}EntityDefinitions({entity_id})/Attributes"
        f"?$filter=LogicalName eq '{logical_col_name}'&$select=MetadataId",
        headers=client._headers(),
    )
    if resp.status_code != 200:
        print(f"  [WARN] Could not look up attribute {logical_col_name}")
        return False
    attrs = resp.json().get("value", [])
    if not attrs:
        print(f"  [INFO] Column {logical_col_name} does not exist (already deleted).")
        return True
    attr_id = attrs[0]["MetadataId"]
    del_resp = requests.delete(
        f"{client.api_url}EntityDefinitions({entity_id})/Attributes({attr_id})",
        headers=client._headers(),
    )
    if del_resp.status_code in (200, 204):
        return True
    print(f"  [FAIL] Delete {logical_col_name}: HTTP {del_resp.status_code} - {del_resp.text[:300]}")
    return False


def parse_to_iso(val: str) -> str | None:
    """Parse 'M/D/YYYY h:MM AM/PM' (and other reasonable formats) to ISO 8601.
    Output uses 'Z' suffix; with TimeZoneIndependent the value is stored as
    that literal moment regardless."""
    if not val or str(val).strip() in ("", "-"):
        return None
    s = str(val).strip()
    try:
        dt = du_parser.parse(s, dayfirst=False)  # treat MDY (project standard)
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


# ---------------------------------------------------------------- main flow

def _resolve_pk_keys(client) -> tuple[str, str | None]:
    """Returns (pk_logical, pk_display_or_None)."""
    pk_logical = f"{TABLE_LOGICAL}id"
    try:
        colmap = client.get_column_mapping(TABLE_LOGICAL)
        logical_to_display = {v: k for k, v in colmap.items()}
        return pk_logical, logical_to_display.get(pk_logical)
    except Exception:
        return pk_logical, None


def _get_record_id(row: dict, pk_logical: str, pk_display: str | None) -> str | None:
    if pk_display:
        rid = row.get(pk_display)
        if rid:
            return rid
    return row.get(pk_logical)


def phase_1_add_backup(client, entity_id, progress) -> None:
    if progress["phase_1_done"]:
        print("[Phase 1/6] Backup column already added — skipping.")
        return
    print("[Phase 1/6] Adding backup column 'bck_publish_time'...")
    if not add_string_column(client, entity_id, "cr673_bck_publish_time", "bck_publish_time", 200):
        print("[FATAL] Could not add backup column.")
        sys.exit(1)
    publish_entity(client, TABLE_LOGICAL)
    time.sleep(5)
    progress["phase_1_done"] = True
    save_progress(progress)
    print("  [OK] Backup column added and published.")


def phase_2_copy_to_backup(client, progress) -> None:
    if progress["phase_3_done"]:
        # Original column has been dropped — Phase 2 is moot.
        print("[Phase 2/6] Original column already dropped — skipping.")
        return
    print("[Phase 2/6] Copying publish_time -> bck_publish_time...")
    rows = client.get_all_rows(
        table_api_name=TABLE_API,
        select_columns=["RFP_ID", "publish_time", "bck_publish_time"],
        table_logical_name=TABLE_LOGICAL,
        use_display_names=True,
    )
    print(f"  Total rows fetched: {len(rows)}")

    pk_logical, pk_display = _resolve_pk_keys(client)
    completed = set(progress["phase_2_completed_ids"])
    to_skip_already_backed = sum(1 for r in rows if (r.get("bck_publish_time") or "").strip())
    print(f"  Resume state: {len(completed)} previously completed; "
          f"{to_skip_already_backed} rows already have a backup value.")

    copied = 0
    skipped_blank = 0
    failures = 0
    since_save = 0
    for i, row in enumerate(rows, 1):
        rid = _get_record_id(row, pk_logical, pk_display)
        if not rid:
            continue
        if rid in completed:
            continue
        # If the backup already has a value (from a prior partial run), record
        # as completed so we don't re-touch it next time.
        if (row.get("bck_publish_time") or "").strip():
            completed.add(rid)
            continue
        src = (row.get("publish_time") or "").strip()
        if not src:
            skipped_blank += 1
            completed.add(rid)
            continue
        try:
            client.update_row(TABLE_API, rid, {"bck_publish_time": src},
                              table_logical_name=TABLE_LOGICAL)
            completed.add(rid)
            copied += 1
            since_save += 1
        except Exception as e:
            failures += 1
            if failures <= 5:
                print(f"  [WARN] Copy failed for record {rid}: {e}")
        if since_save >= SAVE_EVERY:
            progress["phase_2_completed_ids"] = sorted(completed)
            save_progress(progress)
            since_save = 0
            print(f"  ...progress: {copied} copied, {len(completed)} marked done so far.")

    progress["phase_2_completed_ids"] = sorted(completed)
    save_progress(progress)
    print(f"  [OK] Copy complete. copied={copied}, blank_skipped={skipped_blank}, failed={failures}")


def phase_3_drop_original(client, progress) -> None:
    if progress["phase_3_done"]:
        print("[Phase 3/6] Original column already dropped — skipping.")
        return
    print("[Phase 3/6] Dropping original 'cr673_publish_time' column...")
    entity_id = get_entity_id(client, TABLE_LOGICAL)
    if not delete_column(client, entity_id, "cr673_publish_time"):
        print("  [FAIL] Could not delete original column. Aborting.")
        print("  Backup data is safe in 'bck_publish_time'.")
        sys.exit(1)
    publish_entity(client, TABLE_LOGICAL)
    time.sleep(10)
    progress["phase_3_done"] = True
    save_progress(progress)
    print("  [OK] Original column deleted and published.")


def phase_4_create_datetime(client, progress) -> None:
    if progress["phase_4_done"]:
        print("[Phase 4/6] DateTime column already created — skipping.")
        return
    print("[Phase 4/6] Creating new 'cr673_publish_time' as DateTime "
          "(TimeZoneIndependent)...")
    entity_id = get_entity_id(client, TABLE_LOGICAL)
    if not add_datetime_column(client, entity_id, "cr673_publish_time", "publish_time"):
        print("  [FAIL] Could not create DateTime column. Aborting.")
        sys.exit(1)
    publish_entity(client, TABLE_LOGICAL)
    time.sleep(10)
    client.clear_column_mapping_cache(TABLE_LOGICAL)
    progress["phase_4_done"] = True
    save_progress(progress)
    print("  [OK] DateTime column created and published.")


def phase_5_migrate_data(client, progress) -> None:
    print("[Phase 5/6] Parsing backup text -> writing ISO datetime to new column...")
    client.clear_column_mapping_cache(TABLE_LOGICAL)
    rows = client.get_all_rows(
        table_api_name=TABLE_API,
        select_columns=["RFP_ID", "bck_publish_time", "publish_time"],
        table_logical_name=TABLE_LOGICAL,
        use_display_names=True,
    )
    print(f"  Total rows fetched: {len(rows)}")

    pk_logical, pk_display = _resolve_pk_keys(client)
    completed = set(progress["phase_5_completed_ids"])
    print(f"  Resume state: {len(completed)} previously completed.")

    migrated = 0
    parse_failures = 0
    write_failures = 0
    blank_skipped = 0
    already_set = 0
    since_save = 0
    bad_samples: list[str] = []

    for i, row in enumerate(rows, 1):
        rid = _get_record_id(row, pk_logical, pk_display)
        if not rid:
            continue
        if rid in completed:
            continue
        # If the new publish_time is already populated (from a prior run or new
        # ingestion), don't overwrite — just mark complete.
        if row.get("publish_time"):
            already_set += 1
            completed.add(rid)
            continue
        src = (row.get("bck_publish_time") or "").strip()
        if not src:
            blank_skipped += 1
            completed.add(rid)
            continue
        iso = parse_to_iso(src)
        if not iso:
            parse_failures += 1
            if len(bad_samples) < 10:
                bad_samples.append(src)
            continue
        try:
            client.update_row(TABLE_API, rid, {"publish_time": iso},
                              table_logical_name=TABLE_LOGICAL)
            completed.add(rid)
            migrated += 1
            since_save += 1
        except Exception as e:
            write_failures += 1
            if write_failures <= 5:
                print(f"  [WARN] Write failed for record {rid} (value '{src}' -> '{iso}'): {e}")
        if since_save >= SAVE_EVERY:
            progress["phase_5_completed_ids"] = sorted(completed)
            save_progress(progress)
            since_save = 0
            print(f"  ...progress: {migrated} migrated so far.")

    progress["phase_5_completed_ids"] = sorted(completed)
    save_progress(progress)
    print(f"  [OK] Migration complete. migrated={migrated}, "
          f"already_set={already_set}, blank_skipped={blank_skipped}, "
          f"parse_failures={parse_failures}, write_failures={write_failures}")
    if bad_samples:
        print("  Sample unparseable values:")
        for s in bad_samples:
            print(f"    - {s!r}")


def phase_6_publish(client, progress) -> None:
    if progress["phase_6_done"]:
        print("[Phase 6/6] Final publish already done — skipping.")
        return
    print("[Phase 6/6] Final PublishXml on entity...")
    publish_entity(client, TABLE_LOGICAL)
    progress["phase_6_done"] = True
    save_progress(progress)
    print("  [OK] Published.")


def _print_progress_summary(progress: dict) -> None:
    print("-" * 64)
    print(f"  Progress file: {PROGRESS_FILE}")
    print(f"  Started:       {progress.get('started_at', '?')}")
    print(f"  Last updated:  {progress.get('last_updated', '?')}")
    print("-" * 64)
    for ph, label in [
        (1, "add backup column"),
        (2, "copy publish_time -> backup"),
        (3, "drop original column"),
        (4, "create new DateTime column"),
        (5, "parse text -> write DateTime"),
        (6, "final publish"),
    ]:
        flag = bool(progress.get(f"phase_{ph}_done"))
        marker = "[x]" if flag else "[ ]"
        print(f"  {marker} Phase {ph} — {label}")
    print(f"  Phase-2 record IDs marked done: {len(progress.get('phase_2_completed_ids', []))}")
    print(f"  Phase-5 record IDs marked done: {len(progress.get('phase_5_completed_ids', []))}")
    print("-" * 64)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate cr673_publish_time from STRING to DATETIME (TimeZoneIndependent).",
    )
    parser.add_argument("--reset", action="store_true",
                        help="Delete the progress file before running (start over from Phase 1).")
    parser.add_argument("--show-progress", action="store_true",
                        help="Print current progress and exit (no Dataverse calls).")
    args = parser.parse_args()

    if args.reset:
        if PROGRESS_FILE.exists():
            PROGRESS_FILE.unlink()
            print(f"[RESET] Deleted {PROGRESS_FILE}")
        else:
            print(f"[RESET] No progress file at {PROGRESS_FILE} (nothing to delete).")

    if args.show_progress:
        _print_progress_summary(load_progress())
        return

    print("=" * 64)
    print("  Migrate publish_time: STRING -> DATETIME (TimeZoneIndependent)")
    print("  Table: cr673_bahra_rfps_v2")
    print(f"  Progress file: {PROGRESS_FILE}")
    print("=" * 64)

    client = DataverseClient(TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL)
    print("[AUTH] Ready.\n")

    entity_id = get_entity_id(client, TABLE_LOGICAL)
    if not entity_id:
        print("[FATAL] Cannot find entity metadata!")
        sys.exit(1)
    print(f"[OK] Entity ID: {entity_id}\n")

    progress = load_progress()

    try:
        phase_1_add_backup(client, entity_id, progress)
        print()
        phase_2_copy_to_backup(client, progress)
        print()
        phase_3_drop_original(client, progress)
        print()
        phase_4_create_datetime(client, progress)
        print()
        phase_5_migrate_data(client, progress)
        print()
        phase_6_publish(client, progress)
    except KeyboardInterrupt:
        print("\n[INTERRUPT] Caught Ctrl+C. Saving progress and exiting — re-run to resume.")
        save_progress(progress)
        sys.exit(130)

    print()
    print("=" * 64)
    print("  Migration complete!")
    print(f"  Phase-2 records copied to backup: {len(progress['phase_2_completed_ids'])}")
    print(f"  Phase-5 records migrated to new DT col: {len(progress['phase_5_completed_ids'])}")
    print("  Backup column 'bck_publish_time' RETAINED for safety.")
    print("=" * 64)
    print()
    print("  NEXT STEPS — patch writer code so future inserts send ISO 8601:")
    print("    * core/log_events.py            (normalize_publish_time)")
    print("    * rfp/download_rfp.py           (store_rfp_in_database calls)")
    print("    * automation_logic.py:1531      (store_rfp_in_database)")
    print("    * Support-Files/sync_rfp_publish_date.py:321")
    print("    * Support-Files/normalize_publish_time_format.py:321")
    print("    * Support-Files/fix_missing_publish_date.py:195")
    print("    * Support-Files/download_all_company_rfps.py:260")
    print()


if __name__ == "__main__":
    main()
