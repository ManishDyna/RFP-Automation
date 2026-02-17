import time
import re
from playwright.async_api import Page, expect
from typing import List, Dict, Any, Optional
import re
import asyncio
from typing import Optional
import tempfile
from pathlib import Path

# 🔹 Get all wizStep elements or current step position (from submit_rfp.py)
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

# 🔹 Navigate to a specific wizard step (from submit_rfp.py)
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
                print(f"✅ Successfully navigated to Step {step_index}")
                return step_index
            else:
                print(f"⚠ Target step {step_index}, but current position is {new_position}")

        except Exception as e:
            print(f"⚠ go_to_step attempt {attempt+1} failed: {e}")
            await asyncio.sleep(1)

    print(f"❌ Failed to navigate to Step {step_index} after {max_attempts} attempts")
    return None

# 🔹 Helper: Safe click
async def safe_click(page, selector: str):
    try:
        await page.click(selector, timeout=8000)
        return True
    except Exception as e:
        print(f"⚠ safe_click failed for {selector}: {e}")
        return False

# 🔹 Main process flow
async def flow_of_process_according_to_step(page, current_position, title='-'):
    # Start logging for decline flow
    try:
        from core.log_events import log_event
        log_event("RFP", "Decline", "Start", f"Begin decline flow for '{title}'", title)
    except Exception:
        pass
    # Ensure Step 1 (for decline, we want to be on step 1)
    if current_position != 1:
        print(f"🔄 Current position: {current_position}, need to go to Step 1")
        for _ in range(3):
            result = await go_to_step(page, 1)
            if result == 1:
                current_position = 1
                break
        if current_position != 1:
            print("❌ Could not reach Step 1")
            try:
                from core.log_events import log_event
                log_event("RFP", "Decline", "Fail", "Could not reach Step 1", title)
            except Exception:
                pass
            return False
    
    print("➡ At Step 1: Decline RFP")
    try:
        from core.log_events import log_event
        log_event("RFP", "Decline", "Step", "At Step 1 (Decline)", title)
    except Exception:
        pass

    # Click "Decline to Respond" button
    # decline_button_clicked = await safe_click(page, "//button[span[contains(text(),'Decline to Respond')]]")
    # if not decline_button_clicked:
    #     print("❌ Failed to click 'Decline to Respond' button")
    #     try:
    #         from core.log_events import log_event
    #         log_event("RFP", "Decline", "Fail", "Decline to Respond button not clickable", title)
    #     except Exception:
    #         pass
    #     return False
    # else:
    #     try:
    #         from core.log_events import log_event
    #         log_event("RFP", "Decline", "Click", "Clicked 'Decline to Respond'", title)
    #     except Exception:
    #         pass
    
    await page.wait_for_timeout(5000)

    # Fill textarea using JS (like Selenium execute_script)
    try:
        await page.evaluate("""
        const textarea = document.querySelector("textarea");
        if (textarea) {
                textarea.value = "We Don't Know Right Now";
                // Trigger input event safely
                const event = document.createEvent('HTMLEvents');
                event.initEvent('input', true, true);
                textarea.dispatchEvent(event);
            }
        """)
        print("✅ Filled decline reason textarea")
        try:
            from core.log_events import log_event
            log_event("RFP", "Decline", "Success", "Filled decline reason", title)
        except Exception:
            pass
    except Exception as e:
        print(f"⚠ Failed to fill textarea: {e}")
        try:
            from core.log_events import log_event
            log_event("RFP", "Decline", "Fail", f"Failed to fill decline reason: {e}", title)
        except Exception:
            pass
        return False
    
    await page.wait_for_timeout(10000)

    # Optional: Add confirmation logic here if needed
    # await safe_click(page, "//button[@title='OK Button']")

    print(f"✅ Successfully declined RFP: {title}")
    try:
        from core.log_events import log_event
        log_event("RFP", "Decline", "Complete", f"Declined '{title}'", title)
    except Exception:
        pass
    return True

