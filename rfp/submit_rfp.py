import time
import re
import asyncio
import tempfile
from pathlib import Path
from playwright.async_api import Page, expect
from typing import List, Dict, Any, Optional, Union
from helpers.core_helper import *


# file can be str (single file) or List[str] (multiple)
FileSpec = Union[str, List[str]]

# Assuming these are in a shared location or defined elsewhere

def fetch_from_sharepoint_temp(graph_client, sp_path: str):
    print(f"📥 Fetching from SharePoint: {sp_path}")
    content = graph_client.get_file_content_from_sharepoint(sp_path)
    print("content:-",content)
    if not content:
        raise RuntimeError(f"❌ No content returned from SharePoint for {sp_path}")

    temp_path = Path(tempfile.gettempdir()) / Path(sp_path).name
    data = content.read()

    if not data:
        raise RuntimeError(f"❌ Empty file fetched from SharePoint: {sp_path}")

    with open(temp_path, "wb") as f:
        f.write(data)

    print(f"✅ File saved to temp: {temp_path}, size={len(data)} bytes")
    return str(temp_path)
# ===== MAIN Submit RFP Code =====
# 🔹 Utility: Read the Ariba PageErrorPanel message if visible
async def get_page_error_panel_message(page: Page) -> Optional[str]:
    try:
        for sel in [
            "#PageErrorPanel .msgText",
            "#slidingErrorMsgContent .msgText",
            "#slidingErrorMsg .msgText",
        ]:
            el = page.locator(f"{sel}:visible")
            if await el.count() > 0:
                text = (await el.first.inner_text()).strip()
                if text:
                    return text
    except Exception:
        pass
    return None


# 🔹 Utility: Safe click with retries
async def safe_click(page: Page, selector: str, retries: int = 3, timeout: int = 10000):
    for attempt in range(retries):
        try:
            await page.locator(selector).click(timeout=timeout)
            print(f"✅ Clicked {selector}")
            return True
        except Exception as e:
            print(f"♻️ Retry click {selector} - attempt {attempt+1}: {e}")
            if attempt == retries - 1:  # Last attempt, try force click
                try:
                    await page.locator(selector).click(force=True, timeout=timeout)
                    print(f"✅ Force clicked {selector}")
                    return True
                except Exception as force_error:
                    print(f"❌ Force click also failed for {selector}: {force_error}")
            time.sleep(1)
    print(f"❌ Failed to click {selector}")
    return False

# 🔹 Utility: Safe radio button click
async def safe_radio_click(page: Page, radio_id: str, timeout: int = 5000):
    """
    Specialized function for clicking radio buttons that might be intercepted by labels
    """
    try:
        # Method 1: Try direct click first
        radio_locator = page.locator(f"#{radio_id}")
        await radio_locator.click(timeout=timeout)
        print(f"✅ Clicked radio button #{radio_id}")
        return True
    except Exception as e:
        print(f"♻️ Direct radio click failed, trying alternatives: {e}")
        
        try:
            # Method 2: Try clicking associated label
            label_locator = page.locator(f"label[for='{radio_id}']")
            if await label_locator.count() > 0:
                await label_locator.click(force=True)
                print(f"✅ Clicked label for radio #{radio_id}")
                return True
        except Exception as label_error:
            print(f"♻️ Label click failed: {label_error}")
        
        try:
            # Method 3: Force click the radio button
            await page.locator(f"#{radio_id}").click(force=True)
            print(f"✅ Force clicked radio #{radio_id}")
            return True
        except Exception as force_error:
            print(f"♻️ Force click failed: {force_error}")
        
        try:
            # Method 4: Try JavaScript click
            await page.locator(f"#{radio_id}").evaluate("element => element.click()")
            print(f"✅ JavaScript clicked radio #{radio_id}")
            return True
        except Exception as js_error:
            print(f"❌ All click methods failed for #{radio_id}: {js_error}")
            return False

