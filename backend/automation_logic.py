# === Windows asyncio fix for Playwright subprocess support ===
import sys
import asyncio
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# === Your existing imports ===
from rfp.submit_rfp import submit_rfp
from core.common_imports import *
from config.config import resolve_company_name
from services.system_settings_service import get_setting
from config.runtime_config import USERNAME, PASSWORD
from rfp.download_rfp import *
from core.common_process import *
from helpers.email_helper import *  # if this file exists
from rfp.rfp_reminder import send_rfp_deadline_reminders
from services.dashboard_service import get_dashboard_data
from fastapi import HTTPException
from core.log_events import log_rfp_activity, start_new_run
from bs4 import BeautifulSoup
import tempfile, shutil, uuid
from pathlib import Path
from helpers.failure_logger import record_failure_log, capture_screenshot
from helpers.progress_helper import update_progress


async def _take_error_screenshot(page, label: str = "error") -> str | None:
    """Capture a browser screenshot for error reporting. Returns the temp file path or None."""
    if page is None:
        return None
    try:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_dir = os.path.join(os.getcwd(), "LOGS")
        os.makedirs(screenshot_dir, exist_ok=True)
        path = os.path.join(screenshot_dir, f"screenshot_{label}_{ts}.png")
        await capture_screenshot(page, path)
        return path
    except Exception as e:
        print(f"⚠️  Screenshot capture failed: {e}")
        return None


def _resolve_company(company: str | None) -> str:
    """Normalize requested company, defaulting to configured COMPANY_NAME.
    Maps frontend short names (SEC, Aramco, HADEED) to full portal names.
    """
    value = (company or "").strip()
    if not value:
        return get_setting("COMPANY_NAME", "Saudi Energy")
    # Use the mapping function to convert short names to full names
    return resolve_company_name(value)


def _format_context_html(context: dict | None) -> str:
    if not context:
        return ""
    items = []
    for key, value in context.items():
        if value in (None, "", [], {}):
            continue
        label = str(key).replace("_", " ").title()
        items.append(f"<li><b>{label}:</b> {value}</li>")
    return "<ul>" + "".join(items) + "</ul>" if items else ""


def _notify_failure_via_email(automation_label: str, failure_info: dict, graph_client):
    """
    Send failure notification email with error log path in the body.
    """
    sharepoint_full_path = failure_info.get("sharepoint_full_path", "")
    path_html = ""
    if sharepoint_full_path:
        path_html = f"<p><b>Error Log Path:</b> {sharepoint_full_path}</p>"
    body_html = f"""
    <p>Dear Team,</p>
    <p>The automation <b>{automation_label}</b> encountered an unexpected error.</p>
    {path_html}
    <p>Best Regards,<br>Automation System</p>
    """
    trigger_email(
        csv_file=None,
        graph_client=graph_client,
        subject=f"[Automation Failure] {automation_label}",
        body_html=body_html,
        email_flag="automation_failure",
    )


async def sanitize_filename(name: str) -> str:
    """Sanitize company name for use in filenames"""
    return re.sub(r'[<>:"/\\|?*]', '_', name).strip()

async def wait_for_page_ready(page, context=None):
    """Wait for page to be fully ready"""
    target = context if context else page

    try:
        await page.wait_for_load_state("networkidle", timeout=60000)
    except Exception as e:
        # Network idle timeout is non-critical, page may still be usable
        print(f"⚠️ Network idle wait timeout (non-critical): {type(e).__name__}")

    try:
        await target.wait_for_selector(
            '.loading, .spinner, [aria-busy="true"], .w-loading',
            state='hidden',
            timeout=5000
        )
    except Exception:
        # Loading indicators may not exist on page, this is expected
        pass


async def is_logged_in(page):
    """Check if user is still logged in by checking URL and page elements"""
    try:
        current_url = page.url.lower()
        # If redirected to login page, session expired
        if "login" in current_url or "signin" in current_url:
            return False
        
        # Check if login input field exists (indicates logout)
        try:
            if await login_form_present(page):
                return False
        except Exception:
            pass
        
        # Check if we're on a valid portal page (not login)
        if get_setting("URL", "").lower() in current_url or "ariba" in current_url:
            # Try to find a logged-in indicator
            try:
                # Check for common logged-in elements
                await page.wait_for_selector('body', state='visible', timeout=2000)
                # If we can see the page and it's not login, assume logged in
                return True
            except:
                return False
        
        return True
    except Exception as e:
        print(f"⚠️ Error checking login status: {e}")
        return False


