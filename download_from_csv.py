"""
Download RFPs from Portal — CSV-driven, Local Only
====================================================
Reads a CSV with RFP_ID and Company_Name.
Logs into the Ariba portal, scrapes each company's RFP list to find
the portal links automatically, then downloads only the RFPs listed in
the CSV that don't already exist locally.

No SharePoint. No Dataverse. Just local.

CSV Format (minimum required columns):
    RFP_ID,Company_Name
    Aramco_4202775785,Aramco e-Marketplace
    SEC_12345,Saudi Electricity Company

Usage:
    python download_from_csv.py --csv rfps.csv
    python download_from_csv.py --csv rfps.csv --username user@example.com --password MyPass
    python download_from_csv.py --csv rfps.csv --output "D:/CustomFolder"
    python download_from_csv.py --csv rfps.csv --headless

Credentials (priority order):
    1. --username / --password CLI flags
    2. BAHRA_SAP_USERNAME / BAHRA_SAP_PASSWORD env vars

Retry behaviour:
    - On any network / system error: waits 10 s then retries (up to 3 times)
    - On session expiry / logout: re-logs in automatically then continues
"""

import os
import re
import csv
import sys
import asyncio
import argparse
import traceback
from datetime import datetime

# ─────────────────────────────────────────────────────────────────────────────
# Report statuses  (used as values in the Status column of the CSV report)
# ─────────────────────────────────────────────────────────────────────────────
STATUS_DOWNLOADED       = "Downloaded"
STATUS_SKIPPED_EXISTS   = "Skipped - Already Exists"
STATUS_NOT_FOUND_PORTAL = "Not Found on Portal"
STATUS_PORTAL_ERROR     = "Portal Unavailable"
STATUS_DOWNLOAD_FAILED  = "Download Failed"


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

PORTAL_URL     = "https://service.ariba.com/Sourcing.aw/109582016/aw?awh=r&awssk=u9fNiSxN&dard=1#b0"
DEFAULT_OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ALLRFPs")

MAX_DOWNLOAD_ATTEMPTS = 3    # total attempts per RFP before giving up
RETRY_WAIT_SEC        = 10   # seconds to wait between error retries
LOGIN_MAX_RETRIES     = 3    # how many times to try re-logging in


# ─────────────────────────────────────────────────────────────────────────────
# Path helpers  (mirrors helpers/core_helper.py logic)
# ─────────────────────────────────────────────────────────────────────────────

def _sanitize(name: str) -> str:
    """Strip chars that are illegal in folder/file names."""
    return re.sub(r'[<>:"/\\|?*]', '_', name).strip().rstrip('.')


def _clean_id(rfp_id: str) -> str:
    """Normalise whitespace in an RFP ID (matches clean_rfp_title)."""
    return re.sub(r'\s+', ' ', rfp_id).strip()


def get_downloaded_rfp_folder(rfp_id: str, company_name: str, output_dir: str) -> str:
    """Return  <output_dir>/<Company>/<RFP_ID>/downloaded-rfp/"""
    return os.path.join(
        output_dir,
        _sanitize(company_name),
        _clean_id(rfp_id),
        "downloaded-rfp",
    )


def file_exists_locally(rfp_id: str, company_name: str, output_dir: str) -> tuple[bool, str | None]:
    """True if any .xls/.xlsx already lives in the downloaded-rfp folder."""
    folder = get_downloaded_rfp_folder(rfp_id, company_name, output_dir)
    if not os.path.isdir(folder):
        return False, None
    for f in os.listdir(folder):
        if f.lower().endswith(('.xls', '.xlsx')):
            return True, os.path.join(folder, f)
    return False, None


# ─────────────────────────────────────────────────────────────────────────────
# CSV loader
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_col(headers: list[str], target: str) -> str | None:
    """Case-insensitive column lookup."""
    for h in headers:
        if h.strip().lower().replace(" ", "_") == target.lower():
            return h
    return None


