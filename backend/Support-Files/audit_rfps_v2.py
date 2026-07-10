"""
Audit script to detect corrupted / mismatched data in cr673_bahra_rfps_v2.

Compares the NEW table (v2) against the OLD table (cr673_requestforproposal)
and flags anomalies in every column.

Usage:
  python -m Support-Files.audit_rfps_v2
"""

import re
import sys
from collections import defaultdict
from datetime import datetime
from helpers.dataverse_helper import DataverseClient
from config.config import TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL

# ---------------------------------------------------------------------------
# Table names
# ---------------------------------------------------------------------------
OLD_TABLE_LOGICAL = "cr673_requestforproposal"
OLD_TABLE_API = "cr673_requestforproposals"

NEW_TABLE_LOGICAL = "cr673_bahra_rfps_v2"
NEW_TABLE_API = "cr673_bahra_rfps_v2s"

COLUMNS = [
    "RunID", "RFP_ID", "Company_Name", "RFP_End_Date", "owner_name",
    "publish_time", "participated", "Link", "Matched_Data",
    "Email_Status", "Email_To", "Email_Sent_At", "Downloaded_At",
    "Reminder_1Day_Sent", "Reminder_3Day_Sent",
    "response_count", "first_response_at", "all_responses_at", "rfp_type",
]

# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------
PARTICIPATED_VALID = {"no", "submitted", "declined", "yes", "no bid", "not participated", "open", ""}
EMAIL_STATUS_VALID = {"sent", "sent (actionable)", ""}

STATUS_KEYWORDS = {
    "declined", "submitted", "participated", "yes", "no", "no bid",
    "not participated", "open", "sent", "sent (actionable)",
}

DATE_PATTERNS = [
    re.compile(r"^\d{4}-\d{2}-\d{2}T"),           # ISO 8601
    re.compile(r"^\d{1,2}/\d{1,2}/\d{4}"),         # M/D/YYYY
    re.compile(r"^\d{1,2}-\d{1,2}-\d{4}"),         # M-D-YYYY
    re.compile(r"^\d{4}-\d{2}-\d{2}"),              # YYYY-MM-DD
]

OWNER_NAME_RE = re.compile(r"^[A-Za-z\s\.\,\'\-]+$")


def _val(row, col):
    """Get stripped string value from row."""
    v = row.get(col)
    if v is None:
        return ""
    return str(v).strip()


def _looks_like_date(s):
    return any(p.match(s) for p in DATE_PATTERNS)


def _is_valid_owner_name(name):
    """Return True if name looks like a real person name."""
    if not name:
        return True  # empty is ok
    if len(name) < 3:
        return False
    if name.lower() in STATUS_KEYWORDS:
        return False
    if _looks_like_date(name):
        return False
    if re.search(r"\d", name):
        return False
    if not OWNER_NAME_RE.match(name):
        return False
    return True


def _is_valid_participated(val):
    return val.lower() in PARTICIPATED_VALID


def _is_valid_email_status(val):
    if not val:
        return True
    return val.lower() in EMAIL_STATUS_VALID


def _is_valid_date_field(val):
    if not val or val == "-":
        return True
    return _looks_like_date(val)


