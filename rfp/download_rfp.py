from helpers.core_helper import *
from core.common_imports import *
import re

async def extract_rfp_details_inner_text(page):
    """Use inner_text() which is closer to what you see in browser"""
    owner_name = None
    publish_time = None
    
    try:
        print("  🔍 DEBUG: Starting extract_rfp_details_inner_text function")
        
        # Try multiple selectors to find the table
        selectors_to_try = [
            'div.wideLabels table td',
            'table.wideLabels td',
            'table td',
            'div.wideLabels td',
            '.w-tbl-cell',
            'div[class*="label"] table td'
        ]
        
        all_cells = None
        cell_count = 0
        used_selector = None
        
        for selector in selectors_to_try:
            try:
                locator = page.locator(selector)
                count = await locator.count()
                print(f"  🔍 DEBUG: Selector '{selector}' found {count} cells")
                if count > 0:
                    all_cells = locator
                    cell_count = count
                    used_selector = selector
                    print(f"  ✅ DEBUG: Using selector: {selector}")
                    break
            except Exception as e:
                print(f"  ⚠️  DEBUG: Selector '{selector}' failed: {e}")
                continue
        
        if not all_cells or cell_count == 0:
            print(f"  ❌ DEBUG: No table cells found with any selector")
            print(f"  🔍 DEBUG: Trying to get all text from page for analysis...")
            try:
                body_text = await page.locator('body').inner_text()
                # Look for owner and publish patterns in full text
                lines = body_text.split('\n')
                for i, line in enumerate(lines):
                    line_lower = line.strip().lower()
                    if not owner_name and any(keyword in line_lower for keyword in ['owner', 'owned by', 'created by']):
                        # Look for name in nearby lines
                        for j in range(max(0, i-2), min(len(lines), i+3)):
                            potential = lines[j].strip()
                            # Names can have commas (e.g., "Last, First" format)
                            if (len(potential) > 3 and 
                                re.match(r'^[A-Za-z\s\.\',\-]+$', potential) and
                                not any(kw in potential.lower() for kw in ['owner', 'publish', 'time', 'date', 'currency', 'commodity', 'event', 'type', 'loading', 'ariba', 'supplier', 'rfp'])):
                                owner_name = potential
                                print(f"  ✅ DEBUG: Found owner in full text: {owner_name} (line {j})")
                                break
                    
                    if not publish_time and any(keyword in line_lower for keyword in ['publish', 'published', 'created', 'posted']):
                        # Look for date/time pattern
                        if re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}.*\d{1,2}:\d{2}', line):
                            publish_time = line.strip()
                            print(f"  ✅ DEBUG: Found publish time in full text: {publish_time} (line {i})")
                            break
            except Exception as e:
                print(f"  ⚠️  DEBUG: Error analyzing full text: {e}")
            
            return {'owner': owner_name, 'publish_time': publish_time}
        
        print(f"  🔍 DEBUG: Processing {cell_count} cells from selector: {used_selector}")
        
        # Process each cell
        for i in range(cell_count):
            try:
                # Use inner_text() instead of text_content()
                cell_text = await all_cells.nth(i).inner_text()
                cell_text_original = cell_text.strip()
                cell_text_lower = cell_text_original.lower()
                
                if i < 10:  # Debug first 10 cells
                    print(f"  🔍 DEBUG: Cell {i}: '{cell_text_original[:50]}'")
                
                # Check for owner patterns
                if not owner_name and any(keyword in cell_text_lower for keyword in ['owner', 'owner:', 'owned by', 'created by']):
                    print(f"  🎯 DEBUG: Found owner pattern in cell {i}: '{cell_text_original}'")
                    # Look in nearby cells
                    for j in range(max(0, i-2), min(cell_count, i+3)):
                        try:
                            potential_name = await all_cells.nth(j).inner_text()
                            potential_name = potential_name.strip()
                            print(f"  🔍 DEBUG: Checking cell {j} for owner name: '{potential_name}'")
                            
                            # Skip empty cells
                            if not potential_name or len(potential_name) <= 3:
                                print(f"  ⚠️  DEBUG: Cell {j} skipped - too short or empty")
                                continue
                            
                            # Check regex pattern (allows letters, spaces, commas, dots, hyphens, apostrophes)
                            # Explicitly include comma in the character class: [A-Za-z\s\.,'-]
                            regex_pattern = r'^[A-Za-z\s\.,\'-]+$'
                            regex_match = re.match(regex_pattern, potential_name)
                            print(f"  🔍 DEBUG: Cell {j} regex check - Pattern: {regex_pattern}, Text: '{potential_name}', Match: {regex_match is not None}")
                            
                            if regex_match:
                                print(f"  ✅ DEBUG: Regex matched for cell {j}")
                            else:
                                print(f"  ❌ DEBUG: Regex did NOT match for cell {j}")
                            
                            # Check for excluded keywords
                            excluded_keywords = ['owner', 'publish', 'time', 'date', 'currency', 'commodity', 'event', 'type', 'loading', 'ariba', 'supplier', 'portal', 'rfp']
                            has_excluded = any(keyword in potential_name.lower() for keyword in excluded_keywords)
                            print(f"  🔍 DEBUG: Cell {j} keyword check - Has excluded keywords: {has_excluded}")
                            
                            # Check if it looks like a name (contains letters, spaces, commas, dots, hyphens, apostrophes)
                            # Names can have commas (e.g., "Last, First")
                            if regex_match and not has_excluded:
                                owner_name = potential_name
                                print(f"  ✅✅✅ DEBUG: SUCCESSFULLY SET owner_name: {owner_name}")
                                log_event("RFP", "Extract Details", "Success", f"Found owner: {owner_name}")
                                break
                            else:
                                print(f"  ⚠️  DEBUG: Cell {j} rejected - regex_match: {regex_match is not None}, has_excluded: {has_excluded}")
                        except Exception as e:
                            print(f"  ⚠️  DEBUG: Error checking cell {j}: {e}")
                            import traceback
                            print(f"  🔍 DEBUG: Traceback: {traceback.format_exc()}")
                            continue
                
                # Check for publish time patterns
                if not publish_time and any(keyword in cell_text_lower for keyword in ['publish', 'published', 'created', 'posted', 'time:', 'date:']):
                    print(f"  🎯 DEBUG: Found publish pattern in cell {i}: '{cell_text_original}'")
                    for j in range(max(0, i-2), min(cell_count, i+3)):
                        try:
                            potential_time = await all_cells.nth(j).inner_text()
                            potential_time = potential_time.strip()
                            print(f"  🔍 DEBUG: Checking cell {j} for publish time: '{potential_time}'")
                            
                            # Try multiple date/time patterns
                            patterns = [
                                r'\d{1,2}/\d{1,2}/\d{4}.*\d{1,2}:\d{2}.*[AP]M',  # MM/DD/YYYY HH:MM AM/PM
                                r'\d{1,2}-\d{1,2}-\d{4}.*\d{1,2}:\d{2}',  # MM-DD-YYYY HH:MM
                                r'\d{4}-\d{2}-\d{2}.*\d{2}:\d{2}',  # YYYY-MM-DD HH:MM
                                r'\d{1,2}/\d{1,2}/\d{4}',  # MM/DD/YYYY
                            ]
                            
                            for pattern in patterns:
                                if re.search(pattern, potential_time, re.IGNORECASE):
                                    publish_time = potential_time
                                    print(f"  ✅ DEBUG: Found publish time: {publish_time}")
                                    log_event("RFP", "Extract Details", "Success", f"Found publish time: {publish_time}")
                                    break
                            
                            if publish_time:
                                break
                        except Exception as e:
                            print(f"  ⚠️  DEBUG: Error checking cell {j} for time: {e}")
                            continue
                
                # Break early if both found
                if owner_name and publish_time:
                    break
                    
            except Exception as e:
                print(f"  ⚠️  DEBUG: Error processing cell {i}: {e}")
                continue
        
        print(f"  🔍 DEBUG: Final result - owner_name: {owner_name}, publish_time: {publish_time}")
        return {'owner': owner_name, 'publish_time': publish_time}
        
    except Exception as e:
        error_msg = f"Error extracting RFP details: {str(e)}"
        print(f"  ❌ DEBUG: {error_msg}")
        import traceback
        print(f"  🔍 DEBUG: Traceback:\n{traceback.format_exc()}")
        log_event("RFP", "Extract Details", "Fail", error_msg)
        return {'owner': None, 'publish_time': None}