async def ensure_logged_in(page, retry_count=3):
    """Ensure user is logged in, re-login if needed"""
    for attempt in range(retry_count):
        if await is_logged_in(page):
            return True
        
        print(f"\n⚠️  Session expired - Re-logging in... (Attempt {attempt + 1}/{retry_count})")
        log_event("ALL_RFPS", "ReLogin", "Start", f"Re-login attempt {attempt + 1}")
        
        try:
            # Navigate to login page
            await page.goto(get_setting("URL", ""), wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(1)
            
            # Fill login credentials (waits for the fields itself)
            await fill_login_credentials(page, USERNAME, PASSWORD)

            # Submit login
            try:
                async with page.expect_navigation(wait_until="networkidle", timeout=60000):
                    await page.click('input[type="submit"]')
            except:
                await page.click('input[type="submit"]')
                await page.wait_for_load_state("networkidle", timeout=60000)
            
            await wait_for_page_ready(page)
            await asyncio.sleep(2)
            
            # Verify login was successful
            if await is_logged_in(page):
                print("✅ Re-login successful")
                log_event("ALL_RFPS", "ReLogin", "Success", "Re-login successful")
                return True
            else:
                print(f"⚠️  Re-login attempt {attempt + 1} failed - still not logged in")
                
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Re-login attempt {attempt + 1} failed: {error_msg}")
            log_event("ALL_RFPS", "ReLogin", "Fail", f"Re-login attempt {attempt + 1} failed: {error_msg}")
            if attempt < retry_count - 1:
                await asyncio.sleep(3)  # Wait before retry
    
    print("❌ All re-login attempts failed")
    log_event("ALL_RFPS", "ReLogin", "Fail", "All re-login attempts failed")
    return False


async def export_rfps(page, company_name):
    """Export RFPs for the selected company and handle download with Playwright event-based download"""
    print(f"\n=== Exporting RFPs for {company_name} ===")
    log_event("SYNC", "Export", "Start", f"Starting export for {company_name}")

    # Check if logged in before exporting
    if not await ensure_logged_in(page):
        raise Exception("Not logged in - cannot export RFPs")

    await wait_for_page_ready(page)

    # --- Locate SupplierFrame ---
    frame = None
    for f in page.frames:
        if "SupplierFrame" in (f.name or "") or "SupplierFrame" in (f.url or ""):
            frame = f
            break

    context = frame if frame else page
    print(f"✓ Using {'SupplierFrame' if frame else 'main page'}")
    log_event("SYNC", "Export", "Step", f"Using {'SupplierFrame' if frame else 'main page'} for export")

    # --- Wait for Table Options Button ---
    await context.wait_for_selector('#_lf_t\\$b > div.w-tbl-customize-view', state='visible', timeout=20000)

    # ================================
    # Step 1: Expand All Rows
    # ================================
    print("  ⏳ Opening table options menu...")
    log_event("SYNC", "Export", "Step", "Opening table options menu")
    await context.hover('#_lf_t\\$b > div.w-tbl-customize-view')
    await context.click('#_lf_t\\$b > div.w-tbl-customize-view', force=True)

    await context.wait_for_selector('#_lcbzrc', state='visible', timeout=15000)
    print("✓ Table options menu opened")
    log_event("SYNC", "Export", "Step", "Table options menu opened")

    print("  ⏳ Expanding all rows...")
    log_event("SYNC", "Export", "Step", "Expanding all table rows")
    await context.click('#_lcbzrc', force=True)

    # Wait for data load to stabilize
    await page.wait_for_load_state("networkidle", timeout=60000)

    # Wait for loading spinners to disappear
    try:
        await context.wait_for_selector(
            '.loading, .spinner, [aria-busy="true"], .w-loading',
            state='hidden',
            timeout=10000
        )
    except:
        pass

    # Ensure table rows appear
    try:
        await context.wait_for_selector('table tbody tr, .w-tbl-row', state='attached', timeout=10000)
    except:
        pass

    print("✓ Table expanded - all rows loaded")
    log_event("SYNC", "Export", "Step", "Table expanded - all rows loaded")

    # ================================
    # Step 2: Open Export Menu
    # ================================
    print("  ⏳ Opening export menu...")
    log_event("SYNC", "Export", "Step", "Opening export menu")

    await page.wait_for_load_state("networkidle", timeout=30000)
    await context.wait_for_selector('#_lf_t\\$b > div.w-tbl-customize-view', state='visible', timeout=20000)
    
    await context.hover('#_lf_t\\$b > div.w-tbl-customize-view')
    await context.click('#_lf_t\\$b > div.w-tbl-customize-view', force=True)

    # Wait for export option visibility
    try:
        await context.wait_for_selector('div.awmenu:not(.is-dnone)', state='visible', timeout=10000)
    except:
        pass

    await context.wait_for_selector('#_c\\$r36b', state='attached', timeout=15000)

    # Confirm export button visible using JS
    try:
        await context.evaluate("""
            async () => {
                const maxWait = 15000, start = Date.now();
                const findVisible = () => {
                return Array.from(document.querySelectorAll('a.w-pmi-item'))
                    .find(a => a.textContent.trim() === 'Export all Rows' &&
                            a.offsetParent && getComputedStyle(a).visibility !== 'hidden');
                };
                let btn;
                while (Date.now() - start < maxWait) {
                btn = findVisible();
                if (btn) { btn.click(); return; }
                await new Promise(r => setTimeout(r, 100));
                }
                throw new Error('Export menuitem not visible');
            }
            """)
    except Exception as e:
        print(f"⚠ Warning: {e}")

    print("✓ Export option ready")
    log_event("SYNC", "Export", "Step", "Export option ready")

    # ================================
    # Step 3: Start Download
    # ================================
    print("  ⏳ Starting download...")
    log_event("SYNC", "Export", "Step", "Starting file download")

    
    async with page.expect_download(timeout=180000) as download_info:
        await context.evaluate("""
            () => {
                const btn = document.querySelector('#_c\\\\$r36b');
                if (btn) {
                    btn.scrollIntoView({ behavior: 'instant', block: 'nearest' });
                    btn.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
                    btn.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
                    btn.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true }));
                    btn.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true }));
                    btn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
                }
            }
        """)

    download = await download_info.value
    print("  ✓ Download started!")
    log_event("SYNC", "Export", "Step", "Download started")

    # ================================
    # Step 4: Save File with Correct Extension
    # ================================
    suggested_name = download.suggested_filename or 'data.xls'
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_company_name = await sanitize_filename(company_name)

    # Save to temporary location (no permanent local storage)
    temp_export_dir = tempfile.mkdtemp(prefix="rfp_export_")
    temp_path = os.path.join(temp_export_dir, f"temp_{timestamp}.download")
    await download.save_as(temp_path)

    # Detect actual file type from content
    def detect_file_type(file_path):
        """Detect actual file type by reading file header"""
        try:
            with open(file_path, 'rb') as f:
                header = f.read(8)

            # Check file signatures
            if header[:4] == b'\xD0\xCF\x11\xE0':
                return '.xls'  # Old Excel binary format
            elif header[:4] == b'PK\x03\x04':
                return '.xlsx'  # Modern Excel (ZIP-based)
            elif header[:2] == b'PK':
                return '.xlsx'  # ZIP variant
            elif header[:5] == b'<?xml':
                return '.xml'  # XML format
            elif b'<html' in header.lower() or b'<table' in header.lower():
                return '.html'  # HTML format
            else:
                # Try to read as text to check if CSV
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        first_line = f.readline()
                        if ',' in first_line or '\t' in first_line:
                            return '.csv'
                except:
                    pass

            # Default to xlsx if can't determine
            return '.xlsx'
        except Exception as e:
            print(f"  ⚠ Error detecting file type: {e}")
            return '.xlsx'

    # Detect the real extension
    real_ext = detect_file_type(temp_path)
    log_event("EXPORT", "FileType", "Step", f"Ariba provided: {suggested_name}, detected format: {real_ext}")

    # Create final filename with correct extension
    target_filename = f"{safe_company_name}_{timestamp}{real_ext}"
    target_path = os.path.join(temp_export_dir, target_filename)

    # Rename temp file to final name
    os.rename(temp_path, target_path)

    if os.path.exists(target_path):
        file_size = os.path.getsize(target_path)
        print(f"  ✅ Saved: {target_filename} ({file_size:,} bytes)")
        log_event("SYNC", "Export", "Success", f"File saved: {target_filename} ({file_size:,} bytes)")
    else:
        log_event("SYNC", "Export", "Fail", f"File save failed: {target_filename}")

    return target_path

# === Download & Process RFPs ===
async def download_rfp(page, open_rfps, graph_client, company_name: str):
    if not open_rfps:
        log_event("RFP", "Download", "Skip", "No open RFPs to download")
        return

    # Download RFP files (filtering already done in scrape_open_rfps)
    log_event("RFP", "Download", "Start", f"Downloading {len(open_rfps)}")
    download_result = await download_rfp_files(page, open_rfps, company_name, graph_client)
    new_rfp_titles = download_result["successful"]
    skipped_titles = download_result["skipped"]
    failed_titles = download_result["failed"]

    # Build end-date lookup (title → end date) from the scraped RFP list
    rfp_end_dates = {
        (row.get("Title") or "").strip(): (row.get("RFP_End_Date") or "-").strip()
        for row in open_rfps
    }

    # ── CASE 2: No new RFP found ──────────────────────────────────────────────
    if not new_rfp_titles:
        log_event("RFP", "Process", "Skip", "No new RFPs downloaded - skipping process_folder")

        if failed_titles:
            # Some RFPs failed to download — warn the team
            failed_list = "".join(f"<li>{t}</li>" for t in failed_titles)
            body_html = f"""
            <p>Dear Team,</p>
            <p>The automation ran for <b>{company_name}</b>, but <b>no new RFPs</b> were downloaded.</p>
            <p><b>{len(skipped_titles)}</b> RFP(s) were already processed.</p>
            <p><b>{len(failed_titles)}</b> RFP(s) could not be downloaded (download button may be unavailable):</p>
            <ul>{failed_list}</ul>
            <p>Best Regards,<br>Automation System</p>
            """
        else:
            body_html = f"""
            <p>Dear Team,</p>
            <p>The automation ran successfully for <b>{company_name}</b>, but <b>no new RFPs</b> were found.</p>
            <p>All <b>{len(skipped_titles)}</b> open RFPs already exist in the database.</p>
            <p>Best Regards,<br>Automation System</p>
            """

        trigger_email(
            email_flag="no_new_rfp",
            subject=f"No New RFP Available - {company_name} ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})",
            body_html=body_html,
            company_name=company_name,
        )
        log_event("SYSTEM", "DownloadRFP", "Success", f"Download flow finished (skipped: {len(skipped_titles)}, failed: {len(failed_titles)})")
        return

    # ── CASE 1: New RFP(s) found — process materials then send 1 email per RFP ─
    matched_df, per_rfp_csv_map, not_mateched_files = process_folder(
        graph_client, None, None, company_name=company_name, new_rfp_titles=new_rfp_titles, rfp_end_dates=rfp_end_dates
    )
    print(f"✅ Matched materials processed: {len(per_rfp_csv_map)} RFPs with matches")

    # Send one email per RFP (with matched material CSV if available, otherwise note "no match")
    from helpers.email_helper import send_per_rfp_email
    for rfp_title in new_rfp_titles:
        rfp_end_date = rfp_end_dates.get(rfp_title, "-")
        matched_csv = per_rfp_csv_map.get(rfp_title, None)
        send_per_rfp_email(
            rfp_id=rfp_title,
            company_name=company_name,
            rfp_end_date=rfp_end_date,
            matched_csv_path=matched_csv,
            graph_client=graph_client,
        )
        log_event("EMAIL", "Sent", "Success", message=f"Per-RFP email sent for {rfp_title}", rfp_id=rfp_title)

    log_event("SYSTEM", "DownloadRFP", "Success", f"Download flow finished — {len(new_rfp_titles)} per-RFP emails sent")

async def common_flow(p, graph_client, profile_label: str = "default", company: str | None = None):
    import os
    import pandas as pd
    from datetime import datetime

    target_company = _resolve_company(company)

    # Run browser in headed mode
    headless_mode = False

    print(f"Launching browser in {'headless' if headless_mode else 'headed'} mode")

    # Create an isolated user-data-dir per run to allow parallel automations
    uid = uuid.uuid4().hex[:8]
    profile_dir = Path(tempfile.gettempdir()) / f"pw-profile-{profile_label}-{uid}"
    try:
        if profile_dir.exists():
            shutil.rmtree(profile_dir, ignore_errors=True)
    except Exception:
        pass

    browser = await p.chromium.launch_persistent_context(
        user_data_dir=str(profile_dir),
        headless=headless_mode,
        args=[
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu'
        ],
        viewport={'width': 1280, 'height': 1024}
    )

    page = await browser.new_page()
    await login_and_select_company(page, target_company)
    # Then, scrape only non-participated RFPs for downloading
    open_rfps = await scrape_open_rfps(page, company=target_company)
    # if open_rfps:
    #     timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    #     csv_path = os.path.join(OUTPUT_DIR, f"open_rfps_{timestamp}.csv")
    #     pd.DataFrame(open_rfps).to_csv(csv_path, index=False, encoding="utf-8-sig")

    return open_rfps, page, browser

# === Main Automation Runner ===
async def run_automation_download(company: str | None = None):
    start_new_run()  # Generate new unique RUN_ID for this automation run
    log_event("SYSTEM", "StartRun", "Success", "Automation started")
    target_company = _resolve_company(company)
    graph_client = GraphClient(
        get_setting("CLIENT_ID", ""), get_setting("CLIENT_SECRET", ""), get_setting("TENANT_ID", ""),
        get_setting("SHAREPOINT_HOSTNAME", "bahracables.sharepoint.com"), get_setting("SITE_PATH", "/sites/LiveSite/RFPAutomation"), get_setting("DRIVE_NAME", "Documents")
    )
    graph_client.auth()
    graph_client.resolve_site_and_drive()

    async with async_playwright() as p:
        browser = None
        page = None
        try:
            # Step 1: Common flow (login + scrape)
            open_rfps, page, browser = await common_flow(
                p,
                graph_client,
                profile_label="download",
                company=target_company,
            )
            print(f"[Download] Company '{target_company}' - Found {len(open_rfps)} open RFPs")

            # Step 2: Download flow
            await download_rfp(page, open_rfps, graph_client, company_name=target_company)

            return {"status": "success", "message": "Download RFP flow completed"}

        except Exception as e:
            print(f"Automation error: {str(e)}")
            log_event("SYSTEM", "RunError", "Fail", "Automation error: " + str(e))
            screenshot_path = await _take_error_screenshot(page, "download_rfp")
            failure_info = record_failure_log(
                e,
                context={"automation": "download_rfp", "company": target_company},
                graph_client=graph_client,
                screenshot_path=screenshot_path,
            )
            _notify_failure_via_email("Download RFP", failure_info, graph_client)
            raise HTTPException(status_code=500, detail=f"Automation failed: {str(e)}")
        finally:
            if browser:
                try:
                    await browser.close()
                except Exception as e:
                    print(f"Error closing browser: {str(e)}")
            log_event("SYSTEM", "EndRun", "Success", "Automation Finished")


async def run_automation_download_open_rfps():
    """Download RFPs automation for ALL companies (iterates through COMPANY_OPTIONS)."""
    COMPANY_OPTIONS = get_setting("COMPANY_OPTIONS", [])
    start_new_run()
    log_event("SYSTEM", "StartRun", "Success", f"Download Open RFPs automation started for all {len(COMPANY_OPTIONS)} companies")

    graph_client = GraphClient(
        get_setting("CLIENT_ID", ""), get_setting("CLIENT_SECRET", ""), get_setting("TENANT_ID", ""),
        get_setting("SHAREPOINT_HOSTNAME", "bahracables.sharepoint.com"), get_setting("SITE_PATH", "/sites/LiveSite/RFPAutomation"), get_setting("DRIVE_NAME", "Documents")
    )
    graph_client.auth()
    graph_client.resolve_site_and_drive()

    summary = {
        "total_companies": len(COMPANY_OPTIONS),
        "processed": 0,
        "failed": 0,
        "companies": [],
    }

    for idx, company in enumerate(COMPANY_OPTIONS, 1):
        print(f"\n{'='*70}")
        print(f"[Download Open] Processing company {idx}/{len(COMPANY_OPTIONS)}: {company}")
        print(f"{'='*70}")
        log_event("RFP", "ProcessCompany", "Start", f"Processing company {idx}/{len(COMPANY_OPTIONS)}: {company}")
        update_progress("download", current=idx, total=len(COMPANY_OPTIONS), current_item=company, message=f"Processing {company}")

        async with async_playwright() as p:
            browser = None
            page = None
            try:
                # Login + scrape RFPs for this company
                open_rfps, page, browser = await common_flow(
                    p,
                    graph_client,
                    profile_label=f"download-open-{idx}",
                    company=company,
                )
                print(f"[Download Open] Company '{company}' - Found {len(open_rfps)} RFPs")
                log_event("RFP", "Scrape", "Success", f"Company '{company}': Found {len(open_rfps)} RFPs")

                # Download RFPs for this company
                await download_rfp(page, open_rfps, graph_client, company_name=company)

                summary["processed"] += 1
                summary["companies"].append({"company": company, "status": "success", "rfps_found": len(open_rfps)})
                log_event("RFP", "ProcessCompany", "Success", f"Company '{company}' completed successfully")

            except Exception as e:
                print(f"[Download Open] Error for company '{company}': {str(e)}")
                log_event("SYSTEM", "RunError", "Fail", f"Company '{company}' error: {str(e)}")
                screenshot_path = await _take_error_screenshot(page, f"download_open_{company}")
                failure_info = record_failure_log(
                    e,
                    context={"automation": "download_open_rfps", "company": company},
                    graph_client=graph_client,
                    screenshot_path=screenshot_path,
                )
                _notify_failure_via_email(f"Download Open RFPs - {company}", failure_info, graph_client)
                summary["failed"] += 1
                summary["companies"].append({"company": company, "status": "failed", "error": str(e)})
            finally:
                if browser:
                    try:
                        await browser.close()
                    except Exception as e:
                        print(f"Error closing browser: {str(e)}")

    summary_msg = f"Download Open RFPs complete. Processed: {summary['processed']}/{summary['total_companies']}, Failed: {summary['failed']}"
    print(f"\n{summary_msg}")
    log_event("SYSTEM", "EndRun", "Success", summary_msg)
    return {"status": "success", "message": summary_msg, "summary": summary}


async def run_automation_submit(rfp_id: str, company: str | None = None, allowed_tds_filenames: list[str] | None = None):
    start_new_run()  # Generate new unique RUN_ID for this automation run
    log_event("SYSTEM", "StartRun", "Success", f"Submit RFP {rfp_id} started")
    target_company = _resolve_company(company)
    graph_client = GraphClient(
        get_setting("CLIENT_ID", ""), get_setting("CLIENT_SECRET", ""), get_setting("TENANT_ID", ""),
        get_setting("SHAREPOINT_HOSTNAME", "bahracables.sharepoint.com"), get_setting("SITE_PATH", "/sites/LiveSite/RFPAutomation"), get_setting("DRIVE_NAME", "Documents")
    )
    graph_client.auth()
    graph_client.resolve_site_and_drive()

    async with async_playwright() as p:
        page = None
        browser = None
        try:
            open_rfps, page, browser = await common_flow(
                p,
                graph_client,
                profile_label=f"submit-{rfp_id}",
                company=target_company,
            )
            result = await submit_rfp(page, open_rfps, rfp_id, graph_client, target_company, allowed_tds_filenames=allowed_tds_filenames)
            # result is a list of failed/missing RFPs; empty list means success
            # Check if result contains an "RFP not found" error (portal scraping failed)
            rfp_not_found = any(
                isinstance(r, dict) and r.get("error") for r in (result or [])
            )
            submit_status = "success" if (not result and not rfp_not_found) else f"failed ({len(result)} missing)"
            log_event("SUBMIT", "Result", "Step", f"Submit result: {submit_status}")

            # Extract RFP link from open_rfps data
            rfp_link = None
            for row in open_rfps:
                title = row.get("Title") or ""
                if rfp_ids_match(rfp_id, title):
                    rfp_link = row.get("Link") or ""
                    break

            if not result:
                # Actual success - RFP was found and submitted
                try:
                    trigger_email(rfp_id=rfp_id, email_flag="rfp_saved_draft", graph_client=graph_client, rfp_link=rfp_link)
                except Exception as email_err:
                    print(f"⚠️ Submit success email failed (non-critical): {email_err}")
            else:
                # Failure - either RFP not found in scraped data or submission failed
                error_details = ""
                if rfp_not_found:
                    error_msg = result[0].get("error", "Unknown error") if result else "Unknown error"
                    error_details = (
                        f"RFP '{rfp_id}' could not be processed.\n"
                        f"Reason: {error_msg}\n"
                        f"This may be due to:\n"
                        f"- Portal scraping failed (iframe/locator not found)\n"
                        f"- The uploaded file could not be located\n"
                        f"- The RFP does not exist in the portal for company '{target_company}'"
                    )
                    print(f"❌ {error_details}")
                    log_event("SUBMIT", "Result", "Fail", error_details)

                # Collect any portal-level errors captured during submission
                portal_errors = [
                    r.get("submit_error", "") for r in (result or [])
                    if isinstance(r, dict) and r.get("submit_error")
                ]
                portal_error_html = ""
                if portal_errors:
                    portal_error_items = "".join(f"<li>{e}</li>" for e in portal_errors)
                    portal_error_html = f"<p><b>Portal Error:</b></p><ul>{portal_error_items}</ul>"
                    log_event("SUBMIT", "Result", "Fail", f"Portal errors: {'; '.join(portal_errors)}")

                # Create error log file and attach it to the email
                # Prefer the screenshot taken from the RFP tab (new_page) over the main page
                from helpers.failure_logger import create_rfp_error_log_file
                rfp_tab_screenshots = [
                    r.get("submit_screenshot") for r in (result or [])
                    if isinstance(r, dict) and r.get("submit_screenshot")
                ]
                submit_screenshot = rfp_tab_screenshots[0] if rfp_tab_screenshots else await _take_error_screenshot(page, "submit_rfp")
                error_log_info = create_rfp_error_log_file(
                    rfp_id=rfp_id,
                    context={
                        "automation": "submit_rfp",
                        "company": target_company,
                        "rfp_link": rfp_link,
                        "error_details": error_details if rfp_not_found else ("; ".join(portal_errors) if portal_errors else "Submission failed for one or more RFPs"),
                    },
                    graph_client=graph_client,
                    screenshot_path=submit_screenshot,
                )
                error_path = error_log_info.get("sharepoint_full_path", "")
                path_html = ""
                if error_path:
                    path_html = f"<p><b>Error Log Path:</b> {error_path}</p>"
                error_body = f"""
                <p>Dear Team,</p>
                <p>The RFP with ID <b>{rfp_id}</b> encountered an error during submission.</p>
                {portal_error_html}
                {path_html}
                <p>Best Regards,<br>Automation System</p>
                """
                try:
                    trigger_email(
                        rfp_id=rfp_id,
                        email_flag="error_in_rfp_submission",
                        graph_client=graph_client,
                        rfp_link=rfp_link,
                        body_html=error_body,
                    )
                except Exception as email_err:
                    print(f"⚠️ Submit error email failed (non-critical): {email_err}")
            # await browser.close()
            return {"status": "success", "message": result}

        except Exception as e:
            log_event("SYSTEM", "SubmitError", "Fail", str(e))
            screenshot_path = await _take_error_screenshot(page, "submit_rfp")
            failure_info = record_failure_log(
                e,
                context={
                    "automation": "submit_rfp",
                    "company": target_company,
                    "rfp_id": rfp_id,
                },
                graph_client=graph_client,
                screenshot_path=screenshot_path,
            )
            _notify_failure_via_email("Submit RFP", failure_info, graph_client)
            raise HTTPException(status_code=500, detail=f"Submit failed: {str(e)}")
        finally:
            if browser is not None:
                try:
                    await browser.close()
                except Exception as close_err:
                    print(f"⚠️ Browser close warning (non-critical): {close_err}")
            log_event("SYSTEM", "EndRun", "Success", f"Submit {rfp_id} Finished")


async def run_automation_decline(rfp_id: str, company: str | None = None):
    start_new_run()  # Generate new unique RUN_ID for this automation run
    log_event("SYSTEM", "StartRun", "Success", f"Decline RFP {rfp_id} started")
    target_company = _resolve_company(company)
    graph_client = GraphClient(
        get_setting("CLIENT_ID", ""), get_setting("CLIENT_SECRET", ""), get_setting("TENANT_ID", ""),
        get_setting("SHAREPOINT_HOSTNAME", "bahracables.sharepoint.com"), get_setting("SITE_PATH", "/sites/LiveSite/RFPAutomation"), get_setting("DRIVE_NAME", "Documents")
    )
    graph_client.auth()
    graph_client.resolve_site_and_drive()

    async with async_playwright() as p:
        page = None
        try:
            open_rfps, page, browser = await common_flow(
                p,
                graph_client,
                profile_label=f"decline-{rfp_id}",
                company=target_company,
            )
            result = await decline_rfps(page, open_rfps, target_company, rfp_id)
            # result is a list of failed/missing RFPs; empty list means success
            decline_status = "success" if not result else f"failed ({len(result)} missing)"
            log_event("DECLINE", "Result", "Step", f"Decline result: {decline_status}")

            # Extract RFP link from open_rfps data
            rfp_link = None
            for row in open_rfps:
                title = row.get("Title") or ""
                if rfp_ids_match(rfp_id, title):
                    rfp_link = row.get("Link") or ""
                    break

            if not result:
                try:
                    trigger_email(rfp_id=rfp_id, email_flag="rfp_decline", graph_client=graph_client, rfp_link=rfp_link)
                except Exception as email_err:
                    print(f"⚠️ Decline success email failed (non-critical): {email_err}")
            else:
                # Create error log file and attach it to the email
                from helpers.failure_logger import create_rfp_error_log_file
                decline_screenshot = await _take_error_screenshot(page, "decline_rfp")
                error_log_info = create_rfp_error_log_file(
                    rfp_id=rfp_id,
                    context={
                        "automation": "decline_rfp",
                        "company": target_company,
                        "rfp_link": rfp_link,
                    },
                    graph_client=graph_client,
                    screenshot_path=decline_screenshot,
                )
                error_path = error_log_info.get("sharepoint_full_path", "")
                path_html = ""
                if error_path:
                    path_html = f"<p><b>Error Log Path:</b> {error_path}</p>"
                error_body = f"""
                <p>Dear Team,</p>
                <p>The RFP with ID <b>{rfp_id}</b> encountered an error during decline.</p>
                {path_html}
                <p>Best Regards,<br>Automation System</p>
                """
                try:
                    trigger_email(
                        rfp_id=rfp_id,
                        email_flag="error_in_rfp_decline",
                        graph_client=graph_client,
                        rfp_link=rfp_link,
                        body_html=error_body,
                    )
                except Exception as email_err:
                    print(f"⚠️ Decline error email failed (non-critical): {email_err}")
            return {"status": "success", "message": result}

        except Exception as e:
            log_event("SYSTEM", "DeclineError", "Fail", str(e))
            screenshot_path = await _take_error_screenshot(page, "decline_rfp")
            failure_info = record_failure_log(
                e,
                context={
                    "automation": "decline_rfp",
                    "company": target_company,
                    "rfp_id": rfp_id,
                },
                graph_client=graph_client,
                screenshot_path=screenshot_path,
            )
            _notify_failure_via_email("Decline RFP", failure_info, graph_client)
            raise HTTPException(status_code=500, detail=f"Decline failed: {str(e)}")
        finally:
            try:
                await browser.close()
            except Exception as close_err:
                print(f"⚠️ Browser close warning (non-critical): {close_err}")
            log_event("SYSTEM", "EndRun", "Success", f"Decline {rfp_id} Finished")


async def run_automation_reminder():
    start_new_run()
    log_event("SYSTEM", "StartRun", "Success", "RFP Reminder automation started")
    try:
        result = send_rfp_deadline_reminders()
        return result
    except Exception as e:
        log_event("SYSTEM", "RunError", "Fail", f"RFP Reminder error: {str(e)}")
        failure_info = record_failure_log(e, context={"automation": "rfp_reminder"}, graph_client=None)
        _notify_failure_via_email("RFP Reminder", failure_info, None)
        raise
    finally:
        log_event("SYSTEM", "EndRun", "Success", "RFP Reminder automation finished")


def _normalize_participated(val: str) -> str:
    v = (val or "").strip().lower()
    if v in ("no", "not participated", "open"):
        return "no"
    if v in ("yes", "submitted", "participated"):
        return "submitted"
    if v in ("declined", "no bid"):
        return "declined"
    return v or "no"


async def extract_rfp_data(html_path):
    rfp_data = []
    try:
        log_event("SYNC", "Extract", "Start", f"Extracting RFP data from {html_path}")
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()
        soup = BeautifulSoup(html, "html.parser")

        # 1) Header = first <tr> in the whole HTML that contains any <th>
        header_tr = None
        for tr in soup.find_all("tr"):
            if tr.find("th", recursive=False):
                header_tr = tr
                break
        if not header_tr:
            return rfp_data

        def norm(s: str) -> str:
            return re.sub(r"\s+", " ", (s or "").strip()).lower()

        header_cells = header_tr.find_all("th", recursive=False)
        header_col_count = len(header_cells)
        header_texts = [norm(th.get_text(strip=True)) for th in header_cells]

        # 2) Column map by header names (partial ok)
        col_map = {}
        for idx, txt in enumerate(header_texts):
            if "title" in txt and "title" not in col_map:
                col_map["title"] = idx
            if txt == "id" and "id" not in col_map:
                col_map["id"] = idx
            if "end time" in txt and "end_time" not in col_map:
                col_map["end_time"] = idx
            if "event type" in txt and "event_type" not in col_map:
                col_map["event_type"] = idx
            if "participated" in txt and "participated" not in col_map:
                col_map["participated"] = idx

        # 3) Data table (where rows live)
        table = soup.find("table", {"class": "tableBody"}) or soup.find("table", id="_qml6w")
        if not table:
            return rfp_data

        current_status_group = None
        for tr in table.find_all("tr", recursive=False):
            cls = " ".join(tr.get("class", []))
            if "tableGroupBy" in cls:
                txt = tr.get_text(" ", strip=True)
                m = re.search(r"Status:\s*([A-Za-z ]+)", txt)
                current_status_group = m.group(1).strip() if m else None
                continue

            tds = tr.find_all("td", recursive=False)
            if len(tds) < header_col_count:
                continue  # drop rows with fewer tds than header

            # Title (required, used as RFP_ID)
            if "title" not in col_map:
                continue
            title_td = tds[col_map["title"]]
            a = title_td.find("a", href=True)
            title_span = title_td.find("span")
            raw_title = title_span.get_text(strip=True) if title_span else (a.get_text(strip=True) if a else title_td.get_text(strip=True))
            title = re.sub(r"\s+", " ", raw_title).strip()
            link = a["href"].strip() if a else ""

            rfp_data.append({
                "Title": title,
                "RFP_ID": title,  # Title == RFP_ID
                "Link": link,
                "Doc_ID": tds[col_map["id"]].get_text(strip=True) if "id" in col_map else "",
                "End_Time": tds[col_map["end_time"]].get_text(strip=True) if "end_time" in col_map else "",
                "Event_Type": tds[col_map["event_type"]].get_text(strip=True) if "event_type" in col_map else "",
                "Participated": _normalize_participated(tds[col_map["participated"]].get_text(strip=True)) if "participated" in col_map else "",
                "StatusGroup": current_status_group,
            })

        log_event("SYNC", "Extract", "Success", f"Extracted {len(rfp_data)} RFPs from portal data")
        return rfp_data
    except Exception as e:
        import traceback; traceback.print_exc()
        log_event("SYNC", "Extract", "Fail", f"Failed to extract RFP data: {str(e)}")
        return rfp_data

def _derive_rfp_id(title: str, link: str) -> str | None:
    """
    Try to extract a normalized RFP_ID from title or link (e.g., 'C001697262').
    Returns None if not found.
    """
    import re
    candidates = []
    for text in [title or "", link or ""]:
        # Common SEC / Ariba style like C001697262
        m = re.search(r"\bC\d{9,}\b", text, re.IGNORECASE)
        if m:
            candidates.append(m.group(0).upper())
        # Fallback: pure long digits
        m2 = re.search(r"\b\d{8,}\b", text)
        if m2:
            candidates.append(m2.group(0))
    return candidates[0] if candidates else None

def _desired_status_from_portal_row(row: dict) -> str:
    """
    Use the portal's 'Participated' value as truth.
    """
    return _normalize_participated(row.get("Participated"))


def _build_scraped_index(rfp_data: list[dict]) -> list[dict]:
    """
    Enrich scraped rows with derived RFP_ID and desired status for matching.
    """
    enriched = []
    for r in rfp_data or []:
        title = r.get("Title", "")
        link = r.get("Link", "")
        raw_rfp_id = r.get("RFP_ID", "")
        # Always attempt to derive a clean ID (e.g. "C001697262") from title/link
        derived_id = _derive_rfp_id(title, link)
        # Prefer derived clean ID; fall back to raw value
        rfp_id = derived_id or raw_rfp_id
        desired_status = _desired_status_from_portal_row(r)
        enriched.append({
            **r,
            "RFP_ID": rfp_id,
            "_desired_status": desired_status
        })
    return enriched


def sync_participation_with_db(rfp_data: list[dict], rfp_ids: list[str] | None = None) -> dict:
    """
    Compare scraped RFPs with DB; update 'participated' if mismatched.
    Matching logic:
      - Prefer exact RFP_ID match
      - Fallback: fuzzy match using title via rfp_ids_match(search_id, title)
    If rfp_ids is provided, only sync those specific RFP IDs (dashboard-only sync).
    Returns summary dict.
    """
    log_event("SYNC", "Database", "Start", f"Starting sync with database for {len(rfp_data)} RFPs" +
              (f" (filtered to {len(rfp_ids)} IDs)" if rfp_ids else " (all)"))
    db_rows = get_rfp_activity_data_from_db() or []
    log_event("SYNC", "Database", "Step", f"Retrieved {len(db_rows)} records from database")
    scraped = _build_scraped_index(rfp_data)

    # If rfp_ids filter is provided, only keep scraped entries matching those dashboard IDs.
    # Dashboard sends DB-style IDs (e.g., "SEC RFP-C001752892") while _build_scraped_index
    # derives clean IDs (e.g., "C001752892"), so match using rfp_ids_match for fuzzy comparison.
    if rfp_ids:
        rfp_ids_set = {rid.strip() for rid in rfp_ids if rid.strip()}
        def _matches_any_dashboard_id(s):
            s_id = (s.get("RFP_ID") or "").strip()
            s_title = s.get("Title", "")
            for did in rfp_ids_set:
                if s_id and s_id == did:
                    return True
                if s_id and rfp_ids_match(s_id, did):
                    return True
                if s_title and rfp_ids_match(did, s_title):
                    return True
            return False
        scraped = [s for s in scraped if _matches_any_dashboard_id(s)]
        log_event("SYNC", "Database", "Step", f"Filtered scraped data to {len(scraped)} RFPs matching dashboard IDs")

    # Build quick indices — index by both raw RFP_ID and derived clean ID
    db_by_id = {}
    for row in db_rows:
        rid = (row.get("RFP_ID") or "").strip()
        if rid:
            db_by_id[rid] = row
            # Also index by derived clean ID (e.g., "C001752892") for cross-format matching
            derived = _derive_rfp_id(rid, "")
            if derived and derived != rid:
                db_by_id[derived] = row

    updated = 0
    checked = 0
    not_found = 0
    errors = 0
    details = []

    for s in scraped:
        checked += 1
        s_id = (s.get("RFP_ID") or "").strip()
        s_title = s.get("Title", "")
        target_status = (s.get("_desired_status") or "").strip().lower()

        # Attempt exact ID match (works for both raw and derived IDs via dual-indexed db_by_id)
        matched_db = db_by_id.get(s_id) if s_id else None

        # Fallback to fuzzy title-based matching if no exact match
        if not matched_db:
            for row in db_rows:
                db_id = (row.get("RFP_ID") or "").strip()
                if db_id and (rfp_ids_match(db_id, s_title) or rfp_ids_match(s_id, db_id)):
                    matched_db = row
                    break

        if not matched_db:
            not_found += 1
            details.append({"RFP_ID": s_id or "-", "Title": s_title, "result": "db_not_found"})
            continue

        current_status = (matched_db.get("participated") or "").strip().lower()
        # Update if portal status differs from DB status
        if target_status and current_status != target_status:
            try:
                record_id = matched_db.get("RFP_ID") or s_id or ""
                ok = update_rfp_participation_status(record_id, target_status, category="submit")
                if ok:
                    updated += 1
                    details.append({"RFP_ID": record_id, "from": current_status, "to": target_status, "result": "updated"})
                else:
                    errors += 1
                    details.append({"RFP_ID": record_id, "from": current_status, "to": target_status, "result": "update_failed"})
            except Exception as e:
                errors += 1
                details.append({"RFP_ID": s_id or "-", "error": str(e), "result": "exception"})
        else:
            details.append({"RFP_ID": s_id or "-", "Title": s_title, "result": "no_change"})
    summary = {
        "checked": checked,
        "updated": updated,
        "db_not_found": not_found,
        "errors": errors,
        "details": details[:50],  # trim verbosity
    }
    
    log_event("SYNC", "Database", "Success", 
              f"Sync completed: {checked} checked, {updated} updated, {not_found} not found, {errors} errors")
    
    return summary

# === Sync portal data (export all RFPs and update DB participation) ===
async def run_automation_sync_portal(rfp_ids: list[str] | None = None):
    """Sync portal participation status for ALL companies in COMPANY_OPTIONS."""
    import json
    COMPANY_OPTIONS = get_setting("COMPANY_OPTIONS", [])
    start_new_run()  # Generate new unique RUN_ID for this automation run
    log_event("SYSTEM", "StartRun", "Success",
              f"Sync portal started for all {len(COMPANY_OPTIONS)} companies" +
              (f" (filtered to {len(rfp_ids)} dashboard RFPs)" if rfp_ids else ""))

    graph_client = GraphClient(
        get_setting("CLIENT_ID", ""), get_setting("CLIENT_SECRET", ""), get_setting("TENANT_ID", ""),
        get_setting("SHAREPOINT_HOSTNAME", "bahracables.sharepoint.com"), get_setting("SITE_PATH", "/sites/LiveSite/RFPAutomation"), get_setting("DRIVE_NAME", "Documents")
    )
    log_event("SYNC", "Setup", "Step", "Initializing SharePoint client")
    graph_client.auth()
    graph_client.resolve_site_and_drive()
    log_event("SYNC", "Setup", "Success", "SharePoint client authenticated")

    # Aggregate results across all companies
    all_rfp_data = []
    summary = {
        "total_companies": len(COMPANY_OPTIONS),
        "processed": 0,
        "failed": 0,
        "total_checked": 0,
        "total_updated": 0,
        "companies": [],
    }

    for idx, company in enumerate(COMPANY_OPTIONS, 1):
        print(f"\n{'='*70}")
        print(f"[Sync Portal] Processing company {idx}/{len(COMPANY_OPTIONS)}: {company}")
        print(f"{'='*70}")
        log_event("SYNC", "ProcessCompany", "Start", f"Processing company {idx}/{len(COMPANY_OPTIONS)}: {company}")
        update_progress("sync", current=idx, total=len(COMPANY_OPTIONS), current_item=company, message=f"Syncing {company}")

        async with async_playwright() as p:
            browser = None
            page = None
            try:
                # Step 1: Login and scrape open RFPs directly from portal
                open_rfps, page, browser = await common_flow(
                    p, graph_client,
                    profile_label=f"sync-{idx}",
                    company=company,
                )
                log_event("SYNC", "Scrape", "Success", f"Company '{company}': Scraped {len(open_rfps)} open RFPs from portal")

                # Step 2: Map scraped data to sync format
                rfp_data = []
                for r in open_rfps:
                    rfp_data.append({
                        "Title": r.get("Title", ""),
                        "RFP_ID": r.get("Title", ""),
                        "Link": r.get("Link", ""),
                        "Doc_ID": r.get("ID", ""),
                        "End_Time": r.get("RFP_End_Date", ""),
                        "Event_Type": r.get("Event Type", ""),
                        "Participated": _normalize_participated(r.get("Status", "")),
                        "StatusGroup": "Open",
                        "Company": company,
                    })
                log_event("SYNC", "Map", "Success", f"Company '{company}': Mapped {len(rfp_data)} open RFPs for sync")

                # Step 3: Compare against DB and update mismatches
                log_event("SYNC", "Database", "Start", f"Company '{company}': Starting database sync for {len(rfp_data)} open RFPs" +
                         (f" (filtered to {len(rfp_ids)} dashboard RFPs)" if rfp_ids else ""))
                sync_result = sync_participation_with_db(rfp_data, rfp_ids=rfp_ids)
                log_event("SYNC", "Database", "Success",
                         f"Company '{company}': {sync_result.get('updated', 0)} updated, "
                         f"{sync_result.get('checked', 0)} checked")

                all_rfp_data.extend(rfp_data)
                summary["processed"] += 1
                summary["total_checked"] += sync_result.get("checked", 0)
                summary["total_updated"] += sync_result.get("updated", 0)
                summary["companies"].append({
                    "company": company,
                    "status": "success",
                    "rfps_scraped": len(rfp_data),
                    "sync_result": sync_result,
                })
                log_event("SYNC", "ProcessCompany", "Success", f"Company '{company}' completed successfully")

            except Exception as e:
                print(f"[Sync Portal] Error for company '{company}': {str(e)}")
                log_event("SYNC", "ProcessCompany", "Fail", f"Company '{company}' error: {str(e)}")
                screenshot_path = await _take_error_screenshot(page, f"sync_portal_{company}")
                failure_info = record_failure_log(
                    e,
                    context={"automation": "sync_portal", "company": company},
                    graph_client=graph_client,
                    screenshot_path=screenshot_path,
                )
                _notify_failure_via_email(f"Sync Portal - {company}", failure_info, graph_client)
                summary["failed"] += 1
                summary["companies"].append({"company": company, "status": "failed", "error": str(e)})
            finally:
                if browser:
                    try:
                        await browser.close()
                    except Exception as close_err:
                        print(f"⚠️ Browser close warning (non-critical): {close_err}")

    # Save combined sync data to JSON log file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    sync_data = {
        "sync_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "direct_scrape",
        "total_companies": len(COMPANY_OPTIONS),
        "total_rfps_scraped": len(all_rfp_data),
        "rfp_data": all_rfp_data,
        "sync_summary": summary,
    }

    json_filename = f"sync_data_{timestamp}.json"
    json_path = os.path.join(get_setting("OUTPUT_DIR", os.path.join(os.getcwd(), "ALLRFPs")), json_filename)

    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(sync_data, f, indent=2, ensure_ascii=False)
        log_event("SYNC", "Save", "Success", f"Sync data saved to JSON: {json_filename}")
        print(f"✅ Sync data saved to: {json_path}")

        try:
            log_event("SYNC", "SharePoint", "Uploading", f"Uploading {json_filename} to SharePoint")
            graph_client.sync_local_to_sharepoint(json_path, f"{get_setting('SP_BASE_FOLDER', 'RFP-logs')}/Sync-Data")
            log_event("SYNC", "SharePoint", "Success", f"JSON file uploaded to SharePoint: {json_filename}")
        except Exception as e:
            log_event("SYNC", "SharePoint", "Fail", f"Failed to upload JSON to SharePoint: {str(e)}")
            print(f"⚠ Could not upload JSON to SharePoint: {e}")
    except Exception as e:
        log_event("SYNC", "Save", "Fail", f"Failed to save sync data to JSON: {str(e)}")
        print(f"⚠ Could not save sync data to JSON: {e}")

    summary_msg = (f"Sync Portal complete. Companies: {summary['processed']}/{summary['total_companies']}, "
                   f"Failed: {summary['failed']}, Checked: {summary['total_checked']}, Updated: {summary['total_updated']}")
    print(f"\n{summary_msg}")
    log_event("SYSTEM", "EndRun", "Success", summary_msg)
    return {"status": "success", "message": summary_msg, "summary": summary, "json_file": json_filename}