# 🔹 Get all wizStep elements or current step position
async def get_wizstep_position(page: Page, all_steps: bool = False) -> Optional[Any]:
    try:
        await page.locator(".rfxTOCBody").wait_for(timeout=10000)

        wiz_boxes = page.locator(".rfxTOCBody .wizBox")
        count = await wiz_boxes.count()
        print("wiz_boxes count:", count)

        steps_locator = None
        for i in range(count):
            step_elements = wiz_boxes.nth(i).locator(".wizStep, .wizStepCurrent")
            step_count = await step_elements.count()
            if step_count > 0:
                steps_locator = step_elements
                break

        if not steps_locator:
            print("❌ No wizBox with wizard steps found")
            return None

        if all_steps:
            return steps_locator

        step_count = await steps_locator.count()
        for i in range(step_count):
            step = steps_locator.nth(i)
            class_attr = await step.get_attribute("class") or ""
            if "wizStepCurrent" in class_attr:
                print(f"wizStepCurrent is at position: {i + 1}")
                return i + 1
        return None
    except Exception as e:
        print(f"⚠ Error finding wizStep position: {e}")
        return None

# 🔹 Navigate to a specific wizard step
async def go_to_step(page: Page, step_index: int, max_attempts: int = 3) -> Optional[int]:
    for attempt in range(max_attempts):
        try:
            print(f"🔄 Attempt {attempt+1}: Navigating to Step {step_index}...")

            steps_locator = await get_wizstep_position(page, all_steps=True)
            if not steps_locator:
                print("❌ steps_locator is None")
                await asyncio.sleep(1)
                continue

            count = await steps_locator.count()
            print("steps count:", count)

            if count < step_index:
                print(f"❌ Not enough steps found (found {count}, needed {step_index})")
                await asyncio.sleep(1)
                continue

            target_step = steps_locator.nth(step_index - 1)
            
            # Sometimes clickable child is inside
            clickable = target_step.locator("a, span, div").first

            # Try normal click
            try:
                await clickable.click(force=True)
            except Exception as e:
                print(f"⚠ Normal click failed, trying JS click: {e}")
                handle = await target_step.element_handle()
                if handle:
                    await page.evaluate("(el) => el.click()", handle)
                else:
                    continue

            # Wait for update
            await page.wait_for_timeout(1500)

            # Verify active step
            new_position = await get_wizstep_position(page)
            if new_position == step_index:
                print(f"🎯 Successfully navigated to Step {step_index}")
                return new_position
            else:
                print(f"⚠ Step did not become active (current: {new_position}), retrying...")
                await asyncio.sleep(1)
                continue

        except Exception as e:
            print(f"⚠ Attempt {attempt+1} failed: {e}")
            await asyncio.sleep(1)

    print(f"❌ Could not reliably navigate to Step {step_index}")
    return None