def load_csv(csv_path: str) -> list[dict]:
    """
    Return list of dicts: [{'rfp_id': ..., 'company_name': ...}, ...]
    Only RFP_ID and Company_Name columns are required.
    """
    if not os.path.isfile(csv_path):
        _die(f"CSV file not found: {csv_path}")

    rows: list[dict] = []
    with open(csv_path, newline='', encoding='utf-8-sig') as fh:
        reader = csv.DictReader(fh)
        headers = list(reader.fieldnames or [])

        col_id  = _resolve_col(headers, "rfp_id")
        col_co  = _resolve_col(headers, "company_name")

        if not col_id:
            _die(f"CSV must have a 'RFP_ID' column.  Found: {headers}")
        if not col_co:
            _die(f"CSV must have a 'Company_Name' column.  Found: {headers}")

        for lineno, row in enumerate(reader, start=2):
            rfp_id  = (row.get(col_id)  or "").strip()
            company = (row.get(col_co)  or "").strip()
            if not rfp_id or not company:
                print(f"  [WARN] Row {lineno}: missing rfp_id or company_name — skipped")
                continue
            rows.append({"rfp_id": rfp_id, "company_name": company})

    return rows


def group_by_company(rows: list[dict]) -> dict[str, list[str]]:
    """Return {company_name: [rfp_id, ...], ...}"""
    groups: dict[str, list[str]] = {}
    for r in rows:
        groups.setdefault(r['company_name'], []).append(r['rfp_id'])
    return groups


# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────

def _die(msg: str):
    print(f"[ERROR] {msg}")
    sys.exit(1)


def _log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


# ─────────────────────────────────────────────────────────────────────────────
# Portal session helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _wait_ready(page, timeout: int = 30000):
    """Best-effort wait for the page to settle."""
    try:
        await page.wait_for_load_state("networkidle", timeout=timeout)
    except Exception:
        pass
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=5000)
    except Exception:
        pass


async def is_logged_in(page) -> bool:
    """Return True if the current page looks like an authenticated portal page."""
    try:
        url = page.url.lower()
        if "login" in url or "signin" in url:
            return False
        # Presence of the username input means we are on the login page
        if await page.locator('xpath=//*[@id="_boebpb"]/div[1]/input').count() > 0:
            return False
        return True
    except Exception:
        return False


