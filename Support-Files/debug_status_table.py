"""Quick diagnostic: dump the cr673_bhara_rfp_statuses table to figure out
which column actually carries the saved_draft / declined values, and what
the real display names are.

Avoids importing services/* to dodge a circular import."""

import sys
import os
import io
from pathlib import Path

# Force UTF-8 stdout on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Add project root to path (matches sync_participant_status.py pattern)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from helpers.dataverse_helper import DataverseClient
from config.config import TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL

dv = DataverseClient(
    tenant_id=TENANT_ID,
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    resource_url=RESOURCE_URL,
)

status_api = "cr673_bhara_rfp_statuses"
status_logical = "cr673_bhara_rfp_status"

print(f"Reading from: api={status_api}, logical={status_logical}")
print("=" * 80)

rows = dv.get_all_rows(
    table_api_name=status_api,
    table_logical_name=status_logical,
    use_display_names=True,
)

print(f"Fetched {len(rows or [])} rows total")
print("=" * 80)

if not rows:
    print("[WARN] Table is empty or query returned nothing")
    sys.exit(0)

# Sample the first row's column names
print("First row keys (display names):")
first = rows[0]
for k in first.keys():
    print(f"  -{k!r}  -->sample value: {first[k]!r}")

print("=" * 80)

# Count unique values per likely column
from collections import Counter

# Try to find from_this / to_this / RFP_ID columns by name pattern
def find_keys(rows, patterns):
    keys = set()
    for r in rows[:5]:
        for k in r.keys():
            norm = k.lower().replace(" ", "").replace("_", "")
            for p in patterns:
                if p in norm:
                    keys.add(k)
    return list(keys)

from_keys = find_keys(rows, ["fromthis", "previousstatus", "from"])
to_keys = find_keys(rows, ["tothis", "currentstatus", "to"])
rfp_keys = find_keys(rows, ["rfpid", "rfpreference"])

print(f"Candidate FROM_THIS keys: {from_keys}")
print(f"Candidate TO_THIS keys:   {to_keys}")
print(f"Candidate RFP_ID keys:    {rfp_keys}")
print("=" * 80)

# For each candidate from/to key, show the distribution of values
for k in from_keys + to_keys:
    vals = Counter(str(r.get(k, "")) for r in rows)
    print(f"\nDistribution of {k!r} ({len(vals)} distinct):")
    for v, c in vals.most_common(15):
        print(f"  {c:>6}  x{v!r}")

# Sample 5 full rows for visual inspection
print("=" * 80)
print("Sample of 5 rows (full):")
import json
for r in rows[:5]:
    print(json.dumps({k: str(v) for k, v in r.items()}, indent=2, default=str))
    print("-" * 40)
