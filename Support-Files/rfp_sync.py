"""
RFP 3-Way Sync: Dataverse <-> SharePoint <-> Local Host

Ensures RFP records and files are consistent across all three locations:
1. Dataverse  - RFP metadata records (RFP_ID, Company_Name, status, etc.)
2. SharePoint - RFP files (Excel, TDS, etc.) stored in RFP-logs/ALLRFPs/...
3. Local Host - RFP files stored in ALLRFPs/... on the server filesystem

Sync directions handled:
- Dataverse record exists but file missing in SharePoint → download from SP or flag
- Dataverse record exists but file missing locally → download from SharePoint
- SharePoint has file but no Dataverse record → create Dataverse record
- SharePoint has file but not locally → download to local
- Local has file but not in SharePoint → upload to SharePoint
- Local has file but no Dataverse record → create Dataverse record
"""

import os
import re
from datetime import datetime
from typing import List, Optional

from config.config import (
    TENANT_ID, CLIENT_ID, CLIENT_SECRET,
    SHAREPOINT_HOSTNAME, SITE_PATH, DRIVE_NAME,
    RESOURCE_URL, OUTPUT_DIR, SP_BASE_FOLDER,
    COMPANY_OPTIONS, COMPANY_NAME,
    RFP_ACTIVITY_LOG_TABLE_API, RFP_ACTIVITY_LOG_TABLE_LOGICAL,
)
from helpers.dataverse_helper import DataverseClient
from helpers.progress_helper import update_progress


# ─────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────

def _safe_company(name: str) -> str:
    """Sanitize company name for filesystem / SP path usage."""
    return re.sub(r'[<>:"/\\|?*]', '_', name).strip().rstrip('.')


def _init_clients():
    """Create and authenticate Dataverse + SharePoint clients."""
    from helpers.sharepoint_helper import GraphClient

    dv = DataverseClient(TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL)

    sp = GraphClient(
        CLIENT_ID, CLIENT_SECRET, TENANT_ID,
        SHAREPOINT_HOSTNAME, SITE_PATH, DRIVE_NAME,
    )
    sp.auth()
    sp.resolve_site_and_drive()

    return dv, sp


def _list_local_rfps(company_name: str) -> list:
    """
    Scan ALLRFPs/<CompanyName>/ on local disk.
    Returns list of dicts: [{'rfp_id': ..., 'company_name': ..., 'local_path': ..., 'files': [...]}]
    """
    safe_company = _safe_company(company_name)
    company_dir = os.path.join(OUTPUT_DIR, safe_company)
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
                'company_name': company_name,
                'local_path': downloaded_dir,
                'files': files,
            })

    return results


# ─────────────────────────────────────────────────────────
# Phase 1 – Build inventory from each source
# ─────────────────────────────────────────────────────────

def _build_dataverse_index(dv_records: list) -> dict:
    """
    Build a lookup dict keyed by (rfp_id_lower, company_lower) from Dataverse records.
    """
    index = {}
    for rec in dv_records:
        rfp_id = (rec.get("RFP_ID") or "").strip()
        company = (rec.get("Company_Name") or "").strip()
        if rfp_id and company:
            key = (rfp_id.lower(), company.lower())
            index[key] = rec
    return index


def _build_sharepoint_index(sp, company_name: str) -> dict:
    """
    Scan SharePoint ALLRFPs/<Company>/ and return a lookup dict
    keyed by (rfp_folder_name_lower, company_lower).
    Value is list of file info dicts.
    """
    safe_company = _safe_company(company_name)
    sp_company_path = f"{SP_BASE_FOLDER}/ALLRFPs/{safe_company}"
    index = {}

    try:
        rfp_folders = sp.list_folders_in_directory(sp_company_path)
    except Exception as e:
        print(f"[WARN] Cannot list SP company folder {sp_company_path}: {e}")
        return index

    for folder in rfp_folders:
        folder_name = folder['name']
        downloaded_path = f"{folder['path']}/downloaded-rfp"

        try:
            files = sp.list_files_in_directory(downloaded_path, ['.xls', '.xlsx'])
        except Exception:
            files = []

        key = (folder_name.lower(), company_name.lower())
        index[key] = {
            'rfp_id': folder_name,
            'company_name': company_name,
            'sp_path': downloaded_path,
            'files': files,
        }

    return index


