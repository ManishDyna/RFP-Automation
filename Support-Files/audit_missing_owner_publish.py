"""
Audit: count RFP rows in Dataverse missing owner_name / publish_time, grouped by company.

Read-only. No writes, no schema changes. Used to size the empty-field problem
per company before applying the fixes documented in
~/.claude/plans/check-in-this-sytem-polymorphic-tower.md.

Usage:
  python Support-Files/audit_missing_owner_publish.py
"""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from helpers.dataverse_helper import DataverseClient
from config.config import (
    TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL,
    RFP_ACTIVITY_LOG_TABLE_API, RFP_ACTIVITY_LOG_TABLE_LOGICAL,
)


def _is_empty(val) -> bool:
    if val is None:
        return True
    s = str(val).strip()
    return s == "" or s == "-"


def main():
    dv = DataverseClient(TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL)

    print(f"Fetching rows from {RFP_ACTIVITY_LOG_TABLE_API} ...")
    rows = dv.get_all_rows(
        table_api_name=RFP_ACTIVITY_LOG_TABLE_API,
        select_columns=["RFP_ID", "Company_Name", "owner_name", "publish_time"],
        table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL,
        use_display_names=True,
    )
    print(f"Fetched {len(rows)} rows.\n")

    if not rows:
        print("No rows returned. Nothing to audit.")
        return

    df = pd.DataFrame(rows)
    df["Company_Name"] = df["Company_Name"].fillna("(empty)").replace("", "(empty)")
    df["_owner_empty"] = df["owner_name"].map(_is_empty)
    df["_publish_empty"] = df["publish_time"].map(_is_empty)
    df["_both_empty"] = df["_owner_empty"] & df["_publish_empty"]

    grouped = df.groupby("Company_Name").agg(
        total=("RFP_ID", "count"),
        owner_empty=("_owner_empty", "sum"),
        publish_empty=("_publish_empty", "sum"),
        both_empty=("_both_empty", "sum"),
    ).astype(int)

    grouped["owner_empty_pct"] = (grouped["owner_empty"] / grouped["total"] * 100).round(1)
    grouped["publish_empty_pct"] = (grouped["publish_empty"] / grouped["total"] * 100).round(1)
    grouped["both_empty_pct"] = (grouped["both_empty"] / grouped["total"] * 100).round(1)

    grouped = grouped.sort_values("total", ascending=False)

    print("=" * 110)
    print(f"  AUDIT: empty owner_name / publish_time in {RFP_ACTIVITY_LOG_TABLE_LOGICAL}")
    print("=" * 110)
    print(grouped.to_string())
    print("=" * 110)

    totals = {
        "total": int(grouped["total"].sum()),
        "owner_empty": int(grouped["owner_empty"].sum()),
        "publish_empty": int(grouped["publish_empty"].sum()),
        "both_empty": int(grouped["both_empty"].sum()),
    }
    print(
        f"\nOverall: {totals['total']} rows | "
        f"owner_empty={totals['owner_empty']} ({totals['owner_empty']*100//max(totals['total'],1)}%) | "
        f"publish_empty={totals['publish_empty']} ({totals['publish_empty']*100//max(totals['total'],1)}%) | "
        f"both_empty={totals['both_empty']} ({totals['both_empty']*100//max(totals['total'],1)}%)"
    )


if __name__ == "__main__":
    main()
