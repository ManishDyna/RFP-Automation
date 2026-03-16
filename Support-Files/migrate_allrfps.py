"""
One-time migration script: Upload local RFP folders to SharePoint and insert records into Dataverse.

Usage:
    python migrate_allrfps.py              # Full migration
    python migrate_allrfps.py --dry-run    # Preview matching without uploading/inserting

Source: C:\python\bahar-electric\Bahra-SAP-E-bidding-automation\Playwright\ALLRFPs
Target: SharePoint RFP-logs/ALLRFPs/{CompanyName}/{RFP_Title}/
        Dataverse cr673_requestforproposals table
"""

import sys
import os
import re
import json
import uuid
import asyncio
import logging
import argparse
from datetime import datetime
from pathlib import Path

# Fix Windows console encoding for emoji characters in log_events.py
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.config import (
    CLIENT_ID, CLIENT_SECRET, TENANT_ID,
    SHAREPOINT_HOSTNAME, SITE_PATH, DRIVE_NAME,
    SP_BASE_FOLDER,
    RFP_ACTIVITY_LOG_TABLE_API, RFP_ACTIVITY_LOG_TABLE_LOGICAL,
)
from helpers.core_helper import (
    DATAVERSE, normalize_filename, clean_rfp_title, rfp_ids_match, sanitize_filter_value,
)

# Lazy imports to avoid circular dependency
# GraphClient and extract_rfp_data are imported inside functions that use them

# ===== CONSTANTS =====
SOURCE_BASE = r"C:\python\bahar-electric\Bahra-SAP-E-bidding-automation\Playwright\ALLRFPs"
SP_ALLRFPS_PATH = f"{SP_BASE_FOLDER}/ALLRFPs"
PROGRESS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "migration_progress.json")
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "migration.log")

COMPANY_MAP = {
    "sec": {
        "html": os.path.join(SOURCE_BASE, "Saudi Electricity Company_20251218_111600.html"),
        "folder": os.path.join(SOURCE_BASE, "Saudi Electricity Company"),
        "company_name": "Saudi Electricity Company",
    },
    "aramco": {
        "html": os.path.join(SOURCE_BASE, "Aramco e-Marketplace_20251209_145709.html"),
        "folder": os.path.join(SOURCE_BASE, "Aramco e-Marketplace"),
        "company_name": "Aramco e-Marketplace",
    },
}

logger = logging.getLogger("migration")


# ===== PROGRESS TRACKING =====

def load_progress() -> dict:
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "started_at": datetime.now().isoformat(),
        "completed_uploads": [],
        "completed_db_inserts": [],
        "failed_uploads": {},
        "failed_db_inserts": {},
        "unmatched_html": [],
        "unmatched_folders": [],
        "stats": {"total_uploads": 0, "total_db_inserts": 0, "total_skipped_empty": 0},
    }


def save_progress(progress: dict):
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2, ensure_ascii=False)


# ===== FOLDER SCANNING =====

def scan_local_folders(company_folder: str) -> list[dict]:
    """Scan a company folder for RFP subfolders."""
    results = []
    if not os.path.exists(company_folder):
        logger.warning(f"Company folder not found: {company_folder}")
        return results

    for folder_name in sorted(os.listdir(company_folder)):
        folder_path = os.path.join(company_folder, folder_name)
        if not os.path.isdir(folder_path):
            continue

        downloaded_rfp_path = os.path.join(folder_path, "downloaded-rfp")
        has_files = False
        file_list = []

        if os.path.exists(downloaded_rfp_path):
            file_list = [
                f for f in os.listdir(downloaded_rfp_path)
                if os.path.isfile(os.path.join(downloaded_rfp_path, f))
            ]
            has_files = len(file_list) > 0

        results.append({
            "folder_name": folder_name,
            "folder_path": folder_path,
            "has_files": has_files,
            "files": file_list,
            "normalized": normalize_filename(folder_name),
        })

    return results


# ===== FUZZY MATCHING =====

def extract_numeric_id(text: str) -> str | None:
    """Extract the primary numeric/alphanumeric ID from an RFP title or folder name."""
    # Pattern 1: C followed by 7+ digits (SEC style: C001697262, C00143716)
    m = re.search(r"C\d{7,}", text, re.IGNORECASE)
    if m:
        return m.group(0).upper()
    # Pattern 2: 10+ digit pure number (Aramco style: 4202775785)
    m = re.search(r"\d{10,}", text)
    if m:
        return m.group(0)
    # Pattern 3: 7-9 digit number
    m = re.search(r"\d{7,9}", text)
    if m:
        return m.group(0)
    return None