def process_folder(graph_client, folder, master_csv, company_name: str = None):
    """
    Process downloaded RFP Excel files, match materials with master CSV,
    and generate/upload a matched materials CSV.
    Optionally fetch the RFP activity log from Dataverse instead of CSV.
    If no local Excel files found, fetches from SharePoint.
    """
    log_event("RFP", "Process Folder", "Start", f"Processing folder: {folder}")
    excel_files = get_all_excel_files(folder)

    # If no local Excel files found, try to fetch from SharePoint
    if not excel_files and company_name:
        print(f"⚠️ No local Excel files found, fetching from SharePoint...")
        log_event("RFP", "Process Folder", "Downloading", "Fetching RFP files from SharePoint")
        try:
            downloaded_files = graph_client.download_rfp_files_from_sharepoint(
                company_name=company_name,
                local_output_dir=folder,
                sp_base_folder=SP_BASE_FOLDER
            )
            if downloaded_files:
                excel_files = downloaded_files
                log_event("RFP", "Process Folder", "Success", f"Downloaded {len(downloaded_files)} RFP files from SharePoint")
            else:
                log_event("RFP", "Process Folder", "Warning", "No RFP files found in SharePoint")
        except Exception as e:
            error_msg = f"Could not fetch RFP files from SharePoint: {e}"
            print(f"⚠️ {error_msg}")
            log_event("RFP", "Process Folder", "Fail", error_msg)

    if not excel_files:
        error_msg = "No Excel files found in folder or SharePoint"
        log_event("RFP", "Process Folder", "Fail", error_msg, "")
        raise FileNotFoundError(f"❌ {error_msg}")

    # 🔹 Download Master Material CSV if not exists locally
    try:
        print(f"🔄 Downloading 'Master material' from SharePoint...")
        log_event("RFP", "Download Master", "Downloading", "Fetching master material CSV from SharePoint")
        master_csv_path = graph_client.download_file_from_sharepoint(
            sp_path=f"{SP_BASE_FOLDER}/master-files/material.csv",
            local_path=master_csv
        )
        print(f"✅ Master file downloaded: {master_csv_path}")
        log_event("RFP", "Download Master", "Success", f"Master file downloaded: {master_csv_path}")
        master = pd.read_csv(master_csv_path)
    except Exception as e:
        error_msg = f"Could not download master file from SharePoint: {e}"
        log_event("RFP", "Download Master", "Fail", error_msg)
        raise FileNotFoundError(f"❌ {error_msg}")

    # 🔹 Find 'material' column in master CSV
    master_col = find_column_name(master.columns, "material")
    if not master_col:
        error_msg = "No 'material' column in master CSV"
        log_event("RFP", "Process Folder", "Fail", error_msg)
        raise ValueError(f"❌ {error_msg}")

    # 🔹 Download and load Keywords CSV for keyword matching
    keywords_list = []
    keywords_csv_local = os.path.join(OUTPUT_DIR, "unique_keywords.csv")
    try:
        print(f"🔄 Downloading 'unique_keywords' from SharePoint...")
        log_event("RFP", "Download Keywords", "Downloading", "Fetching unique keywords CSV from SharePoint")
        keywords_csv_path = graph_client.download_file_from_sharepoint(
            sp_path=f"{SP_BASE_FOLDER}/master-files/unique_keywords.csv",
            local_path=keywords_csv_local
        )
        keywords_df = pd.read_csv(keywords_csv_path)
        keywords_col = find_column_name(keywords_df.columns, "keywords") or find_column_name(keywords_df.columns, "keyword")
        if keywords_col:
            # Use to_dict('records') for better performance (faster than iterrows)
            for row in keywords_df.to_dict('records'):
                keyword_value = str(row.get(keywords_col, "")).strip()
                if keyword_value and keyword_value.lower() != 'nan':
                    for kw in keyword_value.split(','):
                        kw_clean = kw.strip().upper()
                        if kw_clean:
                            keywords_list.append(kw_clean)
        print(f"✅ Loaded {len(keywords_list)} keywords for matching")
        log_event("RFP", "Download Keywords", "Success", f"Loaded {len(keywords_list)} keywords for matching")
    except Exception as e:
        error_msg = f"Could not load keywords: {e}"
        print(f"⚠ {error_msg}")
        log_event("RFP", "Download Keywords", "Warning", error_msg)
        keywords_list = []  # Continue without keywords if file not found

    # 🔹 Load RFP activity log=
    print("🔄 Fetching RFP activity log from Dataverse...")
    log_event("RFP", "Fetch Activity Log", "Downloading", "Fetching RFP activity log from Dataverse")
    try:
        rows = get_rfp_activity_data_from_db()
        print("rows:-",rows)
        log_df = pd.DataFrame(rows)
        if log_df.empty:
            log_df = pd.DataFrame(columns=["RFP_ID", "Email_Status", "RFP_End_Date"])
        print(f"✅ Loaded {len(log_df)} rows from Dataverse")
        log_event("RFP", "Fetch Activity Log", "Success", f"Loaded {len(log_df)} rows from Dataverse")
    except Exception as e:
        error_msg = f"Could not fetch RFP log from Dataverse: {e}"
        print(f"⚠ {error_msg}")
        log_event("RFP", "Fetch Activity Log", "Fail", error_msg)
        log_df = pd.DataFrame(columns=["RFP_ID", "Email_Status", "RFP_End_Date"])
    
    print("log_df:-",log_df)
    
    all_matches = []
    not_mateched_files = []
    processed_rfps = set()
    files_processed = 0
    files_skipped = 0
    files_failed = 0

    # 🔹 Process each downloaded Excel file
    for excel_path in excel_files:
        file_name = os.path.basename(excel_path)
        rfp_id = os.path.splitext(file_name)[0]

        # Skip already emailed RFPs
        if not log_df.empty and rfp_id in log_df["RFP_ID"].astype(str).values:
            email_status = log_df.loc[log_df["RFP_ID"].astype(str) == rfp_id, "Email_Status"].values
            if email_status.size > 0 and str(email_status[0]).lower() == "sent":
                print(f"⏩ Skipping {rfp_id}, email already sent.")
                # log_event("RFP", "Process File", "Skip", f"Email already sent for RFP: {rfp_id}", rfp_id)
                files_skipped += 1
                continue

        processed_rfps.add(rfp_id)
        log_event("RFP", "Process File", "Processing", f"Processing file: {file_name}", rfp_id)

        try:
            df = pd.read_excel(excel_path, sheet_name="Other Content")
            log_event("RFP", "Process File", "Success", f"Successfully read Excel file: {file_name}", rfp_id)
            files_processed += 1
        except Exception as e:
            error_msg = f"Could not read {excel_path}: {e}"
            print(f"⚠ {error_msg}")
            log_event("RFP", "Process File", "Fail", error_msg, rfp_id)
            files_failed += 1
            continue

        col_name = find_column_name(df.columns, "name")
        if not col_name:
            log_event("RFP", "Process File", "Fail", f"Column 'name' not found in file: {file_name}", rfp_id)
            files_failed += 1
            continue
        
        # Find Description column for keyword matching
        col_desc = find_column_name(df.columns, "description")
        
        for idx, value in df[col_name].items():
            if pd.isna(value):
                continue
            
            # Get Name and Description text for keyword matching
            name_text = str(value) if not pd.isna(value) else ""
            description_text = str(df.iloc[idx][col_desc]) if col_desc and not pd.isna(df.iloc[idx][col_desc]) else ""
            
            for mat in re.findall(r'\d{9}', name_text):
                
                # Method 1: Exact Material Code Match
                matched_rows = master[master[master_col].astype(str) == mat]
                is_matched = not matched_rows.empty
                
                # Method 2: Keyword Matching (only if exact match failed)
                if not is_matched and keywords_list:
                    # Extract keywords from Name and Description (comma-separated)
                    name_keywords = extract_keywords_from_text(name_text)
                    desc_keywords = extract_keywords_from_text(description_text)
                    all_material_keywords = set(name_keywords + desc_keywords)
                    
                    # Check if any keyword from CSV matches any keyword from material
                    for csv_keyword in keywords_list:
                        # Check if CSV keyword appears in any material keyword
                        for mat_keyword in all_material_keywords:
                            if csv_keyword in mat_keyword or mat_keyword in csv_keyword:
                                is_matched = True
                                break
                        if is_matched:
                            break
                
                if is_matched:
                    # Get RFP End Date from log if available
                    RFP_End_Date = "-"
                    if not log_df.empty:
                        match_row = log_df.loc[log_df["RFP_ID"].astype(str) == str(rfp_id), "RFP_End_Date"]
                        if not match_row.empty:
                            RFP_End_Date = match_row.iloc[0]

                    # If matched by keyword but no exact code match, search master for rows with matching keywords
                    if matched_rows.empty and keywords_list:
                        # Try to find rows in master that contain the matched keywords
                        # Search in material code column and other text columns
                        name_keywords = extract_keywords_from_text(name_text)
                        desc_keywords = extract_keywords_from_text(description_text)
                        all_material_keywords = set(name_keywords + desc_keywords)
                        
                        # Search master CSV for rows containing any of the matched keywords
                        keyword_matched_rows = pd.DataFrame()
                        for mat_keyword in all_material_keywords:
                            if mat_keyword:
                                # Search in material column
                                temp_matches = master[master[master_col].astype(str).str.contains(mat_keyword, case=False, na=False)]
                                if not temp_matches.empty:
                                    keyword_matched_rows = pd.concat([keyword_matched_rows, temp_matches]).drop_duplicates()
                                
                                # Also search in other text columns if they exist
                                for col in master.columns:
                                    if col != master_col and master[col].dtype == 'object':
                                        try:
                                            temp_matches = master[master[col].astype(str).str.contains(mat_keyword, case=False, na=False)]
                                            if not temp_matches.empty:
                                                keyword_matched_rows = pd.concat([keyword_matched_rows, temp_matches]).drop_duplicates()
                                        except:
                                            pass
                        
                        if not keyword_matched_rows.empty:
                            matched_rows = keyword_matched_rows.head(1)  # Use first matching row
                    
                    # Create records from matched rows (use to_dict for better performance)
                    if not matched_rows.empty:
                        for record in matched_rows.to_dict('records'):
                            # Update with extra info
                            record.update({
                                "SourceFile": file_name,
                                "RFP_Title": rfp_id,
                                "RFP_End_Date": RFP_End_Date,
                                "TDS_file_path": get_sharepoint_rfp_tds_path(rfp_id, mat),
                                "RowNumber": idx + 2,
                                "ColumnName": col_name,
                                "ExtractedMaterial": mat
                            })
                            # Capture specific columns from Excel
                            for col_index in [2, 7, 13, 14, 17, 19, 22]:
                                if col_index - 1 < len(df.columns):
                                    header = df.columns[col_index - 1]
                                    record[header] = df.iloc[idx, col_index - 1]
                                else:
                                    record[f"MissingCol_{col_index}"] = None
                            all_matches.append(record)
                    else:
                        # Keyword matched but no row found in master - still create a record with material code
                        # This ensures we don't lose keyword-matched materials
                        record = {master_col: mat}  # Start with material code
                        # Add other columns from master with empty values
                        for col in master.columns:
                            if col not in record:
                                record[col] = None
                        
                        record.update({
                            "SourceFile": file_name,
                            "RFP_Title": rfp_id,
                            "RFP_End_Date": RFP_End_Date,
                            "TDS_file_path": get_sharepoint_rfp_tds_path(rfp_id, mat),
                            "RowNumber": idx + 2,
                            "ColumnName": col_name,
                            "ExtractedMaterial": mat,
                            "MatchMethod": "keyword"  # Indicate this was matched by keyword
                        })
                        # Capture specific columns from Excel
                        for col_index in [2, 7, 13, 14, 17, 19, 22]:
                            if col_index - 1 < len(df.columns):
                                header = df.columns[col_index - 1]
                                record[header] = df.iloc[idx, col_index - 1]
                            else:
                                record[f"MissingCol_{col_index}"] = None
                        all_matches.append(record)
                else:
                    not_mateched_files.append(file_name)

    # Only Containt Unique RFP_ID in not_mateched_files
    not_mateched_files = list(set(not_mateched_files))
    # 🔹 Prepare final DataFrame
    result_df = pd.DataFrame(all_matches)
    print("not_mateched_files:-",not_mateched_files)
    if not result_df.empty:
        # ✅ Generate timestamped CSV
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_csv = os.path.join(OUTPUT_DIR, f"matched_materials_{timestamp}.csv")
        try:
            result_df.to_csv(output_csv, index=False)
            print(f"✅ Exported matches to {output_csv}")
            log_event("RFP", "Files Matching", "Success", f"Exported {len(result_df)} matched materials to {output_csv}", '')
        except Exception as e:
            error_msg = f"Failed to export CSV: {str(e)}"
            print(f"⚠ {error_msg}")
            log_event("RFP", "Files Matching", "Fail", error_msg)
            output_csv = "export_failed"

        # ✅ Upload to SharePoint
        if output_csv != "export_failed":
            try:
                log_event("Sharepoint", "Upload", "Uploading", f"Uploading {output_csv} to SharePoint")
                graph_client.sync_local_to_sharepoint(output_csv, f"{SP_BASE_FOLDER}/ALLRFPs")
                log_event("Sharepoint", "Upload", "Success", f"File uploaded to SharePoint: {output_csv}")
            except Exception as e:
                error_msg = f"Could not upload {output_csv} to SharePoint: {e}"
                print(f"⚠ {error_msg}")
                log_event("Sharepoint", "Upload", "Fail", error_msg)

        # ✅ Log activity for new RFPs
        for rfp_id in processed_rfps:
            matches_in_file = result_df[result_df["RFP_Title"] == rfp_id]
            if not matches_in_file.empty:
                log_rfp_activity(
                    rfp_id=rfp_id,
                    Downloaded_At=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    Matched_Data=matches_in_file,
                    company_name=company_name
                )
    else:
        print("not_mateched_files:-", not_mateched_files)
        print("✅ No new matched materials found.")
        output_csv = "not_matched_data"
        log_event("RFP", "Files Matching", "Info", f"No matched materials found. Files processed: {files_processed}, Skipped: {files_skipped}, Failed: {files_failed}")

    # Summary log
    summary_msg = f"Processing complete. Files processed: {files_processed}, Skipped: {files_skipped}, Failed: {files_failed}, Matches found: {len(result_df)}"
    log_event("RFP", "Process Folder", "Complete", summary_msg)
    
    return result_df, output_csv, not_mateched_files

