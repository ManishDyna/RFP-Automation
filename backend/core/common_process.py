from core.common_imports import *
from core.log_events import log_rfp_activity
from core.rfp_row_parser import (
    RFP_TABLE_SELECTOR,
    RFP_ROW_CLASS,
    RFP_GROUP_ROW_CLASS,
    RFP_OPEN_GROUP_RE,
    is_open_group_header,
    parse_open_group_count,
    parse_open_rfp_row,
)

# Expanding a status group is an AJAX postback, so the Open rows appear a
# round-trip after the click. Poll the real extraction rather than a proxy
# selector — see _collect_open_rows.
OPEN_ROWS_POLL_ATTEMPTS = 40
OPEN_ROWS_POLL_INTERVAL_MS = 500


async def _collect_open_rows(table):
    """Row handles belonging to the "Status: Open" group.

    Walks the table sequentially, toggling membership at each tableGroupBy
    header, so other groups (Completed, Pending Selection) are skipped even
    when they are expanded too. Rows of Ariba's nested `<table class="mls">`
    cell wrappers carry no class and fall through both branches.
    """
    rows = []
    in_open_group = False
    for tr in await table.locator('tr').element_handles():
        class_attr = (await tr.get_attribute('class')) or ''
        if RFP_GROUP_ROW_CLASS in class_attr:
            in_open_group = is_open_group_header((await tr.inner_text()) or '')
            continue
        if in_open_group and RFP_ROW_CLASS in class_attr:
            rows.append(tr)
    return rows


async def _dump_listing_table(frame, company, attempt):
    """Save the listing table's markup when extraction comes back empty.

    Zero rows means either the group is genuinely empty or Ariba reshaped its
    markup again — and those look identical in the log. This dump is the
    fixture needed to add a new generation to
    Support-Files/verify_open_rfp_selectors.py.
    """
    try:
        # Separates "the table filter matched nothing" from "the rows never
        # arrived" — the two ways this can come back empty.
        all_tables = await frame.locator(RFP_TABLE_SELECTOR).count()
        open_tables = await frame.locator(RFP_TABLE_SELECTOR).filter(
            has_text=RFP_OPEN_GROUP_RE
        ).count()
        all_rows = await frame.locator(f'{RFP_TABLE_SELECTOR} tr.{RFP_ROW_CLASS}').count()
        print(
            f"  -> diagnostics: {all_tables} x {RFP_TABLE_SELECTOR}, "
            f"{open_tables} containing a 'Status: Open (N)' header, "
            f"{all_rows} tr.{RFP_ROW_CLASS} in total"
        )

        html = await frame.locator(RFP_TABLE_SELECTOR).first.evaluate('el => el.outerHTML')
        safe_company = re.sub(r'[^A-Za-z0-9]+', '-', company or 'unknown').strip('-')
        os.makedirs('LOGS', exist_ok=True)
        path = os.path.join('LOGS', f'open_rfp_table_{safe_company}_attempt{attempt}.html')
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write(html)
        print(f"  -> listing table markup dumped to {path}")
    except Exception as e:
        print(f"  -> could not dump listing table markup: {e}")

# ===== LOGIN =====
# Ariba's generated widget ids (_boebpb, _xcbcqb, ...) rotate on every SAP
# redeploy, so anchor on the form field NAME instead — Ariba's own login POST
# depends on `UserName`/`Password`, so those cannot change silently.
# The username input carries no id at all, only name="UserName"; the password
# input is the one with a real static id="Password".
USERNAME_SELECTORS = (
    'input[name="UserName"]',
    'td.w-login-form-input-user input[name="UserName"]',
    'td.w-login-form-input-user input.w-txt-dsize',
)
PASSWORD_SELECTORS = (
    '#Password',
    'input[name="Password"]:not([type="hidden"])',
)

# Short probe for the fallback selectors — the first one already absorbed the
# full wait, so anything still missing is missing, not slow.
_FALLBACK_PROBE_MS = 2000


async def _first_visible(page, selectors, timeout):
    """Return the first selector in `selectors` that becomes visible, else None.

    The first selector gets the full `timeout` (it doubles as the page-ready
    wait); the rest are probed briefly.
    """
    for index, selector in enumerate(selectors):
        try:
            locator = page.locator(selector).first
            await locator.wait_for(
                state="visible",
                timeout=timeout if index == 0 else _FALLBACK_PROBE_MS,
            )
            return locator
        except Exception:
            continue
    return None