# Attached Files after uploading excel file
async def upload_attachments_via_bidding_console(
    page,
    material_to_files: Dict[str, FileSpec],
    *,
    form_name: str = "BiddingConsole",
    max_rows: Optional[int] = None,
    wait_after_ok_ms: int = 1000
 ) -> None:

    # Find Out the Form Name 
    form = page.locator(f"form[name='{form_name}']")
    await form.wait_for(timeout=20000)

    rows = form.locator("tr.rowClass, tr.stItemRow")
    row_count = await rows.count()
    if max_rows:
        row_count = min(row_count, max_rows)
    print(f"🔎 Detected {row_count} candidate rows inside form '{form_name}'")

    def to_list(v: FileSpec) -> List[str]:
        if isinstance(v, list):
            return [str(Path(p)) for p in v]
        return [str(Path(v))]

    async def detect_material_code(row) -> Optional[str]:
        try:
            txt = (await row.inner_text()).strip()
        except Exception:
            return None
        m = re.search(r"\b(\d{8,})\b", txt)  # adjust if your codes differ
        return m.group(1) if m else None

    for i in range(row_count):
        row = rows.nth(i)
        try:
            await row.scroll_into_view_if_needed(timeout=5000)
        except Exception:
            pass

        mat_code = await detect_material_code(row)
        if not mat_code or mat_code not in material_to_files:
            continue

        files = to_list(material_to_files[mat_code])
        print(f"📦 Row {i}: material {mat_code} → {files}")

        # Handle More… / Less… state inside this row
        toggle = row.locator("a:has-text('More...'), a:has-text('Less...')")
        if await toggle.count() == 0:
            print(f"⚠ No More/Less toggle for {mat_code}; trying to proceed.")
        else:
            try:
                txt = (await toggle.first.inner_text()).strip().lower()
            except Exception:
                txt = ""
            # If it's showing 'More...', the details are collapsed → expand it
            if "more..." in txt:
                try:
                    await toggle.first.click(timeout=8000)
                except Exception as e:
                    print(f"⚠ Could not click 'More...' for {mat_code}: {e}")
                    continue
            # If 'Less...' is shown, it's already expanded → do nothing

        # Pick the attach link that belongs to THIS row:
        # choose the first 'Attach a file' link that appears after this row in DOM
        attach_link = row.locator("xpath=following::a[contains(normalize-space(.),'Attach a file')][1]")
        try:
            await attach_link.wait_for(timeout=8000)
        except Exception:
            print(f"❌ 'Attach a file' not found for {mat_code}; skipping.")
            continue

        # Navigate to Add Attachment page
        try:
            async with page.expect_navigation(wait_until="domcontentloaded", timeout=20000):
                await attach_link.click()
        except Exception as e:
            print(f"⚠ Navigation to Add Attachment failed for {mat_code}: {e}")
            continue

        # On Add Attachment page: choose file(s) and OK
        file_input = page.locator("input[type='file']")
        try:
            await file_input.wait_for(timeout=15000)
            await file_input.set_input_files(files)
        except Exception as e:
            print(f"❌ Could not set files for {mat_code}: {e}")
            # Return best-effort and continue
            try:
                await page.go_back()
                await form.wait_for(timeout=15000)
            except Exception:
                pass
            continue

        ok_btn = page.locator("button:has-text('OK')")
        try:
            async with page.expect_navigation(wait_until="domcontentloaded", timeout=20000):
                await ok_btn.last.click()
        except Exception:
            try:
                await ok_btn.last.click()
            except Exception:
                pass
            await page.wait_for_timeout(wait_after_ok_ms)

        # Ensure we are back to the form
        try:
            await form.wait_for(timeout=20000)
        except Exception:
            try:
                await page.go_back()
                await form.wait_for(timeout=20000)
            except Exception:
                print(f"⚠ Could not return to grid after attaching for {mat_code}; continuing.")
                continue

        await page.wait_for_timeout(300)