# ===== DOWNLOAD RFP FILES =====
async def attempt_download(page, row, company_name: str, attempts="Attempt 1", graph_client=None):
    title = (row.get("Title") or "").strip()
    link = (row.get("Link") or "").strip()
    RFP_End_Date = (row.get("RFP_End_Date") or "-").strip()
    participated = (row.get("Status") or "").strip()

    if not link:
        log_event("RFP", "Download", "Skip", "No link", title)
        return False
    
    # Check if already exists in new folder structure
    clean_title = clean_rfp_title(title)
    excel_file_path = get_rfp_excel_file_path(title, company_name)
    if os.path.exists(excel_file_path):
        print(f"✔ Already exists: {clean_title}")
        return True
       
    success = False
    new_page = await page.context.new_page()
    try:
        log_event("RFP", "Download", "Downloading", attempts, title)
        log_event("RFP", "Download", "Navigating", f"Navigating to RFP page: {link}", title)
        await new_page.goto(link, wait_until="domcontentloaded", timeout=60000)
        log_event("RFP", "Download", "Success", "Page navigation successful", title)
    except Exception as e:
        error_msg = f"Failed to navigate to page: {str(e)}"
        log_event("RFP", "Download", "Fail", error_msg, title)
        await new_page.close()
        return False
    
    rfp_details = None
    try:
        # Click optional elements
        # Review Event details anchor tab
        log_event("RFP", "Download", "Clicking", "Clicking on #_c8_tuc button", title)
        clicked = await click_if_visible(new_page, "#_c8_tuc", timeout=3000)
        if clicked:
            print("Click on First #_c8_tuc button")
            log_event("RFP", "Download", "Success", "Successfully clicked #_c8_tuc button", title)
        else:
            log_event("RFP", "Download", "Warning", "#_c8_tuc button not found or not clickable", title)

        # pause for 10 seconds 
        # Here We Not Need to Pause but for fallback we are pausing for 20 seconds
        await asyncio.sleep(10)
        # Extract RFP details (owner_name and publish_time) before clicking
        try:
            print(f"🔍 Extracting RFP details for: {title}")
            rfp_details = await extract_rfp_details_inner_text(new_page)
            print(f"📋 Extracted details - Owner: {rfp_details['owner']}, Publish Time: {rfp_details['publish_time']}")
            if rfp_details.get('owner') or rfp_details.get('publish_time'):
                log_event("RFP", "Extract Details", "Success", f"Extracted owner: {rfp_details.get('owner')}, publish_time: {rfp_details.get('publish_time')}", title)
        except Exception as e:
            error_msg = f"Could not extract RFP details: {e}"
            print(f"⚠ {error_msg}")
            log_event("RFP", "Extract Details", "Fail", error_msg, title)
            rfp_details = {'owner': None, 'publish_time': None}

        old_url = new_page.url
        log_event("RFP", "Download", "Clicking", "Attempting to click #_iiyvqc button", title)
        clicked_success = False
        for attempt in range(20):
            clicked = await click_if_visible(new_page, "#_iiyvqc", timeout=2000)
            if clicked and new_page.url != old_url:
                clicked_success = True
                log_event("RFP", "Download", "Success", f"Successfully clicked #_iiyvqc button on attempt {attempt + 1}", title)
                break
        if not clicked_success:
            log_event("RFP", "Download", "Warning", "#_iiyvqc button click did not change URL after 20 attempts", title)

        # Ensure the download button is truly actionable
        btn = new_page.locator("#_gktadc")
        try:
            log_event("RFP", "Download", "Waiting", "Waiting for download button to be visible and ready", title)
            await btn.wait_for(state="visible", timeout=8000)
            # Wait until it's enabled and not covered by overlays
            await new_page.wait_for_function(
                """el => el && !el.disabled && el.offsetParent !== null
                       && (() => { const r = el.getBoundingClientRect();
                                   const x = r.left + r.width/2, y = r.top + r.height/2;
                                   const e = document.elementFromPoint(x,y);
                                   return e && (e === el || el.contains(e));
                                 })()""",
                arg=await btn.element_handle(),
                timeout=8000
            )
            log_event("RFP", "Download", "Success", "Download button is ready", title)
        except Exception as e:
            error_msg = f"Download button not ready: {str(e)}"
            log_event("RFP", "Download", "Fail", error_msg, title)
            raise

        # Trigger download without waiting for navigation
        log_event("RFP", "Download", "Downloading", "Initiating file download", title)
        async with new_page.expect_download(timeout=20000) as dl_info:
            await btn.click(no_wait_after=True)
            print("Clicked on Download Button #_gktadc")
            log_event("RFP", "Download", "Success", "Download button clicked successfully", title)
        download = await dl_info.value

        # Use new folder structure: ALLRFPs/RFP_title/downloaded-rfp/RFP_title.xls
        clean_title = clean_rfp_title(title)
        final_filename = download.suggested_filename or f"{clean_title}.xls"
        # Extract extension from suggested filename or use .xls
        if download.suggested_filename:
            _, ext = os.path.splitext(download.suggested_filename)
            if not ext:
                ext = ".xls"
        else:
            ext = ".xls"
        
        # Save to new structure: ALLRFPs/CompanyName/RFP_title/downloaded-rfp/RFP_title.xls
        material_folder = get_rfp_material_file_path(title, company_name)
        final_path = os.path.join(material_folder, f"{clean_title}{ext}")
        
        print("Downloading:", final_filename)
        print("File Path:-",final_path)
        log_event("RFP", "Download", "Saving", f"Saving file: {final_filename} to {final_path}", title)

        await download.save_as(final_path)
        log_event("RFP", "Download", "Success", f"Successfully downloaded on first attempt and files saved on this path {final_path}", title)
        log_rfp_activity(
            rfp_id=title,
            Downloaded_At=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            RFP_End_Date=RFP_End_Date,
            owner_name=rfp_details['owner'] if rfp_details else None,
            publish_time=rfp_details['publish_time'] if rfp_details else None,
            participated=participated,
            link=link,
            company_name=company_name
        )
        success = True

        # Upload to SharePoint using new folder structure
        print("graph_client:-",graph_client)
        if graph_client:
            try:
                sp_material_path = get_sharepoint_rfp_material_path(title, company_name=company_name)
                log_event("Sharepoint", "Upload", "Uploading", f"Uploading {final_path} to SharePoint", title)
                graph_client.upload_file_as(final_path, sp_material_path, os.path.basename(final_path))
                log_event("Sharepoint", "Upload", "Success", f"Successfully uploaded {final_path} to SharePoint", title)
            except Exception as e:
                error_msg = f"Failed to upload {final_path} to SharePoint: {str(e)}"
                log_event("Sharepoint", "Upload", "Fail", error_msg, title)

    except Exception as e:
        error_msg = f"Download failed: {str(e)}"
        log_event("RFP", "Download", "Fail", error_msg, title)

        # Fallback: check latest file in Downloads
        log_event("RFP", "Download", "Fallback", "Attempting fallback: checking Downloads folder", title)
        latest_file = None
        for attempt in range(30):
            latest_file = get_latest_file(DOWNLOAD_DIR, title)
            if latest_file and not latest_file.endswith(".crdownload"):
                log_event("RFP", "Download", "Fallback", f"Found file in Downloads folder: {latest_file}", title)
                break
            await asyncio.sleep(1)
        if latest_file:
            # Use new folder structure for fallback file
            clean_title = clean_rfp_title(title)
            _, ext = os.path.splitext(latest_file)
            if not ext:
                ext = ".xls"
            material_folder = get_rfp_material_file_path(title, company_name)
            final_path = os.path.join(material_folder, f"{clean_title}{ext}")
            try:
                shutil.move(latest_file, final_path)
                log_event("RFP", "Download", "Success", f"Moved fallback file to {final_path}", title)
                # Log RFP activity with extracted details (if available)
                log_rfp_activity(
                    rfp_id=title,
                    Downloaded_At=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    RFP_End_Date=RFP_End_Date,
                    owner_name=rfp_details['owner'] if rfp_details else None,
                    publish_time=rfp_details['publish_time'] if rfp_details else None,
                    participated=participated,
                    link=link,
                    company_name=company_name
                )
                if graph_client:
                    try:
                        sp_material_path = get_sharepoint_rfp_material_path(title, company_name)
                        log_event("Sharepoint", "Upload", "Uploading", f"Uploading fallback file {final_path} to SharePoint", title)
                        graph_client.upload_file_as(final_path, sp_material_path, os.path.basename(final_path))
                        log_event("Sharepoint", "Upload", "Success", f"Successfully uploaded fallback file {final_path} to SharePoint", title)
                    except Exception as e:
                        error_msg = f"Failed to upload fallback file to SharePoint: {str(e)}"
                        log_event("Sharepoint", "Upload", "Fail", error_msg, title)
                success = True
            except Exception as e:
                error_msg = f"Failed to move fallback file: {str(e)}"
                log_event("RFP", "Download", "Fail", error_msg, title)
        else:
            log_event("RFP", "Download", "Fail", "Fallback: No file found in Downloads folder after 30 attempts", title)

    finally:
        try:
            await new_page.close()
            log_event("RFP", "Download", "Complete", "Download attempt completed", title)
        except Exception as e:
            error_msg = f"Error closing page: {str(e)}"
            log_event("RFP", "Download", "Warning", error_msg, title)

    return success