def build_folder_index(folders: list[dict]) -> dict:
    """Build lookup indices for fast matching."""
    by_exact_name = {}
    by_normalized = {}
    by_extracted_id = {}

    for f in folders:
        clean = clean_rfp_title(f["folder_name"])
        by_exact_name[clean] = f
        by_normalized[f["normalized"]] = f

        eid = extract_numeric_id(f["folder_name"])
        if eid:
            # Store in a list to handle duplicates (multiple folders with same numeric ID)
            if eid not in by_extracted_id:
                by_extracted_id[eid] = f
            # Keep the first one found (they're sorted alphabetically)

    return {
        "by_exact_name": by_exact_name,
        "by_normalized": by_normalized,
        "by_extracted_id": by_extracted_id,
    }


def match_html_to_folder(html_row: dict, folder_index: dict) -> dict | None:
    """Multi-tier matching of an HTML RFP record to a local folder."""
    title = html_row.get("Title", "")

    # Tier 1: Exact match (after whitespace cleanup)
    clean = clean_rfp_title(title)
    if clean in folder_index["by_exact_name"]:
        return folder_index["by_exact_name"][clean]

    # Tier 2: Normalized match (strip all non-alphanumeric)
    norm = normalize_filename(title)
    if norm in folder_index["by_normalized"]:
        return folder_index["by_normalized"][norm]

    # Tier 3: Extracted ID match
    html_id = extract_numeric_id(title)
    if html_id and html_id in folder_index["by_extracted_id"]:
        return folder_index["by_extracted_id"][html_id]

    # Tier 4: Substring containment using rfp_ids_match
    for _fname, fdict in folder_index["by_normalized"].items():
        if rfp_ids_match(title, fdict["folder_name"]) or rfp_ids_match(fdict["folder_name"], title):
            return fdict

    return None


# ===== SHAREPOINT UPLOAD =====

def ensure_graph_client_valid(graph_client):
    """Re-authenticate if token is likely expired (~50 min threshold)."""
    if not hasattr(graph_client, "_auth_time"):
        graph_client._auth_time = datetime.now()

    elapsed = (datetime.now() - graph_client._auth_time).total_seconds()
    if elapsed > 3000:  # Re-auth every 50 minutes
        logger.info("Re-authenticating SharePoint client (token refresh)")
        graph_client.auth()
        graph_client.resolve_site_and_drive()
        graph_client._auth_time = datetime.now()


def upload_rfp_folder(graph_client, folder_path: str,
                      company_name: str, folder_name: str):
    """Upload a single RFP folder to SharePoint."""
    clean_title = clean_rfp_title(folder_name)
    sp_target = f"{SP_ALLRFPS_PATH}/{company_name}/{clean_title}"
    graph_client.sync_local_to_sharepoint(folder_path, sp_target)


# ===== DATAVERSE INSERT =====

def insert_rfp_record(rfp_data: dict, company_name: str, run_id: str) -> bool:
    """Insert/update a single RFP record in Dataverse with migration-specific values."""
    try:
        rfp_id = rfp_data.get("RFP_ID") or rfp_data.get("Title", "")
        link = rfp_data.get("Link", "")
        end_date = rfp_data.get("End_Time", "")

        row_data = {
            "RFP_ID": rfp_id,
            "Company_Name": company_name,
            "Link": link,
            "participated": "OLD",
            "Email_Status": "Sent",
            "Downloaded_At": datetime.now().strftime("%#m/%#d/%Y %#I:%M %p"),
            "RunID": run_id,
        }

        if end_date and end_date.strip() and end_date != "-":
            row_data["RFP_End_Date"] = end_date

        # Check if record already exists
        safe_rfp_id = sanitize_filter_value(rfp_id)
        safe_company = sanitize_filter_value(company_name)
        existing = DATAVERSE.query_rows(
            RFP_ACTIVITY_LOG_TABLE_API,
            filter_expr=f"RFP_ID eq '{safe_rfp_id}' and Company_Name eq '{safe_company}'",
            top=1,
            table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL,
            use_display_names=True,
        )

        if existing and "value" in existing and len(existing["value"]) > 0:
            record = existing["value"][0]
            record_id = record.get(f"{RFP_ACTIVITY_LOG_TABLE_LOGICAL}id")
            DATAVERSE.update_row(
                RFP_ACTIVITY_LOG_TABLE_API,
                record_id,
                row_data,
                table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL,
            )
            logger.info(f"    DB Updated: {rfp_id}")
        else:
            DATAVERSE.insert_row(
                RFP_ACTIVITY_LOG_TABLE_API,
                row_data,
                table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL,
            )
            logger.info(f"    DB Inserted: {rfp_id}")

        return True
    except Exception as e:
        logger.error(f"    DB FAILED for {rfp_data.get('Title', '?')}: {e}")
        return False


