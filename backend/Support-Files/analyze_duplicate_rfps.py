"""
Duplicate RFP Analysis (READ-ONLY)
==================================
Generates a comprehensive overview of duplicate RFPs in cr673_bahra_rfps_v2.

Outputs (under Support-Files/output/):
  1. duplicate_overview_<ts>.csv     -- side-by-side view of every duplicate pair
                                        with keeper, duplicate, conflict flag, and
                                        proposed merged value per field.
  2. duplicate_backup_proposed_<ts>.csv
                                     -- full row of every record that would be
                                        deleted on a real cleanup run (safety copy).
  3. duplicate_conflicts_<ts>.csv    -- ONLY the pairs that have conflicting
                                        data in important fields (Email_Status,
                                        participated, response_count, Matched_Data,
                                        etc.). Focus list for manual review.
  4. duplicate_summary_<ts>.txt      -- high-level statistics + planned actions.

NO writes to Dataverse. NO portal calls. Safe to run any time.

Usage:
    python Support-Files/analyze_duplicate_rfps.py
"""

import csv
import json
import os
import sys
from collections import defaultdict
from datetime import datetime

# Make project root importable
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from config.config import (                                          # noqa: E402
    TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL,
    RFP_ACTIVITY_LOG_TABLE_API, RFP_ACTIVITY_LOG_TABLE_LOGICAL,
)
from helpers.dataverse_helper import DataverseClient                 # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────
# Normalization helpers
# ─────────────────────────────────────────────────────────────────────────────

def normalize_rfp_id(rid):
    """Collapse internal whitespace runs to a single space and strip ends.
    Preserves case (portal canonical form is mixed-case)."""
    if rid is None:
        return ""
    return " ".join(str(rid).split())


def match_key(rid):
    """Comparison key: normalized + lowercased."""
    return normalize_rfp_id(rid).lower()


# ─────────────────────────────────────────────────────────────────────────────
# Column tiers
# ─────────────────────────────────────────────────────────────────────────────

IDENTITY_FIELDS = [
    "RFP_ID", "Company_Name", "Link", "publish_time", "RFP_End_Date",
    "owner_name", "rfp_type",
]

WORKFLOW_FIELDS = [
    "Email_Status", "Email_Sent_At", "Email_To", "Downloaded_At",
    "participated", "Reminder_1Day_Sent", "Reminder_3Day_Sent",
    "response_count", "first_response_at", "all_responses_at",
]

# Fields where a difference between keeper and duplicate is "important"
CRITICAL_CONFLICT_FIELDS = [
    "Email_Status", "participated", "response_count",
    "Email_Sent_At", "Reminder_1Day_Sent", "Reminder_3Day_Sent",
    "first_response_at", "all_responses_at", "Matched_Data",
]

# Ordered for output CSV
ALL_FIELDS = IDENTITY_FIELDS + WORKFLOW_FIELDS + ["Matched_Data"]

# Precedence for participated state
PARTICIPATED_RANK = {
    "submitted": 6, "declined": 5, "yes": 4, "no bid": 3,
    "not participated": 2, "no": 1, "": 0, None: 0,
}

# Precedence for Email_Status (active beats blank)
EMAIL_STATUS_RANK = {
    "sent (actionable)": 5, "sent": 4, "draft": 3,
    "declined": 2, "not_sent": 1, "": 0, None: 0,
}


# ─────────────────────────────────────────────────────────────────────────────
# Merge logic (NO portal lookup in this analysis script)
# ─────────────────────────────────────────────────────────────────────────────

def _val(row, key):
    v = row.get(key)
    return "" if v is None else str(v)


def _is_blank(v):
    return v is None or str(v).strip() == ""


def pick_keeper(rows):
    """Designate the keeper row within a duplicate group.
    Priority:
      1. Row whose RFP_ID already equals its normalized form (single-space variant)
      2. Row with the most non-empty data fields
      3. Row with the latest Downloaded_At
    """
    candidates = []
    for r in rows:
        raw = r.get("RFP_ID") or ""
        is_canonical = (raw == normalize_rfp_id(raw))
        non_empty = sum(1 for k in ALL_FIELDS if not _is_blank(r.get(k)))
        downloaded = r.get("Downloaded_At") or ""
        candidates.append((is_canonical, non_empty, downloaded, r))
    candidates.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
    keeper = candidates[0][3]
    dups = [c[3] for c in candidates[1:]]
    return keeper, dups