async def download_rfp_files(page, rfps, company_name: str, graph_client=None):
    log_event("RFP", "Download Batch", "Start", f"Starting download for {len(rfps)} RFPs")
    missing = []
    successful = []
    total_rfps = len(rfps)
    
    for row in rfps:
        title = row.get("Title", "")
        if await attempt_download(page, row, company_name, graph_client=graph_client):
            successful.append(title)
            
        else:
            missing.append(row)
            log_event("RFP", "Download", "Fail", "Failed on first attempt", title)

    if missing:
        log_event("RFP", "Retry", "Downloading", f"Retrying {len(missing)} failed downloads")
        still_missing = []
        for row in missing:
            title = row.get("Title", "")
            log_event("RFP", "Retry", "Downloading", "Attempt 2", title)
            if await attempt_download(page, row, company_name, "Attempt 2", graph_client=graph_client):
                successful.append(title)
                log_event("RFP", "Retry", "Success", f"Successfully downloaded on retry", title)
            else:
                still_missing.append(title)
                log_event("RFP", "Retry", "Fail", "Failed on retry attempt", title)
        
        if still_missing:
            for t in still_missing:
                log_event("RFP", "Retry", "Fail", "Still missing after retry", t)
        else:
            log_event("RFP", "Retry", "Success", "All failed downloads recovered on retry")
    
    # Summary log
    success_count = len(successful)
    failed_count = len(missing) if not missing else (len(still_missing) if 'still_missing' in locals() and still_missing else 0)
    summary_msg = f"Download batch complete. Total: {total_rfps}, Successful: {success_count}, Failed: {failed_count}"
    log_event("RFP", "Download Batch", "Complete", summary_msg)
   
