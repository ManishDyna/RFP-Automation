# import requests
# url = "https://0vv8220f-8000.inc1.devtunnels.ms/api/actionable-card/response"
# # url = "http://localhost:8000/api/actionable-card/response"
# response = requests.post(url, json={}, headers={"Content-Type": "application/json"})
# print(response.status_code)
# print(response.text)
import msal

TENANT_ID = "46aa82d0-1a4b-4b08-b520-514ccbe1e7ca"
CLIENT_ID = "97312492-991a-46be-91de-62430026f72d"
CLIENT_SECRET = "pDN8Q~kLKXRoOmEB5PvLRDo-zVH2o91IjRtaJagr"

# This is the App Id URI from your Actionable Message registration
APP_ID_URI = "api://auth-am-0528b4b8-fcbe-47ab-94a1-fa698a9d76ab/97312492-991a-46be-91de-62430026f72d"

app = msal.ConfidentialClientApplication(
    CLIENT_ID,
    authority=f"https://login.microsoftonline.com/{TENANT_ID}",
    client_credential=CLIENT_SECRET,
)

# Try to acquire token for the App Id URI (this is what Outlook tries to do)
result = app.acquire_token_for_client(scopes=[f"{APP_ID_URI}/.default"])

if "access_token" in result:
    print("✅ Token acquired — AAD app is configured correctly")
    print(f"Token: {result['access_token'][:50]}...")
else:
    print("❌ Token acquisition FAILED — this is why Outlook can't call your server")
    print(f"Error: {result.get('error')}")
    print(f"Description: {result.get('error_description')}")