# ===== MAIN ORCHESTRATOR =====

async def run_migration(dry_run: bool = False):
    """Main migration entry point."""
    # Lazy imports to avoid circular dependency
    from helpers.sharepoint_helper import GraphClient
    from automation_logic import extract_rfp_data as _extract_rfp_data

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
        ],
    )

    run_id = str(uuid.uuid4())
    logger.info(f"{'='*70}")
    logger.info(f"MIGRATION {'DRY-RUN' if dry_run else 'START'}")
    logger.info(f"RunID: {run_id}")
    logger.info(f"Source: {SOURCE_BASE}")
    logger.info(f"{'='*70}")

    progress = load_progress()

    # Initialize SharePoint client (skip in dry-run)
    graph_client = None
    if not dry_run:
        graph_client = GraphClient(
            CLIENT_ID, CLIENT_SECRET, TENANT_ID,
            SHAREPOINT_HOSTNAME, SITE_PATH, DRIVE_NAME,
        )
        graph_client.auth()
        graph_client.resolve_site_and_drive()
        graph_client._auth_time = datetime.now()
        logger.info("SharePoint client authenticated")

    # Process each company
    for company_key, config in COMPANY_MAP.items():
        company_name = config["company_name"]
        logger.info(f"\n{'='*70}")
        logger.info(f"Processing: {company_name}")
        logger.info(f"{'='*70}")

        # Step A: Parse HTML
        html_rfps = await _extract_rfp_data(config["html"])
        logger.info(f"  HTML records parsed: {len(html_rfps)}")

        # Step B: Scan local folders
        local_folders = scan_local_folders(config["folder"])
        folders_with_files = [f for f in local_folders if f["has_files"]]
        logger.info(f"  Local folders found: {len(local_folders)} (with files: {len(folders_with_files)})")

        # Step C: Build matching index
        folder_index = build_folder_index(local_folders)

        # Step D: Match HTML records to folders
        matched = []
        html_unmatched = []
        matched_folder_names = set()

        for html_row in html_rfps:
            folder = match_html_to_folder(html_row, folder_index)
            if folder:
                matched.append((html_row, folder))
                matched_folder_names.add(folder["folder_name"])
            else:
                html_unmatched.append(html_row)

        folder_only = [f for f in local_folders if f["folder_name"] not in matched_folder_names]

        logger.info(f"  Matched (HTML + folder): {len(matched)}")
        logger.info(f"  HTML-only (no folder): {len(html_unmatched)}")
        logger.info(f"  Folder-only (no HTML): {len(folder_only)}")

        # Log unmatched for review
        if html_unmatched:
            logger.info(f"  --- Unmatched HTML titles (first 10) ---")
            for h in html_unmatched[:10]:
                logger.info(f"    {h.get('Title', '?')}")
                key = f"{company_name}/{h.get('Title', '?')}"
                if key not in progress["unmatched_html"]:
                    progress["unmatched_html"].append(key)

        if folder_only:
            logger.info(f"  --- Unmatched folders (first 10) ---")
            for f in folder_only[:10]:
                logger.info(f"    {f['folder_name']}")
                key = f"{company_name}/{f['folder_name']}"
                if key not in progress["unmatched_folders"]:
                    progress["unmatched_folders"].append(key)

        if dry_run:
            logger.info(f"  [DRY-RUN] Skipping uploads and DB inserts for {company_name}")
            save_progress(progress)
            continue

        # Step E: Upload ALL local folders to SharePoint
        total_to_upload = len(local_folders)
        logger.info(f"\n  --- Uploading {total_to_upload} folders to SharePoint ---")

        for idx, folder_info in enumerate(local_folders, 1):
            upload_key = f"{company_name}/{folder_info['folder_name']}"

            if upload_key in progress["completed_uploads"]:
                continue

            ensure_graph_client_valid(graph_client)

            if not folder_info["has_files"]:
                # Create empty folder structure on SharePoint
                try:
                    clean_title = clean_rfp_title(folder_info["folder_name"])
                    sp_path = f"{SP_ALLRFPS_PATH}/{company_name}/{clean_title}/downloaded-rfp"
                    graph_client.ensure_folder_path(sp_path)
                    progress["completed_uploads"].append(upload_key)
                    progress["stats"]["total_skipped_empty"] += 1
                except Exception as e:
                    progress["failed_uploads"][upload_key] = f"Empty folder error: {str(e)}"
                    logger.error(f"  [{idx}/{total_to_upload}] FAILED (empty): {folder_info['folder_name']} - {e}")

                if idx % 10 == 0:
                    save_progress(progress)
                continue

            logger.info(f"  [{idx}/{total_to_upload}] Uploading: {folder_info['folder_name']} ({len(folder_info['files'])} files)")
            try:
                upload_rfp_folder(graph_client, folder_info["folder_path"], company_name, folder_info["folder_name"])
                progress["completed_uploads"].append(upload_key)
                progress["stats"]["total_uploads"] += 1
            except Exception as e:
                progress["failed_uploads"][upload_key] = str(e)
                logger.error(f"    Upload FAILED: {e}")

            if idx % 10 == 0:
                save_progress(progress)

        save_progress(progress)

        # Step F: Insert DB records for matched items (HTML + folder)
        total_db = len(matched) + len(folder_only) + len(html_unmatched)
        logger.info(f"\n  --- Inserting {total_db} DB records ---")

        db_counter = 0

        # F1: Matched items (have both HTML metadata and local folder)
        for html_row, folder_info in matched:
            db_key = f"{company_name}/{html_row.get('Title', '?')}"
            if db_key in progress["completed_db_inserts"]:
                continue

            db_counter += 1
            logger.info(f"  [DB {db_counter}/{total_db}] {html_row.get('Title', '?')}")
            ok = insert_rfp_record(html_row, company_name, run_id)
            if ok:
                progress["completed_db_inserts"].append(db_key)
                progress["stats"]["total_db_inserts"] += 1
            else:
                progress["failed_db_inserts"][db_key] = "insert failed"

            if db_counter % 10 == 0:
                save_progress(progress)

        # F2: Folder-only items (no HTML metadata)
        for folder_info in folder_only:
            db_key = f"{company_name}/{folder_info['folder_name']}"
            if db_key in progress["completed_db_inserts"]:
                continue

            minimal_rfp = {
                "RFP_ID": folder_info["folder_name"],
                "Title": folder_info["folder_name"],
                "Link": "",
                "End_Time": "",
            }

            db_counter += 1
            logger.info(f"  [DB {db_counter}/{total_db}] (folder-only) {folder_info['folder_name']}")
            ok = insert_rfp_record(minimal_rfp, company_name, run_id)
            if ok:
                progress["completed_db_inserts"].append(db_key)
                progress["stats"]["total_db_inserts"] += 1
            else:
                progress["failed_db_inserts"][db_key] = "insert failed"

            if db_counter % 10 == 0:
                save_progress(progress)

        # F3: HTML-only items (no local folder, still insert DB record)
        for html_row in html_unmatched:
            db_key = f"{company_name}/{html_row.get('Title', '?')}"
            if db_key in progress["completed_db_inserts"]:
                continue

            db_counter += 1
            logger.info(f"  [DB {db_counter}/{total_db}] (html-only) {html_row.get('Title', '?')}")
            ok = insert_rfp_record(html_row, company_name, run_id)
            if ok:
                progress["completed_db_inserts"].append(db_key)
                progress["stats"]["total_db_inserts"] += 1
            else:
                progress["failed_db_inserts"][db_key] = "insert failed"

            if db_counter % 10 == 0:
                save_progress(progress)

        save_progress(progress)

    # Final summary
    logger.info(f"\n{'='*70}")
    logger.info(f"MIGRATION {'DRY-RUN ' if dry_run else ''}COMPLETE")
    logger.info(f"{'='*70}")
    logger.info(f"Total uploads:         {progress['stats'].get('total_uploads', 0)}")
    logger.info(f"Total DB inserts:      {progress['stats'].get('total_db_inserts', 0)}")
    logger.info(f"Empty folders created: {progress['stats'].get('total_skipped_empty', 0)}")
    logger.info(f"Upload failures:       {len(progress['failed_uploads'])}")
    logger.info(f"DB insert failures:    {len(progress['failed_db_inserts'])}")
    logger.info(f"HTML-only (no folder): {len(progress['unmatched_html'])}")
    logger.info(f"Folder-only (no HTML): {len(progress['unmatched_folders'])}")
    logger.info(f"Progress file:         {PROGRESS_FILE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate local RFP files to SharePoint and Dataverse")
    parser.add_argument("--dry-run", action="store_true", help="Preview matching results without uploading or inserting")
    args = parser.parse_args()

    asyncio.run(run_migration(dry_run=args.dry_run))