def _build_local_index(company_name: str) -> dict:
    """
    Scan local ALLRFPs/<Company>/ and return a lookup dict
    keyed by (rfp_folder_name_lower, company_lower).
    """
    index = {}
    for item in _list_local_rfps(company_name):
        key = (item['rfp_id'].lower(), company_name.lower())
        index[key] = item
    return index


# ─────────────────────────────────────────────────────────
# Phase 2 – Sync actions
# ─────────────────────────────────────────────────────────

def _sync_sp_to_local(sp, sp_entry: dict, company_name: str) -> dict:
    """Download files from SharePoint to local filesystem."""
    from helpers.core_helper import get_rfp_material_file_path

    rfp_id = sp_entry['rfp_id']
    local_dir = get_rfp_material_file_path(rfp_id, company_name)
    os.makedirs(local_dir, exist_ok=True)

    downloaded = []
    failed = []

    for file_info in sp_entry.get('files', []):
        sp_file_path = file_info['path']
        file_name = file_info['name']
        local_file = os.path.join(local_dir, file_name)

        if os.path.exists(local_file):
            print(f"  [SKIP] Already exists locally: {file_name}")
            downloaded.append(local_file)
            continue

        try:
            sp.ensure_token()
            sp.download_file_from_sharepoint(sp_file_path, local_file)
            downloaded.append(local_file)
            print(f"  [OK] SP → Local: {file_name}")
        except Exception as e:
            failed.append({'file': file_name, 'error': str(e)})
            print(f"  [FAIL] SP → Local: {file_name} — {e}")

    return {'downloaded': downloaded, 'failed': failed}


def _sync_local_to_sp(sp, local_entry: dict, company_name: str) -> dict:
    """Upload files from local filesystem to SharePoint."""
    from helpers.core_helper import get_sharepoint_rfp_material_path

    rfp_id = local_entry['rfp_id']
    local_dir = local_entry['local_path']
    sp_dest = get_sharepoint_rfp_material_path(rfp_id, company_name)

    uploaded = []
    failed = []

    for file_name in local_entry.get('files', []):
        local_file = os.path.join(local_dir, file_name)
        if not os.path.exists(local_file):
            continue

        try:
            sp.ensure_token()
            if not sp.site_id or not sp.drive_id:
                sp.resolve_site_and_drive()
            sp.ensure_folder_path(sp_dest)
            sp.upload_file_as(local_file, sp_dest, file_name)
            uploaded.append(file_name)
            print(f"  [OK] Local → SP: {file_name}")
        except Exception as e:
            failed.append({'file': file_name, 'error': str(e)})
            print(f"  [FAIL] Local → SP: {file_name} — {e}")

    return {'uploaded': uploaded, 'failed': failed}


def _ensure_dataverse_record(dv: DataverseClient, rfp_id: str, company_name: str) -> bool:
    """Create a Dataverse record for an RFP if it doesn't already exist."""
    from helpers.core_helper import sanitize_filter_value
    from core.log_events import get_current_run_id

    try:
        safe_rfp_id = sanitize_filter_value(rfp_id)
        safe_company = sanitize_filter_value(company_name)
        filter_expr = f"RFP_ID eq '{safe_rfp_id}' and Company_Name eq '{safe_company}'"

        existing = dv.query_rows(
            RFP_ACTIVITY_LOG_TABLE_API,
            filter_expr=filter_expr,
            top=1,
            table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL,
            use_display_names=True,
        )

        if existing and "value" in existing and len(existing["value"]) > 0:
            print(f"  [EXISTS] Dataverse record already present: {rfp_id}")
            return True

        row_data = {
            "RFP_ID": rfp_id,
            "Company_Name": company_name,
            "Downloaded_At": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "RunID": get_current_run_id(),
        }

        dv.insert_row(
            RFP_ACTIVITY_LOG_TABLE_API,
            row_data,
            table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL,
        )
        print(f"  [OK] Created Dataverse record: {rfp_id}")
        return True
    except Exception as e:
        print(f"  [FAIL] Dataverse insert for {rfp_id}: {e}")
        return False