# ===== Download All RFPs from All Companies =====
async def get_all_companies_from_portal(page):
    """Extract all company names from the dropdown"""
    log_event("ALL_RFPS", "GetCompanies", "Start", "Retrieving company list from portal")
    
    try:
        more_link = page.get_by_role("link", name=re.compile(r"^more(\.\.\.)?$", re.IGNORECASE))
        await more_link.click()
        await page.wait_for_selector('#_shtkfc', state='visible', timeout=10000)
    except Exception as e:
        log_event("ALL_RFPS", "GetCompanies", "Fail", f"Error clicking More link: {str(e)}")
        return []
    
    company_links = await page.locator('a.w-pmi-item').all()
    
    companies = []
    for link in company_links:
        try:
            text = await link.text_content()
            if text and text.strip():
                companies.append(text.strip())
        except:
            continue
    
    log_event("ALL_RFPS", "GetCompanies", "Success", f"Found {len(companies)} companies")
    return companies


async def select_company_from_portal(page, company_name):
    """Select a specific company from the portal"""
    log_event("ALL_RFPS", "SelectCompany", "Start", f"Selecting company: {company_name}")
    
    # Check if logged in before selecting company
    if not await ensure_logged_in(page):
        raise Exception("Not logged in - cannot select company")
    
    more_link = page.get_by_role("link", name=re.compile(r"^more(\.\.\.)?$", re.IGNORECASE))
    await more_link.click()
    
    await page.wait_for_selector('#_shtkfc', state='visible', timeout=10000)
    
    company_link = page.locator(f'xpath=//a[normalize-space(text())="{company_name}"]')
    
    try:
        async with page.expect_navigation(wait_until="domcontentloaded", timeout=60000):
            await company_link.click()
    except:
        pass
    
    await wait_for_page_ready(page)
    
    # Check login again after navigation
    if not await ensure_logged_in(page):
        raise Exception("Session expired during company selection")
    
    log_event("ALL_RFPS", "SelectCompany", "Success", f"Company {company_name} loaded")