async def do_login(page, username: str, password: str) -> bool:
    """
    Navigate to the portal home and log in.
    Returns True on success, False otherwise.
    """
    for attempt in range(1, LOGIN_MAX_RETRIES + 1):
        try:
            _log(f"Login attempt {attempt}/{LOGIN_MAX_RETRIES} …")
            await page.goto(PORTAL_URL, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(2)

            # Username field
            user_input = page.locator('xpath=//*[@id="_boebpb"]/div[1]/input')
            if await user_input.count() == 0:
                user_input = page.locator('input[type="text"]').first
            await user_input.fill(username)

            # Password field
            await page.locator('#Password').fill(password)

            # Submit
            try:
                async with page.expect_navigation(wait_until="networkidle", timeout=60000):
                    await page.click('input[type="submit"]')
            except Exception:
                await page.click('input[type="submit"]')
                await _wait_ready(page, 60000)

            await asyncio.sleep(2)

            if await is_logged_in(page):
                _log("Logged in successfully.")
                return True

            _log(f"Login attempt {attempt} failed — still on login page.")

        except Exception as exc:
            _log(f"Login attempt {attempt} error: {exc}")
            if attempt < LOGIN_MAX_RETRIES:
                await asyncio.sleep(5)

    _log("All login attempts failed.")
    return False


async def ensure_logged_in(page, username: str, password: str) -> bool:
    """Re-login if the session has expired; return True if authenticated."""
    if await is_logged_in(page):
        return True
    _log("Session expired or logged out — re-logging in …")
    return await do_login(page, username, password)


# ─────────────────────────────────────────────────────────────────────────────
# Company navigation + RFP scraping
# ─────────────────────────────────────────────────────────────────────────────

async def navigate_to_company(page, company_name: str):
    """
    Click 'More…' then select the target company from the portal menu.
    After this call the company's RFP listing page is open.
    """
    _log(f"Navigating to company: {company_name}")

    # Click the "More…" / "More" link
    more_link = page.get_by_role("link", name=re.compile(r"^more(\.\.\.)?$", re.IGNORECASE)).first
    await more_link.click()

    # Wait for menu to appear
    menu = page.locator('div.awmenu:not(.is-dnone)').first
    try:
        await menu.wait_for(timeout=10000)
    except Exception:
        await more_link.click()
        await menu.wait_for(timeout=8000)

    # Click the company link
    company_item = page.locator("a.w-pmi-item:visible").filter(has_text=company_name).first
    await company_item.wait_for(state="attached", timeout=10000)

    try:
        await company_item.scroll_into_view_if_needed()
    except Exception:
        pass

    try:
        async with page.expect_navigation(wait_until="domcontentloaded", timeout=60000):
            await company_item.click(timeout=5000)
    except Exception:
        try:
            handle = await company_item.element_handle()
            if handle:
                await page.evaluate("el => el.click()", handle)
        except Exception:
            pass

    await _wait_ready(page)
    _log(f"Company '{company_name}' loaded.")


async def scrape_rfps_for_company(page, company_name: str) -> list[dict]:
    """
    Scrape the portal RFP list for a given company.
    Returns a list of dicts: [{Title, Link, ID, RFP_End_Date, Status}, ...]
    """
    _log(f"Scraping RFP list for: {company_name}")

    for attempt in range(1, 4):
        try:
            # Locate SupplierFrame
            await page.wait_for_selector("iframe", timeout=20000)
            frame = None
            for f in page.frames:
                if "SupplierFrame" in (f.name or "") or "SupplierFrame" in (f.url or ""):
                    frame = f
                    break
            if not frame:
                raise RuntimeError("SupplierFrame not found")

            # Click the "Open RFP" link
            await frame.wait_for_selector('a[id*="_03mdrd"]', timeout=20000)
            await frame.click('a[id*="_03mdrd"]')

            # Wait for RFP table rows
            await frame.wait_for_selector('#_swbzed tr.tableRow1', timeout=30000)

            rows_el = await frame.query_selector_all('#_swbzed tr.tableRow1')
            rfps = []
            for row_el in rows_el:
                cells = await row_el.query_selector_all('td')
                if not cells:
                    continue
                link_el = await cells[0].query_selector('a')
                link    = (await link_el.get_attribute("href") or "").strip() if link_el else ""
                title   = (await cells[1].inner_text()).strip() if len(cells) > 1 else ""
                rfp_id  = (await cells[3].inner_text()).strip() if len(cells) > 3 else ""
                end_dt  = (await cells[5].inner_text()).strip() if len(cells) > 5 else ""
                status  = (await cells[9].inner_text()).strip() if len(cells) > 9 else ""

                rfps.append({
                    "Title":       title,
                    "Link":        link,
                    "ID":          rfp_id,
                    "RFP_End_Date": end_dt,
                    "Status":      status,
                })

            _log(f"Found {len(rfps)} RFPs in portal for '{company_name}'.")
            return rfps

        except Exception as exc:
            _log(f"Scrape attempt {attempt} failed: {exc}")
            if attempt < 3:
                await asyncio.sleep(RETRY_WAIT_SEC)
                await page.reload()
                await _wait_ready(page)

    _log(f"Could not scrape RFPs for '{company_name}' after retries.")
    return []


def match_rfp_ids(csv_ids: list[str], portal_rfps: list[dict]) -> list[dict]:
    """
    Return the subset of portal_rfps whose Title matches one of the CSV RFP IDs.
    Matching is case-insensitive and strips extra whitespace.
    Also returns unmatched IDs for reporting.
    """
    csv_map = {_clean_id(i).lower(): _clean_id(i) for i in csv_ids}

    matched  : list[dict] = []
    matched_ids: set[str] = set()

    for rfp in portal_rfps:
        title_key = _clean_id(rfp.get("Title", "")).lower()
        if title_key in csv_map:
            matched.append(rfp)
            matched_ids.add(title_key)

    unmatched = [orig for key, orig in csv_map.items() if key not in matched_ids]
    return matched, unmatched


# ─────────────────────────────────────────────────────────────────────────────
# Single-RFP download
# ─────────────────────────────────────────────────────────────────────────────

async def _click_if_visible(page, selector: str, timeout: int = 3000) -> bool:
    try:
        loc = page.locator(selector)
        if await loc.count() > 0:
            await loc.first.wait_for(state="visible", timeout=timeout)
            await loc.first.click()
            return True
    except Exception:
        pass
    return False


async def _download_single(page, rfp: dict, company_name: str, output_dir: str) -> bool:
    """
    Open the RFP link in a new tab, click through the Ariba button sequence,
    download the file, and save it locally.
    Returns True on success.
    """
    title   = _clean_id(rfp.get("Title", ""))
    link    = (rfp.get("Link") or "").strip()

    if not link:
        _log(f"  [SKIP] No link available for RFP: {title}")
        return False

    save_dir  = get_downloaded_rfp_folder(title, company_name, output_dir)
    os.makedirs(save_dir, exist_ok=True)

    new_page = await page.context.new_page()
    try:
        _log(f"  Opening RFP page …")
        await new_page.goto(link, wait_until="domcontentloaded", timeout=60000)

        # Check for redirect to login (session drop mid-download)
        if "login" in new_page.url.lower() or "signin" in new_page.url.lower():
            _log("  Session expired mid-download (redirected to login).")
            await new_page.close()
            return None  # Signal: needs re-login

        # Step 1 — Review Event details tab
        clicked = await _click_if_visible(new_page, "#_c8_tuc", timeout=5000)
        if clicked:
            _log("  Clicked #_c8_tuc (Review Event details)")
        await asyncio.sleep(10)

        # Step 2 — Content / View tab
        old_url = new_page.url
        for _ in range(20):
            clicked = await _click_if_visible(new_page, "#_iiyvqc", timeout=2000)
            if clicked and new_page.url != old_url:
                _log("  Clicked #_iiyvqc (Content tab)")
                break
            await asyncio.sleep(0.5)

        # Step 3 — Wait for Download button
        btn = new_page.locator("#_gktadc")
        await btn.wait_for(state="visible", timeout=10000)
        await new_page.wait_for_function(
            """el => el && !el.disabled && el.offsetParent !== null
                   && (() => {
                       const r = el.getBoundingClientRect();
                       const e = document.elementFromPoint(r.left + r.width/2, r.top + r.height/2);
                       return e && (e === el || el.contains(e));
                   })()""",
            arg=await btn.element_handle(),
            timeout=10000,
        )
        _log("  Download button ready — triggering download …")

        # Step 4 — Trigger download
        async with new_page.expect_download(timeout=120000) as dl_info:
            await btn.click(no_wait_after=True)

        download  = await dl_info.value
        suggested = download.suggested_filename or f"{title}.xls"
        ext       = os.path.splitext(suggested)[1] or ".xls"
        dest_file = os.path.join(save_dir, f"{title}{ext}")

        await download.save_as(dest_file)
        size_kb = os.path.getsize(dest_file) / 1024
        _log(f"  [OK] Saved → {dest_file}  ({size_kb:.1f} KB)")
        return True

    except Exception as exc:
        _log(f"  Download error: {exc}")
        return False
    finally:
        try:
            await new_page.close()
        except Exception:
            pass


async def download_with_retry(
    page,
    rfp: dict,
    company_name: str,
    output_dir: str,
    username: str,
    password: str,
) -> bool:
    """
    Wrap _download_single with:
      - auto re-login on session expiry
      - 10-second wait + retry on any network/system error
    Returns True on success.
    """
    title = _clean_id(rfp.get("Title", ""))

    for attempt in range(1, MAX_DOWNLOAD_ATTEMPTS + 1):
        _log(f"  Attempt {attempt}/{MAX_DOWNLOAD_ATTEMPTS} for: {title}")

        # Always ensure we're logged in before each attempt
        logged_in = await ensure_logged_in(page, username, password)
        if not logged_in:
            _log("  Cannot log in — skipping this RFP.")
            return False

        result = await _download_single(page, rfp, company_name, output_dir)

        if result is True:
            return True

        if result is None:
            # Session dropped inside _download_single → re-login then retry
            _log("  Re-logging in after mid-download session drop …")
            ok = await do_login(page, username, password)
            if not ok:
                _log("  Re-login failed — skipping.")
                return False
            # Don't count this as a real attempt; next iteration will retry
            continue

        # result is False → a download error occurred
        if attempt < MAX_DOWNLOAD_ATTEMPTS:
            _log(f"  Waiting {RETRY_WAIT_SEC}s before retry …")
            await asyncio.sleep(RETRY_WAIT_SEC)

    _log(f"  [FAIL] Gave up after {MAX_DOWNLOAD_ATTEMPTS} attempts: {title}")
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Report writer
# ─────────────────────────────────────────────────────────────────────────────

def write_report_csv(report_rows: list[dict], output_dir: str, run_started_at: str) -> str:
    """
    Write a CSV report to <output_dir>/RFP_Download_Report_<timestamp>.csv.

    Report structure
    ────────────────
    Block 1 – Run Summary  (key/value pairs with blank separator)
    Block 2 – Per-RFP detail rows

    Per-RFP columns:
        RFP_ID | Company_Name | Status | Reason | Local_File | Processed_At

    Status values:
        Downloaded            – file successfully saved locally
        Skipped - Already Exists – file was already present before the run
        Not Found on Portal   – RFP ID was not in the portal list (after retries)
        Portal Unavailable    – company page could not be reached / scraped
        Download Failed       – found on portal but download errored out

    Returns the full path of the written report file.
    """
    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(output_dir, f"RFP_Download_Report_{timestamp}.csv")
    os.makedirs(output_dir, exist_ok=True)

    # ── Build summary counts ──────────────────────────────────────────────
    total          = len(report_rows)
    downloaded     = sum(1 for r in report_rows if r["Status"] == STATUS_DOWNLOADED)
    skipped        = sum(1 for r in report_rows if r["Status"] == STATUS_SKIPPED_EXISTS)
    not_on_portal  = sum(1 for r in report_rows if r["Status"] == STATUS_NOT_FOUND_PORTAL)
    portal_error   = sum(1 for r in report_rows if r["Status"] == STATUS_PORTAL_ERROR)
    failed         = sum(1 for r in report_rows if r["Status"] == STATUS_DOWNLOAD_FAILED)

    companies = sorted({r["Company_Name"] for r in report_rows})

    summary_block = [
        ["RFP Download Report"],
        ["Run Started",          run_started_at],
        ["Report Generated",     datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
        [""],
        ["── Summary ──────────────────────────"],
        ["Total RFPs in CSV",       total],
        ["Downloaded (new)",        downloaded],
        ["Skipped (already exist)", skipped],
        ["Not Found on Portal",     not_on_portal],
        ["Portal Unavailable",      portal_error],
        ["Download Failed",         failed],
        [""],
        ["── Companies processed ──────────────"],
    ]
    for co in companies:
        co_rows   = [r for r in report_rows if r["Company_Name"] == co]
        co_ok     = sum(1 for r in co_rows if r["Status"] == STATUS_DOWNLOADED)
        co_skip   = sum(1 for r in co_rows if r["Status"] == STATUS_SKIPPED_EXISTS)
        co_miss   = sum(1 for r in co_rows if r["Status"] in (STATUS_NOT_FOUND_PORTAL, STATUS_PORTAL_ERROR))
        co_fail   = sum(1 for r in co_rows if r["Status"] == STATUS_DOWNLOAD_FAILED)
        summary_block.append([
            co,
            f"total={len(co_rows)}",
            f"downloaded={co_ok}",
            f"skipped={co_skip}",
            f"not_found={co_miss}",
            f"failed={co_fail}",
        ])

    summary_block.append([""])
    summary_block.append(["── Detail ────────────────────────────"])
    summary_block.append([""])

    detail_header = ["RFP_ID", "Company_Name", "Status", "Reason", "Local_File", "Processed_At"]

    with open(report_path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)

        # Summary block
        for row in summary_block:
            writer.writerow(row)

        # Detail block
        writer.writerow(detail_header)
        for r in report_rows:
            writer.writerow([
                r.get("RFP_ID",       ""),
                r.get("Company_Name", ""),
                r.get("Status",       ""),
                r.get("Reason",       ""),
                r.get("Local_File",   ""),
                r.get("Processed_At", ""),
            ])

    return report_path


def _report_row(
    rfp_id: str,
    company_name: str,
    status: str,
    reason: str = "",
    local_file: str = "",
) -> dict:
    """Build a single report-row dict."""
    return {
        "RFP_ID":       rfp_id,
        "Company_Name": company_name,
        "Status":       status,
        "Reason":       reason,
        "Local_File":   local_file,
        "Processed_At": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Main runner
# ─────────────────────────────────────────────────────────────────────────────

async def run(csv_path: str, output_dir: str, username: str, password: str, headless: bool):
    from playwright.async_api import async_playwright

    run_started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = load_csv(csv_path)
    if not rows:
        _die("No valid rows in CSV.")

    os.makedirs(output_dir, exist_ok=True)
    company_groups = group_by_company(rows)

    print()
    print("=" * 65)
    print("  Portal RFP Downloader  —  CSV-driven, Local Only")
    print("=" * 65)
    print(f"  CSV file  : {csv_path}")
    print(f"  Output    : {output_dir}")
    print(f"  Total RFPs: {len(rows)}  across  {len(company_groups)} companies")
    print(f"  Headless  : {headless}")
    print("=" * 65)
    print()

    # ── report_rows accumulates one entry per RFP throughout the whole run ──
    report_rows: list[dict] = []

    # ── Pre-flight: which RFPs already exist locally? ──────────────────────
    to_process:  list[dict] = []
    pre_skipped: list[dict] = []
    for row in rows:
        exists, path = file_exists_locally(row['rfp_id'], row['company_name'], output_dir)
        if exists:
            _log(f"[SKIP] {row['rfp_id']} ({row['company_name']}) — exists: {path}")
            pre_skipped.append(row)
            report_rows.append(_report_row(
                rfp_id=row['rfp_id'],
                company_name=row['company_name'],
                status=STATUS_SKIPPED_EXISTS,
                reason="File already exists in local ALLRFPs folder",
                local_file=path or "",
            ))
        else:
            to_process.append(row)

    print()
    _log(f"Pre-flight: {len(pre_skipped)} already exist, {len(to_process)} to download.")
    print()

    if not to_process:
        _log("Nothing to download — all files already exist locally.")
        report_path = write_report_csv(report_rows, output_dir, run_started_at)
        _log(f"Report saved → {report_path}")
        return

    stats = {
        "downloaded":  0,
        "failed":      0,
        "skipped_pre": len(pre_skipped),
        "no_match":    0,
        "portal_err":  0,
    }

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=headless,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        context = await browser.new_context(accept_downloads=True, viewport={"width": 1280, "height": 1024})
        page    = await context.new_page()

        # ── Initial login ──────────────────────────────────────────────────
        _log("Logging in to portal …")
        if not await do_login(page, username, password):
            await browser.close()
            _die("Initial login failed. Check your credentials.")

        # ── Process each company ───────────────────────────────────────────
        for company_name, csv_ids in company_groups.items():

            # Only work on IDs that aren't already downloaded
            pending_ids = [
                rid for rid in csv_ids
                if not file_exists_locally(rid, company_name, output_dir)[0]
            ]
            if not pending_ids:
                _log(f"[{company_name}] All RFPs already downloaded — skipping company.")
                continue

            print()
            print(f"  {'─'*60}")
            _log(f"Company: {company_name}  ({len(pending_ids)} RFP(s) to download)")
            print(f"  {'─'*60}")

            # ── Ensure session before navigating ──────────────────────────
            if not await ensure_logged_in(page, username, password):
                _log(f"Cannot log in — skipping all {len(pending_ids)} RFP(s) for '{company_name}'.")
                for rid in pending_ids:
                    report_rows.append(_report_row(
                        rfp_id=rid, company_name=company_name,
                        status=STATUS_PORTAL_ERROR,
                        reason="Could not log in to portal before processing this company",
                    ))
                stats["portal_err"] += len(pending_ids)
                continue

            # ── Navigate to company & scrape RFP list ─────────────────────
            nav_ok = False
            for nav_attempt in range(1, 3):   # 2 navigation attempts
                try:
                    await navigate_to_company(page, company_name)
                    nav_ok = True
                    break
                except Exception as exc:
                    _log(f"Navigation attempt {nav_attempt} failed: {exc}")
                    if nav_attempt < 2:
                        _log(f"Waiting {RETRY_WAIT_SEC}s and retrying …")
                        await asyncio.sleep(RETRY_WAIT_SEC)
                        await ensure_logged_in(page, username, password)

            if not nav_ok:
                _log(f"Could not navigate to '{company_name}' — skipping company.")
                for rid in pending_ids:
                    report_rows.append(_report_row(
                        rfp_id=rid, company_name=company_name,
                        status=STATUS_PORTAL_ERROR,
                        reason="Company page could not be reached on portal after 2 attempts",
                    ))
                stats["portal_err"] += len(pending_ids)
                continue

            portal_rfps = await scrape_rfps_for_company(page, company_name)

            if not portal_rfps:
                _log(f"No RFPs found on portal for '{company_name}' after retries — skipping.")
                for rid in pending_ids:
                    report_rows.append(_report_row(
                        rfp_id=rid, company_name=company_name,
                        status=STATUS_PORTAL_ERROR,
                        reason="Portal returned no RFP list for this company after 2 scrape attempts",
                    ))
                stats["portal_err"] += len(pending_ids)
                continue

            # ── Match CSV IDs against portal data ─────────────────────────
            matched_rfps, unmatched_ids = match_rfp_ids(pending_ids, portal_rfps)

            # Record not-found-on-portal RFPs
            if unmatched_ids:
                _log(f"[WARN] {len(unmatched_ids)} CSV ID(s) not found in portal list for '{company_name}':")
                for uid in unmatched_ids:
                    _log(f"       - {uid}")
                    report_rows.append(_report_row(
                        rfp_id=uid, company_name=company_name,
                        status=STATUS_NOT_FOUND_PORTAL,
                        reason=(
                            "RFP ID was not found in the portal's RFP list after scraping "
                            f"({len(portal_rfps)} RFPs visible on portal). "
                            "The RFP may be closed, expired, or the ID may differ from the portal title."
                        ),
                    ))
                stats["no_match"] += len(unmatched_ids)

            _log(f"Matched {len(matched_rfps)} RFP(s) on portal — starting downloads …")

            # ── Download each matched RFP ─────────────────────────────────
            for idx, rfp in enumerate(matched_rfps, start=1):
                title = _clean_id(rfp.get("Title", ""))
                print()
                _log(f"[{idx}/{len(matched_rfps)}]  {title}  |  {company_name}")

                # Final local-existence guard
                exists, path = file_exists_locally(title, company_name, output_dir)
                if exists:
                    _log(f"  [SKIP] Already exists: {path}")
                    report_rows.append(_report_row(
                        rfp_id=title, company_name=company_name,
                        status=STATUS_SKIPPED_EXISTS,
                        reason="File appeared locally during run (added by another process or previous attempt)",
                        local_file=path or "",
                    ))
                    continue

                success = await download_with_retry(
                    page, rfp, company_name, output_dir, username, password
                )

                if success:
                    _, saved_path = file_exists_locally(title, company_name, output_dir)
                    report_rows.append(_report_row(
                        rfp_id=title, company_name=company_name,
                        status=STATUS_DOWNLOADED,
                        reason="",
                        local_file=saved_path or "",
                    ))
                    stats["downloaded"] += 1
                else:
                    report_rows.append(_report_row(
                        rfp_id=title, company_name=company_name,
                        status=STATUS_DOWNLOAD_FAILED,
                        reason=(
                            f"Download failed after {MAX_DOWNLOAD_ATTEMPTS} attempts. "
                            "Possible causes: no Excel file on portal, download button unavailable, "
                            "network timeout, or session could not be recovered."
                        ),
                    ))
                    stats["failed"] += 1

        await browser.close()

    # ── Final summary (console) ────────────────────────────────────────────
    total_no_file = stats["no_match"] + stats["portal_err"]
    print()
    print("=" * 65)
    print("  Download Run Complete")
    print("=" * 65)
    print(f"  Total RFPs in CSV         : {len(rows)}")
    print(f"  Skipped (already existed) : {stats['skipped_pre']}")
    print(f"  Not found on portal       : {stats['no_match']}")
    print(f"  Portal unavailable        : {stats['portal_err']}")
    print(f"  Download failed           : {stats['failed']}")
    print(f"  Downloaded (new)          : {stats['downloaded']}")
    print("=" * 65)
    print(f"  Files saved to: {output_dir}")

    # ── Write report CSV ───────────────────────────────────────────────────
    report_path = write_report_csv(report_rows, output_dir, run_started_at)
    print()
    print(f"  Report CSV → {report_path}")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Download RFPs from Ariba portal using a CSV file (no SharePoint, no Dataverse)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
CSV must have at minimum: RFP_ID, Company_Name
No 'Link' column needed — links are scraped from the portal automatically.

Examples:
  python download_from_csv.py --csv my_rfps.csv
  python download_from_csv.py --csv my_rfps.csv --headless
  python download_from_csv.py --csv my_rfps.csv --username me@co.com --password secret
        """,
    )
    parser.add_argument("--csv",      required=True, help="Path to the input CSV file")
    parser.add_argument("--output",   default=DEFAULT_OUTPUT, help=f"Local ALLRFPs folder (default: {DEFAULT_OUTPUT})")
    parser.add_argument("--username", default=None, help="Portal username (or set BAHRA_SAP_USERNAME)")
    parser.add_argument("--password", default=None, help="Portal password (or set BAHRA_SAP_PASSWORD)")
    parser.add_argument("--headless", action="store_true", default=False, help="Run browser in headless mode")

    args = parser.parse_args()

    username = args.username or os.getenv("BAHRA_SAP_USERNAME", "").strip()
    password = args.password or os.getenv("BAHRA_SAP_PASSWORD", "").strip()

    if not username or not password:
        _die(
            "Credentials required.\n"
            "  Use --username / --password  or  set environment variables:\n"
            "    BAHRA_SAP_USERNAME=...\n"
            "    BAHRA_SAP_PASSWORD=..."
        )

    asyncio.run(run(
        csv_path=args.csv,
        output_dir=args.output,
        username=username,
        password=password,
        headless=args.headless,
    ))


if __name__ == "__main__":
    main()
