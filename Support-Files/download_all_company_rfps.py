"""
Download ALL RFPs for a Company (or All Companies) — Standalone, Local Only
===========================================================================

End-to-end pipeline:
  1. Log in to the Ariba portal
  2. Navigate to the target company
  3. Expand all status groups (Open, Completed, Pending Selection, ...)
  4. Click the portal's "Export all Rows" button -> download master Excel listing
  5. Parse the listing
  6. Download each individual RFP one-by-one to a local folder

No SharePoint. No Dataverse. No FastAPI. Just local files.

This script is a standalone counterpart to the web UI's
"Download Historical Data" dialog (see automation_logic.run_automation_download_all_rfps).
The two share the same Playwright selectors and flow, but this script writes
everything locally and is safe to run from the command line.

Usage:
    # Single company
    python download_all_company_rfps.py --company "Saudi Energy"

    # All companies from config.COMPANY_OPTIONS
    python download_all_company_rfps.py

    # Headless + custom output
    python download_all_company_rfps.py --company "Aramco e-Marketplace" --headless --output "D:/RFPs"

Credentials (priority order):
    1. --username / --password CLI flags
    2. BAHRA_SAP_USERNAME / BAHRA_SAP_PASSWORD env vars

Output layout:
    <output>/
    +-- <Company>/
    |   +-- _master_listing/
    |   |   +-- All-RFPs_<timestamp>.<ext>      (the exported master Excel)
    |   +-- <RFP_Title>/
    |       +-- downloaded-rfp/
    |           +-- <RFP_Title>.xls             (individual RFP file)
    +-- RFP_Download_Report_<timestamp>.csv     (per-RFP run report)
"""

import os
import re
import csv
import sys
import asyncio
import argparse
from datetime import datetime

# Allow importing config.config (and the rest of the project) from the parent directory.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from config.config import URL as PORTAL_URL, COMPANY_OPTIONS  # noqa: E402

# ---------------------------------------------------------------------------
# Optional integrations — Dataverse persistence, run logging, owner/publish
# extraction. These mirror what automation_logic.download_single_rfp_file does
# in the web flow. If any import fails (e.g. environment can't reach
# Dataverse), we degrade gracefully and just write files locally.
# ---------------------------------------------------------------------------
_INTEGRATIONS_OK = True
_INTEGRATION_ERR: str | None = None
try:
    # Pre-load leaf modules first to defuse a circular import in services/__init__.py:
    #   helpers.core_helper -> core.common_imports -> config.runtime_config
    #     -> helpers.credentials_provider -> services.system_settings_service
    #     -> services/__init__.py -> services.dashboard_service -> helpers.core_helper (partial!)
    # Importing dataverse_helper + system_settings_service directly first makes
    # them available before the cycle has a chance to form.
    from helpers.dataverse_helper import DataverseClient  # noqa: E402, F401
    from services.system_settings_service import get_setting  # noqa: E402

    from rfp.download_rfp import extract_rfp_details_inner_text  # noqa: E402
    from core.log_events import (  # noqa: E402
        log_event,
        start_new_run,
        get_current_run_id,
        normalize_date_format,
    )
    from helpers.core_helper import DATAVERSE, sanitize_filter_value  # noqa: E402
except Exception as _exc:  # pragma: no cover — env-dependent
    _INTEGRATIONS_OK = False
    _INTEGRATION_ERR = str(_exc)

    # Stub fallbacks so the rest of the script can run without integrations.
    async def extract_rfp_details_inner_text(page):  # type: ignore
        return {"owner": None, "publish_time": None}

    def log_event(*_a, **_kw):  # type: ignore
        pass

    def start_new_run():  # type: ignore
        return None

    def get_current_run_id():  # type: ignore
        return None

    def normalize_date_format(val):  # type: ignore
        return str(val).strip() if val else ""

    def sanitize_filter_value(val: str) -> str:  # type: ignore
        return (val or "").replace("'", "''")

    DATAVERSE = None  # type: ignore

    def get_setting(key: str, default=None):  # type: ignore
        return default


# ---------------------------------------------------------------------------
# Report statuses
# ---------------------------------------------------------------------------
STATUS_DOWNLOADED       = "Downloaded"
STATUS_SKIPPED_EXISTS   = "Skipped - Already Exists"
STATUS_NOT_FOUND_PORTAL = "Not Found on Portal"
STATUS_PORTAL_ERROR     = "Portal Unavailable"
STATUS_DOWNLOAD_FAILED  = "Download Failed"


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_OUTPUT        = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ALLRFPs")
MAX_DOWNLOAD_ATTEMPTS = 1     # attempts per RFP before giving up
RETRY_WAIT_SEC        = 10    # wait between download retries
LOGIN_MAX_RETRIES     = 3     # how many times to try logging in
MASTER_EXPORT_TIMEOUT = 180000  # ms — the listing export can be slow


# ---------------------------------------------------------------------------
# Logging / utility
# ---------------------------------------------------------------------------
def _log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def _die(msg: str):
    print(f"[ERROR] {msg}")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------
