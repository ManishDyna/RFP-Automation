"""
Quick test script to send Adaptive Card emails to test users.
Run this AFTER:
  1. FastAPI server is running (dashboard_main.py)
  2. Port 8000 is forwarded and public in VS Code
  3. At least 1 hour has passed since Actionable Message registration
"""
from helpers.email_helper import send_actionable_rfp_emails

# Test with a fake RFP ID
rfp_id = "SEC RFP C001743167"
company_name = "Saudi Electricity Company"
rfp_end_date = "02/26/2026 02:15 AM"

print(f"Sending Adaptive Card emails for: {rfp_id}")
print(f"Company: {company_name}")
print(f"Due Date: {rfp_end_date}")
print("-" * 50)

result = send_actionable_rfp_emails(
    rfp_id=rfp_id,
    company_name=company_name,
    rfp_end_date=rfp_end_date,
    matched_csv_path=None,    # No attachment for test
    graph_client=None,
)

print("-" * 50)
print(f"Done! Result: {result}")
print("\nCheck your Outlook inbox for the Adaptive Card email.")