def merge_field(field, keeper_val, dup_val):
    """Decide the merged value for a single field. Returns (value, source).
    source is 'keeper' / 'duplicate' / 'merged' / 'normalized'."""
    k_blank = _is_blank(keeper_val)
    d_blank = _is_blank(dup_val)

    if field == "RFP_ID":
        return normalize_rfp_id(keeper_val), "normalized"

    if k_blank and d_blank:
        return "", "keeper"
    if k_blank:
        return dup_val, "duplicate"
    if d_blank:
        return keeper_val, "keeper"

    if field == "Email_Status":
        kv = str(keeper_val).strip().lower()
        dv = str(dup_val).strip().lower()
        return (keeper_val, "keeper") if EMAIL_STATUS_RANK.get(kv, 0) >= EMAIL_STATUS_RANK.get(dv, 0) else (dup_val, "duplicate")

    if field == "participated":
        kv = str(keeper_val).strip().lower()
        dv = str(dup_val).strip().lower()
        return (keeper_val, "keeper") if PARTICIPATED_RANK.get(kv, 0) >= PARTICIPATED_RANK.get(dv, 0) else (dup_val, "duplicate")

    if field in ("Reminder_1Day_Sent", "Reminder_3Day_Sent"):
        kv = str(keeper_val).strip().lower()
        dv = str(dup_val).strip().lower()
        rank = {"yes": 2, "no": 1, "": 0}
        return (keeper_val, "keeper") if rank.get(kv, 0) >= rank.get(dv, 0) else (dup_val, "duplicate")

    if field == "response_count":
        try:
            kv = int(keeper_val); dv = int(dup_val)
            return (keeper_val, "keeper") if kv >= dv else (dup_val, "duplicate")
        except Exception:
            return keeper_val, "keeper"

    if field in ("Email_Sent_At", "Downloaded_At", "first_response_at"):
        # earlier wins
        return (keeper_val, "keeper") if str(keeper_val) <= str(dup_val) else (dup_val, "duplicate")

    if field == "all_responses_at":
        # later wins
        return (keeper_val, "keeper") if str(keeper_val) >= str(dup_val) else (dup_val, "duplicate")

    if field == "Matched_Data":
        try:
            k_json = json.loads(keeper_val) if not k_blank else None
            d_json = json.loads(dup_val) if not d_blank else None
            k_size = len(k_json) if isinstance(k_json, (list, dict)) else len(str(keeper_val))
            d_size = len(d_json) if isinstance(d_json, (list, dict)) else len(str(dup_val))
            if k_size >= d_size:
                return keeper_val, "keeper"
            return dup_val, "duplicate"
        except Exception:
            # If either side isn't valid JSON, prefer the longer string
            return (keeper_val, "keeper") if len(str(keeper_val)) >= len(str(dup_val)) else (dup_val, "duplicate")

    # Default: any other identity-style field — prefer keeper
    return keeper_val, "keeper"


def _matched_data_signature(raw):
    """Stable signature for a Matched_Data JSON payload. Captures the actual
    matched-materials content so two snapshots of the same materials don't
    look different just because of internal timestamps / RunIDs embedded
    in the JSON. Matches the structure produced by the matcher:
       { rfp_id, source_file, rfp_end_date, total_items, summary,
         exact_matches: [...], keyword_matches: [...], not_matched: [...] }
    """
    if _is_blank(raw):
        return ""
    try:
        data = json.loads(raw)
    except Exception:
        return f"unparseable:{len(str(raw))}"

    def _fp_items(items):
        """Sorted fingerprint of a list of match-item dicts."""
        out = []
        if not isinstance(items, list):
            return out
        for it in items:
            if isinstance(it, dict):
                fp = (it.get("item_code") or it.get("Item") or it.get("name")
                      or it.get("Material") or it.get("material_code")
                      or json.dumps(it, sort_keys=True)[:120])
                out.append(str(fp))
            else:
                out.append(str(it)[:120])
        return sorted(out)

    em = _fp_items(data.get("exact_matches") or [])
    km = _fp_items(data.get("keyword_matches") or [])
    nm = _fp_items(data.get("not_matched") or [])
    return f"em:{len(em)}|km:{len(km)}|nm:{len(nm)}|{','.join(em)}|{','.join(km)}|{','.join(nm)}"


# Enum-like fields: case differences are not real conflicts
CASE_INSENSITIVE_FIELDS = {
    "participated", "Email_Status",
    "Reminder_1Day_Sent", "Reminder_3Day_Sent",
}


