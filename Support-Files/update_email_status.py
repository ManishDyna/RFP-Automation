"""One-time script: Set Email_Status = 'Sent' for all rows in bahra_rfps table."""

from helpers.dataverse_helper import DataverseClient
from config.config import (
    TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL,
    RFP_ACTIVITY_LOG_TABLE_API, RFP_ACTIVITY_LOG_TABLE_LOGICAL,
)

dv = DataverseClient(TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL)

# Fetch all rows (only need the record ID and current Email_Status)
print("Fetching all rows from bahra_rfps...")
rows = dv.get_all_rows(
    RFP_ACTIVITY_LOG_TABLE_API,
    select_columns=["Email_Status"],
    table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL,
    use_display_names=True,
)

print(f"Total rows found: {len(rows)}")

# Get column mapping to find the logical name for Email_Status
col_map = dv.get_column_mapping(RFP_ACTIVITY_LOG_TABLE_LOGICAL)
email_status_logical = col_map.get("Email_Status", "Email_Status")
print(f"Email_Status logical name: {email_status_logical}")

id_key = "Request for Proposal"  # display name of the primary key
updated = 0
skipped = 0
errors = 0

not_sent = [r for r in rows if r.get("Email_Status") != "Sent"]
print(f"Already 'Sent': {len(rows) - len(not_sent)}, Need update: {len(not_sent)}")

for row in not_sent:
    record_id = row.get(id_key)
    try:
        dv.update_row(
            RFP_ACTIVITY_LOG_TABLE_API,
            record_id,
            {email_status_logical: "Sent"},
            use_display_names=False,
        )
        updated += 1
    except Exception as e:
        errors += 1
        if errors <= 3:
            print(f"Error updating {record_id}: {e}")

print(f"\nDone! Updated: {updated}, Already 'Sent': {len(rows) - len(not_sent)}, Errors: {errors}")