async def build_materials_dict_from_excel_reuse(excel_local_path: str, graph_client, rfp_title: str, company_name: str) -> Dict[str, str]:
    """
    Builds { material_code: local_pdf_path } by listing all PDFs in the TDS folder
    and matching them to material codes found in the Excel file.
    Matches when a material code appears anywhere in the filename.
    """
    codes = extract_materials_from_excel(excel_local_path, include_details=False)
    print(f"📋 Material codes from Excel: {sorted(codes)}")
    mapping: Dict[str, str] = {}

    if not codes:
        print("⚠ No material codes found in Excel, skipping TDS lookup")
        return mapping

    # List all PDF files in the TDS SharePoint folder
    tds_folder = get_sharepoint_rfp_tds_path(rfp_title, company_name)
    print(f"📂 Listing TDS files in: {tds_folder}")

    try:
        tds_files = graph_client.list_files_in_directory(tds_folder, ['.pdf'])
    except Exception as e:
        print(f"⚠ Could not list TDS folder: {e}")
        tds_files = []

    print(f"📎 Found {len(tds_files)} PDF(s) in TDS folder: {[f['name'] for f in tds_files]}")

    if not tds_files:
        print("⚠ No TDS files found in SharePoint folder")
        return mapping

    # Match files to material codes: check if any code appears in the filename
    matched_files = set()
    for file_info in tds_files:
        filename = file_info["name"]
        sp_path = file_info["path"]
        for code in codes:
            if code in filename and code not in mapping:
                try:
                    local_path = fetch_from_sharepoint_temp(graph_client, sp_path)
                    if local_path:
                        mapping[code] = local_path
                        matched_files.add(filename)
                        print(f"✅ Matched TDS: {filename} → material {code}")
                except Exception as e:
                    print(f"⚠ Failed to fetch TDS '{filename}' for {code}: {e}")
                break

    # Fallback: if exactly 1 unmatched code and 1 unmatched file remain, auto-map
    unmatched_codes = codes - set(mapping.keys())
    unmatched_files = [f for f in tds_files if f["name"] not in matched_files]
    if len(unmatched_codes) == 1 and len(unmatched_files) == 1:
        code = next(iter(unmatched_codes))
        file_info = unmatched_files[0]
        try:
            local_path = fetch_from_sharepoint_temp(graph_client, file_info["path"])
            if local_path:
                mapping[code] = local_path
                print(f"✅ Auto-mapped TDS: {file_info['name']} → material {code} (single unmatched pair)")
        except Exception as e:
            print(f"⚠ Failed to fetch auto-mapped TDS '{file_info['name']}' for {code}: {e}")

    print(f"📦 TDS mapping ready: {len(mapping)}/{len(codes)} materials matched")
    return mapping