async def company_file_exists(company_name, rfps_folder):
    """Check if company file already exists in RFPs folder"""
    safe_name = await sanitize_filename(company_name)
    
    if not os.path.exists(rfps_folder):
        return False, None
    
    for file in os.listdir(rfps_folder):
        if file.lower().startswith(safe_name.lower()):
            return True, file
    
    return False, None


async def download_single_rfp_file(page, rfp_data, company_name, allrfps_base_folder, graph_client=None):
    """Download a single RFP file, upload to SharePoint, and log in Dataverse.
    Checks SharePoint and Dataverse to determine if file already exists. No local storage.
    Returns: (status, error_reason, needs_relogin, file_path, owner_name, publish_time)
    """
    import tempfile
    from helpers.core_helper import click_if_visible, clean_rfp_title, get_sharepoint_rfp_material_path
    from helpers.core_helper import DATAVERSE, sanitize_filter_value
    _act_api = get_setting("RFP_ACTIVITY_LOG_TABLE_API", "cr673_bahra_rfps_v2s")
    _act_logical = get_setting("RFP_ACTIVITY_LOG_TABLE_LOGICAL", "cr673_bahra_rfps_v2")
    from rfp.download_rfp import extract_rfp_details_inner_text

    title = rfp_data.get('Title', '').strip()
    link = rfp_data.get('Link', '').strip()

    if not link:
        return 'failed', "No link provided", False, None, None, None

    clean_title = clean_rfp_title(title)

    # Check if file already exists in Dataverse
    try:
        safe_rfp_id = sanitize_filter_value(title)
        safe_company = sanitize_filter_value(company_name)
        existing_result = DATAVERSE.query_rows(
            _act_api,
            filter_expr=f"RFP_ID eq '{safe_rfp_id}' and Company_Name eq '{safe_company}'",
            top=1,
            table_logical_name=_act_logical,
            use_display_names=True
        )
        if existing_result and "value" in existing_result and len(existing_result["value"]) > 0:
            print(f"  ⏩ Already exists in Dataverse: {title}")
            return 'skipped', 'File already exists in Dataverse', False, None, None, None
    except Exception as check_error:
        print(f"  ⚠ Dataverse check failed (will proceed with download): {check_error}")

    status = 'failed'
    error_reason = None
    needs_relogin = False
    file_path = None
    owner_name = None
    publish_time = None
    new_page = await page.context.new_page()

    try:
        await new_page.goto(link, wait_until="domcontentloaded", timeout=60000)

        # Check if redirected to login page
        if "login" in new_page.url.lower() or "signin" in new_page.url.lower():
            needs_relogin = True
            error_reason = "Session expired"
            return 'failed', error_reason, needs_relogin, None, None, None

        # Wait for page to be fully loaded before extracting details
        await wait_for_page_ready(new_page)
        await asyncio.sleep(2)

        # Extract RFP details (owner_name and publish_time) before clicking download buttons
        try:
            rfp_details = await extract_rfp_details_inner_text(new_page, company_name=company_name)
            owner_name = rfp_details.get('owner')
            publish_time = rfp_details.get('publish_time')

            if owner_name or publish_time:
                log_event("ALL_RFPS", "ExtractDetails", "Success",
                         f"Extracted owner: {owner_name}, publish_time: {publish_time} for {title}")
            else:
                log_event("ALL_RFPS", "ExtractDetails", "Warning",
                         f"Could not extract owner or publish time for {title}.")
        except Exception as e:
            log_event("ALL_RFPS", "ExtractDetails", "Fail", f"Could not extract RFP details: {e} for {title}")

        # Click through download steps
        await click_if_visible(new_page, "#_c8_tuc", timeout=4000)

        old_url = new_page.url
        for _ in range(20):
            clicked = await click_if_visible(new_page, "#_iiyvqc", timeout=2000)
            if clicked and new_page.url != old_url:
                break

        await new_page.wait_for_load_state('networkidle', timeout=8000)

        async with new_page.expect_download(timeout=15000) as dl_info:
            await new_page.click("#_gktadc")

        download = await dl_info.value

        # Use clean title for filename
        suggested_name = download.suggested_filename or f"{clean_title}.xls"
        if not suggested_name.endswith(('.xls', '.xlsx')):
            suggested_name = f"{clean_title}.xls"
        else:
            ext = os.path.splitext(suggested_name)[1]
            suggested_name = f"{clean_title}{ext}"

        # Save to temp directory, upload to SharePoint, then cleanup
        temp_dir = tempfile.mkdtemp(prefix="rfp_download_")
        temp_path = os.path.join(temp_dir, suggested_name)

        await download.save_as(temp_path)

        # Upload to SharePoint directly (save_as succeeded = file is ready)
        if graph_client:
            try:
                sp_material_path = get_sharepoint_rfp_material_path(title, company_name)
                graph_client.upload_file_as(temp_path, sp_material_path, os.path.basename(temp_path))
                log_event("ALL_RFPS", "Upload", "Success", f"Uploaded {suggested_name} to SharePoint for {title}")
            except Exception as upload_err:
                log_event("ALL_RFPS", "Upload", "Fail", f"Failed to upload to SharePoint: {upload_err} for {title}")

        status = 'success'
        error_reason = None
        file_path = temp_path

        # Cleanup temp file
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass

    except Exception as e:
        error_msg = str(e)
        if any(keyword in error_msg.lower() for keyword in ['timeout', 'navigation', 'unauthorized', 'forbidden']):
            needs_relogin = True
        error_reason = error_msg
    finally:
        await new_page.close()

    return status, error_reason, needs_relogin, file_path, owner_name, publish_time


