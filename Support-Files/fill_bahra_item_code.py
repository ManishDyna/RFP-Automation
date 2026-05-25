"""
Fill the `bahra_item_code` column in the cr673_bahra_material_master Dataverse
table for the material codes provided by the user (mapping extracted from the
4 Bahra material list screenshots).

Pre-conditions
--------------
1. The bahra_item_code column already exists on the table. Logical name is
   `cr6db_bahra_item_code` (different publisher prefix from the rest of the
   table's `cr673_*` columns, so it is written using the logical name directly
   to bypass the display-name lookup).

Behaviour
---------
* For each (material_code, bahra_item_code) mapping:
    - If the material_code row EXISTS, PATCH `bahra_item_code` and refresh
      `updated_date`.
    - If the material_code row is MISSING, INSERT a new row with
      `material_code`, `description` (from screenshots when available),
      `bahra_item_code`, `is_active='true'`, and both `created_date` and
      `updated_date` set to "now".
* Idempotent: re-running rewrites the same value; no duplicates are created
  because INSERT only fires when the lookup returns zero rows.
* Special cases preserved verbatim:
    - `BEL908202xxx-SEC` items   -> stored as-is.
    - `FCS00647 / FCS00643`      -> stored as the literal slash-separated string.
* Date format follows what's already in the table: `%Y-%m-%d %H:%M:%S`.

Usage
-----
    python Support-Files\fill_bahra_item_code.py             # apply updates + inserts
    python Support-Files\fill_bahra_item_code.py --dry-run   # preview only
"""

import sys
import argparse
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from helpers.dataverse_helper import DataverseClient
from config.config import (
    TENANT_ID,
    CLIENT_ID,
    CLIENT_SECRET,
    RESOURCE_URL,
    MATERIAL_MASTER_TABLE_LOGICAL,
    MATERIAL_MASTER_TABLE_API,
)


# Material Code -> Bahra Item Code (verbatim from screenshots).
MAPPINGS: dict[str, str] = {
    # ---- Cables (screenshot 1) ----
    "908101001": "71050004",
    "908101002": "71050002",
    "908111001": "14510025",
    "908111002": "14510026",
    "908111003": "14510027",
    "908111004": "14510028",
    "908111005": "14710315",
    "908111006": "14710316",
    "908111007": "14710317",
    "908111010": "13413021",
    "908111011": "13413020",
    "908111101": "14110200",
    "908111102": "14110210",
    "908112120": "71090020",
    "908113004": "23210604",
    "908113005": "23010603",
    "908113006": "25010610",
    "908113009": "25010601",
    "908114004": "23402612",
    "908114005": "25402609",
    # ---- Hardware / Pole accessories (screenshots 2-4) ----
    "908202032": "FCS00645",
    "908202042": "FCS00635",
    "908202044": "FCS00866",
    "908202053": "BEL908202053-SEC",
    "908202054": "BEL908202054-SEC",
    "908202067": "FCS00636",
    "908202080": "FCS00637",
    "908202081": "FCS00638",
    "908202082": "FCS00639",
    "908202086": "FCS00644",
    "908202186": "FCS00640",
    "908202189": "BEL908202189-SEC",
    "908202204": "FCS00641",
    "908202205": "FCS00642",
    "908202207": "FCS00646",
    "908202212": "BEL908202212-SEC",
    "908202228": "FCS00647 / FCS00643",
    "908202098": "BEL908202098-SEC",
    "908202260": "FCS00862",
    "908202258": "FCS00863",
    "908202265": "FCS00867",
    "908202263": "FCS00871",
    "908202242": "FCS00930",
    "908202243": "FCS00931",
    "908202244": "FCS00932",
    "908202245": "FCS00933",
    "908202246": "FCS00934",
    "908202247": "FCS00935",
    "908202259": "FCS00936",
    "908202248": "FCS00881",
    "908202249": "FCS00880",
    "908202250": "FCS00879",
    "908202251": "FCS00878",
    "908202252": "FCS00877",
    "908202253": "FCS00876",
    "908202254": "FCS00874",
    "908202255": "FCS00875",
    "908202256": "FCS00873",
    "908202257": "FCS00872",
    "908202262": "FCS00868",
    "908202264": "FCS00869",
    "908202266": "FCS00860",
    "908202267": "FCS00861",
    "908202268": "FCS00882",
    "908202272": "FCS00883",
    "908202273": "FCS00884",
    "908202274": "FCS00886",
    "908202275": "FCS00885",
    "908202276": "FCS00887",
    "908202277": "FCS00888",
    "908202278": "FCS00889",
    "908202279": "FCS00890",
    "908202280": "FCS00891",
}