# 🔹 Main process flow
async def flow_of_process_according_to_step(page, current_position: int, graph_client: Any, title: str, company_name: str, rfp_id: str = None) -> bool:
    # Log start of submit flow for this RFP
    try:
        log_event("RFP", "Submit", "Start", f"Begin submit flow for '{title}'", title)
    except Exception:
        pass
    if current_position != 2:
        for _ in range(1):
            current_position = await go_to_step(page, 2)
            if current_position == 2:
                break
        if current_position != 2:
            print("❌ Could not reach Step 2")
            try:
                log_event("RFP", "Submit", "Fail", "Could not reach Step 2", title)
            except Exception:
                pass
            return False
    
    print("Reach Out to secound Step")
    try:
        log_event("RFP", "Submit", "Step", "At Step 2 (Terms/Agreement)", title)
    except Exception:
        pass

    await page.wait_for_timeout(1000)
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight);")

    print("Click on radio button #_x3fmod")
    if await page.locator("#_x3fmod").is_visible(timeout=5000):
        success = await safe_radio_click(page, "_x3fmod")
        if success:
            await safe_click(page, "#_ali5ud")
            print("✅ Clicked OK button")
            await safe_click(page, "#_kfai0c")
            print("✅ Agreement confirmed")
            try:
                log_event("RFP", "Submit", "Success", "Agreement confirmed", title)
            except Exception:
                pass
        else:
            print("❌ Could not click agreement checkbox, skipping to Done button")
            await safe_click(page, "#_bywhoc")
            print("✅ Clicked Done button")
            try:
                log_event("RFP", "Submit", "Warning", "Agreement checkbox not clickable, clicked Done", title)
            except Exception:
                pass
    else:
        await safe_click(page, "#_bywhoc")
        print("✅ Clicked Done button")
        try:
            log_event("RFP", "Submit", "Info", "Agreement section not visible, clicked Done", title)
        except Exception:
            pass

    await page.wait_for_timeout(5000)

    position = await get_wizstep_position(page)
    if position != 3:
        await go_to_step(page, 3)
    try:
        log_event("RFP", "Submit", "Step", "At Step 3 (Pricing)", title)
    except Exception:
        pass

    await safe_click(page, "#text__rkuw9c")
    print("✅ Currency dropdown opened")
    await safe_click(page, "#_rkuw9c89")
    print("✅ Selected SAR currency")
    try:
        log_event("RFP", "Submit", "Success", "Currency set to SAR", title)
    except Exception:
        pass

    await page.wait_for_timeout(5000)
    await page.get_by_text("Select Using Excel").click(timeout=15000)

    await page.wait_for_timeout(5000)
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.2);")
    await page.wait_for_timeout(10000)
    
    download_button = page.locator("button[title*='Download Content']")

    try:
        await download_button.click(timeout=5000)
        try:
            log_event("RFP", "Submit", "Click", "Clicked 'Download Content'", title)
        except Exception:
            pass
    except Exception:
        await page.get_by_text("Select Using Excel").click()
        # await download_button.click()
        try:
            log_event("RFP", "Submit", "Click", "Clicked 'Download Content' after re-opening menu", title)
        except Exception:
            pass
    
    # Determine the lookup title — user's rfp_id is what was used during upload
    lookup_title = rfp_id if rfp_id else title
    print(f"🔍 Fetching Excel for submission | rfp_id='{rfp_id}' | portal title='{title}'")

    # Build all folder paths to try (in priority order)
    # Priority 1: rfp-upload-file folder using rfp_id (matches upload path exactly)
    # Priority 2: rfp-upload-file folder using portal title (fallback)
    # Priority 3: downloaded-rfp folder using rfp_id
    # Priority 4: downloaded-rfp folder using portal title
    upload_path = None
    upload_filename = None

    titles_to_try = []
    if rfp_id and clean_rfp_title(rfp_id) != clean_rfp_title(title):
        titles_to_try.append(rfp_id)
    titles_to_try.append(title)

    # ── Step 1: Try rfp-upload-file folder (latest uploaded file) ──
    for try_title in titles_to_try:
        folder_sp = get_sharepoint_rfp_savedrfp_path(try_title, company_name)
        print(f"📂 Looking for latest Excel in rfp-upload-file: '{folder_sp}'")
        try:
            content, filename = graph_client.get_latest_excel_from_folder(folder_sp)
            temp_path = Path(tempfile.gettempdir()) / filename
            data = content.read()
            if not data:
                raise RuntimeError("Empty file")
            with open(temp_path, "wb") as f:
                f.write(data)
            upload_path = str(temp_path)
            upload_filename = filename
            print(f"✅ Latest Excel from rfp-upload-file: '{filename}' → {upload_path}")
            break
        except Exception as e:
            print(f"⚠️ rfp-upload-file lookup failed for '{try_title}': {e}")
            continue

    # ── Step 2: Fallback to downloaded-rfp folder ──
    if not upload_path:
        for try_title in titles_to_try:
            folder_sp = get_sharepoint_rfp_material_path(try_title, company_name)
            print(f"📂 Fallback: looking for latest Excel in downloaded-rfp: '{folder_sp}'")
            try:
                content, filename = graph_client.get_latest_excel_from_folder(folder_sp)
                temp_path = Path(tempfile.gettempdir()) / filename
                data = content.read()
                if not data:
                    raise RuntimeError("Empty file")
                with open(temp_path, "wb") as f:
                    f.write(data)
                upload_path = str(temp_path)
                upload_filename = filename
                print(f"✅ Latest Excel from downloaded-rfp: '{filename}' → {upload_path}")
                break
            except Exception as e:
                print(f"⚠️ downloaded-rfp lookup failed for '{try_title}': {e}")
                continue

    if not upload_path:
        raise RuntimeError(
            f"❌ Could not find any Excel file in rfp-upload-file or downloaded-rfp "
            f"for '{lookup_title}' (company: '{company_name}'). "
            f"Please upload the filled Excel file first."
        )

    await page.locator("input[type='file']").set_input_files(upload_path)
    await page.wait_for_timeout(9000)
    import_clicked = await safe_click(page, "button[title*='Import Excel Bidding']")
    if not import_clicked:
        print("❌ Failed to click 'Import Excel Bidding' button - Excel import may not work")
        try:
            log_event("RFP", "Submit", "Fail", "Could not click 'Import Excel Bidding' button", title)
        except Exception:
            pass
        return False
    print("Clicked Upload button")
    try:
        log_event("RFP", "Submit", "Upload", f"Imported Excel bidding from {Path(upload_path).name}", title)
    except Exception:
        pass

    await page.wait_for_timeout(5000)

    # ── Check if Ariba portal showed a validation error after Excel import ──
    # Must check BEFORE proceeding — portal shows inline errors immediately after import
    ariba_error_text = None
    ariba_error_screenshot = None
    try:
        error_selectors = [
            ".portletError",
            ".messageError",
            "[id*='errorMessage']",
            ".alertMessage",
            "[class*='errorMessageText']",
            "[class*='error'][class*='text']",
            ".w-messageBox.w-error",
            "#PageErrorPanel .msgText",
            "#slidingErrorMsgContent .msgText",
            "#slidingErrorMsg .msgText",
        ]
        for selector in error_selectors:
            err_el = page.locator(f"{selector}:visible")
            if await err_el.count() > 0:
                text = (await err_el.first.inner_text()).strip()
                if text:
                    ariba_error_text = text
                    break
    except Exception:
        pass

    if ariba_error_text:
        # Capture screenshot RIGHT NOW — error dialog is still visible on screen
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            shot_dir = os.path.join(os.getcwd(), "LOGS")
            os.makedirs(shot_dir, exist_ok=True)
            ariba_error_screenshot = os.path.join(shot_dir, f"ariba_excel_error_{ts}.png")
            await page.screenshot(path=ariba_error_screenshot, full_page=True)
            print(f"[Screenshot] Ariba error captured: {ariba_error_screenshot}")
        except Exception as ss_err:
            print(f"[WARN] Could not capture Ariba error screenshot: {ss_err}")
        try:
            log_event("RFP", "Submit", "Fail", f"Ariba portal rejected Excel file: {ariba_error_text}", title)
        except Exception:
            pass
        raise RuntimeError(f"Ariba portal rejected the Excel file — {ariba_error_text}")

    # Click "Use selected lots" - use safe_click with error handling
    lots_clicked = await safe_click(page, "button[title*='Use selected lots']")
    if lots_clicked:
        print("✅ Clicked 'Use selected lots'")
    else:
        print("⚠️ 'Use selected lots' button not found or not clickable - may not be required for this RFP")
    await page.wait_for_timeout(5000)
    try:
        log_event("RFP", "Submit", "Click", f"'Use selected lots' clicked: {lots_clicked}", title)
    except Exception:
        pass

    # ── Check for Ariba portal page-level errors after "Use selected lots" ──
    portal_error_after_lots = await get_page_error_panel_message(page)
    if portal_error_after_lots:
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            shot_dir = os.path.join(os.getcwd(), "LOGS")
            os.makedirs(shot_dir, exist_ok=True)
            shot_path = os.path.join(shot_dir, f"ariba_portal_error_{ts}.png")
            await page.screenshot(path=shot_path, full_page=True)
            print(f"[Screenshot] Portal error captured: {shot_path}")
        except Exception:
            pass
        try:
            log_event("RFP", "Submit", "Fail", f"Ariba portal error: {portal_error_after_lots}", title)
        except Exception:
            pass
        raise RuntimeError(f"Ariba portal error: {portal_error_after_lots}")

    # Handle currency change warning (may or may not appear — check twice with delay)
    currency_confirmed = False
    for attempt in range(2):
        try:
            currency_dialog = page.locator('#currencyChangeWarningConfirmationId:visible')
            if await currency_dialog.count() > 0:
                await safe_click(page, '#currencyChangeWarningConfirmationId button[title="OK"]')
                print("✅ Currency change warning confirmed")
                currency_confirmed = True
                break
            elif attempt == 0:
                print("ℹ️ Currency dialog not visible yet, waiting 3s and retrying...")
                await page.wait_for_timeout(3000)
            else:
                print("ℹ️ No currency change warning dialog appeared")
        except Exception as e:
            print(f"⚠️ Currency change warning handling (attempt {attempt + 1}): {e}")
            if attempt == 0:
                await page.wait_for_timeout(3000)

    # Click the correct OK inside the visible import confirmation dialog
    try:
        dialog = page.locator('#importConfirmationId:visible')
        await dialog.wait_for(state='visible', timeout=15000)

        ok_btn = dialog.get_by_role('button', name='OK').locator(':visible').first
        await expect(ok_btn).to_be_visible()
        await expect(ok_btn).to_be_enabled()
        await ok_btn.click()
        print("✅ Import confirmation dialog confirmed")
    except Exception as e:
        print(f"⚠️ Import confirmation dialog not found or already dismissed: {e}")
        # ── Check for portal page-level error that may have blocked the dialog ──
        portal_error_msg = await get_page_error_panel_message(page)
        if portal_error_msg:
            try:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                shot_dir = os.path.join(os.getcwd(), "LOGS")
                os.makedirs(shot_dir, exist_ok=True)
                shot_path = os.path.join(shot_dir, f"ariba_portal_error_{ts}.png")
                await page.screenshot(path=shot_path, full_page=True)
                print(f"[Screenshot] Portal error captured: {shot_path}")
            except Exception:
                pass
            try:
                log_event("RFP", "Submit", "Fail", f"Ariba portal error blocked import confirmation: {portal_error_msg}", title)
            except Exception:
                pass
            raise RuntimeError(f"Ariba portal error: {portal_error_msg}")
        # Try alternate approach - click any visible OK button in the import confirmation
        try:
            await safe_click(page, '#importConfirmationId button[title="OK"]')
        except Exception:
            pass
    try:
        log_event("RFP", "Submit", "Success", "Confirmed import dialog", title)
    except Exception:
        pass

    # Attached Files after uploading excel file with their respective sections
    # Use rfp_id for TDS lookup since that's how files were uploaded
    tds_title = rfp_id if rfp_id else title
    materials_files = await build_materials_dict_from_excel_reuse(upload_path, graph_client, tds_title, company_name=company_name)
    print("materials_files:-",materials_files)
    # If no materials found with rfp_id, try with portal title as fallback
    if not materials_files and rfp_id and rfp_id != title:
        print(f"🔄 No TDS files found with rfp_id '{rfp_id}', trying portal title '{title}'...")
        materials_files = await build_materials_dict_from_excel_reuse(upload_path, graph_client, title, company_name=company_name)
        print("materials_files (fallback):-",materials_files)

    await upload_attachments_via_bidding_console(page, materials_files)
    try:
        log_event("RFP", "Submit", "Success", f"Uploaded {len(materials_files)} attachments", title)
    except Exception:
        pass
    
    # Click on Submit button
    # await safe_click(page, "button[title*='Submit Entire Response']")
    # print("✅ Clicked Submit button")
    
    save_clicked = await safe_click(page, "button[title*='Save your response; it will not be submitted to the owner']")
    if not save_clicked:
        print("❌ Save draft button not found or not clickable")
        try:
            log_event("RFP", "Submit", "Fail", "Save draft button not found", title)
        except Exception:
            pass
        return False
    print("✅ Clicked Save draft button")
    await page.wait_for_timeout(5000)

    # Verify save was accepted — check for portal error after save
    save_error = None
    try:
        error_selectors = [".portletError", ".messageError", "[id*='errorMessage']", ".alertMessage"]
        for selector in error_selectors:
            err_el = page.locator(f"{selector}:visible")
            if await err_el.count() > 0:
                text = (await err_el.first.inner_text()).strip()
                if text:
                    save_error = text
                    break
    except Exception:
        pass

    if save_error:
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            shot_dir = os.path.join(os.getcwd(), "LOGS")
            os.makedirs(shot_dir, exist_ok=True)
            shot_path = os.path.join(shot_dir, f"ariba_save_error_{ts}.png")
            await page.screenshot(path=shot_path, full_page=True)
            print(f"[Screenshot] Save error captured: {shot_path}")
        except Exception:
            pass
        try:
            log_event("RFP", "Submit", "Fail", f"Ariba rejected save draft: {save_error}", title)
        except Exception:
            pass
        raise RuntimeError(f"Ariba portal rejected save draft — {save_error}")

    try:
        log_event("RFP", "Submit", "Success", "Saved draft (not submitted)", title)
    except Exception:
        pass

    try:
        log_event("RFP", "Submit", "Complete", f"Submit flow complete for '{title}'", title)
    except Exception:
        pass
    return True

