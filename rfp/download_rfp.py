from helpers.core_helper import *
from core.common_imports import *
from config.config import OUTPUT_DIR
import re
import tempfile
import shutil

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


def process_folder(graph_client, folder, master_csv, company_name: str = None, new_rfp_titles: list = None):
    """
    Process downloaded RFP Excel files, match materials with master CSV,
    and generate/upload a matched materials CSV.
    If new_rfp_titles is provided, only process those specific RFPs.
    """
    log_event("RFP", "Process Folder", "Start", f"Processing RFPs for company: {company_name}")

    # Temp dir only for master/keywords CSVs (not for RFP files)
    temp_process_dir = tempfile.mkdtemp(prefix="rfp_process_")
    excel_files = []

    # Find Excel files for only the newly downloaded RFPs
    if company_name and new_rfp_titles:
        local_company_dir = os.path.join(OUTPUT_DIR, company_name)
        clean_titles = {clean_rfp_title(t) for t in new_rfp_titles}
        print(f"🔄 Looking for {len(new_rfp_titles)} newly downloaded RFPs in: {local_company_dir}")
        log_event("RFP", "Process Folder", "Scanning", f"Looking for {len(new_rfp_titles)} new RFP files")
        if os.path.exists(local_company_dir):
            for root, dirs, files in os.walk(local_company_dir):
                for f in files:
                    if f.lower().endswith(('.xls', '.xlsx')):
                        file_id = os.path.splitext(f)[0]
                        if file_id in clean_titles:
                            excel_files.append(os.path.join(root, f))
            if excel_files:
                log_event("RFP", "Process Folder", "Success", f"Found {len(excel_files)} new RFP files to process")
            else:
                log_event("RFP", "Process Folder", "Warning", "No matching Excel files found for new RFPs")
        else:
            log_event("RFP", "Process Folder", "Warning", f"Local folder not found: {local_company_dir}")
    elif company_name:
        # Fallback: scan all local files if no specific titles provided
        local_company_dir = os.path.join(OUTPUT_DIR, company_name)
        print(f"🔄 Looking for RFP files in local folder: {local_company_dir}")
        log_event("RFP", "Process Folder", "Scanning", "Scanning local ALLRFPs folder for Excel files")
        if os.path.exists(local_company_dir):
            for root, dirs, files in os.walk(local_company_dir):
                for f in files:
                    if f.lower().endswith(('.xls', '.xlsx')):
                        excel_files.append(os.path.join(root, f))
            if excel_files:
                log_event("RFP", "Process Folder", "Success", f"Found {len(excel_files)} local RFP files")
            else:
                log_event("RFP", "Process Folder", "Warning", "No Excel files found in local folder")
        else:
            log_event("RFP", "Process Folder", "Warning", f"Local folder not found: {local_company_dir}")

    if not excel_files:
        log_event("RFP", "Process Folder", "Info", "No Excel files found locally - nothing to process", "")
        print("✅ No Excel files found locally - nothing to process.")
        shutil.rmtree(temp_process_dir, ignore_errors=True)
        return pd.DataFrame(), "no_files", []

    # 🔹 Load Material Master — Dataverse is now the source of truth.
    #    Falls back to SharePoint CSV if the Dataverse table is empty.
    from services.master_data_service import (
        get_all_materials_for_matching,
        get_all_keywords_for_matching,
    )

    print(f"🔄 Loading material master from Dataverse portal...")
    log_event("RFP", "Load Master", "Loading", "Fetching material master from Dataverse")
    dv_materials = get_all_materials_for_matching()

    if dv_materials:
        # Build a DataFrame matching the old master format (single 'material' column)
        master = pd.DataFrame({"material": dv_materials})
        master_col = "material"
        print(f"✅ Loaded {len(dv_materials)} material codes from Dataverse portal")
        log_event("RFP", "Load Master", "Success", f"Loaded {len(dv_materials)} material codes from Dataverse")
    else:
        # Fallback: download from SharePoint CSV (legacy path)
        master_csv_temp = os.path.join(temp_process_dir, "master_material.csv")
        try:
            print(f"⚠ Dataverse material table is empty — falling back to SharePoint CSV...")
            log_event("RFP", "Load Master", "Fallback", "Dataverse empty — fetching material CSV from SharePoint")
            master_csv_path = graph_client.download_file_from_sharepoint(
                sp_path=f"{SP_BASE_FOLDER}/master-files/material.csv",
                local_path=master_csv_temp
            )
            print(f"✅ Master file downloaded from SharePoint: {master_csv_path}")
            log_event("RFP", "Load Master", "Success", f"Master file downloaded from SharePoint: {master_csv_path}")
            master = pd.read_csv(master_csv_path)
        except Exception as e:
            error_msg = f"Could not load material master from Dataverse or SharePoint: {e}"
            log_event("RFP", "Load Master", "Fail", error_msg)
            raise FileNotFoundError(f"❌ {error_msg}")

        master_col = find_column_name(master.columns, "material")
        if not master_col:
            error_msg = "No 'material' column in master CSV"
            log_event("RFP", "Process Folder", "Fail", error_msg)
            raise ValueError(f"❌ {error_msg}")

    # 🔹 Load Keywords — Dataverse first, SharePoint fallback
    print(f"🔄 Loading keywords from Dataverse portal...")
    log_event("RFP", "Load Keywords", "Loading", "Fetching keywords from Dataverse")
    keywords_list = get_all_keywords_for_matching()

    if keywords_list:
        print(f"✅ Loaded {len(keywords_list)} keywords from Dataverse portal")
        log_event("RFP", "Load Keywords", "Success", f"Loaded {len(keywords_list)} keywords from Dataverse")
    else:
        # Fallback: SharePoint CSV
        keywords_csv_local = os.path.join(temp_process_dir, "unique_keywords.csv")
        try:
            print(f"⚠ Dataverse keywords table is empty — falling back to SharePoint CSV...")
            log_event("RFP", "Load Keywords", "Fallback", "Dataverse empty — fetching keywords CSV from SharePoint")
            keywords_csv_path = graph_client.download_file_from_sharepoint(
                sp_path=f"{SP_BASE_FOLDER}/master-files/unique_keywords.csv",
                local_path=keywords_csv_local
            )
            keywords_df = pd.read_csv(keywords_csv_path)
            keywords_col = (
                find_column_name(keywords_df.columns, "keywords")
                or find_column_name(keywords_df.columns, "keyword")
            )
            if keywords_col:
                for row in keywords_df.to_dict('records'):
                    keyword_value = str(row.get(keywords_col, "")).strip()
                    if keyword_value and keyword_value.lower() != 'nan':
                        for kw in keyword_value.split(','):
                            kw_clean = kw.strip().upper()
                            if kw_clean:
                                keywords_list.append(kw_clean)
            print(f"✅ Loaded {len(keywords_list)} keywords from SharePoint")
            log_event("RFP", "Load Keywords", "Success", f"Loaded {len(keywords_list)} keywords from SharePoint")
        except Exception as e:
            error_msg = f"Could not load keywords: {e}"
            print(f"⚠ {error_msg}")
            log_event("RFP", "Load Keywords", "Warning", error_msg)
            keywords_list = []  # Continue without keywords if unavailable

    # 🔹 Load RFP activity log — only for the RFPs we found locally
    rfp_ids = [os.path.splitext(os.path.basename(f))[0] for f in excel_files]
    print(f"🔄 Fetching activity log for {len(rfp_ids)} RFPs from Dataverse...")
    log_event("RFP", "Fetch Activity Log", "Downloading", f"Fetching activity log for {len(rfp_ids)} RFPs")
    try:
        # Build OData filter: RFP_ID eq 'X' or RFP_ID eq 'Y' ...
        filter_parts = [f"RFP_ID eq '{sanitize_filter_value(rid)}'" for rid in rfp_ids]
        filter_expr = " or ".join(filter_parts)
        result = DATAVERSE.query_rows(
            RFP_ACTIVITY_LOG_TABLE_API,
            filter_expr=filter_expr,
            select="RFP_ID,Email_Status,RFP_End_Date,owner_name,publish_time,Company_Name,participated,Link,Material_Matched,Keyword_Matched,Matched_Data",
            top=len(rfp_ids),
            table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL,
            use_display_names=True
        )
        rows = result.get("value", []) if isinstance(result, dict) else result if isinstance(result, list) else []
        log_df = pd.DataFrame(rows)
        if log_df.empty:
            log_df = pd.DataFrame(columns=["RFP_ID", "Email_Status", "RFP_End_Date"])
        print(f"✅ Loaded {len(log_df)} rows from Dataverse (for {len(rfp_ids)} RFPs)")
        log_event("RFP", "Fetch Activity Log", "Success", f"Loaded {len(log_df)} rows for {len(rfp_ids)} RFPs")
    except Exception as e:
        error_msg = f"Could not fetch RFP log from Dataverse: {e}"
        print(f"⚠ {error_msg}")
        log_event("RFP", "Fetch Activity Log", "Fail", error_msg)
        log_df = pd.DataFrame(columns=["RFP_ID", "Email_Status", "RFP_End_Date"])
    
    all_matches = []
    not_mateched_files = []
    files_with_any_match = set()   # track which files had at least one material match
    processed_rfps = set()
    files_processed = 0
    files_skipped = 0
    files_failed = 0

    # 🔹 Process each downloaded Excel file
    for excel_path in excel_files:
        file_name = os.path.basename(excel_path)
        rfp_id = os.path.splitext(file_name)[0]

        # Skip already emailed RFPs (only relevant when processing all local files)
        if not new_rfp_titles and not log_df.empty and rfp_id in log_df["RFP_ID"].astype(str).values:
            email_status = log_df.loc[log_df["RFP_ID"].astype(str) == rfp_id, "Email_Status"].values
            if email_status.size > 0 and str(email_status[0]).lower() == "sent":
                print(f"⏩ Skipping {rfp_id}, email already sent.")
                files_skipped += 1
                continue

        processed_rfps.add(rfp_id)
        log_event("RFP", "Process File", "Processing", f"Processing file: {file_name}", rfp_id)

        try:
            df = pd.read_excel(excel_path, sheet_name="Other Content")
            log_event("RFP", "Process File", "Success", f"Read sheet 'Other Content' from: {file_name}", rfp_id)
            files_processed += 1
        except Exception:
            # Fallback: find sheet containing expected columns
            EXPECTED_COLUMNS = ["intend to respond", "currency", "material number", "price", "quantity"]
            df = None
            try:
                all_sheets = pd.ExcelFile(excel_path).sheet_names
                for sheet in all_sheets:
                    sheet_df = pd.read_excel(excel_path, sheet_name=sheet)
                    sheet_cols_lower = [str(c).lower().strip() for c in sheet_df.columns]
                    matches = sum(1 for ec in EXPECTED_COLUMNS if any(ec in sc for sc in sheet_cols_lower))
                    if matches >= 2:
                        df = sheet_df
                        log_event("RFP", "Process File", "Success", f"Found matching sheet '{sheet}' ({matches} columns matched) in: {file_name}", rfp_id)
                        files_processed += 1
                        break
            except Exception as e2:
                log_event("RFP", "Process File", "Fail", f"Could not read {file_name}: {e2}", rfp_id)
                files_failed += 1
                continue

            if df is None:
                log_event("RFP", "Process File", "Fail", f"No sheet with expected columns found in: {file_name} (sheets: {all_sheets})", rfp_id)
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
                
                # Get RFP End Date from log (needed for all records)
                RFP_End_Date = "-"
                if not log_df.empty:
                    match_row = log_df.loc[log_df["RFP_ID"].astype(str) == str(rfp_id), "RFP_End_Date"]
                    if not match_row.empty:
                        RFP_End_Date = match_row.iloc[0]

                if is_matched:
                    files_with_any_match.add(file_name)   # mark this file as having at least one match

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
                                "ExtractedMaterial": mat,
                                "MatchMethod": "exact",
                                "is_matched": True,
                                "ExcelName": name_text,
                                "ExcelDescription": description_text,
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
                            "MatchMethod": "keyword",
                            "is_matched": True,
                            "ExcelName": name_text,
                            "ExcelDescription": description_text,
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
                    # Unmatched material — store for dialog display
                    record = {master_col: mat}
                    for col in master.columns:
                        if col not in record:
                            record[col] = None
                    record.update({
                        "SourceFile": file_name,
                        "RFP_Title": rfp_id,
                        "RFP_End_Date": RFP_End_Date,
                        "TDS_file_path": "",
                        "RowNumber": idx + 2,
                        "ColumnName": col_name,
                        "ExtractedMaterial": mat,
                        "MatchMethod": None,
                        "is_matched": False,
                        "ExcelName": name_text,
                        "ExcelDescription": description_text,
                    })
                    for col_index in [2, 7, 13, 14, 17, 19, 22]:
                        if col_index - 1 < len(df.columns):
                            header = df.columns[col_index - 1]
                            record[header] = df.iloc[idx, col_index - 1]
                        else:
                            record[f"MissingCol_{col_index}"] = None
                    all_matches.append(record)

    # A file is "not matched" only if NONE of its materials had any match
    not_mateched_files = [
        os.path.basename(f)
        for f in excel_files
        if os.path.basename(f) not in files_with_any_match
    ]
    # 🔹 Prepare final DataFrame
    result_df = pd.DataFrame(all_matches)
    print("not_mateched_files:-", not_mateched_files)

    # Per-RFP matched material CSV map: {rfp_id: csv_path}
    per_rfp_csv_map = {}
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if not result_df.empty:
        # ✅ Generate per-RFP matched material CSVs
        for rfp_id_key in result_df["RFP_Title"].dropna().unique():
            rfp_matches = result_df[result_df["RFP_Title"] == rfp_id_key]
            if rfp_matches.empty:
                continue
            per_rfp_csv = os.path.join(OUTPUT_DIR, f"matched_materials_{rfp_id_key}_{timestamp}.csv")
            try:
                rfp_matches.to_csv(per_rfp_csv, index=False)
                print(f"✅ Exported per-RFP matches for {rfp_id_key} to {per_rfp_csv}")
                log_event("RFP", "Files Matching", "Success", f"Exported {len(rfp_matches)} matches for {rfp_id_key}", rfp_id_key)

                # Upload per-RFP CSV to SharePoint
                try:
                    sp_folder = f"{SP_BASE_FOLDER}/ALLRFPs/{company_name}/{clean_rfp_title(rfp_id_key)}"
                    log_event("Sharepoint", "Upload", "Uploading", f"Uploading per-RFP matched CSV for {rfp_id_key}")
                    graph_client.sync_local_to_sharepoint(per_rfp_csv, sp_folder)
                    log_event("Sharepoint", "Upload", "Success", f"Per-RFP matched CSV uploaded for {rfp_id_key}")
                except Exception as e:
                    error_msg = f"Could not upload per-RFP CSV for {rfp_id_key}: {e}"
                    print(f"⚠ {error_msg}")
                    log_event("Sharepoint", "Upload", "Fail", error_msg)

                per_rfp_csv_map[rfp_id_key] = per_rfp_csv
            except Exception as e:
                error_msg = f"Failed to export per-RFP CSV for {rfp_id_key}: {str(e)}"
                print(f"⚠ {error_msg}")
                log_event("RFP", "Files Matching", "Fail", error_msg)

        log_event("RFP", "Files Matching", "Success", f"Generated {len(per_rfp_csv_map)} per-RFP matched material CSVs")

        # ✅ Log activity for new RFPs
        for rfp_id in processed_rfps:
            matches_in_file = result_df[result_df["RFP_Title"] == rfp_id]

            if not matches_in_file.empty:
                log_rfp_activity(
                    rfp_id=rfp_id,
                    Downloaded_At=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    Matched_Data=matches_in_file,
                    company_name=company_name,
                )
    else:
        print("not_mateched_files:-", not_mateched_files)
        print("✅ No new matched materials found.")
        log_event("RFP", "Files Matching", "Info", f"No matched materials found. Files processed: {files_processed}, Skipped: {files_skipped}, Failed: {files_failed}")

    # Summary log
    summary_msg = f"Processing complete. Files processed: {files_processed}, Skipped: {files_skipped}, Failed: {files_failed}, Matches found: {len(result_df)}"
    log_event("RFP", "Process Folder", "Complete", summary_msg)

    # Clean up temp dir (only held master/keywords CSVs)
    shutil.rmtree(temp_process_dir, ignore_errors=True)

    return result_df, per_rfp_csv_map, not_mateched_files