async def fill_login_credentials(page, username, password, timeout=20000):
    """Fill the Ariba supplier login form, tolerant of rotating widget ids.

    Raises RuntimeError naming every selector tried, rather than letting a
    single stale locator burn 30s and surface an opaque Playwright timeout.
    """
    user_box = await _first_visible(page, USERNAME_SELECTORS, timeout)
    if user_box is None:
        raise RuntimeError(
            f"Ariba login: username field not found at {page.url}. "
            f"Tried: {', '.join(USERNAME_SELECTORS)}. "
            "Ariba likely changed the login markup — re-inspect the page."
        )
    await user_box.fill(username)

    pwd_box = await _first_visible(page, PASSWORD_SELECTORS, timeout)
    if pwd_box is None:
        raise RuntimeError(
            f"Ariba login: password field not found at {page.url}. "
            f"Tried: {', '.join(PASSWORD_SELECTORS)}."
        )
    await pwd_box.fill(password)


async def login_form_present(page) -> bool:
    """True if the Ariba supplier login form is on screen (i.e. we are logged out).

    Deliberately count-based and non-blocking: this runs before every export via
    `is_logged_in`, so it must not spend a wait budget on the common case where
    we are logged in and the form is legitimately absent.
    """
    for selector in USERNAME_SELECTORS:
        try:
            if await page.locator(selector).count() > 0:
                return True
        except Exception:
            continue
    return False


async def login_and_select_company(page, company_name: str | None = None):
    target_company = (company_name or COMPANY_NAME).strip() or COMPANY_NAME
    await page.goto(URL, timeout=60000)
    # Read fresh from Dataverse so a password changed on the dashboard is used immediately.
    portal_username, portal_password = get_sap_credentials()
    await fill_login_credentials(page, portal_username, portal_password)
    async with page.expect_navigation(wait_until="domcontentloaded", timeout=60000):
        await page.click('input[type="submit"]')
    log_event("LOGIN", "Login", "Success", "Logged in")

    # Open the “More” menu
    more_link = page.get_by_role("link", name=re.compile(r"^more(\.\.\.)?$", re.I)).first
    await more_link.click()

    # Wait for a visible menu panel
    menu = page.locator('div.awmenu:not(.is-dnone), .w-pmi-menu:visible, .menu-panel:visible').first
    try:
        await menu.wait_for(timeout=10000)
    except:
        # If not open, click again
        await more_link.click()
        await menu.wait_for(timeout=8000)

    # Target the visible company item
    item = page.locator("a.w-pmi-item:visible").filter(has_text=target_company).first
    await item.wait_for(state="attached", timeout=10000)

    # Click with scroll/hover fallback; JS click last
    try:
        await item.scroll_into_view_if_needed()
    except:
        pass
    try:
        await item.click(timeout=5000)
    except:
        try:
            parent = item.locator("xpath=..")
            await parent.hover(timeout=2000)
            await item.click(timeout=3000)
        except:
            handle = await item.element_handle()
            if handle:
                await page.evaluate("el => el.click()", handle)

    log_event("LOGIN", "SelectCompany", "Success", f"Selected {target_company}")