# ─────────────────────────────────────────────────────────
# Main 3-Way Sync
# ─────────────────────────────────────────────────────────

def run_three_way_sync(company: str = None) -> dict:
    """
    Perform a 3-way sync across Dataverse, SharePoint, and Local for one or all companies.

    Returns summary dict with counts and details per action.
    """
    from core.log_events import log_event, start_new_run
    from helpers.core_helper import get_rfp_activity_data_from_db

    start_new_run()
    log_event("3WAY_SYNC", "StartRun", "Success", f"Starting 3-way sync for {company or 'all companies'}")

    # Resolve target companies
    if company and company.strip():
        companies = [company.strip()]
    else:
        companies = list(COMPANY_OPTIONS)

    # Initialize clients
    dv, sp = _init_clients()
    log_event("3WAY_SYNC", "Setup", "Success", "Clients authenticated")

    # Fetch all Dataverse records once
    all_dv_records = get_rfp_activity_data_from_db()
    log_event("3WAY_SYNC", "Fetch", "Success", f"Fetched {len(all_dv_records)} Dataverse records")

    summary = {
        'companies_processed': 0,
        'sp_to_local': {'downloaded': 0, 'failed': 0},
        'local_to_sp': {'uploaded': 0, 'failed': 0},
        'created_in_dataverse': 0,
        'already_synced': 0,
        'errors': [],
        'details': [],
    }

    total_companies = len(companies)

    for comp_idx, comp_name in enumerate(companies, 1):
        update_progress("sync_all", comp_idx, total_companies, comp_name, f"Syncing {comp_name}")
        log_event("3WAY_SYNC", "Company", "Start", f"[{comp_idx}/{total_companies}] Processing {comp_name}")

        try:
            # Filter Dataverse records for this company
            comp_dv_records = [r for r in all_dv_records if (r.get("Company_Name") or "").strip() == comp_name]
            dv_index = _build_dataverse_index(comp_dv_records)
            sp_index = _build_sharepoint_index(sp, comp_name)
            local_index = _build_local_index(comp_name)

            # Only sync RFPs that have files in ALLRFPs (SP or Local).
            # Dataverse-only records (no file anywhere) are ignored.
            all_keys = set(sp_index.keys()) | set(local_index.keys())
            log_event("3WAY_SYNC", "Company", "Step",
                      f"{comp_name}: {len(dv_index)} in DV, {len(sp_index)} in SP, {len(local_index)} local, {len(all_keys)} with files")

            for key in all_keys:
                rfp_id = ((sp_index.get(key, {}).get("rfp_id"))
                          or (local_index.get(key, {}).get("rfp_id"))
                          or key[0])

                in_dv = key in dv_index
                in_sp = key in sp_index
                in_local = key in local_index

                detail = {
                    'rfp_id': rfp_id,
                    'company': comp_name,
                    'was_in_dv': in_dv,
                    'was_in_sp': in_sp,
                    'was_in_local': in_local,
                    'actions': [],
                }

                # ── All three in sync ──
                if in_dv and in_sp and in_local:
                    summary['already_synced'] += 1
                    detail['actions'].append('already_synced')
                    summary['details'].append(detail)
                    continue

                # ── Ensure Dataverse record ──
                if not in_dv:
                    ok = _ensure_dataverse_record(dv, rfp_id, comp_name)
                    if ok:
                        summary['created_in_dataverse'] += 1
                        detail['actions'].append('created_dv_record')
                    else:
                        summary['errors'].append(f"Failed to create DV record: {rfp_id}")
                        detail['actions'].append('dv_create_failed')

                # ── SharePoint → Local (file exists in SP but not locally) ──
                if in_sp and not in_local:
                    res = _sync_sp_to_local(sp, sp_index[key], comp_name)
                    summary['sp_to_local']['downloaded'] += len(res['downloaded'])
                    summary['sp_to_local']['failed'] += len(res['failed'])
                    detail['actions'].append(f"sp_to_local ({len(res['downloaded'])} ok, {len(res['failed'])} fail)")
                    for f in res['failed']:
                        summary['errors'].append(f"SP->Local fail {rfp_id}: {f['file']} - {f['error']}")

                # ── Local → SharePoint (file exists locally but not in SP) ──
                if in_local and not in_sp:
                    res = _sync_local_to_sp(sp, local_index[key], comp_name)
                    summary['local_to_sp']['uploaded'] += len(res['uploaded'])
                    summary['local_to_sp']['failed'] += len(res['failed'])
                    detail['actions'].append(f"local_to_sp ({len(res['uploaded'])} ok, {len(res['failed'])} fail)")
                    for f in res['failed']:
                        summary['errors'].append(f"Local->SP fail {rfp_id}: {f['file']} - {f['error']}")

                summary['details'].append(detail)

            summary['companies_processed'] += 1
            log_event("3WAY_SYNC", "Company", "Success", f"Finished {comp_name}")

        except Exception as e:
            summary['errors'].append(f"Company {comp_name} error: {str(e)}")
            log_event("3WAY_SYNC", "Company", "Fail", f"Error processing {comp_name}: {str(e)}")

    # Final log
    log_event("3WAY_SYNC", "EndRun", "Success",
              f"3-way sync complete: {summary['already_synced']} synced, "
              f"{summary['sp_to_local']['downloaded']} SP→Local, "
              f"{summary['local_to_sp']['uploaded']} Local→SP, "
              f"{summary['created_in_dataverse']} new DV records, "
              f"{len(summary['errors'])} errors")

    return summary