def _sanitize(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', '_', name).strip().rstrip('.')


def _clean_id(rfp_id: str) -> str:
    return re.sub(r'\s+', ' ', rfp_id).strip()


def get_downloaded_rfp_folder(rfp_id: str, company_name: str, output_dir: str) -> str:
    return os.path.join(
        output_dir,
        _sanitize(company_name),
        _clean_id(rfp_id),
        "downloaded-rfp",
    )


def get_master_listing_folder(company_name: str, output_dir: str) -> str:
    return os.path.join(output_dir, _sanitize(company_name), "_master_listing")


def file_exists_locally(rfp_id: str, company_name: str, output_dir: str):
    folder = get_downloaded_rfp_folder(rfp_id, company_name, output_dir)
    if not os.path.isdir(folder):
        return False, None
    for f in os.listdir(folder):
        if f.lower().endswith(('.xls', '.xlsx')):
            return True, os.path.join(folder, f)
    return False, None


# ---------------------------------------------------------------------------
# Dataverse helpers (ported from automation_logic.store_rfp_in_database)
# All Dataverse operations are best-effort: a failure here NEVER stops the
# download loop — we just print a warning and move on.
# ---------------------------------------------------------------------------
def _rfp_activity_api() -> str:
    return get_setting("RFP_ACTIVITY_LOG_TABLE_API", "cr673_bahra_rfps_v2s")


def _rfp_activity_logical() -> str:
    return get_setting("RFP_ACTIVITY_LOG_TABLE_LOGICAL", "cr673_bahra_rfps_v2")


def check_rfp_exists_in_dataverse(rfp_id: str, company_name: str) -> bool:
    """True if an RFP row with this RFP_ID + Company_Name already exists."""
    if DATAVERSE is None:
        return False
    try:
        result = DATAVERSE.query_rows(
            _rfp_activity_api(),
            filter_expr=(
                f"RFP_ID eq '{sanitize_filter_value(rfp_id)}' "
                f"and Company_Name eq '{sanitize_filter_value(company_name)}'"
            ),
            top=1,
            table_logical_name=_rfp_activity_logical(),
            use_display_names=True,
        )
        return bool(result and result.get("value"))
    except Exception as exc:
        _log(f"  [WARN] Dataverse existence check failed (will proceed): {exc}")
        return False


def store_rfp_in_database(rfp_data: dict, company_name: str,
                          owner_name: str | None = None,
                          publish_time: str | None = None) -> bool:
    """Insert or update the RFP row in the Dataverse activity log table.

    Mirrors automation_logic.store_rfp_in_database. Returns True on success.
    """
    if DATAVERSE is None:
        return False

    api = _rfp_activity_api()
    logical = _rfp_activity_logical()

    try:
        rfp_id = rfp_data.get("RFP_ID") or rfp_data.get("Title", "")
        link = rfp_data.get("Link", "") or ""
        end_date = rfp_data.get("RFP_End_Date") or rfp_data.get("End_Time", "")
        participated = (rfp_data.get("Participated", "")
                        or rfp_data.get("participated", "")) or ""

        existing = DATAVERSE.query_rows(
            api,
            filter_expr=(
                f"RFP_ID eq '{sanitize_filter_value(rfp_id)}' "
                f"and Company_Name eq '{sanitize_filter_value(company_name)}'"
            ),
            top=1,
            table_logical_name=logical,
            use_display_names=True,
        )

        row = {
            "RFP_ID":        rfp_id,
            "Company_Name":  company_name,
            "Link":          link,
            "participated":  participated.lower() if participated else "",
            "Downloaded_At": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "RunID":         get_current_run_id() or "",
        }
        if end_date and end_date != "-":
            row["RFP_End_Date"] = normalize_date_format(end_date)
        if owner_name:
            row["owner_name"] = owner_name
        if publish_time:
            row["publish_time"] = publish_time

        if existing and existing.get("value"):
            existing_row = existing["value"][0]
            record_id = existing_row[f"{logical}id"]
            update_data = {k: v for k, v in row.items()
                           if v and v != existing_row.get(k, "")}
            if update_data:
                DATAVERSE.update_row(api, record_id, update_data,
                                     table_logical_name=logical)
                log_event("ALL_RFPS", "Database", "Updated",
                          f"Updated RFP {rfp_id} for {company_name}",
                          rfp_id=rfp_id)
        else:
            DATAVERSE.insert_row(api, row, table_logical_name=logical)
            log_event("ALL_RFPS", "Database", "Inserted",
                      f"Inserted RFP {rfp_id} for {company_name}",
                      rfp_id=rfp_id)
        return True
    except Exception as exc:
        log_event("ALL_RFPS", "Database", "Fail",
                  f"Failed to store RFP in database: {exc}")
        _log(f"  [WARN] Dataverse write failed: {exc}")
        return False


# ---------------------------------------------------------------------------
# Playwright session helpers (login / logged-in detection)
# ---------------------------------------------------------------------------
async def _wait_ready(page, timeout: int = 30000):
    try:
        await page.wait_for_load_state("networkidle", timeout=timeout)
    except Exception:
        pass
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=5000)
    except Exception:
        pass


async def _page_has_login_form(page) -> bool:
    LOGIN_SELECTORS = [
        'xpath=//*[@id="_boebpb"]/div[1]/input',
        'input[name="UserName"]',
        'input[id="UserName"]',
        '#UserName',
        'input[name="username"]',
        'input[type="password"]',
    ]
    for sel in LOGIN_SELECTORS:
        try:
            if await page.locator(sel).count() > 0:
                return True
        except Exception:
            pass
    return False


async def is_logged_in(page) -> bool:
    try:
        url = page.url.lower()
        if any(kw in url for kw in ("login", "signin", "logon", "sso", "auth?")):
            return False
        if await _page_has_login_form(page):
            return False
        return True
    except Exception:
        return False