def store_rfp_in_database(rfp_data, company_name, file_path=None, owner_name=None, publish_time=None):
    """Store RFP data in RFP activity log table"""
    from helpers.core_helper import DATAVERSE
    from core.log_events import get_current_run_id
    _act_api = get_setting("RFP_ACTIVITY_LOG_TABLE_API", "cr673_bahra_rfps_v2s")
    _act_logical = get_setting("RFP_ACTIVITY_LOG_TABLE_LOGICAL", "cr673_bahra_rfps_v2")

    try:
        rfp_id = rfp_data.get('RFP_ID') or rfp_data.get('Title', '')
        link = rfp_data.get('Link', '')
        end_date = rfp_data.get('RFP_End_Date') or rfp_data.get('End_Time', '')
        participated = rfp_data.get('Participated', '') or rfp_data.get('participated', '')

        # Check if RFP already exists
        existing_result = DATAVERSE.query_rows(
            _act_api,
            filter_expr=f"RFP_ID eq '{rfp_id}' and Company_Name eq '{company_name}'",
            top=1,
            table_logical_name=_act_logical,
            use_display_names=True
        )
        
        # Only include fields that exist in the table
        row_data = {
            "RFP_ID": rfp_id,  # RFP_ID contains the title information
            "Company_Name": company_name,
            "Link": link,
            "participated": participated.lower() if participated else "",
            "Downloaded_At": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "RunID": get_current_run_id()
        }
        
        # Only add RFP_End_Date if it has a valid value (normalize to MM/DD/YYYY HH:MM AM/PM)
        if end_date and end_date != '-':
            from core.log_events import normalize_date_format
            row_data["RFP_End_Date"] = normalize_date_format(end_date)
        
        # Add owner_name / publish_time if provided and non-blank (Fix 5).
        # Reject pure-whitespace strings so we don't insert garbage; bare None
        # is omitted entirely so Dataverse keeps any pre-existing value on UPDATE.
        if owner_name is not None and str(owner_name).strip():
            row_data["owner_name"] = str(owner_name).strip()

        if publish_time is not None and str(publish_time).strip():
            row_data["publish_time"] = publish_time
        
        # Note: File_Path doesn't exist in the table, so we can't store it
        # The file path is already in the folder structure: ALLRFPs/CompanyName/RFPName/downloaded-rfp/
        
        if existing_result and "value" in existing_result and len(existing_result["value"]) > 0:
            # Update existing record
            existing_row = existing_result["value"][0]
            record_id = existing_row[f"{_act_logical}id"]
            
            # Only update if there are changes
            update_data = {}
            for key, value in row_data.items():
                if value and value != existing_row.get(key, ""):
                    update_data[key] = value
            
            if update_data:
                DATAVERSE.update_row(
                    _act_api,
                    record_id,
                    update_data,
                    table_logical_name=_act_logical
                )
                log_event("ALL_RFPS", "Database", "Updated", f"Updated RFP {rfp_id} for {company_name}")
        else:
            # Insert new record
            DATAVERSE.insert_row(
                _act_api,
                row_data,
                table_logical_name=_act_logical
            )
            log_event("ALL_RFPS", "Database", "Inserted", f"Inserted RFP {rfp_id} for {company_name}")
        
        return True
    except Exception as e:
        log_event("ALL_RFPS", "Database", "Fail", f"Failed to store RFP in database: {str(e)}")
        return False


