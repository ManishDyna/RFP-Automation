"""
Download All Files & Folders from SharePoint to Local System
=============================================================
Self-contained script using Microsoft Graph API directly.
Avoids circular imports by not importing from helpers/core.

Usage:
    python download_from_sharepoint.py                                  # Download entire RFP-logs folder
    python download_from_sharepoint.py --folder "RFP-logs/ALLRFPs"      # Download specific subfolder
    python download_from_sharepoint.py --output "D:/Backup"             # Custom local destination
"""

import os
import sys
import argparse
import time
import requests
import msal
from datetime import datetime

# Add project root to path so config is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.config import (
    CLIENT_ID, CLIENT_SECRET, TENANT_ID,
    SHAREPOINT_HOSTNAME, SITE_PATH, DRIVE_NAME,
    SP_BASE_FOLDER, SCOPES,
)


class SharePointDownloader:
    """Lightweight Graph API client for downloading files from SharePoint."""

    def __init__(self, client_id, client_secret, tenant_id, hostname, site_path, drive_name):
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self.hostname = hostname
        self.site_path = site_path
        self.drive_name = drive_name
        self.token = None
        self.token_expiry = 0
        self.headers = None
        self.site_id = None
        self.drive_id = None

    def auth(self):
        app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}",
            client_credential=self.client_secret,
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
            print("Token expired, re-authenticating...")
            self.auth()

    def resolve_site_and_drive(self):
        site_url = f"https://graph.microsoft.com/v1.0/sites/{self.hostname}:{self.site_path}"
        r = requests.get(site_url, headers=self.headers)
        if r.status_code != 200:
            raise RuntimeError(f"Resolve site failed: {r.status_code} {r.text}")
        self.site_id = r.json().get("id")

        drives_url = f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/drives"
        r = requests.get(drives_url, headers=self.headers)
        if r.status_code != 200:
            raise RuntimeError(f"List drives failed: {r.status_code} {r.text}")
        for d in r.json().get("value", []):
            if d.get("name") == self.drive_name:
                self.drive_id = d.get("id")
                break
        if not self.drive_id:
            raise RuntimeError(f"Drive '{self.drive_name}' not found")

    def download_all(self, sp_folder_path: str, local_base_dir: str):
        """Recursively download all files and folders from SharePoint to local."""
        stats = {"downloaded": 0, "failed": 0, "total_files": 0, "total_folders": 0, "errors": []}
        self._download_recursive(sp_folder_path, local_base_dir, sp_folder_path, stats)

        print(f"\n{'='*60}")
        print(f"  Download Complete!")
        print(f"  Total files found : {stats['total_files']}")
        print(f"  Downloaded        : {stats['downloaded']}")
        print(f"  Failed            : {stats['failed']}")
        print(f"  Folders created   : {stats['total_folders']}")
        print(f"{'='*60}")

        if stats["errors"]:
            print(f"\n  Failed files:")
            for err in stats["errors"]:
                print(f"    - {err}")

        return stats

    def _download_recursive(self, sp_folder_path: str, local_base_dir: str, sp_root: str, stats: dict):
        self.ensure_token()

        url = f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/drives/{self.drive_id}/root:/{sp_folder_path}:/children"
        response = requests.get(url, headers=self.headers)

        if response.status_code != 200:
            print(f"  Could not access folder '{sp_folder_path}': {response.status_code}")
            stats["errors"].append(f"Folder access failed: {sp_folder_path} ({response.status_code})")
            return

        items = response.json().get("value", [])

        # Handle pagination for large folders
        next_link = response.json().get("@odata.nextLink")
        while next_link:
            self.ensure_token()
            resp = requests.get(next_link, headers=self.headers)
            if resp.status_code == 200:
                data = resp.json()
                items.extend(data.get("value", []))
                next_link = data.get("@odata.nextLink")
            else:
                break

        for item in items:
            name = item.get("name", "")
            is_folder = "folder" in item

            if is_folder:
                stats["total_folders"] += 1
                subfolder_sp = f"{sp_folder_path}/{name}"
                relative_path = subfolder_sp[len(sp_root):].lstrip("/")
                local_folder = os.path.join(local_base_dir, relative_path)
                os.makedirs(local_folder, exist_ok=True)
                print(f"  [Folder] {relative_path}/")
                self._download_recursive(subfolder_sp, local_base_dir, sp_root, stats)
            else:
                stats["total_files"] += 1
                file_sp_path = f"{sp_folder_path}/{name}"
                relative_path = file_sp_path[len(sp_root):].lstrip("/")
                local_file_path = os.path.join(local_base_dir, relative_path)

                try:
                    os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
                    self.ensure_token()
                    download_url = f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/drives/{self.drive_id}/root:/{file_sp_path}:/content"
                    file_resp = requests.get(download_url, headers=self.headers, stream=True)

                    if file_resp.status_code == 200:
                        with open(local_file_path, "wb") as f:
                            for chunk in file_resp.iter_content(chunk_size=8192):
                                f.write(chunk)
                        size_kb = os.path.getsize(local_file_path) / 1024
                        print(f"  [OK] {relative_path} ({size_kb:.1f} KB)")
                        stats["downloaded"] += 1
                    else:
                        print(f"  [FAIL] {relative_path} -> {file_resp.status_code}")
                        stats["failed"] += 1
                        stats["errors"].append(f"{relative_path} ({file_resp.status_code})")
                except Exception as e:
                    print(f"  [ERROR] {relative_path} -> {e}")
                    stats["failed"] += 1
                    stats["errors"].append(f"{relative_path} ({e})")


def main():
    parser = argparse.ArgumentParser(description="Download all files & folders from SharePoint to local system")
    parser.add_argument(
        "--folder",
        default=SP_BASE_FOLDER,
        help=f"SharePoint folder path to download (default: '{SP_BASE_FOLDER}')",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Local directory to save files (default: ./SharePoint-Downloads/<timestamp>)",
    )
    args = parser.parse_args()

    # Default output directory with timestamp
    if args.output:
        local_dir = args.output
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        local_dir = os.path.join(os.getcwd(), "SharePoint-Downloads", timestamp)

    os.makedirs(local_dir, exist_ok=True)

    print("=" * 60)
    print("  SharePoint -> Local Download")
    print("=" * 60)
    print(f"  SharePoint Site : {SHAREPOINT_HOSTNAME}{SITE_PATH}")
    print(f"  Drive           : {DRIVE_NAME}")
    print(f"  Source Folder   : {args.folder}")
    print(f"  Local Dest      : {local_dir}")
    print("=" * 60)

    # Initialize and authenticate
    client = SharePointDownloader(
        CLIENT_ID, CLIENT_SECRET, TENANT_ID,
        SHAREPOINT_HOSTNAME, SITE_PATH, DRIVE_NAME,
    )
    client.auth()
    client.resolve_site_and_drive()

    print(f"\n  Authenticated. Starting download...\n")

    # Download everything
    stats = client.download_all(args.folder, local_dir)

    print(f"\n  All files saved to: {local_dir}")

    if stats["failed"] > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
