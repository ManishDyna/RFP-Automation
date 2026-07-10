from core.common_imports import *
from core.log_events import log_rfp_activity

# ===== LOGIN =====
# async def login_and_select_company(page):
#     await page.goto(URL)
#     await page.fill('xpath=//*[@id="_boebpb"]/div[1]/input', USERNAME)
#     await page.fill('#Password', PASSWORD)
#     await page.click('input[type="submit"]')
#     log_event("LOGIN", "Login", "Success", "Logged in")
#     print("Login SucessFully")

#     # await page.click('#_jlt7md') More...
#     # await page.wait_for_selector('xpath=//a[normalize-space(text())="More"]')
    
#     more_link = page.get_by_role("link", name=re.compile(r"^more(\.\.\.)?$", re.IGNORECASE))
#     await more_link.click()
#     await page.wait_for_selector(f'xpath=//a[normalize-space(text())="{COMPANY_NAME}"]')
#     await page.click(f'xpath=//a[normalize-space(text())="{COMPANY_NAME}"]')
#     log_event("LOGIN", "SelectCompany", "Success", f"Selected {COMPANY_NAME}")
#     print("Select Company")



async def login_and_select_company(page, company_name: str | None = None):
    target_company = (company_name or COMPANY_NAME).strip() or COMPANY_NAME
    await page.goto(URL, timeout=60000)
    await page.fill('xpath=//*[@id="_boebpb"]/div[1]/input', USERNAME)
    await page.fill('#Password', PASSWORD)
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
            # Primary: locate by text content (Ariba IDs like _03mdrd are dynamic).
            # State-aware: only click when collapsed — clicking an expanded group
            # would collapse it and hide the Open RFP rows.
            # Fallback: original ID-based selector, also state-aware. Open
            toggled = False
            try:
                open_group_row = frame.locator(
                    'tr.tableGroupBy',
                    has_text=re.compile(r'Status:\s*Open\s*\(\d+\)')
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
                toggled = True
            except Exception as e:
                print(f"Text-based selector failed, falling back to ID: {e}")

            if not toggled:
                try:
                    await frame.wait_for_selector('a[id*="_03mdrd"]', timeout=20000)
                    fallback_link = frame.locator('a[id*="_03mdrd"]').first
                    fallback_icon = fallback_link.locator('span[class*="w-togglebox-icon-"]').first
                    icon_class = (await fallback_icon.get_attribute('class')) or ''
                    if 'w-togglebox-icon-off' in icon_class:
                        await fallback_link.click()
                        print("Expanded 'Status: Open' group via fallback ID selector")
                    else:
                        print("'Status: Open' group already expanded (fallback path) — skip click")
                except Exception as e:
                    log_event("RFP", "Scrape", "Fail", f"Both Status:Open selectors failed: {e}")
                    raise

            # Wait until the RFP table is fully loaded
            await frame.wait_for_selector('#_swbzed tr.tableRow1', timeout=20000)

            # Extract only rows that belong to the "Status: Open" group.
            # Walk the table sequentially; toggle in_open_group when we cross a
            # tableGroupBy header so other groups (Completed, Pending Selection)
            # are ignored even when they are also expanded.
            all_trs = await frame.query_selector_all('#_swbzed tr')
            rows = []
            in_open_group = False
            for tr in all_trs:
                class_attr = (await tr.get_attribute('class')) or ''
                if 'tableGroupBy' in class_attr:
                    header_text = (await tr.inner_text()) or ''
                    in_open_group = bool(re.search(r'Status:\s*Open\s*\(\d+\)', header_text))
                    continue
                if in_open_group and 'tableRow1' in class_attr:
                    rows.append(tr)

            print(f"Data Extraction:-- {len(rows)} Open RFP rows")
            open_rfps = []

            for row in rows:
                cells = await row.query_selector_all('td')
                if not cells:
                    continue

                link_el = await cells[0].query_selector('a')
                rfp_link = await link_el.get_attribute("href") if link_el else ""
                title = await cells[1].inner_text() if len(cells) > 1 else ""
                rfp_id = await cells[3].inner_text() if len(cells) > 3 else ""
                RFP_End_Date = await cells[5].inner_text() if len(cells) > 5 else ""
                rfp_type = await cells[8].inner_text() if len(cells) > 8 else ""
                participant = await cells[9].inner_text() if len(cells) > 9 else ""

                # Only add non-participated RFPs for downloading
                # if participant.strip().lower() == "no":
                from core.log_events import normalize_date_format
                open_rfps.append({
                    "Title": title.strip(),
                    "Link": rfp_link.strip(),
                    "ID": rfp_id.strip(),
                    "Event Type": rfp_type.strip(),
                    "RFP_End_Date": normalize_date_format(RFP_End_Date.strip()),
                    "Status": participant.strip(),
                })

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