# ===== DOWNLOAD RFP FILES =====
async def attempt_download(page, row, company_name: str, attempts="Attempt 1", graph_client=None):
    title = (row.get("Title") or "").strip()
    link = (row.get("Link") or "").strip()
    RFP_End_Date = (row.get("RFP_End_Date") or "-").strip()
    participated = (row.get("Status") or "").strip()

    if not link:
        log_event("RFP", "Download", "Skip", "No link", title)
        return False

    clean_title = clean_rfp_title(title)

    # Build local storage path
    local_rfp_dir = os.path.join(OUTPUT_DIR, company_name, clean_title, "downloaded-rfp")
    os.makedirs(local_rfp_dir, exist_ok=True)
    local_file_path = os.path.join(local_rfp_dir, f"{clean_title}.xls")

    # Check DB Email_Status first — if email already sent, skip everything
    email_already_sent = False
    existing_db_record = None
    try:
        safe_rfp_id = sanitize_filter_value(title)
        safe_company = sanitize_filter_value(company_name)
        db_result = DATAVERSE.query_rows(
            RFP_ACTIVITY_LOG_TABLE_API,
            filter_expr=f"RFP_ID eq '{safe_rfp_id}' and Company_Name eq '{safe_company}'",
            top=1,
            table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL,
            use_display_names=True
        )
        if db_result and "value" in db_result and db_result["value"]:
            existing_db_record = db_result["value"][0]
            db_email_status = existing_db_record.get("Email_Status", "") or ""
            if "sent" in db_email_status.lower():
                email_already_sent = True
    except Exception as e:
        log_event("RFP", "Download", "Warning", f"DB Email_Status check failed: {e}", title)
        # Continue — don't skip if DB check fails

    if email_already_sent:
        log_event("RFP", "Download", "Skip", f"Email already sent — skipping RFP", title)
        return "skipped"

    # 1. If file exists locally, ensure DB record + SharePoint, then treat as processable
    if os.path.exists(local_file_path):
        # Ensure DB record exists (reuse existing_db_record from check above)
        if not existing_db_record:
            log_event("RFP", "Download", "Insert", "File exists locally but not in Dataverse — inserting", title)
            log_rfp_activity(
                rfp_id=title,
                Downloaded_At=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                RFP_End_Date=RFP_End_Date,
                participated=participated,
                link=link,
                company_name=company_name
            )
        else:
            log_event("RFP", "Download", "Info", "File exists locally, email not yet sent — will process + email", title)

        # Upload to SharePoint only if missing
        if graph_client:
            try:
                sp_material_path = get_sharepoint_rfp_material_path(title, company_name=company_name)
                sp_file_full_path = f"{sp_material_path}/{os.path.basename(local_file_path)}"
                sp_check = graph_client._get_item_by_path(sp_file_full_path)
                sp_json = sp_check.json() if sp_check.status_code == 200 else {}
                file_exists = sp_check.status_code == 200 and "folder" not in sp_json
                if file_exists:
                    log_event("Sharepoint", "Upload", "Skip", "File already exists in SharePoint", title)
                else:
                    reason = "folder exists but file missing" if sp_check.status_code == 200 else f"not found ({sp_check.status_code})"
                    log_event("Sharepoint", "Upload", "Uploading", f"File missing in SharePoint ({reason}), uploading from local", title)
                    graph_client.upload_file_as(local_file_path, sp_material_path, os.path.basename(local_file_path))
                    log_event("Sharepoint", "Upload", "Success", "Uploaded local file to SharePoint", title)
            except Exception as e:
                log_event("Sharepoint", "Upload", "Warning", f"SharePoint check/upload failed: {e}", title)

        return True  # Email not yet sent — add to new_rfp_titles so it gets processed + emailed

    # 2. File does NOT exist locally — always download, then ensure SharePoint + Dataverse
    log_event("RFP", "Download", "Proceed", "File not found locally — downloading from portal", title)

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

        # Save to local folder (persistent storage)
        clean_title = clean_rfp_title(title)
        final_filename = download.suggested_filename or f"{clean_title}.xls"

        print("Downloading:", final_filename)
        log_event("RFP", "Download", "Saving", f"Saving file: {final_filename} to local", title)

        await download.save_as(local_file_path)
        log_event("RFP", "Download", "Success", f"Successfully downloaded: {final_filename}", title)

        # Upload to SharePoint only if not already there
        if graph_client:
            try:
                sp_material_path = get_sharepoint_rfp_material_path(title, company_name=company_name)
                sp_file_full_path = f"{sp_material_path}/{os.path.basename(local_file_path)}"
                sp_check = graph_client._get_item_by_path(sp_file_full_path)
                sp_json = sp_check.json() if sp_check.status_code == 200 else {}
                file_exists = sp_check.status_code == 200 and "folder" not in sp_json
                if file_exists:
                    log_event("Sharepoint", "Upload", "Skip", "File already exists in SharePoint", title)
                else:
                    reason = "folder exists but file missing" if sp_check.status_code == 200 else f"not found ({sp_check.status_code})"
                    log_event("Sharepoint", "Upload", "Uploading", f"Uploading {final_filename} to SharePoint ({reason})", title)
                    graph_client.upload_file_as(local_file_path, sp_material_path, os.path.basename(local_file_path))
                    log_event("Sharepoint", "Upload", "Success", f"Successfully uploaded {final_filename} to SharePoint", title)
            except Exception as e:
                error_msg = f"Failed to upload {final_filename} to SharePoint: {str(e)}"
                log_event("Sharepoint", "Upload", "Fail", error_msg, title)

        # Log RFP activity in Dataverse
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
            clean_title = clean_rfp_title(title)
            try:
                # Move fallback file to local folder
                shutil.move(latest_file, local_file_path)
                log_event("RFP", "Download", "Success", f"Fallback file saved to local", title)

                # Upload to SharePoint only if not already there
                if graph_client:
                    try:
                        sp_material_path = get_sharepoint_rfp_material_path(title, company_name)
                        sp_file_full_path = f"{sp_material_path}/{os.path.basename(local_file_path)}"
                        sp_check = graph_client._get_item_by_path(sp_file_full_path)
                        sp_json = sp_check.json() if sp_check.status_code == 200 else {}
                        file_exists = sp_check.status_code == 200 and "folder" not in sp_json
                        if file_exists:
                            log_event("Sharepoint", "Upload", "Skip", "File already exists in SharePoint", title)
                        else:
                            reason = "folder exists but file missing" if sp_check.status_code == 200 else f"not found ({sp_check.status_code})"
                            log_event("Sharepoint", "Upload", "Uploading", f"Uploading fallback file to SharePoint ({reason})", title)
                            graph_client.upload_file_as(local_file_path, sp_material_path, os.path.basename(local_file_path))
                            log_event("Sharepoint", "Upload", "Success", f"Successfully uploaded fallback file to SharePoint", title)
                    except Exception as e:
                        error_msg = f"Failed to upload fallback file to SharePoint: {str(e)}"
                        log_event("Sharepoint", "Upload", "Fail", error_msg, title)

                # Log RFP activity in Dataverse
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
            except Exception as e:
                error_msg = f"Failed to process fallback file: {str(e)}"
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
    """Returns the list of newly downloaded RFP titles (excludes skipped ones)."""
    log_event("RFP", "Download Batch", "Start", f"Starting download for {len(rfps)} RFPs")
    missing = []
    successful = []
    skipped = []
    total_rfps = len(rfps)

    for row in rfps:
        title = row.get("Title", "")
        result = await attempt_download(page, row, company_name, graph_client=graph_client)
        if result == "skipped":
            skipped.append(title)
        elif result:
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
            result = await attempt_download(page, row, company_name, "Attempt 2", graph_client=graph_client)
            if result and result != "skipped":
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
    new_download_count = len(successful)
    skipped_count = len(skipped)
    failed_count = len(missing) if not missing else (len(still_missing) if 'still_missing' in locals() and still_missing else 0)
    summary_msg = f"Download batch complete. Total: {total_rfps}, New: {new_download_count}, Skipped: {skipped_count}, Failed: {failed_count}"
    log_event("RFP", "Download Batch", "Complete", summary_msg)

    return successful
   