# 🔹 High-level RFP submission
async def submit_rfp(page, data: List[Dict[str, str]], rfp_id: str, graph_client: Any, company_name: str) -> List[Dict[str, str]]:
   
    filtered_data = []
    for row in data:
        title = row.get("Title") or ""
        # Here Checking the RFP ID is matching with the Title portal
        if rfp_ids_match(rfp_id, title):
            filtered_data.append(row)
            print(f"✅ Found matching RFP: '{title}'")

    if not filtered_data:
        print(f"⚠ No RFP found with ID '{rfp_id}' in data.")
        # Return a failure indicator - NOT empty list (empty list = success)
        return [{"Title": rfp_id, "error": "RFP not found in scraped portal data. The portal scraping may have failed or the RFP does not exist."}]

    async def _screenshot_new_page(new_page, label: str) -> Optional[str]:
        """Take a screenshot from the RFP tab before it's closed."""
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            shot_dir = os.path.join(os.getcwd(), "LOGS")
            os.makedirs(shot_dir, exist_ok=True)
            path = os.path.join(shot_dir, f"{label}_{ts}.png")
            await new_page.screenshot(path=path, full_page=True)
            print(f"[Screenshot] Captured from RFP tab: {path}")
            return path
        except Exception as ss_err:
            print(f"[WARN] Could not capture RFP tab screenshot: {ss_err}")
            return None

    async def attempt_submit_rfp(row: Dict[str, str], main_page):
        title = (row.get("Title") or "").strip()
        link = (row.get("Link") or "").strip()
        print(f"\n➡ Processing RFP: {title}")
        if not link:
            print(f"⚠ No link for {title}, skipping.")
            return {"error": "No link found for this RFP", "screenshot": None}

        new_page = None
        try:
            async with main_page.context.expect_page() as new_page_info:
                await main_page.evaluate(f"window.open('{link}', '_blank');")

            new_page = await new_page_info.value
            await new_page.wait_for_load_state()

            current_position = await get_wizstep_position(new_page)
            if await flow_of_process_according_to_step(new_page, current_position, graph_client=graph_client, title=title, company_name=company_name, rfp_id=rfp_id):

                print(f"✅ RFP '{title}' processed successfully.")
                # Update participation status to "saved_draft"
                try:
                    from helpers.core_helper import update_rfp_participation_status
                    status_updated = update_rfp_participation_status(rfp_id, "saved_draft")
                    if not status_updated:
                        print(f"⚠️ Could not update participation status for RFP: {rfp_id}")
                except Exception as status_err:
                    print(f"⚠️ Error updating participation status: {status_err}")
                try:
                    await new_page.close()
                except Exception:
                    pass
                return True
            else:
                print(f"⚠ Failed to process RFP: {title}")
                shot = await _screenshot_new_page(new_page, "submit_rfp_failure")
                try:
                    await new_page.close()
                except Exception:
                    pass
                return {"error": "Submission flow returned failure (check logs for details)", "screenshot": shot}

        except Exception as e:
            print(f"❌ Error processing RFP '{title}': {e}")
            shot = None
            if new_page:
                shot = await _screenshot_new_page(new_page, "submit_rfp_error")
                try:
                    await new_page.close()
                except Exception:
                    pass
            return {"error": str(e), "screenshot": shot}

    missing = []
    for row in filtered_data:
        result = await attempt_submit_rfp(row, page)
        if result is not True:
            row_copy = dict(row)
            if isinstance(result, dict):
                if result.get("error"):
                    row_copy["submit_error"] = result["error"]
                if result.get("screenshot"):
                    row_copy["submit_screenshot"] = result["screenshot"]
            missing.append(row_copy)

    return missing