def _non_empty_count(row, columns):
    """Count non-empty columns in row."""
    return sum(1 for c in columns if _val(row, c))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 70)
    print("  AUDIT: cr673_bahra_rfps_v2 Data Quality Report")
    print("=" * 70)

    client = DataverseClient(
        tenant_id=TENANT_ID,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        resource_url=RESOURCE_URL,
    )
    print("[AUTH] Token acquired.\n")

    # ----- Fetch both tables -----
    print("[1/5] Fetching all rows from NEW table (v2)...")
    new_rows = client.get_all_rows(
        table_api_name=NEW_TABLE_API,
        table_logical_name=NEW_TABLE_LOGICAL,
        use_display_names=True,
    )
    print(f"       Total rows in v2: {len(new_rows)}\n")

    print("[2/5] Fetching all rows from OLD table...")
    old_rows = client.get_all_rows(
        table_api_name=OLD_TABLE_API,
        table_logical_name=OLD_TABLE_LOGICAL,
        use_display_names=True,
    )
    print(f"       Total rows in old table: {len(old_rows)}\n")

    # Build lookup: RFP_ID -> best old row (latest Downloaded_At)
    old_map = {}
    for row in old_rows:
        rfp_id = _val(row, "RFP_ID")
        if not rfp_id:
            continue
        if rfp_id not in old_map:
            old_map[rfp_id] = row
        else:
            existing_dl = _val(old_map[rfp_id], "Downloaded_At")
            new_dl = _val(row, "Downloaded_At")
            if new_dl and (not existing_dl or new_dl > existing_dl):
                old_map[rfp_id] = row

    # ----- Collect issues -----
    issues_owner = []       # corrupted owner_name
    issues_participated = []
    issues_email_status = []
    issues_date = []        # bad date fields
    issues_other = []       # other mismatches vs old table
    duplicates = defaultdict(list)  # RFP_ID -> list of rows
    missing_from_v2 = []    # in old but not in v2

    new_rfp_ids = set()

    print("[3/5] Analyzing v2 rows for anomalies...")

    for row in new_rows:
        rfp_id = _val(row, "RFP_ID")
        if not rfp_id:
            continue

        # Track duplicates
        duplicates[rfp_id].append(row)
        new_rfp_ids.add(rfp_id)

        old_row = old_map.get(rfp_id, {})
        company = _val(row, "Company_Name") or "Unknown"

        # --- owner_name ---
        owner = _val(row, "owner_name")
        if not _is_valid_owner_name(owner):
            old_owner = _val(old_row, "owner_name")
            issues_owner.append({
                "RFP_ID": rfp_id,
                "Company": company,
                "current_owner": owner,
                "old_table_owner": old_owner if old_owner else "(empty in old table too)",
            })

        # --- participated ---
        part = _val(row, "participated")
        if not _is_valid_participated(part):
            old_part = _val(old_row, "participated")
            issues_participated.append({
                "RFP_ID": rfp_id,
                "Company": company,
                "current_value": part,
                "old_table_value": old_part,
            })

        # --- Email_Status ---
        email_st = _val(row, "Email_Status")
        if not _is_valid_email_status(email_st):
            old_email_st = _val(old_row, "Email_Status")
            issues_email_status.append({
                "RFP_ID": rfp_id,
                "Company": company,
                "current_value": email_st,
                "old_table_value": old_email_st,
            })

        # --- Date fields ---
        for date_col in ["RFP_End_Date", "publish_time", "Email_Sent_At", "Downloaded_At"]:
            dval = _val(row, date_col)
            if dval and dval != "-" and not _is_valid_date_field(dval):
                old_dval = _val(old_row, date_col)
                issues_date.append({
                    "RFP_ID": rfp_id,
                    "Company": company,
                    "column": date_col,
                    "current_value": dval,
                    "old_table_value": old_dval,
                })

        # --- Cross-check key columns vs old table ---
        if old_row:
            for col in ["owner_name", "publish_time", "RFP_End_Date", "Company_Name"]:
                v2_val = _val(row, col)
                old_val = _val(old_row, col)
                if old_val and not v2_val:
                    issues_other.append({
                        "RFP_ID": rfp_id,
                        "Company": company,
                        "column": col,
                        "v2_value": "(empty)",
                        "old_table_value": old_val,
                        "issue": "Missing in v2 but exists in old table",
                    })

    # ----- Duplicates -----
    print("[4/5] Checking for duplicates...")
    dup_groups = {k: v for k, v in duplicates.items() if len(v) > 1}

    # ----- Missing from v2 -----
    print("[5/5] Checking for RFPs missing from v2...")
    for rfp_id, old_row in old_map.items():
        if rfp_id not in new_rfp_ids:
            missing_from_v2.append({
                "RFP_ID": rfp_id,
                "Company": _val(old_row, "Company_Name"),
                "owner_name": _val(old_row, "owner_name"),
                "RFP_End_Date": _val(old_row, "RFP_End_Date"),
                "participated": _val(old_row, "participated"),
            })

    # =====================================================================
    #  REPORT
    # =====================================================================
    lines = []

    def pr(text=""):
        try:
            print(text)
        except UnicodeEncodeError:
            print(text.encode("ascii", "replace").decode("ascii"))
        lines.append(text)

    pr()
    pr("=" * 70)
    pr("  AUDIT REPORT --cr673_bahra_rfps_v2")
    pr(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    pr("=" * 70)

    # --- Summary ---
    pr()
    pr("-" * 70)
    pr("  SECTION 1: SUMMARY")
    pr("-" * 70)
    pr(f"  Total rows in v2 table       : {len(new_rows)}")
    pr(f"  Total rows in old table       : {len(old_rows)}")
    pr(f"  Unique RFP_IDs in v2          : {len(new_rfp_ids)}")
    pr(f"  Unique RFP_IDs in old         : {len(old_map)}")
    pr()
    pr(f"  Corrupted owner_name          : {len(issues_owner)}")
    pr(f"  Invalid participated          : {len(issues_participated)}")
    pr(f"  Invalid Email_Status          : {len(issues_email_status)}")
    pr(f"  Invalid date fields           : {len(issues_date)}")
    pr(f"  Missing values (vs old table) : {len(issues_other)}")
    pr(f"  Duplicate RFP_ID groups       : {len(dup_groups)}")
    pr(f"  RFPs missing from v2          : {len(missing_from_v2)}")
    total_issues = (len(issues_owner) + len(issues_participated) +
                    len(issues_email_status) + len(issues_date) +
                    len(issues_other) + len(dup_groups) + len(missing_from_v2))
    pr(f"  -- TOTAL ISSUES               : {total_issues}")

    # --- Section 2: Corrupted owner_name ---
    pr()
    pr("-" * 70)
    pr("  SECTION 2: CORRUPTED owner_name")
    pr("-" * 70)
    if not issues_owner:
        pr("  (none)")
    for i, item in enumerate(issues_owner, 1):
        pr(f"  {i}. RFP_ID       : {item['RFP_ID']}")
        pr(f"     Company       : {item['Company']}")
        pr(f"     Current value : {item['current_owner']}")
        pr(f"     Old table     : {item['old_table_owner']}")
        pr()

    # --- Section 3: Invalid participated ---
    pr("-" * 70)
    pr("  SECTION 3: INVALID participated VALUES")
    pr("-" * 70)
    if not issues_participated:
        pr("  (none)")
    for i, item in enumerate(issues_participated, 1):
        pr(f"  {i}. RFP_ID       : {item['RFP_ID']}")
        pr(f"     Company       : {item['Company']}")
        pr(f"     Current value : {item['current_value']}")
        pr(f"     Old table     : {item['old_table_value']}")
        pr()

    # --- Section 4: Invalid Email_Status ---
    pr("-" * 70)
    pr("  SECTION 4: INVALID Email_Status VALUES")
    pr("-" * 70)
    if not issues_email_status:
        pr("  (none)")
    for i, item in enumerate(issues_email_status, 1):
        pr(f"  {i}. RFP_ID       : {item['RFP_ID']}")
        pr(f"     Company       : {item['Company']}")
        pr(f"     Current value : {item['current_value']}")
        pr(f"     Old table     : {item['old_table_value']}")
        pr()

    # --- Section 5: Invalid date fields ---
    pr("-" * 70)
    pr("  SECTION 5: INVALID DATE FIELDS")
    pr("-" * 70)
    if not issues_date:
        pr("  (none)")
    for i, item in enumerate(issues_date, 1):
        pr(f"  {i}. RFP_ID       : {item['RFP_ID']}")
        pr(f"     Company       : {item['Company']}")
        pr(f"     Column        : {item['column']}")
        pr(f"     Current value : {item['current_value']}")
        pr(f"     Old table     : {item['old_table_value']}")
        pr()

    # --- Section 6: Missing values vs old table ---
    pr("-" * 70)
    pr("  SECTION 6: MISSING VALUES (exist in old, empty in v2)")
    pr("-" * 70)
    if not issues_other:
        pr("  (none)")
    for i, item in enumerate(issues_other, 1):
        pr(f"  {i}. RFP_ID       : {item['RFP_ID']}")
        pr(f"     Company       : {item['Company']}")
        pr(f"     Column        : {item['column']}")
        pr(f"     v2 value      : {item['v2_value']}")
        pr(f"     Old table     : {item['old_table_value']}")
        pr()

    # --- Section 7: Duplicates ---
    pr("-" * 70)
    pr("  SECTION 7: DUPLICATE RFP_IDs IN V2")
    pr("-" * 70)
    if not dup_groups:
        pr("  (none)")
    for rfp_id, rows in dup_groups.items():
        pr(f"  RFP_ID: {rfp_id}  ({len(rows)} copies)")
        # Rank by completeness
        ranked = sorted(rows, key=lambda r: _non_empty_count(r, COLUMNS), reverse=True)
        for j, r in enumerate(ranked):
            filled = _non_empty_count(r, COLUMNS)
            tag = " <- KEEP (most complete)" if j == 0 else " <- DELETE"
            record_id = r.get(f"{NEW_TABLE_LOGICAL}id", "?")
            pr(f"     [{j+1}] record_id={record_id}  filled={filled}/{len(COLUMNS)}"
               f"  owner={_val(r, 'owner_name') or '-'}"
               f"  participated={_val(r, 'participated') or '-'}{tag}")
        pr()

    # --- Section 8: Missing from v2 ---
    pr("-" * 70)
    pr("  SECTION 8: RFPs IN OLD TABLE BUT MISSING FROM V2")
    pr("-" * 70)
    if not missing_from_v2:
        pr("  (none)")
    for i, item in enumerate(missing_from_v2, 1):
        pr(f"  {i}. RFP_ID       : {item['RFP_ID']}")
        pr(f"     Company       : {item['Company']}")
        pr(f"     owner_name    : {item['owner_name']}")
        pr(f"     RFP_End_Date  : {item['RFP_End_Date']}")
        pr(f"     participated  : {item['participated']}")
        pr()

    pr("=" * 70)
    pr("  END OF REPORT")
    pr("=" * 70)

    # Save to file
    report_path = "Support-Files/audit_report.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\n[SAVED] Report written to {report_path}")


if __name__ == "__main__":
    main()