async def run_automation_download_all_rfps(selected_company: str = ""):
    """Main function to download all RFPs from selected company or all companies
    
    Args:
        selected_company: Company name to filter. If empty or "All Companies", processes all companies.
    """
    start_new_run()
    company_filter = selected_company.strip() if selected_company else ""
    filter_text = f" for {company_filter}" if company_filter else " from all companies"
    log_event("ALL_RFPS", "StartRun", "Success", f"Download all RFPs automation started{filter_text}")

    # No local folder setup needed — files go to temp dirs and SharePoint only

    # Initialize SharePoint client for file existence checks
    graph_client = GraphClient(
        get_setting("CLIENT_ID", ""), get_setting("CLIENT_SECRET", ""), get_setting("TENANT_ID", ""),
        get_setting("SHAREPOINT_HOSTNAME", "bahracables.sharepoint.com"), get_setting("SITE_PATH", "/sites/LiveSite/RFPAutomation"), get_setting("DRIVE_NAME", "Documents")
    )
    graph_client.auth()
    graph_client.resolve_site_and_drive()
    log_event("ALL_RFPS", "Setup", "Success", "SharePoint client authenticated for file checks")

    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir="C:\\playwright-profile",
            headless=False,
            args=['--no-sandbox', '--disable-dev-shm-usage'],
            viewport={'width': 1280, 'height': 720},
            accept_downloads=True
        )
        
        page = await browser.new_page()
        
        try:
            # Login
            log_event("ALL_RFPS", "Login", "Start", "Starting login")
            await page.goto(get_setting("URL", ""), wait_until="domcontentloaded")
            await fill_login_credentials(page, USERNAME, PASSWORD)

            try:
                async with page.expect_navigation(wait_until="networkidle", timeout=60000):
                    await page.click('input[type="submit"]')
            except:
                await page.wait_for_load_state("networkidle")
            
            await wait_for_page_ready(page)
            log_event("ALL_RFPS", "Login", "Success", "Login successful")
            
            # Get all companies
            companies = await get_all_companies_from_portal(page)
            
            if not companies:
                log_event("ALL_RFPS", "GetCompanies", "Fail", "No companies found")
                return {"status": "error", "message": "No companies found"}
            
            # Filter companies based on selection
            if company_filter and company_filter.lower() != "all companies":
                # Filter to selected company only
                filtered_companies = [c for c in companies if c == company_filter]
                if not filtered_companies:
                    log_event("ALL_RFPS", "FilterCompany", "Fail", f"Company '{company_filter}' not found in portal")
                    return {"status": "error", "message": f"Company '{company_filter}' not found in portal"}
                companies = filtered_companies
                log_event("ALL_RFPS", "FilterCompany", "Success", f"Filtered to company: {company_filter}")

            # Initialize progress tracking
            update_progress("download", current=0, total=len(companies), message="Starting download...")
            
            summary = {
                "total_companies": len(companies),
                "processed": 0,
                "skipped": 0,
                "failed": 0,
                "downloaded_rfps": 0,
                "failed_rfps": 0,
                "skipped_rfps": 0,
                "companies": [],
                "selected_company": company_filter if company_filter else "All Companies"
            }
            
            # Process each company
            for idx, company in enumerate(companies, 1):
                # Update progress for UI
                update_progress("download", current=idx, total=len(companies), current_item=company, message=f"Processing {company}")

                company_summary = {
                    "company": company,
                    "status": "processing",
                    "exported_file": None,
                    "rfps_found": 0,
                    "rfps_downloaded": 0,
                    "rfps_failed": 0,
                    "rfps_skipped": 0,
                    "errors": []
                }

                print(f"\n{'='*70}")
                print(f"Processing {idx}/{len(companies)}: {company}")
                print(f"{'='*70}")
                log_event("ALL_RFPS", "ProcessCompany", "Start", f"Processing company {idx}/{len(companies)}: {company}")
                
                # No local file check — individual RFP existence is checked
                # against SharePoint and Dataverse in download_single_rfp_file
                try:
                    # Check if logged in before processing company
                    if not await ensure_logged_in(page):
                        error_msg = "Failed to re-login. Skipping company."
                        print(f"  ❌ {error_msg}")
                        log_event("ALL_RFPS", "ProcessCompany", "Fail", f"{company}: {error_msg}")
                        company_summary["status"] = "failed"
                        company_summary["errors"].append(error_msg)
                        summary["failed"] += 1
                        summary["companies"].append(company_summary)
                        continue
                    
                    # Select company
                    await select_company_from_portal(page, company)
                    
                    # Check login again after company selection
                    if not await ensure_logged_in(page):
                        error_msg = "Session expired after company selection. Re-logging in..."
                        print(f"  ⚠️  {error_msg}")
                        log_event("ALL_RFPS", "ProcessCompany", "Warning", f"{company}: {error_msg}")
                        if not await ensure_logged_in(page):
                            error_msg = "Failed to re-login after company selection"
                            company_summary["status"] = "failed"
                            company_summary["errors"].append(error_msg)
                            summary["failed"] += 1
                            summary["companies"].append(company_summary)
                            continue
                        # Re-select company after re-login
                        await select_company_from_portal(page, company)
                    
                    # Export RFPs (HTML/Excel) to temp directory
                    exported_path = await export_rfps(page, company)
                    company_summary["exported_file"] = os.path.basename(exported_path)

                    # Extract RFP data from exported file
                    rfp_data_list = await extract_rfp_data(exported_path)
                    company_summary["rfps_found"] = len(rfp_data_list)

                    # Clean up temp export file (no longer needed after extraction)
                    try:
                        shutil.rmtree(os.path.dirname(exported_path), ignore_errors=True)
                    except Exception:
                        pass
                    
                    if not rfp_data_list:
                        company_summary["status"] = "completed"
                        company_summary["errors"].append("No RFPs found in exported file")
                        summary["companies"].append(company_summary)
                        continue
                    
                    # Download individual RFP files
                    # Folder structure will be created in download_single_rfp_file: ALLRFPs/CompanyName/RFPName/downloaded-rfp/
                    for rfp_idx, rfp_data in enumerate(rfp_data_list, 1):
                        print(f"\n  [{rfp_idx}/{len(rfp_data_list)}] {rfp_data.get('Title', 'Unknown')}")
                        
                        # Check if logged in before each RFP download
                        if not await ensure_logged_in(page):
                            error_msg = "Failed to re-login after session expired"
                            print(f"  ❌ {error_msg}")
                            company_summary["rfps_failed"] += 1
                            summary["failed_rfps"] += 1
                            company_summary["errors"].append(f"RFP {rfp_data.get('Title', 'Unknown')}: {error_msg}")
                            log_event("ALL_RFPS", "DownloadRFP", "Fail", f"Failed to download {rfp_data.get('Title', 'Unknown')}: {error_msg}")
                            # Try to continue with next RFP
                            continue
                        
                        # Re-select company after re-login if needed
                        try:
                            current_url = page.url.lower()
                            if "login" not in current_url:
                                # Make sure we're on the right company page
                                await select_company_from_portal(page, company)
                        except:
                            pass
                        
                        status, error_reason, needs_relogin, file_path, owner_name, publish_time = await download_single_rfp_file(
                            page, rfp_data, company, None, graph_client=graph_client
                        )
                        
                        if status == 'success':
                            company_summary["rfps_downloaded"] += 1
                            summary["downloaded_rfps"] += 1
                            
                            # Store in database with correct file path, owner_name, and publish_time
                            store_rfp_in_database(rfp_data, company, file_path, owner_name, publish_time)
                        elif status == 'skipped':
                            company_summary["rfps_skipped"] += 1
                            summary["skipped_rfps"] += 1
                            # Still store in database if file exists (owner and publish time may be None for skipped files)
                            store_rfp_in_database(rfp_data, company, file_path, owner_name, publish_time)
                        else:
                            company_summary["rfps_failed"] += 1
                            summary["failed_rfps"] += 1
                            company_summary["errors"].append(f"RFP {rfp_data.get('Title', 'Unknown')}: {error_reason}")
                            
                            if needs_relogin:
                                # Try to re-login
                                if await ensure_logged_in(page):
                                    # Re-select company after re-login
                                    try:
                                        await select_company_from_portal(page, company)
                                    except Exception as e:
                                        print(f"  ⚠️  Warning: Could not re-select company after re-login: {e}")
                        
                        await asyncio.sleep(1)
                    
                    company_summary["status"] = "completed"
                    summary["processed"] += 1
                    
                except Exception as e:
                    error_msg = str(e)
                    print(f"  ❌ Error processing company: {error_msg}")
                    log_event("ALL_RFPS", "ProcessCompany", "Fail", f"Error processing {company}: {error_msg}")
                    company_summary["status"] = "failed"
                    company_summary["errors"].append(error_msg)
                    summary["failed"] += 1
                
                summary["companies"].append(company_summary)
            
            # Final summary logged via log_event
            
            log_event("ALL_RFPS", "EndRun", "Success", 
                     f"Completed: {summary['processed']} companies, {summary['downloaded_rfps']} RFPs downloaded")
            
            return {
                "status": "success",
                "message": "Download all RFPs completed",
                "summary": summary
            }
            
        except Exception as e:
            error_msg = str(e)
            log_event("ALL_RFPS", "RunError", "Fail", f"Automation error: {error_msg}")
            screenshot_path = await _take_error_screenshot(page, "download_all_rfps")
            failure_info = record_failure_log(
                e,
                context={"automation": "download_all_rfps", "selected_company": company_filter},
                graph_client=graph_client,
                screenshot_path=screenshot_path,
            )
            _notify_failure_via_email("Download All RFPs", failure_info, graph_client)
            return {"status": "error", "message": error_msg}

        finally:
            await browser.close()