async def do_login(page, username: str, password: str) -> bool:
    USER_SELECTORS = [
        'xpath=//*[@id="_boebpb"]/div[1]/input',
        '#UserName',
        'input[name="UserName"]',
        'input[id="UserName"]',
        'input[type="email"]',
        'input[type="text"]',
    ]
    PASS_SELECTORS = [
        '#Password',
        'input[name="Password"]',
        'input[id="Password"]',
        'input[type="password"]',
    ]
    SUBMIT_SELECTORS = [
        'input[type="submit"]',
        'button[type="submit"]',
        '#loginButton',
        'button:has-text("Log in")',
        'button:has-text("Sign in")',
    ]

    for attempt in range(1, LOGIN_MAX_RETRIES + 1):
        try:
            _log(f"Login attempt {attempt}/{LOGIN_MAX_RETRIES} ...")
            await page.goto(PORTAL_URL, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(3)
            await _wait_ready(page, 30000)

            if await is_logged_in(page):
                _log("Already authenticated after navigation.")
                return True

            user_loc = None
            for sel in USER_SELECTORS:
                loc = page.locator(sel)
                if await loc.count() > 0:
                    user_loc = loc.first
                    break
            if user_loc is None:
                _log(f"  Attempt {attempt}: username field not found - retrying.")
                await asyncio.sleep(5)
                continue
            await user_loc.click()
            await user_loc.fill(username)

            pass_loc = None
            for sel in PASS_SELECTORS:
                loc = page.locator(sel)
                if await loc.count() > 0:
                    pass_loc = loc.first
                    break
            if pass_loc is None:
                _log(f"  Attempt {attempt}: password field not found - retrying.")
                await asyncio.sleep(5)
                continue
            await pass_loc.click()
            await pass_loc.fill(password)

            submitted = False
            for sel in SUBMIT_SELECTORS:
                loc = page.locator(sel)
                if await loc.count() > 0:
                    try:
                        async with page.expect_navigation(wait_until="networkidle", timeout=60000):
                            await loc.first.click()
                    except Exception:
                        await loc.first.click()
                        await _wait_ready(page, 60000)
                    submitted = True
                    break
            if not submitted:
                _log(f"  Attempt {attempt}: submit button not found - retrying.")
                await asyncio.sleep(5)
                continue

            await asyncio.sleep(3)
            if await is_logged_in(page):
                _log("Logged in successfully.")
                return True
            _log(f"  Attempt {attempt}: still on login page after submit.")
            await asyncio.sleep(5)

        except Exception as exc:
            _log(f"  Login attempt {attempt} error: {exc}")
            if attempt < LOGIN_MAX_RETRIES:
                await asyncio.sleep(5)

    _log("All login attempts failed.")
    return False


async def ensure_logged_in(page, username: str, password: str) -> bool:
    if await is_logged_in(page):
        return True
    _log("Session expired or logged out - re-logging in ...")
    return await do_login(page, username, password)


# ---------------------------------------------------------------------------
# Company navigation
# ---------------------------------------------------------------------------
async def navigate_to_company(page, company_name: str):
    _log(f"Navigating to company: {company_name}")

    more_link = page.get_by_role("link", name=re.compile(r"^more(\.\.\.)?$", re.IGNORECASE)).first
    await more_link.click()

    menu = page.locator('div.awmenu:not(.is-dnone)').first
    try:
        await menu.wait_for(timeout=10000)
    except Exception:
        await more_link.click()
        await menu.wait_for(timeout=8000)

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


# ---------------------------------------------------------------------------
# Master listing export (expand all rows + click "Export all Rows")
# Ported from automation_logic.export_rfps.
# ---------------------------------------------------------------------------
def _detect_file_type(file_path: str) -> str:
    """Detect actual file type by reading the file header."""
    try:
        with open(file_path, 'rb') as f:
            header = f.read(8)
        if header[:4] == b'\xD0\xCF\x11\xE0':
            return '.xls'
        if header[:4] == b'PK\x03\x04' or header[:2] == b'PK':
            return '.xlsx'
        if header[:5] == b'<?xml':
            return '.xml'
        lower = header.lower()
        if b'<html' in lower or b'<table' in lower:
            return '.html'
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                first_line = f.readline()
            if ',' in first_line or '\t' in first_line:
                return '.csv'
        except Exception:
            pass
        return '.xlsx'
    except Exception as e:
        _log(f"  Warning: file-type detection failed: {e}")
        return '.xlsx'


async def export_master_listing(page, company_name: str, output_dir: str) -> str:
    """
    Open the table-options menu, click "Expand All Rows", then click
    "Export all Rows" and save the downloaded master listing locally.

    Returns the absolute path of the saved master file.
    """
    _log(f"Exporting master RFP listing for: {company_name}")
    await _wait_ready(page)

    # Find the SupplierFrame iframe (some Ariba layouts host the table there)
    frame = None
    for f in page.frames:
        if "SupplierFrame" in (f.name or "") or "SupplierFrame" in (f.url or ""):
            frame = f
            break
    ctx = frame if frame else page
    _log(f"  Using {'SupplierFrame' if frame else 'main page'} for export")

    # Wait for the table-options gear
    await ctx.wait_for_selector('#_lf_t\\$b > div.w-tbl-customize-view', state='visible', timeout=20000)

    # ----- Step 1: open menu and click "Expand All Rows" -----
    _log("  Opening table options menu ...")
    await ctx.hover('#_lf_t\\$b > div.w-tbl-customize-view')
    await ctx.click('#_lf_t\\$b > div.w-tbl-customize-view', force=True)

    await ctx.wait_for_selector('#_lcbzrc', state='visible', timeout=15000)
    _log("  Clicking 'Expand All Rows' ...")
    await ctx.click('#_lcbzrc', force=True)

    # Wait for the table to settle after expansion
    await page.wait_for_load_state("networkidle", timeout=60000)
    try:
        await ctx.wait_for_selector(
            '.loading, .spinner, [aria-busy="true"], .w-loading',
            state='hidden',
            timeout=10000,
        )
    except Exception:
        pass
    try:
        await ctx.wait_for_selector('table tbody tr, .w-tbl-row', state='attached', timeout=10000)
    except Exception:
        pass
    _log("  Table expanded - all rows loaded")

    # ----- Step 2: re-open menu, click "Export all Rows" -----
    _log("  Opening export menu ...")
    await page.wait_for_load_state("networkidle", timeout=30000)
    await ctx.wait_for_selector('#_lf_t\\$b > div.w-tbl-customize-view', state='visible', timeout=20000)
    await ctx.hover('#_lf_t\\$b > div.w-tbl-customize-view')
    await ctx.click('#_lf_t\\$b > div.w-tbl-customize-view', force=True)

    try:
        await ctx.wait_for_selector('div.awmenu:not(.is-dnone)', state='visible', timeout=10000)
    except Exception:
        pass
    await ctx.wait_for_selector('#_c\\$r36b', state='attached', timeout=15000)

    # Ensure the "Export all Rows" anchor is actually visible before clicking
    try:
        await ctx.evaluate(
            """
            async () => {
                const maxWait = 15000, start = Date.now();
                const findVisible = () =>
                    Array.from(document.querySelectorAll('a.w-pmi-item'))
                        .find(a => a.textContent.trim() === 'Export all Rows'
                                && a.offsetParent
                                && getComputedStyle(a).visibility !== 'hidden');
                let btn;
                while (Date.now() - start < maxWait) {
                    btn = findVisible();
                    if (btn) { btn.click(); return; }
                    await new Promise(r => setTimeout(r, 100));
                }
                throw new Error('Export menuitem not visible');
            }
            """
        )
    except Exception as e:
        _log(f"  Warning while locating Export menu item: {e}")

    # ----- Step 3: trigger download via synthesized mouse events -----
    _log("  Starting master-listing download ...")
    async with page.expect_download(timeout=MASTER_EXPORT_TIMEOUT) as dl_info:
        await ctx.evaluate(
            """
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
            """
        )
    download = await dl_info.value
    _log("  Master-listing download started.")

    # Save to the company's _master_listing folder with the correct extension
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    master_folder = get_master_listing_folder(company_name, output_dir)
    os.makedirs(master_folder, exist_ok=True)

    raw_path = os.path.join(master_folder, f"_temp_{timestamp}.download")
    await download.save_as(raw_path)

    real_ext = _detect_file_type(raw_path)
    final_path = os.path.join(master_folder, f"All-RFPs_{timestamp}{real_ext}")
    os.rename(raw_path, final_path)

    size_kb = os.path.getsize(final_path) / 1024
    _log(f"  Master listing saved -> {final_path}  ({size_kb:.1f} KB)")
    return final_path


# ---------------------------------------------------------------------------
# Parse the master listing (HTML / xls / xlsx / xml / csv)
# Ported from automation_logic.extract_rfp_data with non-HTML fallbacks.
# ---------------------------------------------------------------------------
def _normalize_participated(val: str) -> str:
    v = (val or "").strip().lower()
    if v in ("no", "not participated", "open"):
        return "no"
    if v in ("yes", "submitted", "participated"):
        return "submitted"
    if v in ("declined", "no bid"):
        return "declined"
    return v or ""


def _parse_html_listing(path: str) -> list[dict]:
    """Parse an HTML/XML/XLS-as-HTML export. Mirrors automation_logic.extract_rfp_data."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        _die("BeautifulSoup not installed. Run: pip install beautifulsoup4")

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        html = f.read()
    soup = BeautifulSoup(html, "html.parser")

    header_tr = None
    for tr in soup.find_all("tr"):
        if tr.find("th", recursive=False):
            header_tr = tr
            break
    if not header_tr:
        return []

    def norm(s: str) -> str:
        return re.sub(r"\s+", " ", (s or "").strip()).lower()

    header_cells = header_tr.find_all("th", recursive=False)
    header_col_count = len(header_cells)
    header_texts = [norm(th.get_text(strip=True)) for th in header_cells]

    col_map: dict[str, int] = {}
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

    table = soup.find("table", {"class": "tableBody"}) or soup.find("table", id="_qml6w")
    if not table:
        # Fallback: use the first table that contains the header row
        table = header_tr.find_parent("table")
    if not table:
        return []

    rfp_data: list[dict] = []
    current_status_group: str | None = None
    for tr in table.find_all("tr", recursive=False):
        cls = " ".join(tr.get("class", []))
        if "tableGroupBy" in cls:
            txt = tr.get_text(" ", strip=True)
            m = re.search(r"Status:\s*([A-Za-z ]+)", txt)
            current_status_group = m.group(1).strip() if m else None
            continue

        tds = tr.find_all("td", recursive=False)
        if len(tds) < header_col_count:
            continue
        if "title" not in col_map:
            continue

        title_td = tds[col_map["title"]]
        a = title_td.find("a", href=True)
        title_span = title_td.find("span")
        raw_title = (
            title_span.get_text(strip=True) if title_span
            else (a.get_text(strip=True) if a else title_td.get_text(strip=True))
        )
        title = re.sub(r"\s+", " ", raw_title).strip()
        link = a["href"].strip() if a else ""
        if not title:
            continue

        rfp_data.append({
            "Title":        title,
            "RFP_ID":       title,
            "Link":         link,
            "Doc_ID":       tds[col_map["id"]].get_text(strip=True) if "id" in col_map else "",
            "End_Time":     tds[col_map["end_time"]].get_text(strip=True) if "end_time" in col_map else "",
            "Event_Type":   tds[col_map["event_type"]].get_text(strip=True) if "event_type" in col_map else "",
            "Participated": _normalize_participated(tds[col_map["participated"]].get_text(strip=True)) if "participated" in col_map else "",
            "StatusGroup":  current_status_group,
        })
    return rfp_data


def _parse_workbook_listing(path: str) -> list[dict]:
    """Parse a true Excel export (.xls or .xlsx) — used when the export isn't HTML-disguised-as-xls."""
    ext = os.path.splitext(path)[1].lower()
    rows_raw: list[list[str]] = []

    if ext == '.xlsx':
        try:
            import openpyxl
        except ImportError:
            _die("openpyxl not installed. Run: pip install openpyxl")
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        for row in ws.iter_rows(values_only=True):
            rows_raw.append([str(v).strip() if v is not None else "" for v in row])
        wb.close()
    elif ext == '.xls':
        try:
            import xlrd
        except ImportError:
            _die("xlrd not installed. Run: pip install xlrd==1.2.0")
        wb = xlrd.open_workbook(path)
        ws = wb.sheet_by_index(0)
        for r in range(ws.nrows):
            rows_raw.append([str(v).strip() if v else "" for v in ws.row_values(r)])
    else:
        return []

    if not rows_raw:
        return []

    headers = [re.sub(r"\s+", " ", h).strip().lower() for h in rows_raw[0]]
    col = {}
    for i, h in enumerate(headers):
        if "title" in h and "title" not in col:
            col["title"] = i
        if h == "id" and "id" not in col:
            col["id"] = i
        if "end time" in h and "end_time" not in col:
            col["end_time"] = i
        if "event type" in h and "event_type" not in col:
            col["event_type"] = i
        if "participated" in h and "participated" not in col:
            col["participated"] = i

    if "title" not in col:
        return []

    out: list[dict] = []
    for row in rows_raw[1:]:
        title = re.sub(r"\s+", " ", row[col["title"]] if col["title"] < len(row) else "").strip()
        if not title:
            continue
        out.append({
            "Title":        title,
            "RFP_ID":       title,
            "Link":         "",  # no embedded hyperlink in pure workbook rows
            "Doc_ID":       row[col["id"]] if "id" in col and col["id"] < len(row) else "",
            "End_Time":     row[col["end_time"]] if "end_time" in col and col["end_time"] < len(row) else "",
            "Event_Type":   row[col["event_type"]] if "event_type" in col and col["event_type"] < len(row) else "",
            "Participated": _normalize_participated(row[col["participated"]]) if "participated" in col and col["participated"] < len(row) else "",
            "StatusGroup":  None,
        })
    return out


def parse_master_listing(path: str) -> list[dict]:
    """Dispatch to the right parser based on the detected file format."""
    real_ext = _detect_file_type(path)
    if real_ext in ('.html', '.xml'):
        rfps = _parse_html_listing(path)
    elif real_ext in ('.xls', '.xlsx'):
        # Ariba often disguises HTML as .xls — try HTML parser first, then real workbook.
        rfps = _parse_html_listing(path)
        if not rfps:
            rfps = _parse_workbook_listing(path)
    else:
        rfps = _parse_html_listing(path) or _parse_workbook_listing(path)
    _log(f"  Parsed {len(rfps)} RFP rows from master listing ({real_ext}).")
    return rfps


# ---------------------------------------------------------------------------
# Single-RFP download (same flow as download_from_csv.py)
# ---------------------------------------------------------------------------
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


async def _download_single(page, rfp: dict, company_name: str, output_dir: str):
    """
    Open the RFP link, extract owner/publish_time from the detail page,
    click through the Ariba button sequence, and save the file.

    Returns a tuple (status, owner_name, publish_time, local_path) where status is:
        True   on success
        False  on a real error (network / button / timeout)
        None   if a session expiry was detected (caller should re-login)

    owner_name / publish_time / local_path are None when not available.
    """
    title = _clean_id(rfp.get("Title", ""))
    link  = (rfp.get("Link") or "").strip()
    if not link:
        _log(f"  [SKIP] No link available for RFP: {title}")
        return False, None, None, None

    save_dir = get_downloaded_rfp_folder(title, company_name, output_dir)
    os.makedirs(save_dir, exist_ok=True)

    owner_name: str | None = None
    publish_time: str | None = None

    new_page = await page.context.new_page()
    try:
        _log("  Opening RFP page ...")
        await new_page.goto(link, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(2)

        url_lower = new_page.url.lower()
        url_is_login = any(kw in url_lower for kw in ("login", "signin", "logon", "sso", "auth?"))
        form_is_login = await _page_has_login_form(new_page)
        if url_is_login or form_is_login:
            reason = "URL" if url_is_login else "login form detected"
            _log(f"  Session expired mid-download ({reason}). Will re-login.")
            await new_page.close()
            return None, None, None, None

        # ---- Extract owner_name + publish_time BEFORE clicking through download UI
        # (matches automation_logic.download_single_rfp_file order)
        await _wait_ready(new_page, 30000)
        try:
            details = await extract_rfp_details_inner_text(new_page) or {}
            owner_name = details.get("owner")
            publish_time = details.get("publish_time")
            if owner_name or publish_time:
                _log(f"  Extracted -> owner: {owner_name!r}, publish_time: {publish_time!r}")
                log_event("ALL_RFPS", "ExtractDetails", "Success",
                          f"owner={owner_name}, publish_time={publish_time} for {title}",
                          rfp_id=title)
            else:
                log_event("ALL_RFPS", "ExtractDetails", "Warning",
                          f"Could not extract owner or publish time for {title}",
                          rfp_id=title)
        except Exception as exc:
            log_event("ALL_RFPS", "ExtractDetails", "Fail",
                      f"Detail extraction error for {title}: {exc}",
                      rfp_id=title)

        clicked = await _click_if_visible(new_page, "#_c8_tuc", timeout=5000)
        if clicked:
            _log("  Clicked #_c8_tuc (Review Event details)")
        await asyncio.sleep(10)

        old_url = new_page.url
        for _ in range(20):
            clicked = await _click_if_visible(new_page, "#_iiyvqc", timeout=2000)
            if clicked and new_page.url != old_url:
                _log("  Clicked #_iiyvqc (Content tab)")
                break
            await asyncio.sleep(0.5)

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
        _log("  Download button ready - triggering download ...")

        async with new_page.expect_download(timeout=120000) as dl_info:
            await btn.click(no_wait_after=True)
        download = await dl_info.value

        suggested = download.suggested_filename or f"{title}.xls"
        ext = os.path.splitext(suggested)[1] or ".xls"
        dest_file = os.path.join(save_dir, f"{title}{ext}")

        await download.save_as(dest_file)
        size_kb = os.path.getsize(dest_file) / 1024
        _log(f"  [OK] Saved -> {dest_file}  ({size_kb:.1f} KB)")
        return True, owner_name, publish_time, dest_file

    except Exception as exc:
        _log(f"  Download error: {exc}")
        return False, owner_name, publish_time, None
    finally:
        try:
            await new_page.close()
        except Exception:
            pass


async def download_with_retry(page, rfp, company_name, output_dir, username, password):
    """Run _download_single with auto-relogin + retry. Returns (success, owner_name, publish_time, local_path)."""
    title = _clean_id(rfp.get("Title", ""))
    real_attempts = 0
    session_retries = 0
    MAX_SESSION_RETRIES = 5

    last_owner: str | None = None
    last_publish: str | None = None

    while real_attempts < MAX_DOWNLOAD_ATTEMPTS:
        _log(f"  Attempt {real_attempts + 1}/{MAX_DOWNLOAD_ATTEMPTS} for: {title}")

        if not await ensure_logged_in(page, username, password):
            _log("  Cannot log in - skipping this RFP.")
            return False, last_owner, last_publish, None

        status, owner, publish_time, local_path = await _download_single(
            page, rfp, company_name, output_dir
        )
        if owner:
            last_owner = owner
        if publish_time:
            last_publish = publish_time

        if status is True:
            return True, last_owner, last_publish, local_path

        if status is None:
            session_retries += 1
            if session_retries > MAX_SESSION_RETRIES:
                _log(f"  Session dropped {session_retries} times in a row - giving up.")
                return False, last_owner, last_publish, None
            _log(f"  Session drop #{session_retries} - re-logging in ...")
            if not await do_login(page, username, password):
                _log("  Re-login failed - skipping.")
                return False, last_owner, last_publish, None
            await asyncio.sleep(3)
            continue

        real_attempts += 1
        session_retries = 0
        if real_attempts < MAX_DOWNLOAD_ATTEMPTS:
            _log(f"  Waiting {RETRY_WAIT_SEC}s before retry ...")
            await asyncio.sleep(RETRY_WAIT_SEC)

    _log(f"  [FAIL] Gave up after {MAX_DOWNLOAD_ATTEMPTS} attempts: {title}")
    return False, last_owner, last_publish, None


# ---------------------------------------------------------------------------
# Report writer + progress tracker
# ---------------------------------------------------------------------------
def _report_row(rfp_id, company_name, status, reason="", local_file=""):
    return {
        "RFP_ID":       rfp_id,
        "Company_Name": company_name,
        "Status":       status,
        "Reason":       reason,
        "Local_File":   local_file,
        "Processed_At": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def write_report_csv(report_rows, output_dir, run_started_at) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(output_dir, f"RFP_Download_Report_{timestamp}.csv")
    os.makedirs(output_dir, exist_ok=True)

    total         = len(report_rows)
    downloaded    = sum(1 for r in report_rows if r["Status"] == STATUS_DOWNLOADED)
    skipped       = sum(1 for r in report_rows if r["Status"] == STATUS_SKIPPED_EXISTS)
    not_on_portal = sum(1 for r in report_rows if r["Status"] == STATUS_NOT_FOUND_PORTAL)
    portal_error  = sum(1 for r in report_rows if r["Status"] == STATUS_PORTAL_ERROR)
    failed        = sum(1 for r in report_rows if r["Status"] == STATUS_DOWNLOAD_FAILED)

    companies = sorted({r["Company_Name"] for r in report_rows})

    summary = [
        ["RFP Download Report - All RFPs per Company"],
        ["Run Started",      run_started_at],
        ["Report Generated", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
        [""],
        ["-- Summary --"],
        ["Total RFPs",            total],
        ["Downloaded (new)",      downloaded],
        ["Skipped (already exist)", skipped],
        ["Not Found on Portal",   not_on_portal],
        ["Portal Unavailable",    portal_error],
        ["Download Failed",       failed],
        [""],
        ["-- Companies processed --"],
    ]
    for co in companies:
        co_rows = [r for r in report_rows if r["Company_Name"] == co]
        summary.append([
            co,
            f"total={len(co_rows)}",
            f"downloaded={sum(1 for r in co_rows if r['Status'] == STATUS_DOWNLOADED)}",
            f"skipped={sum(1 for r in co_rows if r['Status'] == STATUS_SKIPPED_EXISTS)}",
            f"not_found={sum(1 for r in co_rows if r['Status'] == STATUS_NOT_FOUND_PORTAL)}",
            f"portal_error={sum(1 for r in co_rows if r['Status'] == STATUS_PORTAL_ERROR)}",
            f"failed={sum(1 for r in co_rows if r['Status'] == STATUS_DOWNLOAD_FAILED)}",
        ])
    summary.append([""])
    summary.append(["-- Detail --"])
    summary.append([""])

    with open(report_path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        for row in summary:
            writer.writerow(row)
        writer.writerow(["RFP_ID", "Company_Name", "Status", "Reason", "Local_File", "Processed_At"])
        for r in report_rows:
            writer.writerow([
                r.get("RFP_ID", ""),
                r.get("Company_Name", ""),
                r.get("Status", ""),
                r.get("Reason", ""),
                r.get("Local_File", ""),
                r.get("Processed_At", ""),
            ])
    return report_path


class ProgressTracker:
    BAR_WIDTH = 40

    def __init__(self, total: int):
        self.total = total
        self.done = 0
        self.downloaded = 0
        self.skipped = 0
        self.failed = 0
        self.not_found = 0

    @property
    def pending(self) -> int:
        return max(0, self.total - self.done)

    def update(self, status: str, count: int = 1):
        self.done += count
        if status == STATUS_DOWNLOADED:
            self.downloaded += count
        elif status == STATUS_SKIPPED_EXISTS:
            self.skipped += count
        elif status == STATUS_DOWNLOAD_FAILED:
            self.failed += count
        else:
            self.not_found += count
        self._draw()

    def _draw(self):
        total = self.total or 1
        filled = int(self.BAR_WIDTH * min(self.done, total) / total)
        bar = "#" * filled + "-" * (self.BAR_WIDTH - filled)
        pct = 100.0 * min(self.done, total) / total

        line1 = f"[{bar}]  {self.done:>4} / {self.total}   ({pct:5.1f}%)"
        line2 = (
            f"OK: {self.downloaded:<5} "
            f"Skip: {self.skipped:<5} "
            f"Fail: {self.failed:<5} "
            f"NotFound: {self.not_found:<5} "
            f"Pending: {self.pending}"
        )
        content_w = max(len(line1), len(line2))
        inner_w = len("Progress  ") + content_w + 2
        print()
        print(f"  +-{'-' * inner_w}-+")
        print(f"  | Progress  {line1:<{content_w}} |")
        print(f"  |           {line2:<{content_w}} |")
        print(f"  +-{'-' * inner_w}-+")


# ---------------------------------------------------------------------------
# Per-company processor
# ---------------------------------------------------------------------------
async def process_company(page, company_name, output_dir, username, password,
                          report_rows, progress):
    """Run the full pipeline for one company. Appends to report_rows in place."""
    print()
    print(f"  {'-' * 65}")
    _log(f"Processing company: {company_name}")
    print(f"  {'-' * 65}")
    log_event("ALL_RFPS", "ProcessCompany", "Start",
              f"Begin processing {company_name}")

    # Re-auth before each company (the session may have aged out)
    if not await ensure_logged_in(page, username, password):
        _log(f"  Cannot log in - skipping {company_name}.")
        report_rows.append(_report_row(
            "(company)", company_name, STATUS_PORTAL_ERROR,
            reason="Could not log in to portal before processing this company",
        ))
        progress.total += 1
        progress.update(STATUS_PORTAL_ERROR)
        return

    # Navigate
    try:
        await navigate_to_company(page, company_name)
    except Exception as exc:
        _log(f"  Navigation failed: {exc}")
        report_rows.append(_report_row(
            "(company)", company_name, STATUS_PORTAL_ERROR,
            reason=f"Could not navigate to company page: {exc}",
        ))
        progress.total += 1
        progress.update(STATUS_PORTAL_ERROR)
        return

    # Export the master listing
    try:
        master_path = await export_master_listing(page, company_name, output_dir)
    except Exception as exc:
        _log(f"  Master-listing export failed: {exc}")
        report_rows.append(_report_row(
            "(company)", company_name, STATUS_PORTAL_ERROR,
            reason=f"Failed to export master RFP listing: {exc}",
        ))
        progress.total += 1
        progress.update(STATUS_PORTAL_ERROR)
        return

    # Parse the listing
    rfps = parse_master_listing(master_path)
    if not rfps:
        _log(f"  Master listing parsed but contained 0 RFPs for {company_name}.")
        report_rows.append(_report_row(
            "(company)", company_name, STATUS_NOT_FOUND_PORTAL,
            reason="Master listing exported successfully but no RFP rows could be parsed",
            local_file=master_path,
        ))
        progress.total += 1
        progress.update(STATUS_NOT_FOUND_PORTAL)
        return

    # Grow the progress tracker to include this company's RFPs
    progress.total += len(rfps)
    progress._draw()

    # Download each RFP
    for idx, rfp in enumerate(rfps, start=1):
        title = _clean_id(rfp.get("Title", ""))
        print()
        _log(f"[{idx}/{len(rfps)}] {title}  |  {company_name}  |  status={rfp.get('StatusGroup') or '-'}")
        log_event("ALL_RFPS", "DownloadRFP", "Start",
                  f"Starting {title} ({idx}/{len(rfps)}) for {company_name}", rfp_id=title)

        # ---- Existence checks (local file OR Dataverse row) ----
        exists, path = file_exists_locally(title, company_name, output_dir)
        if exists:
            _log(f"  [SKIP] Already exists locally: {path}")
            report_rows.append(_report_row(
                title, company_name, STATUS_SKIPPED_EXISTS,
                reason="File already exists in local output folder",
                local_file=path or "",
            ))
            # Still upsert into Dataverse so the row reflects this file.
            store_rfp_in_database(rfp, company_name)
            log_event("ALL_RFPS", "DownloadRFP", "Skip",
                      f"{title}: already exists locally", rfp_id=title)
            progress.update(STATUS_SKIPPED_EXISTS)
            continue

        if check_rfp_exists_in_dataverse(title, company_name):
            _log("  [SKIP] Already exists in Dataverse — re-using DB row, skipping download.")
            report_rows.append(_report_row(
                title, company_name, STATUS_SKIPPED_EXISTS,
                reason="RFP already exists in Dataverse (cr673_bahra_rfps_v2)",
            ))
            log_event("ALL_RFPS", "DownloadRFP", "Skip",
                      f"{title}: already exists in Dataverse", rfp_id=title)
            progress.update(STATUS_SKIPPED_EXISTS)
            continue

        if not rfp.get("Link"):
            _log("  [SKIP] No link in master listing - cannot download.")
            report_rows.append(_report_row(
                title, company_name, STATUS_NOT_FOUND_PORTAL,
                reason="Master listing row had no embedded hyperlink (cannot construct download URL)",
            ))
            log_event("ALL_RFPS", "DownloadRFP", "Fail",
                      f"{title}: no link in master listing", rfp_id=title)
            progress.update(STATUS_NOT_FOUND_PORTAL)
            continue

        success, owner_name, publish_time, local_path = await download_with_retry(
            page, rfp, company_name, output_dir, username, password,
        )

        if success:
            if not local_path:
                _, local_path = file_exists_locally(title, company_name, output_dir)
            report_rows.append(_report_row(
                title, company_name, STATUS_DOWNLOADED,
                reason=(
                    f"Downloaded from master listing "
                    f"(status group: {rfp.get('StatusGroup') or 'unknown'}, "
                    f"owner: {owner_name or '-'}, publish_time: {publish_time or '-'})"
                ),
                local_file=local_path or "",
            ))
            # Persist to Dataverse with owner / publish_time
            store_rfp_in_database(rfp, company_name,
                                  owner_name=owner_name,
                                  publish_time=publish_time)
            log_event("ALL_RFPS", "DownloadRFP", "Success",
                      f"{title} downloaded for {company_name}", rfp_id=title)
            progress.update(STATUS_DOWNLOADED)
        else:
            report_rows.append(_report_row(
                title, company_name, STATUS_DOWNLOAD_FAILED,
                reason=(
                    f"Download failed after {MAX_DOWNLOAD_ATTEMPTS} attempt(s). "
                    "Possible causes: no Excel file on portal, download button unavailable, "
                    "network timeout, or session could not be recovered."
                ),
            ))
            log_event("ALL_RFPS", "DownloadRFP", "Fail",
                      f"{title}: download failed after {MAX_DOWNLOAD_ATTEMPTS} attempt(s)",
                      rfp_id=title)
            progress.update(STATUS_DOWNLOAD_FAILED)


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------
async def run(companies: list[str], output_dir: str, username: str, password: str, headless: bool):
    from playwright.async_api import async_playwright

    run_started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    os.makedirs(output_dir, exist_ok=True)

    # Start a fresh RunID so every Dataverse log row and RFP write is grouped.
    run_id = start_new_run()

    print()
    print("=" * 70)
    print("  Portal RFP Downloader  -  All RFPs per Company  (Standalone)")
    print("=" * 70)
    print(f"  Companies   : {len(companies)} -> {', '.join(companies)}")
    print(f"  Output      : {output_dir}")
    print(f"  Headless    : {headless}")
    print(f"  RunID       : {run_id or '(integrations disabled)'}")
    if not _INTEGRATIONS_OK:
        print(f"  WARNING     : Dataverse/log integrations are disabled "
              f"(import error: {_INTEGRATION_ERR}). Files will save locally only.")
    print("=" * 70)
    print()

    log_event("ALL_RFPS", "StartRun", "Success",
              f"Standalone download started for {len(companies)} companies: {', '.join(companies)}")

    report_rows: list[dict] = []
    progress = ProgressTracker(total=0)  # grown as each company's RFP count is discovered

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=headless,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        context = await browser.new_context(
            accept_downloads=True,
            viewport={"width": 1280, "height": 1024},
        )
        page = await context.new_page()

        _log("Logging in to portal ...")
        if not await do_login(page, username, password):
            await browser.close()
            _die("Initial login failed. Check your credentials.")

        for company in companies:
            try:
                await process_company(
                    page, company, output_dir, username, password,
                    report_rows, progress,
                )
            except Exception as exc:
                _log(f"  Unhandled error while processing {company}: {exc}")
                report_rows.append(_report_row(
                    "(company)", company, STATUS_PORTAL_ERROR,
                    reason=f"Unhandled error: {exc}",
                ))

        await browser.close()

    # Final summary
    print()
    print("=" * 70)
    print("  Download Run Complete")
    print("=" * 70)
    print(f"  Companies processed   : {len(companies)}")
    print(f"  Downloaded (new)      : {sum(1 for r in report_rows if r['Status'] == STATUS_DOWNLOADED)}")
    print(f"  Skipped (existed)     : {sum(1 for r in report_rows if r['Status'] == STATUS_SKIPPED_EXISTS)}")
    print(f"  Not Found on Portal   : {sum(1 for r in report_rows if r['Status'] == STATUS_NOT_FOUND_PORTAL)}")
    print(f"  Portal Unavailable    : {sum(1 for r in report_rows if r['Status'] == STATUS_PORTAL_ERROR)}")
    print(f"  Download Failed       : {sum(1 for r in report_rows if r['Status'] == STATUS_DOWNLOAD_FAILED)}")
    print("=" * 70)
    print(f"  Files saved to: {output_dir}")

    report_path = write_report_csv(report_rows, output_dir, run_started_at)
    print()
    print(f"  Report CSV -> {report_path}")
    print()

    log_event("ALL_RFPS", "EndRun", "Success",
              f"Run finished. Downloaded={sum(1 for r in report_rows if r['Status'] == STATUS_DOWNLOADED)}, "
              f"Failed={sum(1 for r in report_rows if r['Status'] == STATUS_DOWNLOAD_FAILED)}, "
              f"Skipped={sum(1 for r in report_rows if r['Status'] == STATUS_SKIPPED_EXISTS)}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Download ALL RFPs for a company (or all companies) from the Ariba portal. Standalone, local only.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  python download_all_company_rfps.py --company "Saudi Energy"
  python download_all_company_rfps.py                                 # processes every company in COMPANY_OPTIONS
  python download_all_company_rfps.py --headless --output "D:/RFPs"
  python download_all_company_rfps.py --company "Aramco e-Marketplace" --username me@co.com --password secret

Known companies (from config.py):
  {', '.join(COMPANY_OPTIONS)}
        """,
    )
    parser.add_argument("--company", default=None,
                        help="Company name to process. If omitted, processes every company in config.COMPANY_OPTIONS.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT,
                        help=f"Local output root (default: {DEFAULT_OUTPUT})")
    parser.add_argument("--username", default=None,
                        help="Portal username (or set BAHRA_SAP_USERNAME)")
    parser.add_argument("--password", default=None,
                        help="Portal password (or set BAHRA_SAP_PASSWORD)")
    parser.add_argument("--headless", action="store_true", default=False,
                        help="Run browser in headless mode")
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

    if args.company:
        target = args.company.strip()
        if target not in COMPANY_OPTIONS:
            _log(f"Warning: '{target}' is not in COMPANY_OPTIONS. Proceeding anyway.")
        companies = [target]
    else:
        companies = list(COMPANY_OPTIONS)
        if not companies:
            _die("No companies in config.COMPANY_OPTIONS and no --company given.")

    asyncio.run(run(
        companies=companies,
        output_dir=args.output,
        username=username,
        password=password,
        headless=args.headless,
    ))


if __name__ == "__main__":
    main()
