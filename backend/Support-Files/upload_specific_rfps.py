"""
Upload specific RFP folders from local ALLRFPs to SharePoint.
Standalone script to avoid circular imports.
"""
import os
import sys
import time
import requests
import msal
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.config import (
    CLIENT_ID, CLIENT_SECRET, TENANT_ID,
    SHAREPOINT_HOSTNAME, SITE_PATH, DRIVE_NAME,
    SP_BASE_FOLDER, OUTPUT_DIR, SCOPES,
)


class SharePointUploader:
    def __init__(self):
        self.token = None
        self.token_expiry = 0
        self.headers = None
        self.site_id = None
        self.drive_id = None

    def auth(self):
        app = msal.ConfidentialClientApplication(
            CLIENT_ID,
            authority=f"https://login.microsoftonline.com/{TENANT_ID}",
            client_credential=CLIENT_SECRET,
        )
        result = app.acquire_token_for_client(SCOPES)
        if "access_token" not in result:
            raise RuntimeError(f"Could not acquire token: {result.get('error_description', result)}")
        self.token = result["access_token"]
        self.token_expiry = time.time() + result.get("expires_in", 3600) - 300
        self.headers = {"Authorization": f"Bearer {self.token}"}
        print("Token acquired successfully.")

    def ensure_token(self):
        if not self.token or time.time() >= self.token_expiry:
            self.auth()

    def resolve_site_and_drive(self):
        site_url = f"https://graph.microsoft.com/v1.0/sites/{SHAREPOINT_HOSTNAME}:{SITE_PATH}"
        r = requests.get(site_url, headers=self.headers)
        if r.status_code != 200:
            raise RuntimeError(f"Resolve site failed: {r.status_code} {r.text}")
        self.site_id = r.json().get("id")

        drives_url = f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/drives"
        r = requests.get(drives_url, headers=self.headers)
        if r.status_code != 200:
            raise RuntimeError(f"List drives failed: {r.status_code} {r.text}")
        for d in r.json().get("value", []):
            if d.get("name") == DRIVE_NAME:
                self.drive_id = d.get("id")
                break
        if not self.drive_id:
            raise RuntimeError(f"Drive '{DRIVE_NAME}' not found")

    def upload_file(self, local_path, remote_path):
        """Upload a file to SharePoint (PUT for <=4MB)."""
        self.ensure_token()
        # URL-encode path segments but preserve '/' separators
        encoded_path = "/".join(quote(seg, safe="") for seg in remote_path.split("/"))
        url = f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/drives/{self.drive_id}/root:/{encoded_path}:/content"
        with open(local_path, "rb") as f:
            r = requests.put(url, headers=self.headers, data=f)
        return r

    def upload_folder(self, local_folder, sp_base_path):
        """Recursively upload all files from a local folder to SharePoint."""
        stats = {"uploaded": 0, "failed": 0, "errors": []}

        for root, dirs, files in os.walk(local_folder):
            for fname in files:
                local_path = os.path.join(root, fname)
                rel_path = os.path.relpath(local_path, local_folder).replace("\\", "/")
                sp_path = f"{sp_base_path}/{rel_path}"

                try:
                    self.ensure_token()
                    r = self.upload_file(local_path, sp_path)
                    size_kb = os.path.getsize(local_path) / 1024
                    if r.status_code in (200, 201):
                        print(f"  [OK] {rel_path} ({size_kb:.1f} KB)")
                        stats["uploaded"] += 1
                    else:
                        print(f"  [FAIL] {rel_path} -> {r.status_code}")
                        stats["failed"] += 1
                        stats["errors"].append(f"{rel_path} ({r.status_code})")
                except Exception as e:
                    print(f"  [ERROR] {rel_path} -> {e}")
                    stats["failed"] += 1
                    stats["errors"].append(f"{rel_path} ({e})")

        return stats


RFPS = [
    ("Saudi Energy", "SEC RFP - C001552728"),
    ("Saudi Energy", "SEC RFP- C001475098 - 6001475098"),
    ("Aramco e-Marketplace", "Third Party Cybersecurity Self-Assessment # 2 (43)"),
]


def main():
    uploader = SharePointUploader()
    uploader.auth()
    uploader.resolve_site_and_drive()

    for company, title in RFPS:
        local_folder = os.path.join(OUTPUT_DIR, company, title)
        sp_folder = f"{SP_BASE_FOLDER}/ALLRFPs/{company}/{title}"

        print(f"\n{'='*60}")
        print(f"Uploading: {title}")
        print(f"  Local   : {local_folder}")
        print(f"  SP path : {sp_folder}")
        print(f"{'='*60}")

        if not os.path.exists(local_folder):
            print(f"  SKIPPED - local folder not found")
            continue

        stats = uploader.upload_folder(local_folder, sp_folder)
        print(f"  Result: {stats['uploaded']} uploaded, {stats['failed']} failed")

    print("\nDone.")


if __name__ == "__main__":
    main()
