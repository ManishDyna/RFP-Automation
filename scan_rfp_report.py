"""
SharePoint RFP Inventory Report Script

Scans the SharePoint folder RFP-logs/ALLRFPs/ and builds a table showing:
  Company Name | RFP ID | Is Excel File Available | Excel Files Path

Usage:
    python scan_rfp_report.py                                        # Full scan
    python scan_rfp_report.py --csv rfp_report.csv                   # Save to CSV
    python scan_rfp_report.py --company "Saudi Electricity Company"  # Single company
    python scan_rfp_report.py --verbose                              # Debug logging
"""

import sys
import os
import time
import logging
import argparse
from datetime import datetime

# Fix Windows console encoding for emoji characters
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import requests

from config.config import (
    CLIENT_ID, CLIENT_SECRET, TENANT_ID,
    SHAREPOINT_HOSTNAME, SITE_PATH, DRIVE_NAME,
    SP_BASE_FOLDER,
)

# ===== CONSTANTS =====
SP_ALLRFPS_PATH = f"{SP_BASE_FOLDER}/ALLRFPs"
EXCEL_EXTENSIONS = ('.xls', '.xlsx')

logger = logging.getLogger(__name__)


REQUEST_TIMEOUT = 30  # seconds


def _get_with_retry(url: str, headers: dict, max_retries: int = 3) -> requests.Response:
    """Make a GET request with retry logic for timeouts and transient errors."""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            return response
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                logger.warning(f"Request failed (attempt {attempt + 1}/{max_retries}), retrying in {wait}s: {e}")
                time.sleep(wait)
            else:
                raise


def list_children_paginated(graph_client, sp_directory_path: str, folders_only: bool = False) -> list:
    """
    List children of a SharePoint directory with full pagination support.

    Args:
        graph_client: Authenticated GraphClient instance
        sp_directory_path: e.g. "RFP-logs/ALLRFPs"
        folders_only: If True, return only folder items

    Returns:
        List of dicts with 'name' and 'path' keys
    """
    graph_client.ensure_token()
    url = (
        f"https://graph.microsoft.com/v1.0/sites/{graph_client.site_id}"
        f"/drives/{graph_client.drive_id}/root:/{sp_directory_path}:/children"
    )

    results = []
    while url:
        response = _get_with_retry(url, graph_client.headers)

        if response.status_code == 404:
            logger.warning(f"Directory not found: {sp_directory_path}")
            return []

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 5))
            logger.warning(f"Rate limited. Sleeping {retry_after}s...")
            time.sleep(retry_after)
            continue

        if response.status_code != 200:
            logger.warning(f"Could not list {sp_directory_path}: HTTP {response.status_code}")
            return []

        data = response.json()
        for item in data.get("value", []):
            is_folder = "folder" in item
            name = item.get("name", "")

            if folders_only and not is_folder:
                continue
            if not folders_only or is_folder:
                results.append({
                    "name": name,
                    "path": f"{sp_directory_path}/{name}",
                })

        url = data.get("@odata.nextLink")

    return results


def check_excel_in_folder(graph_client, rfp_folder_path: str) -> tuple:
    """
    Check if the downloaded-rfp subfolder contains Excel files.

    Args:
        graph_client: Authenticated GraphClient instance
        rfp_folder_path: e.g. "RFP-logs/ALLRFPs/CompanyName/RFP_Title"

    Returns:
        (is_available: bool, excel_paths: list[str])
    """
    downloaded_rfp_path = f"{rfp_folder_path}/downloaded-rfp"
    graph_client.ensure_token()
    url = (
        f"https://graph.microsoft.com/v1.0/sites/{graph_client.site_id}"
        f"/drives/{graph_client.drive_id}/root:/{downloaded_rfp_path}:/children"
    )

    try:
        response = _get_with_retry(url, graph_client.headers)
    except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as e:
        logger.warning(f"Timeout checking {downloaded_rfp_path}: {e}")
        return (False, [])

    if response.status_code == 404:
        return (False, [])

    if response.status_code != 200:
        logger.warning(f"Could not check {downloaded_rfp_path}: HTTP {response.status_code}")
        return (False, [])

    excel_paths = []
    for item in response.json().get("value", []):
        if "folder" in item:
            continue
        name = item.get("name", "")
        if name.lower().endswith(EXCEL_EXTENSIONS):
            excel_paths.append(f"{downloaded_rfp_path}/{name}")

    return (len(excel_paths) > 0, excel_paths)