# ===== SCRAPE =====
async def scrape_open_rfps(page, company=COMPANY_NAME, max_retries=3):
    log_event("RFP", "Scrape", "Start", "Extracting open RFPs")

    for attempt in range(1, max_retries + 1):
        try:
            # Click the main company dropdown
            # await page.click('#_jlt7md')
            more_link = page.get_by_role("link", name=re.compile(r"^more(\.\.\.)?$", re.IGNORECASE))
            await more_link.click()
            await page.wait_for_selector(f'xpath=//a[normalize-space(text())="{company}"]')
            await page.click(f'xpath=//a[normalize-space(text())="{company}"]')

            # Wait until network is idle after navigation
            await page.wait_for_load_state("networkidle")

            # Locate SupplierFrame
            await page.wait_for_selector("iframe")
            frame = None
            for f in page.frames:
                if "SupplierFrame" in (f.name or "") or "SupplierFrame" in (f.url or ""):
                    frame = f
                    break
            if not frame:
                raise Exception("SupplierFrame not found")

            # Expand the "Status: Open" group.
            # Located by text content — Ariba's generated ids rotate on every SAP
            # redeploy, so there is no id worth falling back to (the old
            # `a[id*="_03mdrd"]` fallback could only ever time out).
            # State-aware: only click when collapsed — clicking an expanded group
            # would collapse it and hide the Open RFP rows.
            open_group_row = frame.locator(
                f'tr.{RFP_GROUP_ROW_CLASS}',
                has_text=RFP_OPEN_GROUP_RE
            ).first
            await open_group_row.wait_for(state='visible', timeout=15000)

            toggle_link = open_group_row.locator('a[bh="GAT"]').first
            toggle_icon = toggle_link.locator('span[class*="w-togglebox-icon-"]').first
            icon_class = (await toggle_icon.get_attribute('class')) or ''

            if 'w-togglebox-icon-off' in icon_class:
                await toggle_link.click(timeout=5000)
                print("Expanded 'Status: Open' group")
            else:
                print("'Status: Open' group already expanded — skip click")

            # Wait until the RFP table is fully loaded
            await frame.wait_for_selector(
                f'{RFP_TABLE_SELECTOR} tr.{RFP_ROW_CLASS}', timeout=20000
            )

            # Resolve the listing table by the group header it contains, so a
            # second `table.tableBody` elsewhere in the frame cannot bleed its
            # rows into the walk below.
            table = frame.locator(RFP_TABLE_SELECTOR).filter(
                has_text=RFP_OPEN_GROUP_RE
            ).first

            # Expanding the group is an AJAX postback: the Open rows only exist
            # after the round-trip, while rows of other already-expanded groups
            # are on screen throughout. So waiting on `tr.tableRow1` above is
            # satisfied too early and the walk finds nothing. Poll the real
            # extraction until it reaches the size the header advertises —
            # the wait condition and the extraction are then the same thing.
            expected_open = parse_open_group_count(await open_group_row.inner_text())
            rows = []
            for _ in range(OPEN_ROWS_POLL_ATTEMPTS):
                rows = await _collect_open_rows(table)
                if expected_open is None:
                    if rows:
                        break
                elif len(rows) >= expected_open:
                    break
                await page.wait_for_timeout(OPEN_ROWS_POLL_INTERVAL_MS)

            advertised = '' if expected_open is None else f" (header advertises {expected_open})"
            print(f"Data Extraction:-- {len(rows)} Open RFP rows{advertised}")

            if not rows:
                await _dump_listing_table(frame, company, attempt)

            open_rfps = []

            from core.log_events import normalize_date_format

            for row in rows:
                # Direct-child <td> only. Ariba wraps each cell in a nested
                # <table class="mls">, so a descendant `td` query returns ~10
                # elements per row and the field positions shift whenever that
                # nesting changes — silently, with no error. `./td` is a stable
                # five columns across every captured markup generation.
                cells = await row.query_selector_all('xpath=./td')
                cell_texts = [await cell.inner_text() for cell in cells]

                link_el = await cells[0].query_selector('a') if cells else None
                rfp_link = await link_el.get_attribute("href") if link_el else ""

                fields = parse_open_rfp_row(cell_texts, rfp_link)
                if fields is None:
                    continue  # spacer/layout row, not an RFP

                # Only add non-participated RFPs for downloading
                # if fields["Status"].lower() == "no":
                fields["RFP_End_Date"] = normalize_date_format(fields["RFP_End_Date"])
                open_rfps.append(fields)

            if open_rfps:
                log_event("RFP", "Scrape", "Success", f"Found {len(open_rfps)} RFPs")
                return open_rfps
            else:
                log_event("RFP", "Scrape", "Retry", f"No RFPs found (attempt {attempt})")
                await page.reload(timeout=60000)
                await page.wait_for_load_state("networkidle", timeout=60000)

        except Exception as e:
            log_event("RFP", "Scrape", "Fail", f"Error {e} (attempt {attempt})")
            await page.reload(timeout=60000)
            await page.wait_for_load_state("networkidle", timeout=60000)

    log_event("RFP", "Scrape", "Fail", "No RFPs after retries")
    return []