# Descriptions are only required for INSERTs (rows whose material_code is not
# already in the table). Pulled verbatim from the screenshots so the new rows
# look the same as the rest of the table. Existing rows are not touched.
DESCRIPTIONS: dict[str, str] = {
    "908101002": "CNDCTR, BR, ACSR, Merlin (336.4MCM), 18AL, 1ALWLD, 170MM2",
    "908111001": "CABLE, PWR, 600V/1KV, CU, 1C, 35MM2, XLPE",
    "908202098": "CLAMP,GRD,BRZ,35-70SQMM CU,16MM DIA CWLD",
    "908202260": "DOUBLE ARMING PLATE  HDG 120 (H) X 750 (W) X 12 MM - 908202260",
    "908202258": "DOUBLE ARMING PLATE  HDG 120 (H) X 590 (W) X 12 MM - 908202258",
    "908202265": "CROSSARM FOR SPECIAL POLE STRUCTURES, TYPE- SP-1 HDG 160x160x14x3700mm-908202265",
    "908202263": "CROSSARM BRACES (SET) FOR SPECIAL POLE STRUCTURES 60 X 60 X 5 MM-908202263",
    "908202242": "POLE BAND -STAY CLAMP- FOR CONCRETE POLE STRUCTURES- DIA 390 mm- 908202242",
    "908202243": "POLE BAND -STAY CLAMP- FOR CONCRETE POLE STRUCTURES- DIA 370 mm- 908202243",
    "908202244": "POLE BAND -STAY CLAMP- FOR CONCRETE POLE STRUCTURES- DIA 355 mm- 908202244",
    "908202245": "POLE BAND -STAY CLAMP- FOR CONCRETE POLE STRUCTURES- DIA 300 mm- 908202245",
    "908202246": "POLE BAND -STAY CLAMP- FOR CONCRETE POLE STRUCTURES- DIA 267 mm- 908202246",
    "908202247": "POLE BAND -STAY CLAMP- FOR CONCRETE POLE STRUCTURES- DIA 194 mm- 908202247",
    "908202259": "DOUBLE-ARMING PLATE FOR CP13S & CP14D CONCRETE POLE STRUCTURES- 908202259",
    "908202248": "POLE BAND -STAY CLAMP- FOR SPECIAL POLE STRUCTURES-TYPE 2-908202248",
    "908202249": "POLE BAND -STAY CLAMP- FOR SPECIAL POLE STRUCTURES-TYPE 2-908202249",
    "908202250": "POLE BAND -STAY CLAMP- FOR SPECIAL POLE STRUCTURES-TYPE 1-908202250",
    "908202251": "POLE BAND-STAY CLAMP- FOR SPECIAL POLE STRUCTURES-TYPE 1-908202251",
    "908202252": "POLE BAND -STAY CLAMP- FOR SPECIAL POLE STRUCTURES-TYPE 1-908202252",
    "908202253": "POLE BAND-STAY CLAMP- FOR SPECIAL POLE STRUCTURES-TYPE 1-908202253",
    "908202254": "POLE BAND -STAY CLAMP- FOR SPECIAL POLE STRUCTURES-TYPE 1-908202254",
    "908202255": "POLE BAND-STAY CLAMP- FOR SPECIAL POLE STRUCTURES-TYPE 1-908202255",
    "908202256": "POLE BAND -STAY CLAMP- FOR SPECIAL POLE STRUCTURES-TYPE 1-908202256",
    "908202257": "EARTHWIRE SUSPENSION SUPPORT FOR SPECIAL POLE STRUCTURES L120x12THKx150LG-908202257",
    "908202262": "CROSSARM FOR SPECIAL POLE STRUCTURES, TYPE-SP-2-908202262",
    "908202264": "CROSSARM FOR SPECIAL POLE STRUCTURES, TYPE-SP-3-908202264",
    "908202266": "STEEL PLATE  HDG 450 (W) X 450 (L) X 12 MM -26MM HOLE- 908202266",
    "908202267": "STEEL PLATE  HDG 450 (W) X 450 (L) X 12 MM -34MM HOLE- 908202267",
    "908202268": "EARTHWIRE SUSPENSION SUPPORT FOR SPECIAL POLE STRUCTURES L120x12THKx150LG-908202268",
    "908202272": "ALLEY ARM BRACE FOR SPECIAL POLE STRUCTURES-908202272",
    "908202273": "ALLEY ARM BRACE FOR SPECIAL POLE STRUCTURES-908202273",
    "908202274": "ALLEY ARM BRACE FOR SPECIAL POLE STRUCTURES-908202274",
    "908202275": "ALLEY ARM BRACE FOR SPECIAL POLE STRUCTURES-908202275",
    "908202276": "ALLEY ARM BRACE FOR SPECIAL POLE STRUCTURES-908202276",
    "908202277": "ALLEY ARM BRACE FOR SPECIAL POLE STRUCTURES- 908202277",
    "908202278": "ALLEY ARM BRACE FOR SPECIAL POLE STRUCTURES-908202278",
    "908202279": "ALLEY ARM BRACE FOR SPECIAL POLE STRUCTURES-908202279",
    "908202280": "ALLEY ARM BRACE FOR SPECIAL POLE STRUCTURES-908202280",
}


