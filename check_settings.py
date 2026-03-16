"""Quick check: what section values do system settings have in Dataverse?"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from helpers.dataverse_helper import DataverseClient
from config.config import (
    TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL,
    SYSTEM_SETTINGS_TABLE_API, SYSTEM_SETTINGS_TABLE_LOGICAL,
)

client = DataverseClient(TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL)
rows = client.get_all_rows(
    SYSTEM_SETTINGS_TABLE_API,
    table_logical_name=SYSTEM_SETTINGS_TABLE_LOGICAL,
    use_display_names=True,
)

print(f"Total rows: {len(rows)}")
print("-" * 70)
for r in rows:
    key = r.get("Key", r.get("cr673_key", "-"))
    section = r.get("Section", r.get("cr673_section", "-"))
    sub = r.get("Sub Section", r.get("cr6db_sub_section", "-"))
    print(f"{key:45s} | section={repr(section):15s} | sub={repr(sub)}")
