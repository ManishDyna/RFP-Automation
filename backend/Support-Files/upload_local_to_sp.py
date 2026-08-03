"""
Upload Local → SharePoint (one-way)

Scans local ALLRFPs/<Company>/<RFP_ID>/downloaded-rfp/ folders
and uploads files to SharePoint for any RFP not already present there.

Usage:
  python -m Support-Files.upload_local_to_sp                 # all companies
  python -m Support-Files.upload_local_to_sp --company "X"   # one company
  python -m Support-Files.upload_local_to_sp --company "X" --company "Y"
"""

import argparse
import os
import re

from config.config import (
    TENANT_ID, CLIENT_ID, CLIENT_SECRET,
    SHAREPOINT_HOSTNAME, SITE_PATH, DRIVE_NAME,
    OUTPUT_DIR, SP_BASE_FOLDER, COMPANY_OPTIONS,
)
# Lazy imports inside main() to avoid circular import


def _safe_company(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', '_', name).strip().rstrip('.')


def _list_local_rfps(company_name: str, base_dir: str = None) -> list:
    """Scan <base_dir>/<Company>/ and return RFP entries with Excel files.

    base_dir defaults to OUTPUT_DIR (project-root ALLRFPs/).
    """
    base = base_dir or OUTPUT_DIR
    company_dir = os.path.join(base, _safe_company(company_name))
    results = []

    if not os.path.isdir(company_dir):
        return results

    for rfp_folder in os.listdir(company_dir):
        rfp_path = os.path.join(company_dir, rfp_folder)
        if not os.path.isdir(rfp_path):
            continue

        downloaded_dir = os.path.join(rfp_path, "downloaded-rfp")
        files = []
        if os.path.isdir(downloaded_dir):
            files = [
                f for f in os.listdir(downloaded_dir)
                if f.lower().endswith(('.xls', '.xlsx'))
            ]

        if files:
            results.append({
                'rfp_id': rfp_folder,
                'local_path': downloaded_dir,
                'files': files,
            })

    return results


def _build_sp_index(sp, company_name: str) -> set:
    """Return a set of lowercase RFP folder names present in SharePoint."""
    sp_company_path = f"{SP_BASE_FOLDER}/ALLRFPs/{_safe_company(company_name)}"
    try:
        folders = sp.list_folders_in_directory(sp_company_path)
        return {f['name'].lower() for f in folders}
    except Exception as e:
        print(f"[WARN] Cannot list SP folder {sp_company_path}: {e}")
        return set()


def main():
    from core.common_imports import GraphClient
    from helpers.core_helper import get_sharepoint_rfp_material_path

    parser = argparse.ArgumentParser(description="Upload local RFP Excels to SharePoint")
    parser.add_argument(
        "--company", action="append", default=None,
        help="Limit to one or more companies (repeatable). Default: all in COMPANY_OPTIONS."
    )
    parser.add_argument(
        "--base-dir", default=None,
        help="Local ALLRFPs base directory. Default: project-root ALLRFPs/ from OUTPUT_DIR."
    )
    args = parser.parse_args()

    companies = args.company if args.company else COMPANY_OPTIONS
    base_dir = args.base_dir
    if base_dir:
        base_dir = os.path.abspath(base_dir)
        print(f"[INFO] Using base directory: {base_dir}")

    # Validate company names against known options
    unknown = [c for c in companies if c not in COMPANY_OPTIONS]
    if unknown:
        print(f"[WARN] Unknown company name(s) not in COMPANY_OPTIONS: {unknown}")
        print(f"       Known: {COMPANY_OPTIONS}")

    # ── Init SharePoint client ──
    sp = GraphClient(
        CLIENT_ID, CLIENT_SECRET, TENANT_ID,
        SHAREPOINT_HOSTNAME, SITE_PATH, DRIVE_NAME,
    )
    sp.auth()
    sp.resolve_site_and_drive()

    total_uploaded = 0
    total_skipped = 0
    total_failed = 0

    for company in companies:
        print(f"\n{'='*60}")
        print(f"Company: {company}")
        print('='*60)

        local_rfps = _list_local_rfps(company, base_dir=base_dir)
        if not local_rfps:
            print("  No local RFPs found.")
            continue

        sp_existing = _build_sp_index(sp, company)
        print(f"  Local RFPs: {len(local_rfps)}  |  Already in SP: {len(sp_existing)}")

        for entry in local_rfps:
            rfp_id = entry['rfp_id']

            if rfp_id.lower() in sp_existing:
                print(f"  [SKIP] {rfp_id} — already in SharePoint")
                total_skipped += 1
                continue

            sp_dest = get_sharepoint_rfp_material_path(rfp_id, company)

            for file_name in entry['files']:
                local_file = os.path.join(entry['local_path'], file_name)
                if not os.path.exists(local_file):
                    continue

                try:
                    sp.ensure_token()
                    if not sp.site_id or not sp.drive_id:
                        sp.resolve_site_and_drive()
                    sp.ensure_folder_path(sp_dest)
                    sp.upload_file_as(local_file, sp_dest, file_name)
                    print(f"  [OK]   {rfp_id}/{file_name}")
                    total_uploaded += 1
                except Exception as e:
                    print(f"  [FAIL] {rfp_id}/{file_name} — {e}")
                    total_failed += 1

    # ── Summary ──
    print(f"\n{'='*60}")
    print("DONE")
    print(f"  Uploaded : {total_uploaded}")
    print(f"  Skipped  : {total_skipped}")
    print(f"  Failed   : {total_failed}")
    print('='*60)


if __name__ == "__main__":
    main()