def scan_all_rfps(graph_client, company_filter: str = None) -> list:
    """
    Scan SharePoint ALLRFPs folder and build report rows.

    Args:
        graph_client: Authenticated GraphClient
        company_filter: Optional company name to scan only one company

    Returns:
        List of row dicts with keys:
        'Company Name', 'RFP ID', 'Is Excel File Available', 'Excel Files Path'
    """
    logger.info(f"Listing company folders under {SP_ALLRFPS_PATH}...")
    company_folders = list_children_paginated(graph_client, SP_ALLRFPS_PATH, folders_only=True)

    if not company_folders:
        logger.warning("No company folders found.")
        return []

    # Apply company filter if provided
    if company_filter:
        company_folders = [f for f in company_folders if f["name"].lower() == company_filter.lower()]
        if not company_folders:
            logger.warning(f"Company '{company_filter}' not found.")
            return []

    logger.info(f"Found {len(company_folders)} company folder(s).")

    rows = []
    rfp_count = 0

    for ci, company in enumerate(company_folders, 1):
        company_name = company["name"]
        company_path = company["path"]
        logger.info(f"[{ci}/{len(company_folders)}] Scanning company: {company_name}")

        rfp_folders = list_children_paginated(graph_client, company_path, folders_only=True)
        logger.info(f"  Found {len(rfp_folders)} RFP folder(s) for {company_name}")

        for ri, rfp in enumerate(rfp_folders, 1):
            rfp_name = rfp["name"]
            rfp_path = rfp["path"]

            has_excel, excel_paths = check_excel_in_folder(graph_client, rfp_path)

            rows.append({
                "Company Name": company_name,
                "RFP ID": rfp_name,
                "Is Excel File Available": "Yes" if has_excel else "No",
                "Excel Files Path": " ; ".join(excel_paths) if excel_paths else "",
            })

            rfp_count += 1
            if rfp_count % 10 == 0:
                logger.info(f"  Progress: {ri}/{len(rfp_folders)} RFPs for {company_name} (total: {rfp_count})")

            # Re-authenticate periodically
            if rfp_count % 50 == 0:
                graph_client.ensure_token()

            time.sleep(0.05)

    return rows


def build_report(rows: list) -> pd.DataFrame:
    """Build a DataFrame from scan results and print summary stats."""
    columns = ["Company Name", "RFP ID", "Is Excel File Available", "Excel Files Path"]

    if not rows:
        print("\nNo RFPs found.")
        return pd.DataFrame(columns=columns)

    df = pd.DataFrame(rows, columns=columns)

    # Summary stats
    total = len(df)
    with_excel = len(df[df["Is Excel File Available"] == "Yes"])
    without_excel = total - with_excel

    print(f"\n{'='*60}")
    print(f"  RFP SharePoint Inventory Report")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    print(f"\n  Total RFPs scanned : {total}")
    print(f"  With Excel files   : {with_excel} ({with_excel/total*100:.1f}%)")
    print(f"  Without Excel files: {without_excel} ({without_excel/total*100:.1f}%)")

    # Per-company breakdown
    print(f"\n  By Company:")
    company_stats = df.groupby("Company Name")["Is Excel File Available"].value_counts().unstack(fill_value=0)
    for company in df["Company Name"].unique():
        c_total = len(df[df["Company Name"] == company])
        c_excel = len(df[(df["Company Name"] == company) & (df["Is Excel File Available"] == "Yes")])
        print(f"    {company}: {c_total} total, {c_excel} with Excel")

    print(f"{'='*60}\n")

    return df


def main():
    parser = argparse.ArgumentParser(description="SharePoint RFP Inventory Report")
    parser.add_argument("--csv", type=str, help="Save report to CSV file")
    parser.add_argument("--company", type=str, help="Scan only a specific company")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    try:
        # Import core_helper first to resolve circular dependency chain
        # (core_helper -> common_imports -> sharepoint_helper -> common_imports)
        import helpers.core_helper  # noqa: F401
        from helpers.sharepoint_helper import GraphClient

        logger.info("Authenticating with SharePoint...")
        client = GraphClient(CLIENT_ID, CLIENT_SECRET, TENANT_ID, SHAREPOINT_HOSTNAME, SITE_PATH, DRIVE_NAME)
        client.auth()
        client.resolve_site_and_drive()
        logger.info("Authenticated successfully.")

        # Scan
        rows = scan_all_rfps(client, company_filter=args.company)

        # Build and display report
        df = build_report(rows)

        if not df.empty:
            print(df.to_string(index=False))

        # Save to CSV if requested
        if args.csv and not df.empty:
            df.to_csv(args.csv, index=False, encoding="utf-8-sig")
            logger.info(f"Report saved to: {args.csv}")

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