# ─────────────────────────────────────────────────────────
# Async wrapper (for FastAPI endpoint)
# ─────────────────────────────────────────────────────────

async def run_three_way_sync_async(company: str = None) -> dict:
    """Async wrapper that runs the sync in a thread to avoid blocking the event loop."""
    import asyncio
    return await asyncio.to_thread(run_three_way_sync, company)


# ─────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import json

    # Fix Windows console encoding so emojis in log_events.py don't crash
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    # Bootstrap the circular import chain (common_imports <-> log_events).
    # When running via the server, automation_logic does this automatically.
    import core.common_imports  # noqa: F401

    company_arg = sys.argv[1] if len(sys.argv) > 1 else None
    print(f"\n{'='*60}")
    print(f"  RFP 3-Way Sync: Dataverse <-> SharePoint <-> Local")
    print(f"  Company: {company_arg or 'ALL'}")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    result = run_three_way_sync(company_arg)

    print(f"\n{'='*60}")
    print(f"  SYNC SUMMARY")
    print(f"{'='*60}")
    print(f"  Companies processed : {result['companies_processed']}")
    print(f"  Already in sync     : {result['already_synced']}")
    print(f"  SP → Local downloads: {result['sp_to_local']['downloaded']}")
    print(f"  SP → Local failed   : {result['sp_to_local']['failed']}")
    print(f"  Local → SP uploads  : {result['local_to_sp']['uploaded']}")
    print(f"  Local → SP failed   : {result['local_to_sp']['failed']}")
    print(f"  New DV records      : {result['created_in_dataverse']}")
    print(f"  Errors              : {len(result['errors'])}")
    print(f"{'='*60}")

    if result['errors']:
        print(f"\n  ERRORS:")
        for err in result['errors']:
            print(f"    - {err}")

    print(f"\n  Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