def _now_str() -> str:
    # Match the format already used on existing rows in the table:
    # `2026-02-27 06:58:18`. This is the same format produced by
    # services/master_data_service.py::_now_iso() which writes
    # `%Y-%m-%d %H:%M:%S`. UTC, no timezone suffix.
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def find_record_id(client: DataverseClient, material_code: str) -> str | None:
    """Return the record_id for the row whose material_code matches, or None.

    Note: the helper post-processes query results and rewrites the PK column
    name from logical (`cr673_bahra_material_masterid`) to its display label
    (`Bahra Material Master`). So we look it up under the display name first,
    falling back to the logical name for safety.
    """
    pk_logical = f"{MATERIAL_MASTER_TABLE_LOGICAL}id"
    column_map = client.get_column_mapping(MATERIAL_MASTER_TABLE_LOGICAL)
    logical_to_display = {v: k for k, v in column_map.items()}
    pk_display = logical_to_display.get(pk_logical)

    escaped = material_code.replace("'", "''")
    result = client.query_rows(
        table_api_name=MATERIAL_MASTER_TABLE_API,
        filter_expr=f"material_code eq '{escaped}'",
        select="material_code",
        top=2,
        table_logical_name=MATERIAL_MASTER_TABLE_LOGICAL,
        use_display_names=True,
    )
    rows = result.get("value", []) if isinstance(result, dict) else []
    if not rows:
        return None
    if len(rows) > 1:
        print(f"  [WARN] Multiple rows found for material_code '{material_code}' "
              f"({len(rows)} matches). Updating the first one.")
    row = rows[0]
    return (row.get(pk_display) if pk_display else None) or row.get(pk_logical)


