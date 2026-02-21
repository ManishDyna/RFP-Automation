"""
Download specific RFP folders from SharePoint to local ALLRFPs directory.
Uses the standalone SharePointDownloader to avoid circular imports.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.config import (
    CLIENT_ID, CLIENT_SECRET, TENANT_ID,
    SHAREPOINT_HOSTNAME, SITE_PATH, DRIVE_NAME,
    SP_BASE_FOLDER, OUTPUT_DIR,
)
from download_from_sharepoint import SharePointDownloader

COMPANY_NAME = "Aramco e-Marketplace"

RFP_TITLES = [
    "Aramco_4203238993_CABLE 1KV XLPE PVC 1 C 185MM2 (365MCM)",
    "Aramco_4203239295_CABLE, ELECTRICAL, LOW VOLTAGE",
    "Aramco_4203238675_CABLE, POWER, 5KV THROUGH 35 KV",
]


def main():
    client = SharePointDownloader(
        CLIENT_ID, CLIENT_SECRET, TENANT_ID,
        SHAREPOINT_HOSTNAME, SITE_PATH, DRIVE_NAME,
    )
    client.auth()
    client.resolve_site_and_drive()

    for title in RFP_TITLES:
        sp_folder = f"{SP_BASE_FOLDER}/ALLRFPs/{COMPANY_NAME}/{title}"
        local_folder = os.path.join(OUTPUT_DIR, COMPANY_NAME, title)
        os.makedirs(local_folder, exist_ok=True)

        print(f"\n{'='*60}")
        print(f"Downloading: {title}")
        print(f"  SP path : {sp_folder}")
        print(f"  Local   : {local_folder}")
        print(f"{'='*60}")

        try:
            stats = client.download_all(sp_folder, local_folder, skip_existing=False)
            print(f"  Result: {stats['downloaded']} downloaded, {stats['failed']} failed")
        except Exception as e:
            print(f"  ERROR: {e}")

    print("\nDone.")


if __name__ == "__main__":
    main()