# ===== SharePoint-Dataverse Sync Functions =====

def verify_sharepoint_files_against_dataverse(graph_client, company_name: str = None) -> dict:
    """
    Check every Dataverse RFP record and verify if its file exists in SharePoint.
    No local files are checked - purely SharePoint vs Dataverse.

    Returns:
        dict with 'synced', 'missing_in_sp' (DB has entry, SP missing file),
        'missing_in_db' (SP has file, DB missing entry), 'errors'
    """
    from helpers.core_helper import get_rfp_activity_data_from_db, get_sharepoint_rfp_material_path

    log_event("SP_DV_SYNC", "Verify", "Start", f"Verifying SharePoint files for {company_name or 'all companies'}")

    result = {
        'synced': [],
        'missing_in_sp': [],      # DB has entry but file missing in SharePoint
        'missing_in_db': [],      # SharePoint has file but no DB entry
        'errors': []
    }

    try:
        # ── PHASE 1: Check DB records against SharePoint ──
        dataverse_records = get_rfp_activity_data_from_db()
        log_event("SP_DV_SYNC", "Verify", "Step", f"Retrieved {len(dataverse_records)} records from Dataverse")

        if company_name:
            dataverse_records = [r for r in dataverse_records if r.get("Company_Name") == company_name]
            log_event("SP_DV_SYNC", "Verify", "Step", f"Filtered to {len(dataverse_records)} records for {company_name}")

        # Build a set of known DB rfp_ids for Phase 2
        db_rfp_keys = set()  # (normalized_rfp_id, normalized_company_name)

        for record in dataverse_records:
            rfp_id = record.get("RFP_ID")
            comp_name = record.get("Company_Name")

            if not rfp_id or not comp_name:
                result['errors'].append(f"Record missing RFP_ID or Company_Name: {record}")
                continue

            db_rfp_keys.add((rfp_id.strip().lower(), comp_name.strip().lower()))

            try:
                sp_material_path = get_sharepoint_rfp_material_path(rfp_id, comp_name)
                files = graph_client.list_files_in_directory(sp_material_path, ['.xls', '.xlsx'])

                if files and len(files) > 0:
                    result['synced'].append({
                        'rfp_id': rfp_id,
                        'company_name': comp_name,
                        'files': files
                    })
                else:
                    result['missing_in_sp'].append({
                        'rfp_id': rfp_id,
                        'company_name': comp_name,
                        'link': record.get("Link"),
                        'sp_path': sp_material_path
                    })
            except Exception as e:
                result['errors'].append(f"Error checking {rfp_id}: {str(e)}")

        # ── PHASE 2: Check SharePoint files against DB ──
        log_event("SP_DV_SYNC", "Verify", "Step", "Scanning SharePoint for files without DB entries")

        sp_allrfps_path = f"{get_setting('SP_BASE_FOLDER', 'RFP-logs')}/ALLRFPs"

        # List company folders
        if company_name:
            safe_company = re.sub(r'[<>:"/\\|?*]', '_', company_name).strip()
            company_folders = [{'name': safe_company, 'path': f"{sp_allrfps_path}/{safe_company}"}]
        else:
            company_folders = graph_client.list_folders_in_directory(sp_allrfps_path)

        for company_folder in company_folders:
            comp_folder_name = company_folder['name']
            comp_folder_path = company_folder['path']

            try:
                # List RFP folders under this company
                rfp_folders = graph_client.list_folders_in_directory(comp_folder_path)

                for rfp_folder in rfp_folders:
                    rfp_folder_name = rfp_folder['name']

                    # Check if this RFP exists in DB
                    key = (rfp_folder_name.strip().lower(), comp_folder_name.strip().lower())
                    if key not in db_rfp_keys:
                        # Check if downloaded-rfp folder has files
                        sp_downloaded_path = f"{rfp_folder['path']}/downloaded-rfp"
                        sp_files = graph_client.list_files_in_directory(sp_downloaded_path, ['.xls', '.xlsx'])

                        if sp_files and len(sp_files) > 0:
                            result['missing_in_db'].append({
                                'rfp_id': rfp_folder_name,
                                'company_name': comp_folder_name,
                                'sp_path': sp_downloaded_path,
                                'files': sp_files
                            })
            except Exception as e:
                result['errors'].append(f"Error scanning SP company folder {comp_folder_name}: {str(e)}")

        log_event("SP_DV_SYNC", "Verify", "Success",
                 f"Verification: {len(result['synced'])} synced, "
                 f"{len(result['missing_in_sp'])} missing in SP, "
                 f"{len(result['missing_in_db'])} missing in DB")

    except Exception as e:
        log_event("SP_DV_SYNC", "Verify", "Fail", f"Verification failed: {str(e)}")
        result['errors'].append(f"Verification failed: {str(e)}")

    return result