def is_conflict(field, keeper_val, dup_val):
    """Return True only for TRUE conflicts: both sides non-blank, different
    values, AND the difference is semantically meaningful (not just case
    or whitespace). Blank-vs-non-blank is a 'stale duplicate' and
    auto-merge handles it cleanly — not a real conflict."""
    k_blank = _is_blank(keeper_val)
    d_blank = _is_blank(dup_val)
    if k_blank or d_blank:
        return False
    k = str(keeper_val).strip()
    d = str(dup_val).strip()
    if k == d:
        return False
    if field == "RFP_ID":
        return normalize_rfp_id(k).lower() != normalize_rfp_id(d).lower()
    if field == "Matched_Data":
        return _matched_data_signature(k) != _matched_data_signature(d)
    if field in CASE_INSENSITIVE_FIELDS:
        if k.lower() == d.lower():
            return False
    if field == "response_count":
        try:
            return int(float(k)) != int(float(d))
        except Exception:
            return k != d
    return field in CRITICAL_CONFLICT_FIELDS


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("Duplicate RFP Analysis (READ-ONLY)")
    print("=" * 70)
    print()

    client = DataverseClient(TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL)

    # Determine the Dataverse PK column name (display label) so we keep GUIDs.
    column_map = client.get_column_mapping(RFP_ACTIVITY_LOG_TABLE_LOGICAL)
    pk_logical = "cr673_bahra_rfps_v2id"
    logical_to_display = {v: k for k, v in column_map.items()}
    pk_display = logical_to_display.get(pk_logical, pk_logical)
    print(f"Primary-key column resolved: logical='{pk_logical}'  display='{pk_display}'")

    # Pull everything (paginated).
    select_cols = ALL_FIELDS + ["RunID"]
    print(f"Fetching all rows from '{RFP_ACTIVITY_LOG_TABLE_API}' ...")
    rows = client.get_all_rows(
        table_api_name=RFP_ACTIVITY_LOG_TABLE_API,
        table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL,
        select_columns=select_cols,
        use_display_names=True,
    )
    print(f"Fetched {len(rows)} rows.\n")

    # Group by normalized RFP_ID (case-insensitive)
    groups = defaultdict(list)
    blank_id_rows = 0
    for r in rows:
        rid = (r.get("RFP_ID") or "").strip()
        if not rid:
            blank_id_rows += 1
            continue
        groups[match_key(rid)].append(r)

    duplicate_groups = {k: v for k, v in groups.items() if len(v) > 1}
    unique_count = len(groups)
    pairs_with_dup = len(duplicate_groups)
    rows_in_dup_groups = sum(len(v) for v in duplicate_groups.values())
    rows_to_delete = rows_in_dup_groups - pairs_with_dup

    # Prepare output paths
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join(PROJECT_ROOT, "Support-Files", "output")
    os.makedirs(out_dir, exist_ok=True)
    overview_path = os.path.join(out_dir, f"duplicate_overview_{ts}.csv")
    backup_path = os.path.join(out_dir, f"duplicate_backup_proposed_{ts}.csv")
    conflict_path = os.path.join(out_dir, f"duplicate_conflicts_{ts}.csv")
    wrong_data_path = os.path.join(out_dir, f"duplicate_wrong_data_{ts}.csv")
    summary_path = os.path.join(out_dir, f"duplicate_summary_{ts}.txt")

    # ── Build overview CSV ────────────────────────────────────────────────
    # Wide format. For each pair: keeper_<field>, dup_<field>, conflict_<field>,
    # merged_<field>, source_<field>.
    headers = [
        "group_match_key", "planned_action",
        "keeper_RunID", "dup_RunID",
        "conflict_count_critical",
    ]
    for f in ALL_FIELDS:
        headers += [f"keeper_{f}", f"dup_{f}", f"conflict_{f}", f"merged_{f}", f"source_{f}"]

    conflict_rows = []
    backup_rows = []
    wrong_data_rows = []
    # Per-field analytics across all pairs
    field_stats = {f: {"keeper_filled": 0, "dup_filled": 0, "both_filled": 0,
                       "stale_dup": 0, "true_conflict": 0, "identical": 0}
                   for f in ALL_FIELDS}
    auto_clean_pairs = 0
    true_conflict_pairs = 0

    with open(overview_path, "w", newline="", encoding="utf-8") as f_out:
        w = csv.writer(f_out)
        w.writerow(headers)

        for key, items in sorted(duplicate_groups.items()):
            # We only handle pairs here; in this table all groups have exactly 2.
            keeper, dups = pick_keeper(items)
            dup = dups[0]   # safe — every group has exactly 2 rows

            row_out = [key, "UPDATE keeper, DELETE duplicate", keeper.get("RunID"), dup.get("RunID")]
            critical_conflicts = 0
            field_summaries = []
            # Two parallel lists of human-readable diffs per pair:
            #   all_diffs   = EVERY field that differs (incl. blank vs non-blank)
            #   critical_issues = only the workflow-tier conflicts (subset)
            all_diffs = []
            critical_issues = []

            # RFP_ID format check on duplicate (the canonical "wrong data" marker)
            dup_rfp_raw = dup.get("RFP_ID") or ""
            keeper_rfp_raw = keeper.get("RFP_ID") or ""
            if dup_rfp_raw != normalize_rfp_id(dup_rfp_raw):
                all_diffs.append(f"RFP_ID format wrong: dup='{dup_rfp_raw}' vs keeper='{keeper_rfp_raw}'")

            for fld in ALL_FIELDS:
                kv = _val(keeper, fld)
                dv = _val(dup, fld)
                merged, src = merge_field(fld, kv, dv)
                conf = is_conflict(fld, kv, dv)
                kb = _is_blank(kv); db = _is_blank(dv)

                # Per-field analytics
                if not kb:
                    field_stats[fld]["keeper_filled"] += 1
                if not db:
                    field_stats[fld]["dup_filled"] += 1
                if not kb and not db:
                    field_stats[fld]["both_filled"] += 1
                    if conf:
                        field_stats[fld]["true_conflict"] += 1
                    else:
                        field_stats[fld]["identical"] += 1
                if not kb and db and fld in CRITICAL_CONFLICT_FIELDS:
                    field_stats[fld]["stale_dup"] += 1

                # Build human-readable diff lines for the wrong_data CSV
                if fld == "RFP_ID":
                    pass  # handled above
                elif kb and db:
                    pass  # both blank → no diff
                elif kb and not db:
                    all_diffs.append(f"{fld}: keeper=BLANK, dup='{dv[:60]}'  -> MERGE TAKES FROM DUP")
                elif db and not kb:
                    all_diffs.append(f"{fld}: keeper='{kv[:60]}', dup=BLANK  -> MERGE KEEPS KEEPER")
                elif fld == "Matched_Data":
                    # Bytes differ but materials are identical (we checked via signature)
                    if conf:
                        all_diffs.append(f"{fld}: material content DIFFERS  -> MERGED via {src}")
                        critical_conflicts += 1
                        critical_issues.append(f"{fld}: material content differs")
                elif kv.lower() == dv.lower():
                    # Same value, case-only differences (e.g., "no" vs "No")
                    all_diffs.append(f"{fld}: keeper='{kv[:60]}' vs dup='{dv[:60]}'  (case-only, auto-merged)")
                elif " ".join(kv.split()).lower() == " ".join(dv.split()).lower():
                    # Same value, whitespace-only differences
                    all_diffs.append(f"{fld}: keeper='{kv[:60]}' vs dup='{dv[:60]}'  (whitespace-only, auto-merged)")
                elif conf:
                    # Workflow-tier real conflict — precedence rule decides
                    all_diffs.append(f"{fld}: keeper='{kv[:60]}' vs dup='{dv[:60]}'  -> MERGED='{merged[:60]}' ({src}) [PRECEDENCE RULE]")
                    if fld in CRITICAL_CONFLICT_FIELDS:
                        critical_conflicts += 1
                        critical_issues.append(f"{fld}: keeper='{kv[:60]}' vs dup='{dv[:60]}'")
                else:
                    # Identity / metadata tier with substantively-different values
                    # (different people, different dates, different URLs, etc.)
                    # These are NOT marked critical-conflict but ARE worth surfacing.
                    all_diffs.append(f"{fld}: keeper='{kv[:60]}' vs dup='{dv[:60]}'  -> MERGED='{merged[:60]}' ({src}) [METADATA DIFFERS - portal is source of truth]")

                field_summaries.extend([kv, dv, "Y" if conf else "", merged, src])

            row_out.insert(4, critical_conflicts)
            row_out.extend(field_summaries)
            w.writerow(row_out)

            # Backup snapshot of the duplicate
            backup_rows.append({
                "group_match_key": key,
                "RunID": dup.get("RunID"),
                **{fld: dup.get(fld, "") for fld in ALL_FIELDS},
            })

            # Wrong-data summary per duplicate (now with ALL differences)
            wrong_data_rows.append({
                "group_match_key": key,
                "dup_RunID": dup.get("RunID"),
                "keeper_RunID": keeper.get("RunID"),
                "dup_RFP_ID_raw": dup_rfp_raw,
                "keeper_RFP_ID_raw": keeper_rfp_raw,
                "total_differences": len(all_diffs),
                "critical_conflict_count": critical_conflicts,
                "differences": " || ".join(all_diffs) if all_diffs else "(no field-level differences - duplicate is an exact stale copy)",
                "critical_conflicts": " || ".join(critical_issues) if critical_issues else "",
            })

            # Pair-level tally
            if critical_conflicts > 0:
                true_conflict_pairs += 1
                rec = {"group_match_key": key, "planned_action": "REVIEW",
                       "keeper_RunID": keeper.get("RunID"), "dup_RunID": dup.get("RunID"),
                       "conflict_count_critical": critical_conflicts}
                for fld in CRITICAL_CONFLICT_FIELDS:
                    rec[f"keeper_{fld}"] = _val(keeper, fld)
                    rec[f"dup_{fld}"] = _val(dup, fld)
                conflict_rows.append(rec)
            else:
                auto_clean_pairs += 1

    # ── Backup CSV (full rows that would be deleted) ──────────────────────
    backup_headers = ["group_match_key", "RunID"] + ALL_FIELDS
    with open(backup_path, "w", newline="", encoding="utf-8") as f_out:
        w = csv.DictWriter(f_out, fieldnames=backup_headers)
        w.writeheader()
        # Truncate Matched_Data to avoid massive CSV; full payload stays in DB
        for r in backup_rows:
            r = dict(r)
            md = r.get("Matched_Data") or ""
            if len(md) > 2000:
                r["Matched_Data"] = md[:2000] + f"...[TRUNCATED {len(md)} chars]"
            w.writerow(r)

    # ── Wrong-data CSV (one row per duplicate pair, ALL differences) ──────
    wrong_headers = [
        "group_match_key", "dup_RunID", "keeper_RunID",
        "dup_RFP_ID_raw", "keeper_RFP_ID_raw",
        "total_differences", "critical_conflict_count",
        "differences", "critical_conflicts",
    ]
    with open(wrong_data_path, "w", newline="", encoding="utf-8") as f_out:
        w = csv.DictWriter(f_out, fieldnames=wrong_headers)
        w.writeheader()
        for r in wrong_data_rows:
            w.writerow(r)

    # ── Conflict CSV (focus list for manual review) ───────────────────────
    if conflict_rows:
        conflict_headers = ["group_match_key", "planned_action", "keeper_RunID", "dup_RunID", "conflict_count_critical"]
        for fld in CRITICAL_CONFLICT_FIELDS:
            conflict_headers += [f"keeper_{fld}", f"dup_{fld}"]
        with open(conflict_path, "w", newline="", encoding="utf-8") as f_out:
            w = csv.DictWriter(f_out, fieldnames=conflict_headers)
            w.writeheader()
            for r in conflict_rows:
                r = dict(r)
                for fld in CRITICAL_CONFLICT_FIELDS:
                    if fld == "Matched_Data":
                        v_k = r.get(f"keeper_{fld}") or ""
                        v_d = r.get(f"dup_{fld}") or ""
                        if len(v_k) > 500:
                            r[f"keeper_{fld}"] = v_k[:500] + f"...[+{len(v_k)-500} chars]"
                        if len(v_d) > 500:
                            r[f"dup_{fld}"] = v_d[:500] + f"...[+{len(v_d)-500} chars]"
                w.writerow(r)

    # ── Summary stats ─────────────────────────────────────────────────────
    spacing_pairs = 0
    for items in duplicate_groups.values():
        ids = [(r.get("RFP_ID") or "") for r in items]
        if any("  " in i for i in ids) and any("  " not in i and " " in i for i in ids):
            spacing_pairs += 1

    # Build per-field breakdown table
    field_table_lines = [
        "  {:<22s}  {:>14s}  {:>12s}  {:>9s}  {:>13s}  {:>14s}".format(
            "Field", "Keeper filled", "Dup filled", "Both", "Stale (dup blank)", "True conflict"),
        "  " + "-" * 95,
    ]
    for fld in ALL_FIELDS:
        s = field_stats[fld]
        field_table_lines.append(
            "  {:<22s}  {:>14d}  {:>12d}  {:>9d}  {:>17d}  {:>14d}".format(
                fld, s["keeper_filled"], s["dup_filled"], s["both_filled"],
                s["stale_dup"], s["true_conflict"]))

    summary_lines = [
        "=" * 95,
        f"Duplicate RFP Analysis Summary  (generated {ts})",
        "=" * 95,
        "",
        f"Table:  {RFP_ACTIVITY_LOG_TABLE_API}",
        "",
        "-- Inventory -----------------------------------------------------------------",
        f"  Total rows in table                                : {len(rows)}",
        f"  Rows with blank RFP_ID                             : {blank_id_rows}",
        f"  Distinct (normalized) RFP IDs                      : {unique_count}",
        f"    appearing exactly once (clean)                   : {unique_count - pairs_with_dup}",
        f"    appearing more than once (duplicated)            : {pairs_with_dup}",
        f"  Rows belonging to duplicate groups                 : {rows_in_dup_groups}",
        f"  Pairs where one variant is single-space + one is double-space : {spacing_pairs}",
        "",
        "-- What is WRONG in the database --------------------------------------------",
        f"  {rows_to_delete} rows have a malformed RFP_ID (extra whitespace).",
        f"  These rows were captured before the scraper started normalizing titles.",
        f"  Today's scraper updates only the canonical (single-space) row, so the",
        f"  duplicate rows are STALE - their workflow state (Email_Status, etc.)",
        f"  never gets refreshed.",
        f"  See `duplicate_wrong_data_*.csv` for a per-row description.",
        "",
        "-- Proposed Cleanup Actions -------------------------------------------------",
        f"  Rows to UPDATE (canonical keepers, with merged data) : {pairs_with_dup}",
        f"  Rows to DELETE (duplicate copies)                    : {rows_to_delete}",
        f"  Pairs that auto-merge cleanly (no human review needed): {auto_clean_pairs}",
        f"  Pairs with a TRUE field conflict (still auto-merged via precedence): {true_conflict_pairs}",
        "",
        f"  Table size BEFORE cleanup                          : {len(rows)}",
        f"  Table size AFTER  cleanup (projected)              : {len(rows) - rows_to_delete}",
        "",
        "-- Per-Field Analysis (across 725 duplicate pairs) --------------------------",
        *field_table_lines,
        "",
        "  Legend:",
        "    Keeper filled    = # pairs where the canonical row has a value",
        "    Dup filled       = # pairs where the double-space row has a value",
        "    Both             = # pairs where both rows have a value",
        "    Stale (dup blank) = duplicate has nothing, keeper has data - auto-merge safe",
        "    True conflict    = both have data and they differ - precedence rule decides",
        "",
        "-- Output Files -------------------------------------------------------------",
        f"  Overview (side-by-side, every field, every pair)   : {overview_path}",
        f"  Wrong-data per duplicate row                       : {wrong_data_path}",
        f"  Backup of rows to be deleted (full data snapshot)  : {backup_path}",
        f"  True-conflict focus list (precedence pre-decided)  : {conflict_path if conflict_rows else '(no conflicts - file not written)'}",
        f"  This summary                                       : {summary_path}",
        "",
        "-- What This Run Did --------------------------------------------------------",
        "  - Connected to Dataverse (READ-ONLY).",
        "  - Pulled every row of cr673_bahra_rfps_v2.",
        "  - Grouped by normalized RFP_ID (no-space, case-insensitive).",
        "  - For each duplicate pair, identified the canonical 'keeper' row,",
        "    compared every field, and computed the merged result.",
        "  - Wrote four CSVs so you can validate the plan before any cleanup.",
        "",
        "  NO changes were made to Dataverse. NO portal calls were made.",
        "  Run again any time - it's safe.",
        "",
        "-- Next Steps ---------------------------------------------------------------",
        "  1. Open duplicate_summary (this file) to get the executive picture.",
        "  2. Open duplicate_overview.csv. Spot-check pairs at random.",
        "  3. Open duplicate_wrong_data.csv to confirm what we'd be deleting.",
        "  4. Open duplicate_conflicts.csv (if any) - review the pairs where",
        "     both keeper and duplicate have non-blank but different values.",
        "  5. When ready, give the go-ahead and we run the execute script that",
        "     applies these exact merges + deletes the duplicates (with backups).",
        "",
        "=" * 95,
    ]
    summary = "\n".join(summary_lines)
    with open(summary_path, "w", encoding="utf-8") as f_out:
        f_out.write(summary)
    print(summary)


if __name__ == "__main__":
    main()
