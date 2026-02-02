# === Windows asyncio fix for Playwright subprocess support ===
import sys
import asyncio
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# === Your existing imports ===
from rfp.submit_rfp import submit_rfp
from core.common_imports import *
from config.config import SP_BASE_FOLDER, OUTPUT_DIR, URL, resolve_company_name
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
from helpers.failure_logger import record_failure_log


def _resolve_company(company: str | None) -> str:
    """Normalize requested company, defaulting to configured COMPANY_NAME.
    Maps frontend short names (SEC, Aramco, HADEED) to full portal names.
    """
    value = (company or "").strip()
    if not value:
        return COMPANY_NAME
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
    Send failure notification email with detailed log file attached.
    Email body uses the default simple message; all details are in the attached log file.
    """
    attachments = []
    sharepoint_full_path = failure_info.get("sharepoint_full_path")
    if sharepoint_full_path:
        attachments.append(
            {
                "name": failure_info.get("file_name"),
                "path": sharepoint_full_path,
            }
        )
    # Use default simple email body - all details are in the attached log file
    trigger_email(
        csv_file=None,
        graph_client=graph_client,
        subject=f"[Automation Failure] {automation_label}",
        body_html=None,  # Use default simple message from email_helper
        email_flag="automation_failure",
        attachments=attachments,
    )


async def sanitize_filename(name: str) -> str:
    """Sanitize company name for use in filenames"""
    return re.sub(r'[<>:"/\\|?*]', '_', name).strip()

async def wait_for_page_ready(page, context=None):
    """Wait for page to be fully ready"""
    target = context if context else page
    
    try:
        await page.wait_for_load_state("networkidle", timeout=60000)
    except:
        pass
    
    try:
        await target.wait_for_selector(
            '.loading, .spinner, [aria-busy="true"], .w-loading',
            state='hidden',
            timeout=5000
        )
    except:
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
            login_input = await page.locator('xpath=//*[@id="_boebpb"]/div[1]/input').count()
            if login_input > 0:
                return False
        except:
            pass
        
        # Check if we're on a valid portal page (not login)
        if URL.lower() in current_url or "ariba" in current_url:
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
            await page.goto(URL, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(1)
            
            # Wait for login input to be available
            try:
                await page.wait_for_selector('xpath=//*[@id="_boebpb"]/div[1]/input', state='visible', timeout=10000)
            except:
                # If selector not found, try alternative
                await page.wait_for_selector('#Password', state='visible', timeout=10000)
            
            # Fill login credentials
            await page.fill('xpath=//*[@id="_boebpb"]/div[1]/input', USERNAME)
            await page.fill('#Password', PASSWORD)
            
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

    # Save to temporary location first
    temp_path = os.path.join(OUTPUT_DIR, f"temp_{timestamp}.download")
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
    print(f"  📄 Ariba provided: {suggested_name}")
    print(f"  🔍 Detected format: {real_ext}")

    # Create final filename with correct extension
    target_filename = f"{safe_company_name}_{timestamp}{real_ext}"
    target_path = os.path.join(OUTPUT_DIR, target_filename)

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
    await download_rfp_files(page, open_rfps, company_name, graph_client)

    # Process matched materials
    # try:
    master_csv_local = os.path.join(OUTPUT_DIR, "master_material.csv")
    matched_df, matched_csv_path, not_mateched_files = process_folder(
        graph_client, OUTPUT_DIR, master_csv_local
    )
    print(f"✅ Matched materials processed: {matched_csv_path}")

    trigger_email_rfps = trigger_email(
        csv_file=matched_csv_path, graph_client=graph_client,not_mateched_files=not_mateched_files
    )
    log_event(
        "EMAIL",
        "Sent",
        "Success",
        message=f"Email triggered with {len(matched_df)} matches",
        rfp_id=trigger_email_rfps,
    )

    log_event("SYSTEM", "DownloadRFP", "Success", "Download flow finished")

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
        CLIENT_ID, CLIENT_SECRET, TENANT_ID,
        SHAREPOINT_HOSTNAME, SITE_PATH, DRIVE_NAME
    )
    graph_client.auth()
    graph_client.resolve_site_and_drive()

    async with async_playwright() as p:
        browser = None
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
            failure_info = record_failure_log(
                e,
                context={"automation": "download_rfp", "company": target_company},
                graph_client=graph_client,
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

async def run_automation_submit(rfp_id: str, company: str | None = None):
    start_new_run()  # Generate new unique RUN_ID for this automation run
    log_event("SYSTEM", "StartRun", "Success", f"Submit RFP {rfp_id} started")
    target_company = _resolve_company(company)
    graph_client = GraphClient(
        CLIENT_ID, CLIENT_SECRET, TENANT_ID,
        SHAREPOINT_HOSTNAME, SITE_PATH, DRIVE_NAME
    )
    graph_client.auth()
    graph_client.resolve_site_and_drive()

    async with async_playwright() as p:
        try:
            open_rfps, page, browser = await common_flow(
                p,
                graph_client,
                profile_label=f"submit-{rfp_id}",
                company=target_company,
            )
            result = await submit_rfp(page, open_rfps, rfp_id, graph_client, target_company)
            print("result:-",result)
            
            # Extract RFP link from open_rfps data
            rfp_link = None
            for row in open_rfps:
                title = row.get("Title") or ""
                if rfp_ids_match(rfp_id, title):
                    rfp_link = row.get("Link") or ""
                    break
            
            if not result:
                trigger_email(rfp_id=rfp_id, email_flag="rfp_saved_draft", graph_client=graph_client, rfp_link=rfp_link)
            else:
                # Create error log file and attach it to the email
                from helpers.failure_logger import create_rfp_error_log_file
                error_log_info = create_rfp_error_log_file(
                    rfp_id=rfp_id,
                    context={
                        "automation": "submit_rfp",
                        "company": target_company,
                        "rfp_link": rfp_link,
                    },
                    graph_client=graph_client,
                )
                attachments = []
                if error_log_info.get("sharepoint_full_path"):
                    attachments.append({
                        "name": error_log_info.get("file_name", "error_log.json"),
                        "path": error_log_info.get("sharepoint_full_path"),
                    })
                trigger_email(
                    rfp_id=rfp_id,
                    email_flag="error_in_rfp_submission",
                    graph_client=graph_client,
                    rfp_link=rfp_link,
                    attachments=attachments
                )
            # await browser.close()
            return {"status": "success", "message": result}

        except Exception as e:
            log_event("SYSTEM", "SubmitError", "Fail", str(e))
            failure_info = record_failure_log(
                e,
                context={
                    "automation": "submit_rfp",
                    "company": target_company,
                    "rfp_id": rfp_id,
                },
                graph_client=graph_client,
            )
            _notify_failure_via_email("Submit RFP", failure_info, graph_client)
            raise HTTPException(status_code=500, detail=f"Submit failed: {str(e)}")
        finally:
            try:
                await browser.close()
            except Exception:
                pass
            log_event("SYSTEM", "EndRun", "Success", f"Submit {rfp_id} Finished")

async def run_automation_decline(rfp_id: str, company: str | None = None):
    start_new_run()  # Generate new unique RUN_ID for this automation run
    log_event("SYSTEM", "StartRun", "Success", f"Decline RFP {rfp_id} started")
    target_company = _resolve_company(company)
    graph_client = GraphClient(
        CLIENT_ID, CLIENT_SECRET, TENANT_ID,
        SHAREPOINT_HOSTNAME, SITE_PATH, DRIVE_NAME
    )
    graph_client.auth()
    graph_client.resolve_site_and_drive()

    async with async_playwright() as p:
        try:
            open_rfps, page, browser = await common_flow(
                p,
                graph_client,
                profile_label=f"decline-{rfp_id}",
                company=target_company,
            )
            result = await decline_rfps(page, open_rfps, target_company, rfp_id)
            if result:
                trigger_email(rfp_id=rfp_id,email_flag="rfp_decline",graph_client=graph_client)
            else:
                # Create error log file and attach it to the email
                from helpers.failure_logger import create_rfp_error_log_file
                error_log_info = create_rfp_error_log_file(
                    rfp_id=rfp_id,
                    context={
                        "automation": "decline_rfp",
                        "company": target_company,
                    },
                    graph_client=graph_client,
                )
                attachments = []
                if error_log_info.get("sharepoint_full_path"):
                    attachments.append({
                        "name": error_log_info.get("file_name", "error_log.json"),
                        "path": error_log_info.get("sharepoint_full_path"),
                    })
                trigger_email(
                    rfp_id=rfp_id,
                    email_flag="error_in_rfp_decline",
                    graph_client=graph_client,
                    attachments=attachments
                )
            return {"status": "success", "message": result}

        except Exception as e:
            log_event("SYSTEM", "DeclineError", "Fail", str(e))
            failure_info = record_failure_log(
                e,
                context={
                    "automation": "decline_rfp",
                    "company": target_company,
                    "rfp_id": rfp_id,
                },
                graph_client=graph_client,
            )
            _notify_failure_via_email("Decline RFP", failure_info, graph_client)
            raise HTTPException(status_code=500, detail=f"Decline failed: {str(e)}")
        finally:
            try:
                await browser.close()
            except Exception:
                pass
            log_event("SYSTEM", "EndRun", "Success", f"Decline {rfp_id} Finished")

async def run_automation_reminder():
    return send_rfp_deadline_reminders()


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
        rfp_id = r.get("RFP_ID") or _derive_rfp_id(title, link)
        desired_status = _desired_status_from_portal_row(r)
        enriched.append({
            **r,
            "RFP_ID": rfp_id,
            "_desired_status": desired_status
        })
    return enriched


def sync_participation_with_db(rfp_data: list[dict]) -> dict:
    """
    Compare scraped RFPs with DB; update 'participated' if mismatched.
    Matching logic:
      - Prefer exact RFP_ID match
      - Fallback: fuzzy match using title via rfp_ids_match(search_id, title)
    Returns summary dict.
    """
    log_event("SYNC", "Database", "Start", f"Starting sync with database for {len(rfp_data)} RFPs")
    db_rows = get_rfp_activity_data_from_db() or []
    log_event("SYNC", "Database", "Step", f"Retrieved {len(db_rows)} records from database")
    scraped = _build_scraped_index(rfp_data)

    # Build quick indices
    db_by_id = {}
    for row in db_rows:
        rid = (row.get("RFP_ID") or "").strip()
        if rid:
            db_by_id[rid] = row

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

        # Attempt exact ID match
        matched_db = db_by_id.get(s_id) if s_id else None

        # Fallback to fuzzy title-based matching if no exact match
        if not matched_db and s_id:
            # Look for any db row whose RFP_ID matches the title using existing helper
            for row in db_rows:
                db_id = (row.get("RFP_ID") or "").strip()
                if db_id and rfp_ids_match(db_id, s_title):
                    matched_db = row
                    break

        if not matched_db:
            not_found += 1
            details.append({"RFP_ID": s_id or "-", "Title": s_title, "result": "db_not_found"})
            continue

        current_status = (matched_db.get("participated") or "").strip().lower()
        if target_status and current_status != target_status:
            try:
                # Update only if there is a clear target
                record_id = s_id or matched_db.get("RFP_ID") or ""
                # Use "submit" category for sync operations (matches table structure)
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
async def run_automation_sync_portal():
    import json
    start_new_run()  # Generate new unique RUN_ID for this automation run
    log_event("SYSTEM", "StartRun", "Success", "Sync portal data started")
    
    graph_client = GraphClient(
        CLIENT_ID, CLIENT_SECRET, TENANT_ID,
        SHAREPOINT_HOSTNAME, SITE_PATH, DRIVE_NAME
    )
    log_event("SYNC", "Setup", "Step", "Initializing SharePoint client")
    graph_client.auth()
    graph_client.resolve_site_and_drive()
    log_event("SYNC", "Setup", "Success", "SharePoint client authenticated")

    async with async_playwright() as p:
        browser = None
        try:
            # Common flow to login and select Saudi Ariba company
            log_event("SYNC", "Login", "Start", "Starting login and company selection")
            open_rfps, page, browser = await common_flow(p, graph_client, profile_label="sync")
            log_event("SYNC", "Login", "Success", f"Logged in and selected company. Found {len(open_rfps)} open RFPs")

            # Export all RFPs visible for the selected company
            log_event("SYNC", "Export", "Start", "Starting RFP export from portal")
            exported_path = await export_rfps(page, "SaudiAriba")
            log_event("SYNC", "Export", "Success", f"Export completed. File saved at: {exported_path}")
            
            # Extract RFP data from exported file
            log_event("SYNC", "Extract", "Start", "Extracting RFP data from exported file")
            rfp_data = await extract_rfp_data(exported_path)
            log_event("SYNC", "Extract", "Success", f"Extracted {len(rfp_data)} RFPs from portal")
            
            # Compare against DB and update mismatches
            log_event("SYNC", "Database", "Start", "Starting database sync")
            sync_summary = sync_participation_with_db(rfp_data)
            log_event("SYNC", "Database", "Success", 
                     f"Database sync completed: {sync_summary.get('updated', 0)} updated, "
                     f"{sync_summary.get('checked', 0)} checked")
            
            # Save sync data to JSON file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            sync_data = {
                "sync_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "exported_file": exported_path,
                "total_rfps_extracted": len(rfp_data),
                "rfp_data": rfp_data,
                "sync_summary": sync_summary
            }
            
            json_filename = f"sync_data_{timestamp}.json"
            json_path = os.path.join(OUTPUT_DIR, json_filename) 
            
            try:
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(sync_data, f, indent=2, ensure_ascii=False)
                log_event("SYNC", "Save", "Success", f"Sync data saved to JSON: {json_filename}")
                print(f"✅ Sync data saved to: {json_path}")
                
                # Upload JSON to SharePoint
                try:
                    log_event("SYNC", "SharePoint", "Uploading", f"Uploading {json_filename} to SharePoint")
                    graph_client.sync_local_to_sharepoint(json_path, f"{SP_BASE_FOLDER}/Sync-Data")
                    log_event("SYNC", "SharePoint", "Success", f"JSON file uploaded to SharePoint: {json_filename}")
                except Exception as e:
                    log_event("SYNC", "SharePoint", "Fail", f"Failed to upload JSON to SharePoint: {str(e)}")
                    print(f"⚠ Could not upload JSON to SharePoint: {e}")
            except Exception as e:
                log_event("SYNC", "Save", "Fail", f"Failed to save sync data to JSON: {str(e)}")
                print(f"⚠ Could not save sync data to JSON: {e}")
            
            print("sync_summary:-", sync_summary)
            
            return {
                "status": "success", 
                "message": "Sync portal data completed",
                "summary": sync_summary,
                "json_file": json_filename
            }

        except HTTPException:
            raise
        except Exception as e:
            log_event("SYSTEM", "RunError", "Fail", f"Sync automation error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")
        finally:
            if browser:
                try:
                    await browser.close()
                    log_event("SYNC", "Cleanup", "Step", "Browser closed")
                except Exception:
                    pass
            log_event("SYSTEM", "EndRun", "Success", "Sync portal automation finished")


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


async def download_single_rfp_file(page, rfp_data, company_name, allrfps_base_folder):
    """Download a single RFP file to: ALLRFPs/CompanyName/RFPName/downloaded-rfp/rfpname.xls
    Returns: (status, error_reason, needs_relogin, file_path, owner_name, publish_time)
    """
    from helpers.core_helper import click_if_visible, clean_rfp_title
    from rfp.download_rfp import extract_rfp_details_inner_text
    
    title = rfp_data.get('Title', '').strip()
    link = rfp_data.get('Link', '').strip()
    
    if not link:
        return 'failed', "No link provided", False, None, None, None
    
    # Clean RFP title for folder/file naming
    clean_title = clean_rfp_title(title)
    safe_company_name = await sanitize_filename(company_name)
    
    # Create folder structure: ALLRFPs/CompanyName/RFPName/downloaded-rfp/
    rfp_folder = os.path.join(allrfps_base_folder, safe_company_name, clean_title)
    downloaded_rfp_folder = os.path.join(rfp_folder, "downloaded-rfp")
    os.makedirs(downloaded_rfp_folder, exist_ok=True)
    
    # Check if file already exists
    clean_name = re.sub(r'[^a-z0-9]', '', clean_title.lower())
    try:
        if os.path.exists(downloaded_rfp_folder):
            existing_files = os.listdir(downloaded_rfp_folder)
            already_exists = any(clean_name in re.sub(r'[^a-z0-9]', '', f.lower()) for f in existing_files)
            
            if already_exists:
                # Return existing file path (owner and publish time will be extracted from DB if needed)
                for f in existing_files:
                    if clean_name in re.sub(r'[^a-z0-9]', '', f.lower()):
                        existing_path = os.path.join(downloaded_rfp_folder, f)
                        return 'skipped', 'File already exists', False, existing_path, None, None
    except Exception as check_error:
        pass
    
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
        await asyncio.sleep(2)  # Give extra time for page to render
        
        # Extract RFP details (owner_name and publish_time) before clicking download buttons
        try:
            print(f"\n  {'='*60}")
            print(f"  🔍 DEBUG: Starting extraction for RFP: {title}")
            print(f"  🔍 DEBUG: Current URL: {new_page.url}")
            
            # Check if the page has the expected structure
            try:
                wide_labels_exists = await new_page.locator('div.wideLabels').count()
                table_exists = await new_page.locator('div.wideLabels table').count()
                td_count = await new_page.locator('div.wideLabels table td').count()
                print(f"  🔍 DEBUG: div.wideLabels exists: {wide_labels_exists > 0}")
                print(f"  🔍 DEBUG: div.wideLabels table exists: {table_exists > 0}")
                print(f"  🔍 DEBUG: Total table cells found: {td_count}")
                
                if td_count == 0:
                    # Try alternative selectors
                    alt_selectors = [
                        'table.wideLabels td',
                        'table td',
                        '.w-tbl-cell',
                        'div[class*="label"] table td'
                    ]
                    for selector in alt_selectors:
                        count = await new_page.locator(selector).count()
                        print(f"  🔍 DEBUG: Alternative selector '{selector}': {count} cells")
                        if count > 0:
                            break
            except Exception as debug_e:
                print(f"  ⚠️  DEBUG: Error checking page structure: {debug_e}")
            
            # Extract details
            rfp_details = await extract_rfp_details_inner_text(new_page)
            owner_name = rfp_details.get('owner')
            publish_time = rfp_details.get('publish_time')
            
            print(f"  🔍 DEBUG: Extraction result - owner: {owner_name}, publish_time: {publish_time}")
            
            if owner_name or publish_time:
                print(f"  ✅ SUCCESS - Extracted - Owner: {owner_name}, Publish Time: {publish_time}")
                log_event("ALL_RFPS", "ExtractDetails", "Success", 
                         f"Extracted owner: {owner_name}, publish_time: {publish_time} for {title}")
            else:
                print(f"  ⚠️  WARNING - Could not extract owner or publish time")
                print(f"  🔍 DEBUG: Full extraction result: {rfp_details}")
                
                # Try to get page HTML snippet for debugging
                try:
                    page_title = await new_page.title()
                    print(f"  🔍 DEBUG: Page title: {page_title}")
                    
                    # Get a sample of page content
                    body_text = await new_page.locator('body').inner_text()
                    if 'owner' in body_text.lower() or 'publish' in body_text.lower():
                        print(f"  🔍 DEBUG: Found 'owner' or 'publish' keywords in page text")
                        # Find the relevant section
                        lines = body_text.split('\n')
                        for i, line in enumerate(lines[:50]):  # Check first 50 lines
                            if 'owner' in line.lower() or 'publish' in line.lower():
                                print(f"  🔍 DEBUG: Line {i}: {line[:100]}")
                    else:
                        print(f"  🔍 DEBUG: 'owner' or 'publish' keywords NOT found in page text")
                except Exception as debug_e2:
                    print(f"  ⚠️  DEBUG: Could not get page content for debugging: {debug_e2}")
                
                log_event("ALL_RFPS", "ExtractDetails", "Warning", 
                         f"Could not extract owner or publish time for {title}. Check page structure.")
        except Exception as e:
            error_msg = f"Could not extract RFP details: {e}"
            print(f"  ❌ ERROR - {error_msg}")
            import traceback
            print(f"  🔍 DEBUG: Full traceback:\n{traceback.format_exc()}")
            log_event("ALL_RFPS", "ExtractDetails", "Fail", f"{error_msg} for {title}")
        
        print(f"  {'='*60}\n")
        
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
        # Ensure .xls extension
        if not suggested_name.endswith(('.xls', '.xlsx')):
            suggested_name = f"{clean_title}.xls"
        else:
            # Replace suggested name with clean title but keep extension
            ext = os.path.splitext(suggested_name)[1]
            suggested_name = f"{clean_title}{ext}"
        
        final_path = os.path.join(downloaded_rfp_folder, suggested_name)
        
        await download.save_as(final_path)
        
        if os.path.exists(final_path):
            status = 'success'
            error_reason = None
            file_path = final_path
        else:
            error_reason = "File not saved after download"
        
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
    from config.config import RFP_ACTIVITY_LOG_TABLE_API, RFP_ACTIVITY_LOG_TABLE_LOGICAL
    from helpers.core_helper import DATAVERSE
    from core.log_events import get_current_run_id
    
    try:
        rfp_id = rfp_data.get('RFP_ID') or rfp_data.get('Title', '')
        link = rfp_data.get('Link', '')
        end_date = rfp_data.get('RFP_End_Date') or rfp_data.get('End_Time', '')
        participated = rfp_data.get('Participated', '') or rfp_data.get('participated', '')
        
        # DEBUG: Print what we're about to store
        print(f"\n  📊 DEBUG: Storing RFP in database:")
        print(f"    RFP_ID: {rfp_id}")
        print(f"    Company: {company_name}")
        print(f"    Owner Name: {owner_name}")
        print(f"    Publish Time: {publish_time}")
        print(f"    End Date: {end_date}")
        print(f"    Participated: {participated}")
        
        # Check if RFP already exists
        existing_result = DATAVERSE.query_rows(
            RFP_ACTIVITY_LOG_TABLE_API,
            filter_expr=f"RFP_ID eq '{rfp_id}' and Company_Name eq '{company_name}'",
            top=1,
            table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL,
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
        
        # Only add RFP_End_Date if it has a valid value
        if end_date and end_date != '-':
            row_data["RFP_End_Date"] = end_date
        
        # Add owner_name if provided
        if owner_name:
            row_data["owner_name"] = owner_name
            print(f"    ✅ Adding owner_name to row_data: {owner_name}")
        else:
            print(f"    ⚠️  owner_name is None or empty, not adding to row_data")
        
        # Add publish_time if provided
        if publish_time:
            row_data["publish_time"] = publish_time
            print(f"    ✅ Adding publish_time to row_data: {publish_time}")
        else:
            print(f"    ⚠️  publish_time is None or empty, not adding to row_data")
        
        print(f"    📋 Final row_data keys: {list(row_data.keys())}")
        
        # Note: File_Path doesn't exist in the table, so we can't store it
        # The file path is already in the folder structure: ALLRFPs/CompanyName/RFPName/downloaded-rfp/
        
        if existing_result and "value" in existing_result and len(existing_result["value"]) > 0:
            # Update existing record
            existing_row = existing_result["value"][0]
            record_id = existing_row[f"{RFP_ACTIVITY_LOG_TABLE_LOGICAL}id"]
            
            # Only update if there are changes
            update_data = {}
            for key, value in row_data.items():
                if value and value != existing_row.get(key, ""):
                    update_data[key] = value
            
            if update_data:
                DATAVERSE.update_row(
                    RFP_ACTIVITY_LOG_TABLE_API,
                    record_id,
                    update_data,
                    table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL
                )
                log_event("ALL_RFPS", "Database", "Updated", f"Updated RFP {rfp_id} for {company_name}")
        else:
            # Insert new record
            DATAVERSE.insert_row(
                RFP_ACTIVITY_LOG_TABLE_API,
                row_data,
                table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL
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
    
    # Setup folders - store company-wise in ALLRFPs
    rfps_folder = os.path.join(os.path.dirname(__file__), "temp", "RFPs")
    allrfps_folder = OUTPUT_DIR  # Use OUTPUT_DIR directly (already set to ALLRFPs in config)
    os.makedirs(rfps_folder, exist_ok=True)
    os.makedirs(allrfps_folder, exist_ok=True)
    
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
            await page.goto(URL, wait_until="domcontentloaded")
            await page.fill('xpath=//*[@id="_boebpb"]/div[1]/input', USERNAME)
            await page.fill('#Password', PASSWORD)
            
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
                
                # Check if company file already exists
                exists, existing_file = await company_file_exists(company, rfps_folder)
                if exists:
                    print(f"  ⏩ SKIPPED - File already exists: {existing_file}")
                    company_summary["status"] = "skipped"
                    company_summary["exported_file"] = existing_file
                    summary["skipped"] += 1
                    summary["companies"].append(company_summary)
                    continue
                
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
                    
                    # Export RFPs (HTML/Excel)
                    exported_path = await export_rfps(page, company)
                    company_summary["exported_file"] = exported_path
                    
                    # Extract RFP data from exported file
                    rfp_data_list = await extract_rfp_data(exported_path)
                    company_summary["rfps_found"] = len(rfp_data_list)
                    
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
                            page, rfp_data, company, allrfps_folder
                        )
                        
                        # DEBUG: Print what we got from download
                        print(f"\n  📥 DEBUG: Download result for RFP: {rfp_data.get('Title', 'Unknown')}")
                        print(f"    Status: {status}")
                        print(f"    Owner Name: {owner_name}")
                        print(f"    Publish Time: {publish_time}")
                        print(f"    File Path: {file_path}")
                        
                        if status == 'success':
                            company_summary["rfps_downloaded"] += 1
                            summary["downloaded_rfps"] += 1
                            
                            # Store in database with correct file path, owner_name, and publish_time
                            print(f"  💾 DEBUG: Calling store_rfp_in_database with owner_name={owner_name}, publish_time={publish_time}")
                            store_rfp_in_database(rfp_data, company, file_path, owner_name, publish_time)
                        elif status == 'skipped':
                            company_summary["rfps_skipped"] += 1
                            summary["skipped_rfps"] += 1
                            # Still store in database if file exists (owner and publish time may be None for skipped files)
                            if file_path:
                                print(f"  💾 DEBUG: Calling store_rfp_in_database (skipped) with owner_name={owner_name}, publish_time={publish_time}")
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
            
            # Final summary
            print(f"\n{'='*70}")
            print(f"=== SUMMARY ===")
            print(f"{'='*70}")
            print(f"Total companies: {summary['total_companies']}")
            print(f"✅ Processed: {summary['processed']}")
            print(f"⏩ Skipped: {summary['skipped']}")
            print(f"❌ Failed: {summary['failed']}")
            print(f"📥 RFPs downloaded: {summary['downloaded_rfps']}")
            print(f"⏩ RFPs skipped: {summary['skipped_rfps']}")
            print(f"❌ RFPs failed: {summary['failed_rfps']}")
            print(f"{'='*70}\n")
            
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
            return {"status": "error", "message": error_msg}
        
        finally:
            await browser.close()