# 🔹 High-level RFP decline function
async def decline_rfps(page, data, company_name: str, rfp_id=""):
    context = page.context

    # 🔍 Filter data (add fuzzy matching like in submit_rfp)
    def normalize_filename(name: str) -> str:
        """Normalize for fuzzy matching"""
        return re.sub(r'[^a-z0-9]', '', name.lower())

    def rfp_ids_match(search_id: str, title: str) -> bool:
        """Check if RFP IDs match using normalization"""
        if not search_id or not title:
            return False
        
        normalized_search = normalize_filename(search_id)
        normalized_title = normalize_filename(title)
        
        return normalized_search in normalized_title

    print(f"🔍 Searching for RFP ID: '{rfp_id}' (normalized: '{normalize_filename(rfp_id)}')")
    
    filtered_data = []
    for row in data:
        title = row.get("Title") or ""
        if rfp_id and rfp_ids_match(rfp_id, title):
            filtered_data.append(row)
            print(f"✅ Found matching RFP: '{title}'")

    print(f"📊 Found {len(filtered_data)} matching RFP(s) out of {len(data)} total RFPs")

    if not filtered_data:
        print(f"⚠ No RFP found matching ID '{rfp_id}'")
        return []

    # --- Fix 1: Skip RFPs already declined in Dataverse ---
    try:
        from helpers.core_helper import get_rfp_activity_data_from_db
        from core.log_events import log_event
        db_rows = get_rfp_activity_data_from_db()
        for row in filtered_data[:]:  # iterate over copy
            title = (row.get("Title") or "").strip()
            for db_row in db_rows:
                if db_row.get("RFP_ID") == title:
                    participated = (db_row.get("participated") or "").lower().strip()
                    if participated == "declined":
                        print(f"⏩ Skipping already-declined RFP: {title}")
                        log_event("RFP", "Decline", "Skip", f"Already declined: {title}", title)
                        filtered_data.remove(row)
                    break
    except Exception as db_err:
        print(f"⚠ Could not check Dataverse for decline status: {db_err}")

    if not filtered_data:
        print(f"⚠ All matching RFPs are already declined")
        return []

    # --- Fix 2: Skip RFPs already participated on the portal ---
    for row in filtered_data[:]:  # iterate over copy
        portal_status = (row.get("Status") or "").strip().lower()
        title = (row.get("Title") or "").strip()
        if portal_status in ("declined", "submitted", "yes"):
            print(f"⏩ Skipping RFP with portal status '{portal_status}': {title}")
            try:
                from core.log_events import log_event
                log_event("RFP", "Decline", "Skip", f"Portal status is '{portal_status}'", title)
            except Exception:
                pass
            filtered_data.remove(row)

    if not filtered_data:
        print(f"⚠ No eligible RFPs to decline after filtering")
        return []

    async def attempt_decline_rfps(row):
        title = (row.get("Title") or "").strip()
        link = (row.get("Link") or "").strip()

        print(f"\n➡ Processing RFP: {title}")
        if not link:
            print(f"⚠ No link for {title}, skipping.")
            return False

        try:
            new_page = await context.new_page()
            try:
                from core.log_events import log_event
                log_event("RFP", "Decline", "Navigating", f"Navigating to RFP page: {link}", title)
            except Exception:
                pass
            await new_page.goto(link, wait_until="domcontentloaded", timeout=60000)
            try:
                from core.log_events import log_event
                log_event("RFP", "Decline", "Success", "Page navigation successful", title)
            except Exception:
                pass

            # Get current step position using the enhanced logic
            current_position = await get_wizstep_position(new_page)
            print(f"📍 Current position: {current_position}")

            if await flow_of_process_according_to_step(new_page, current_position, title=title):
                print(f"✅ RFP '{title}' declined successfully.")
                # Update participation status to "declined"
                try:
                    from helpers.core_helper import update_rfp_participation_status
                    status_updated = update_rfp_participation_status(rfp_id, "declined")
                    if not status_updated:
                        print(f"⚠️ Could not update participation status for RFP: {rfp_id}")
                except Exception as status_err:
                    print(f"⚠️ Error updating participation status: {status_err}")
                    # Don't fail the decline if status update fails

                try:
                    from core.log_events import log_event
                    log_event("RFP", "Decline", "Success", "Participation status set to Declined", title)
                except Exception as log_err:
                    print(f"⚠️ Error logging decline event: {log_err}")
                await new_page.wait_for_timeout(10000)
                await new_page.close()
                return True
            else:
                print(f"⚠ Failed to decline RFP: {title}")
                try:
                    from core.log_events import log_event
                    log_event("RFP", "Decline", "Fail", "Decline flow failed", title)
                except Exception as log_err:
                    print(f"⚠️ Error logging decline failure: {log_err}")
                await new_page.close()
                return False
                
        except Exception as e:
            print(f"❌ Error processing RFP '{title}': {e}")
            try:
                from core.log_events import log_event
                log_event("RFP", "Decline", "Fail", f"Exception: {e}", title)
            except Exception:
                pass
            try:
                await new_page.close()
            except:
                pass
            return False

    missing = []
    for row in filtered_data:
        if not await attempt_decline_rfps(row):
            missing.append(row)
    try:
        from core.log_events import log_event
        total = len(filtered_data)
        failed = len(missing)
        success = total - failed
        log_event("RFP", "Decline Batch", "Complete", f"Total: {total}, Success: {success}, Failed: {failed}")
    except Exception:
        pass
    return missing
