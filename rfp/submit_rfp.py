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
    Builds { material_code: local_pdf_path } using new folder structure:
      RFP-logs/ALLRFPs/CompanyName/RFP_title/TDS-files/{material}_TDS.pdf
    Uses fetch_from_sharepoint_temp to cache locally.
    """
    codes = extract_materials_from_excel(excel_local_path, include_details=False)
    print("codes:-",codes)
    mapping: Dict[str, str] = {}
    
    # Use new folder structure: RFP-logs/ALLRFPs/CompanyName/RFP_title/TDS-files/
    for code in codes:
        sp_path = get_sharepoint_rfp_tds_path(rfp_title, company_name, code)
        print("sp_path:-",sp_path)
        try:
            local_path = fetch_from_sharepoint_temp(graph_client, sp_path)
            print("local_path:-",local_path)
            if local_path:
                mapping[code] = local_path
        except Exception as e:
            print(f"🕳 Missing or unreadable TDS for {code}: {sp_path} ({e})")

    print(f"📦 TDS mapping ready for {len(mapping)} materials.")
    return mapping


# 🔹 Main process flow
async def flow_of_process_according_to_step(page, current_position: int, graph_client: Any, title: str, company_name: str) -> bool:
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
    await page.get_by_text("Select Using Excel").click()
    
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
        await download_button.click()
        try:
            log_event("RFP", "Submit", "Click", "Clicked 'Download Content' after re-opening menu", title)
        except Exception:
            pass
    
    print("Before Fetching RFP file title:-",title)

    # Try savedrfp folder first (filled Excel), then downloaded-rfp folder, then old structure
    clean_title = clean_rfp_title(title)
    
    upload_path = None
    # Try savedrfp folder first (contains filled data) - try both .xls and .xlsx
    for ext in ['.xls', '.xlsx']:
        try:
            sp_path_savedrfp = get_sharepoint_rfp_savedrfp_path(title, company_name, f"{clean_title}{ext}")
            print(f"sp_path (savedrfp):- {sp_path_savedrfp}")
            upload_path = fetch_from_sharepoint_temp(graph_client, sp_path_savedrfp)
            print(f"📂 Upload path (savedrfp - filled Excel): {upload_path}")
            break
        except Exception as e:
            print(f"⚠️ Savedrfp {ext} not found: {e}")
            continue
    
    # If not found in rfp-upload-file, try downloaded-rfp folder (original Excel)
    if not upload_path:
        for ext in ['.xls', '.xlsx']:
            try:
                sp_path_material = get_sharepoint_rfp_material_path(title, company_name, f"{clean_title}{ext}")
                print(f"sp_path (material):- {sp_path_material}")
                upload_path = fetch_from_sharepoint_temp(graph_client, sp_path_material)
                print(f"📂 Upload path (downloaded-rfp - original): {upload_path}")
                break
            except Exception as e:
                print(f"⚠️ downloaded-rfp {ext} not found: {e}")
                continue
    
    # If still not found, try old structure as last resort
    if not upload_path:
        for ext in ['.xls', '.xlsx']:
            try:
                sp_path_old = f"{SP_BASE_FOLDER_RFP_UPLOAD_FILES}/{title}{ext}"
                print(f"sp_path (old):- {sp_path_old}")
                upload_path = fetch_from_sharepoint_temp(graph_client, sp_path_old)
                print(f"📂 Upload path (old structure): {upload_path}")
                break
            except Exception as e:
                print(f"⚠️ Old structure {ext} not found: {e}")
                continue
    
    if not upload_path:
        raise RuntimeError(f"Could not find RFP file in rfp-upload-file, downloaded-rfp, or old structure for '{title}'")

    await page.locator("input[type='file']").set_input_files(upload_path)
    await page.wait_for_timeout(9000)
    await safe_click(page, "button[title*='Import Excel Bidding']")
    print("Clicked Upload button")
    try:
        log_event("RFP", "Submit", "Upload", f"Imported Excel bidding from {Path(upload_path).name}", title)
    except Exception:
        pass

    await page.wait_for_timeout(5000)
    await page.locator("button[title*='Use selected lots']").click()
    await page.wait_for_timeout(5000)
    try:
        log_event("RFP", "Submit", "Click", "Clicked 'Use selected lots'", title)
    except Exception:
        pass

    await safe_click(page, '#currencyChangeWarningConfirmationId button[title="OK"]')

    # Click the correct OK inside the visible import confirmation dialog
    dialog = page.locator('#importConfirmationId:visible')
    await dialog.wait_for(state='visible', timeout=15000)

    ok_btn = dialog.get_by_role('button', name='OK').locator(':visible').first
    await expect(ok_btn).to_be_visible()
    await expect(ok_btn).to_be_enabled()
    await ok_btn.click()
    try:
        log_event("RFP", "Submit", "Success", "Confirmed import dialog", title)
    except Exception:
        pass

    # Attached Files after uploading excel file with their respective sections
    materials_files = await build_materials_dict_from_excel_reuse(upload_path, graph_client, title, company_name=company_name)
    print("materials_files:-",materials_files)

    await upload_attachments_via_bidding_console(page, materials_files)
    try:
        log_event("RFP", "Submit", "Success", f"Uploaded {len(materials_files)} attachments", title)
    except Exception:
        pass
    
    # Click on Submit button
    # await safe_click(page, "button[title*='Submit Entire Response']")
    # print("✅ Clicked Submit button")
    
    await safe_click(page, "button[title*='Save your response; it will not be submitted to the owner']")
    print("✅ Clicked Ok button")
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
        return []

    async def attempt_submit_rfp(row: Dict[str, str], main_page) -> bool:
        title = (row.get("Title") or "").strip()
        link = (row.get("Link") or "").strip()
        print(f"\n➡ Processing RFP: {title}")
        if not link:
            print(f"⚠ No link for {title}, skipping.")
            return False

        try:
            async with main_page.context.expect_page() as new_page_info:
                await main_page.evaluate(f"window.open('{link}', '_blank');")
            
            new_page = await new_page_info.value
            await new_page.wait_for_load_state()

            current_position = await get_wizstep_position(new_page)
            if await flow_of_process_according_to_step(new_page, current_position, graph_client=graph_client, title=title, company_name=company_name):
                
                print(f"✅ RFP '{title}' processed successfully.")
                # Update participation status to "Submitted"
                from helpers.core_helper import update_rfp_participation_status
                # Use title here because RFP_ID in Dataverse is stored as full title
                update_rfp_participation_status(rfp_id, "saved_draft")
                return True
            else:
                print(f"⚠ Failed to process RFP: {title}")
                await new_page.close()
                return False

        except Exception as e:
            print(f"❌ Error processing RFP '{title}': {e}")
            return False

    missing = []
    for row in filtered_data:
        if not await attempt_submit_rfp(row, page):
            missing.append(row)
           
    return missing
