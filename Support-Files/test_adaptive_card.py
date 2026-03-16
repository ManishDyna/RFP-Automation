"""
Quick test script to send Adaptive Card emails to test users.
Run this AFTER:
  1. FastAPI server is running (dashboard_main.py)
  2. Port 8000 is forwarded and public in VS Code
  3. At least 1 hour has passed since Actionable Message registration
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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



# import msal

# TENANT_ID = "46aa82d0-1a4b-4b08-b520-514ccbe1e7ca"
# CLIENT_ID = "97312492-991a-46be-91de-62430026f72d"
# CLIENT_SECRET = "pDN8Q~kLKXRoOmEB5PvLRDo-zVH2o91IjRtaJagr"

# # This is the App Id URI from your Actionable Message registration
# APP_ID_URI = "api://auth-am-0528b4b8-fcbe-47ab-94a1-fa698a9d76ab/97312492-991a-46be-91de-62430026f72d"

# app = msal.ConfidentialClientApplication(
#     CLIENT_ID,
#     authority=f"https://login.microsoftonline.com/{TENANT_ID}",
#     client_credential=CLIENT_SECRET,
# )

# # Try to acquire token for the App Id URI (this is what Outlook tries to do)
# result = app.acquire_token_for_client(scopes=[f"{APP_ID_URI}/.default"])

# if "access_token" in result:
#     print("✅ Token acquired — AAD app is configured correctly")
#     print(f"Token: {result['access_token'][:50]}...")
# else:
#     print("❌ Token acquisition FAILED — this is why Outlook can't call your server")
#     print(f"Error: {result.get('error')}")
#     print(f"Description: {result.get('error_description')}")