def diagnose(client: DataverseClient) -> None:
    """Print table metadata + first 10 rows so we can see why filters miss."""
    import requests

    print("--- DIAGNOSE: table metadata ---")
    meta_url = (
        f"{client.api_url}EntityDefinitions(LogicalName='{MATERIAL_MASTER_TABLE_LOGICAL}')"
        f"?$select=LogicalName,EntitySetName,SchemaName,LogicalCollectionName"
    )
    r = requests.get(meta_url, headers=client._headers())
    print(f"  HTTP {r.status_code}")
    if r.status_code == 200:
        for k, v in r.json().items():
            if not k.startswith("@"):
                print(f"  {k}: {v}")
    else:
        print(f"  {r.text[:400]}")

    print("\n--- DIAGNOSE: total row count (unfiltered) ---")
    count_url = f"{client.api_url}{MATERIAL_MASTER_TABLE_API}/$count"
    r = requests.get(count_url, headers={**client._headers(), "Prefer": "odata.maxpagesize=1"})
    print(f"  HTTP {r.status_code}  body: {r.text[:200]}")

    print("\n--- DIAGNOSE: first 10 rows (raw, no display-name mapping) ---")
    raw_url = f"{client.api_url}{MATERIAL_MASTER_TABLE_API}?$top=10"
    r = requests.get(raw_url, headers=client._headers())
    if r.status_code != 200:
        print(f"  HTTP {r.status_code}: {r.text[:400]}")
        return
    rows = r.json().get("value", [])
    print(f"  Got {len(rows)} rows")
    if rows:
        print(f"\n  Columns present on row 0:")
        for k in sorted(rows[0].keys()):
            if k.startswith("@") or k.startswith("_"):
                continue
            v = rows[0][k]
            print(f"    {k!r:45s} = {v!r}")
        print(f"\n  material_code-ish values in first 10 rows:")
        for i, row in enumerate(rows):
            mc = (
                row.get("cr673_material_code")
                or row.get("cr673_materialcode")
                or row.get("cr673_material")
                or "<missing>"
            )
            print(f"    [{i}] cr673_material_code = {mc!r}")

    print("\n--- DIAGNOSE: try filter for one specific code (908101001) ---")
    filter_url = (
        f"{client.api_url}{MATERIAL_MASTER_TABLE_API}"
        f"?$filter=cr673_material_code eq '908101001'&$top=2"
    )
    r = requests.get(filter_url, headers=client._headers())
    print(f"  HTTP {r.status_code}")
    if r.status_code == 200:
        v = r.json().get("value", [])
        print(f"  Rows: {len(v)}")
        for row in v:
            print(f"    -> cr673_material_code = {row.get('cr673_material_code')!r}")
    else:
        print(f"  {r.text[:400]}")

    print("\n--- DIAGNOSE: full display->logical column mapping for this table ---")
    column_map = client.get_column_mapping(MATERIAL_MASTER_TABLE_LOGICAL)
    print(f"  {len(column_map)} mappings:")
    for display, logical in sorted(column_map.items()):
        print(f"    {display!r:45s} -> {logical!r}")

    print("\n--- DIAGNOSE: simulate find_record_id's filter substitution ---")
    test_filter = "material_code eq '908101001'"
    print(f"  Before: {test_filter!r}")
    after = test_filter
    for display, logical in column_map.items():
        new_after = after.replace(display, logical)
        if new_after != after:
            print(f"    .replace({display!r}, {logical!r})  ->  {new_after!r}")
            after = new_after
    print(f"  After:  {after!r}")

    print("\n--- DIAGNOSE: call helper.query_rows exactly as the script does ---")
    pk_logical = f"{MATERIAL_MASTER_TABLE_LOGICAL}id"
    result = client.query_rows(
        table_api_name=MATERIAL_MASTER_TABLE_API,
        filter_expr="material_code eq '908101001'",
        select="material_code",
        top=2,
        table_logical_name=MATERIAL_MASTER_TABLE_LOGICAL,
        use_display_names=True,
    )
    rows = result.get("value", []) if isinstance(result, dict) else []
    print(f"  Helper returned {len(rows)} rows")
    for row in rows:
        print(f"    row keys: {list(row.keys())}")
        print(f"    pk ({pk_logical}): {row.get(pk_logical)!r}")
        print(f"    material_code: {row.get('material_code')!r}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Look up record IDs but skip the PATCH calls.",
    )
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="Print table metadata, row count, and sample rows to find why "
             "material_code lookups miss. Skips updates.",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("  Fill bahra_item_code in Bahra Material Master")
    print("=" * 70)
    print(f"  Dataverse:   {RESOURCE_URL}")
    print(f"  Table (API): {MATERIAL_MASTER_TABLE_API}")
    print(f"  Mappings:    {len(MAPPINGS)}")
    print(f"  Mode:        {'DRY-RUN' if args.dry_run else 'LIVE UPDATE'}")
    print()

    client = DataverseClient(
        tenant_id=TENANT_ID,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        resource_url=RESOURCE_URL,
    )
    print("[AUTH] Token acquired.\n")

    if args.diagnose:
        diagnose(client)
        return

    now_str = _now_str()
    updated = inserted = failed = 0
    inserted_without_description: list[str] = []
    failed_codes: list[tuple[str, str]] = []

    for material_code, bahra_item_code in MAPPINGS.items():
        try:
            record_id = find_record_id(client, material_code)
        except Exception as e:
            failed += 1
            failed_codes.append((material_code, f"lookup error: {e}"))
            print(f"  [FAIL] {material_code}: lookup error - {e}")
            continue

        # ----- UPDATE branch (row already exists) -----
        if record_id:
            if args.dry_run:
                print(f"  [DRY ] UPDATE {material_code} -> '{bahra_item_code}'  (record_id={record_id})")
                updated += 1
                continue
            try:
                client.update_row(
                    table_api_name=MATERIAL_MASTER_TABLE_API,
                    record_id=record_id,
                    data={
                        # Use logical name directly — column lives under the
                        # cr6db_ prefix, not cr673_, so the display-name map
                        # built from cr673_* columns won't resolve it.
                        "cr6db_bahra_item_code": bahra_item_code,
                        "updated_date": now_str,
                    },
                    table_logical_name=MATERIAL_MASTER_TABLE_LOGICAL,
                    use_display_names=True,
                )
                updated += 1
                print(f"  [OK]   UPDATE {material_code} -> '{bahra_item_code}'")
            except Exception as e:
                failed += 1
                failed_codes.append((material_code, str(e)[:200]))
                print(f"  [FAIL] UPDATE {material_code}: {str(e)[:200]}")
            continue

        # ----- INSERT branch (row missing) -----
        description = DESCRIPTIONS.get(material_code, "")
        if not description:
            inserted_without_description.append(material_code)

        if args.dry_run:
            print(f"  [DRY ] INSERT {material_code} -> '{bahra_item_code}'  "
                  f"desc={description[:50]!r}{'...' if len(description) > 50 else ''}")
            inserted += 1
            continue

        try:
            ok = client.insert_row(
                table_api_name=MATERIAL_MASTER_TABLE_API,
                data={
                    "material_code": material_code,
                    "description": description,
                    "is_active": "true",
                    "created_date": now_str,
                    "updated_date": now_str,
                    # Cross-prefix column — pass logical name directly.
                    "cr6db_bahra_item_code": bahra_item_code,
                },
                table_logical_name=MATERIAL_MASTER_TABLE_LOGICAL,
                use_display_names=True,
            )
            if ok:
                inserted += 1
                print(f"  [OK]   INSERT {material_code} -> '{bahra_item_code}'")
            else:
                failed += 1
                failed_codes.append((material_code, "insert returned False"))
                print(f"  [FAIL] INSERT {material_code}: returned False")
        except Exception as e:
            failed += 1
            failed_codes.append((material_code, str(e)[:200]))
            print(f"  [FAIL] INSERT {material_code}: {str(e)[:200]}")

    print()
    print("=" * 70)
    print("  Summary")
    print("=" * 70)
    print(f"  Updated  : {updated}  (existing rows whose bahra_item_code was set)")
    print(f"  Inserted : {inserted}  (new rows created with today's date)")
    print(f"  Failed   : {failed}")
    if inserted_without_description:
        print("\n  Inserted with EMPTY description (not in DESCRIPTIONS dict):")
        for c in inserted_without_description:
            print(f"    - {c}")
    if failed_codes:
        print("\n  Failed operations:")
        for code, err in failed_codes:
            print(f"    - {code}: {err}")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
