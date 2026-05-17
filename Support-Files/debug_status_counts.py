"""Verify _get_system_action_sets() returns expected counts after the fix."""

import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from helpers.dataverse_helper import DataverseClient
from config.config import TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL

dv = DataverseClient(
    tenant_id=TENANT_ID,
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    resource_url=RESOURCE_URL,
)

rows = dv.get_all_rows(
    table_api_name="cr673_bhara_rfp_statuses",
    table_logical_name="cr673_bhara_rfp_status",
    use_display_names=True,
)

print(f"Total status rows: {len(rows)}")

submitted, declined = set(), set()
for r in rows or []:
    rid = (r.get("rfp_id") or "").strip()
    if not rid:
        continue
    to_val = (r.get("to_this") or "").strip().lower()
    if to_val == "saved_draft":
        submitted.add(rid)
    elif to_val == "declined":
        declined.add(rid)

print(f"Submitted by System (to_this='saved_draft'): {len(submitted)} distinct RFPs")
print(f"Declined by System  (to_this='declined'):    {len(declined)} distinct RFPs")

print()
print("Submitted RFPs:")
for r in sorted(submitted):
    print(f"  - {r}")

print()
print(f"Sample of {min(10, len(declined))} declined RFPs:")
for r in list(sorted(declined))[:10]:
    print(f"  - {r}")