async def sync_db_to_sharepoint(page, missing_in_sp: list, graph_client, company_name: str) -> dict:
    """
    Case: DB has entry but file is missing in SharePoint.
    Download from portal → Upload to SharePoint → Update DB timestamp.
    """
    from helpers.core_helper import update_sync_timestamp, get_sharepoint_rfp_material_path

    result = {'synced': 0, 'failed': 0, 'details': []}
    total = len(missing_in_sp)
    log_event("SP_DV_SYNC", "SyncToSP", "Start", f"Downloading {total} missing files to SharePoint")

    for idx, record in enumerate(missing_in_sp, 1):
        rfp_id = record.get('rfp_id')
        comp_name = record.get('company_name')
        link = record.get('link')

        update_progress("sync_sp_dv", idx, total, f"Downloading {rfp_id} to SharePoint")

        detail = {'rfp_id': rfp_id, 'company_name': comp_name, 'status': 'pending'}

        if not link:
            detail['status'] = 'failed'
            detail['error'] = 'No portal link available in DB'
            result['failed'] += 1
            result['details'].append(detail)
            continue

        try:
            log_event("SP_DV_SYNC", "SyncToSP", "Step", f"[{idx}/{total}] Processing {rfp_id}")

            # Prepare rfp_data dict for download_single_rfp_file
            rfp_data = {'Title': rfp_id, 'Link': link}

            # Download from portal (saves to local temp first)
            status, message, needs_relogin, local_path, owner_name, publish_time = await download_single_rfp_file(
                page, rfp_data, comp_name, get_setting("OUTPUT_DIR", os.path.join(os.getcwd(), "ALLRFPs")), graph_client=graph_client
            )

            if needs_relogin:
                detail['status'] = 'failed'
                detail['error'] = 'Session expired - needs relogin'
                result['failed'] += 1
                result['details'].append(detail)
                log_event("SP_DV_SYNC", "SyncToSP", "Fail", f"Session expired for {rfp_id}")
                continue

            if (status == 'success' or status == 'skipped') and local_path and os.path.exists(local_path):
                # Upload to SharePoint
                filename = os.path.basename(local_path)
                sp_material_path = get_sharepoint_rfp_material_path(rfp_id, comp_name)

                try:
                    graph_client.upload_file_as(local_path, sp_material_path, filename)
                    update_sync_timestamp(rfp_id, comp_name)

                    detail['status'] = 'success'
                    detail['sp_path'] = f"{sp_material_path}/{filename}"
                    result['synced'] += 1
                    log_event("SP_DV_SYNC", "SyncToSP", "Success", f"Synced {rfp_id} to SharePoint")
                except Exception as upload_err:
                    detail['status'] = 'failed'
                    detail['error'] = f"Upload failed: {str(upload_err)}"
                    result['failed'] += 1
                    log_event("SP_DV_SYNC", "SyncToSP", "Fail", f"Upload failed for {rfp_id}: {str(upload_err)}")
            else:
                detail['status'] = 'failed'
                detail['error'] = message or 'Download failed'
                result['failed'] += 1
                log_event("SP_DV_SYNC", "SyncToSP", "Fail", f"Download failed for {rfp_id}: {message}")

        except Exception as e:
            detail['status'] = 'failed'
            detail['error'] = str(e)
            result['failed'] += 1
            log_event("SP_DV_SYNC", "SyncToSP", "Fail", f"Error syncing {rfp_id}: {str(e)}")

        result['details'].append(detail)

    log_event("SP_DV_SYNC", "SyncToSP", "Success",
             f"DB→SP sync done: {result['synced']} synced, {result['failed']} failed")
    return result


async def sync_sp_to_database(missing_in_db: list, page=None, open_rfps_by_id: dict = None) -> dict:
    """
    Case: SharePoint has file but no DB entry.
    Store the RFP information into Dataverse.

    When `page` (a Playwright page) and `open_rfps_by_id` (rfp_id -> portal link)
    are provided, the function attempts to scrape owner_name / publish_time from
    the portal before inserting. Falls back to creating a stub row with empty
    metadata when the RFP isn't currently open on the portal (historical files).
    """
    from helpers.core_helper import DATAVERSE
    from core.log_events import get_current_run_id
    from rfp.download_rfp import extract_rfp_details_inner_text
    from helpers.core_helper import click_if_visible
    import asyncio

    result = {'stored': 0, 'failed': 0, 'details': []}
    total = len(missing_in_db)
    open_rfps_by_id = open_rfps_by_id or {}
    log_event("SP_DV_SYNC", "SyncToDB", "Start", f"Storing {total} SharePoint RFPs into Dataverse")

    for idx, record in enumerate(missing_in_db, 1):
        rfp_id = record.get('rfp_id')
        comp_name = record.get('company_name')

        detail = {'rfp_id': rfp_id, 'company_name': comp_name, 'status': 'pending'}

        try:
            log_event("SP_DV_SYNC", "SyncToDB", "Step", f"[{idx}/{total}] Storing {rfp_id} in DB")

            owner_name = None
            publish_time = None
            link = open_rfps_by_id.get(rfp_id) or open_rfps_by_id.get(str(rfp_id))

            if page is not None and link:
                detail_page = await page.context.new_page()
                try:
                    await detail_page.goto(link, wait_until="domcontentloaded", timeout=60000)
                    try:
                        await click_if_visible(detail_page, "#_c8_tuc", timeout=3000)
                        await asyncio.sleep(10)
                    except Exception:
                        pass
                    rfp_details = await extract_rfp_details_inner_text(detail_page, company_name=comp_name)
                    owner_name = rfp_details.get('owner')
                    publish_time = rfp_details.get('publish_time')
                    log_event("SP_DV_SYNC", "ExtractDetails", "Success",
                              f"Scraped owner={owner_name}, publish_time={publish_time} for {rfp_id}")
                except Exception as e:
                    log_event("SP_DV_SYNC", "ExtractDetails", "Warning",
                              f"Failed to scrape {rfp_id}: {e}")
                finally:
                    try:
                        await detail_page.close()
                    except Exception:
                        pass
            else:
                if page is None:
                    log_event("SP_DV_SYNC", "ExtractDetails", "Warning",
                              f"No browser session — creating stub row for {rfp_id} (no owner/publish)")
                else:
                    log_event("SP_DV_SYNC", "ExtractDetails", "Warning",
                              f"RFP {rfp_id} not in current open list — creating stub row (no owner/publish)")

            # Prepare data for insertion
            rfp_data = {
                'RFP_ID': rfp_id,
                'Title': rfp_id
            }

            store_rfp_in_database(
                rfp_data=rfp_data,
                company_name=comp_name,
                file_path=None,
                owner_name=owner_name,
                publish_time=publish_time,
            )

            detail['status'] = 'success'
            result['stored'] += 1
            log_event("SP_DV_SYNC", "SyncToDB", "Success", f"Stored {rfp_id} in DB")

        except Exception as e:
            detail['status'] = 'failed'
            detail['error'] = str(e)
            result['failed'] += 1
            log_event("SP_DV_SYNC", "SyncToDB", "Fail", f"Error storing {rfp_id}: {str(e)}")

        result['details'].append(detail)

    log_event("SP_DV_SYNC", "SyncToDB", "Success",
             f"SP→DB sync done: {result['stored']} stored, {result['failed']} failed")
    return result


async def run_sync_sharepoint_dataverse(company: str = None):
    """
    Main entry point to sync RFP files between SharePoint and Dataverse.

    Logic:
    1. Check Database → for each RFP entry, verify file exists in SharePoint
       - Missing in SP → Download from portal → Upload to SharePoint → Update timestamp
    2. Check SharePoint → for each RFP file, verify entry exists in Database
       - Missing in DB → Store RFP info in Dataverse
    3. No local files used - everything checks against SharePoint
    """
    start_new_run()
    target_company = _resolve_company(company)
    log_event("SP_DV_SYNC", "StartRun", "Success", f"Starting SharePoint-Dataverse sync for {target_company or 'all companies'}")

    # Initialize SharePoint client
    graph_client = GraphClient(
        get_setting("CLIENT_ID", ""), get_setting("CLIENT_SECRET", ""), get_setting("TENANT_ID", ""),
        get_setting("SHAREPOINT_HOSTNAME", "bahracables.sharepoint.com"), get_setting("SITE_PATH", "/sites/LiveSite/RFPAutomation"), get_setting("DRIVE_NAME", "Documents")
    )
    log_event("SP_DV_SYNC", "Setup", "Step", "Initializing SharePoint client")
    graph_client.auth()
    graph_client.resolve_site_and_drive()
    log_event("SP_DV_SYNC", "Setup", "Success", "SharePoint client authenticated")

    # Step 1: Verify both directions
    verify_result = verify_sharepoint_files_against_dataverse(graph_client, target_company)

    missing_in_sp = verify_result.get('missing_in_sp', [])
    missing_in_db = verify_result.get('missing_in_db', [])

    # Steps 2 + 3: Both sync directions share a single browser session so that
    # SP→DB can scrape owner_name / publish_time from the portal (Fix 2).
    sp_to_db_result = {'stored': 0, 'failed': 0, 'details': []}
    db_to_sp_result = {'synced': 0, 'failed': 0, 'details': []}

    if missing_in_db or missing_in_sp:
        async with async_playwright() as p:
            browser = None
            page = None
            try:
                log_event("SP_DV_SYNC", "Login", "Start", "Starting login and company selection")
                open_rfps, page, browser = await common_flow(p, graph_client, profile_label="sync-sp-dv", company=target_company)
                log_event("SP_DV_SYNC", "Login", "Success", f"Logged in and selected company {target_company}")

                open_rfps_by_id = {
                    r.get("Title", ""): r.get("Link", "")
                    for r in (open_rfps or [])
                    if r.get("Title")
                }

                if missing_in_db:
                    log_event("SP_DV_SYNC", "SyncToDB", "Start", f"Storing {len(missing_in_db)} SP orphan files in DB")
                    sp_to_db_result = await sync_sp_to_database(
                        missing_in_db, page=page, open_rfps_by_id=open_rfps_by_id
                    )

                if missing_in_sp:
                    log_event("SP_DV_SYNC", "SyncToSP", "Start", f"Downloading {len(missing_in_sp)} missing files to SharePoint")
                    db_to_sp_result = await sync_db_to_sharepoint(page, missing_in_sp, graph_client, target_company)

            except HTTPException:
                raise
            except Exception as e:
                log_event("SP_DV_SYNC", "RunError", "Fail", f"Sync automation error: {str(e)}")
                screenshot_path = await _take_error_screenshot(page, "sync_sp_dv")
                failure_info = record_failure_log(
                    e,
                    context={"automation": "sync_sharepoint_dataverse", "company": target_company},
                    graph_client=graph_client,
                    screenshot_path=screenshot_path,
                )
                _notify_failure_via_email("SharePoint-Dataverse Sync", failure_info, graph_client)
                raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")
            finally:
                if browser:
                    try:
                        await browser.close()
                        log_event("SP_DV_SYNC", "Cleanup", "Step", "Browser closed")
                    except Exception as close_err:
                        print(f"⚠️ Browser close warning (non-critical): {close_err}")

    # If nothing needed syncing
    if not missing_in_sp and not missing_in_db:
        log_event("SP_DV_SYNC", "EndRun", "Success", "All synced - no action needed")

    log_event("SP_DV_SYNC", "EndRun", "Success",
             f"Sync complete: {db_to_sp_result['synced']} files→SP, "
             f"{sp_to_db_result['stored']} entries→DB")

    return {
        "status": "success",
        "message": "SharePoint-Dataverse sync completed",
        "already_synced": len(verify_result.get('synced', [])),
        "db_to_sp": {
            "synced": db_to_sp_result['synced'],
            "failed": db_to_sp_result['failed'],
            "details": db_to_sp_result['details']
        },
        "sp_to_db": {
            "stored": sp_to_db_result['stored'],
            "failed": sp_to_db_result['failed'],
            "details": sp_to_db_result['details']
        },
        "errors": verify_result.get('errors', [])
    }