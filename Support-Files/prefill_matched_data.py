"""
Script to pre-fill Matched_Data JSON for RFPs missing it in cr673_bahra_rfps_v2.

Loads materials & keywords from Dataverse (falls back to SharePoint CSV).
Downloads RFP Excel from SharePoint if not found locally.
Skips RFPs that already have Matched_Data.

Uses the EXACT same matching logic as the download flow (download_rfp.py)
and outputs the CATEGORIZED JSON format:
  { summary, exact_matches, keyword_matches, not_matched }

Usage:
  python -m Support-Files.prefill_matched_data

Safe to re-run — only updates RFPs with empty Matched_Data.
"""

import os
import re
import json
import math
import sys
import pandas as pd
from datetime import datetime


# ---------------------------------------------------------------------------
# Table names
# ---------------------------------------------------------------------------
TABLE_LOGICAL = "cr673_bahra_rfps_v2"
TABLE_API = "cr673_bahra_rfps_v2s"


# ---------------------------------------------------------------------------
# Helper: find Excel file (local or SharePoint)
# ---------------------------------------------------------------------------
def find_excel_file(rfp_id, company, graph_client):
    """Find RFP Excel file locally or download from SharePoint."""
    from helpers.core_helper import (
        get_rfp_excel_file_path, get_rfp_material_file_path,
        get_sharepoint_rfp_material_path, clean_rfp_title,
    )

    clean_title = clean_rfp_title(rfp_id)

    # Try company-specific path first (fastest — no DB call)
    if company:
        path = get_rfp_excel_file_path(rfp_id, company)
        if os.path.exists(path):
            return path, company

    # Search through all company folders locally — check both root ALLRFPs/
    # and Support-Files/ALLRFPs/ (where manually-scripted companies live).
    project_root = os.getcwd()
    search_roots = [
        os.path.join(project_root, "ALLRFPs"),
        os.path.join(project_root, "Support-Files", "ALLRFPs"),
    ]
    for output_dir in search_roots:
        if not os.path.exists(output_dir):
            continue
        for company_folder in os.listdir(output_dir):
            company_path = os.path.join(output_dir, company_folder)
            if not os.path.isdir(company_path):
                continue
            # Direct check on this base directory (don't rely on get_rfp_excel_file_path,
            # which only knows about OUTPUT_DIR).
            for ext in (".xls", ".xlsx"):
                candidate = os.path.join(
                    company_path, clean_title, "downloaded-rfp", f"{clean_title}{ext}"
                )
                if os.path.exists(candidate):
                    return candidate, company_folder

    # Not found locally — try downloading from SharePoint
    if graph_client and company:
        for ext in ['.xls', '.xlsx']:
            filename = f"{clean_title}{ext}"
            sp_path = get_sharepoint_rfp_material_path(rfp_id, company, filename)
            try:
                local_path = os.path.join(
                    get_rfp_material_file_path(rfp_id, company),
                    filename
                )
                graph_client.download_file_from_sharepoint(sp_path, local_path)
                print(f"    [OK] Downloaded from SharePoint: {sp_path}")
                return local_path, company
            except Exception:
                continue

    return None, company


# ---------------------------------------------------------------------------
# Keyword matching helpers (shared by both code paths)
# ---------------------------------------------------------------------------
def _try_keyword_match(name_text, description_text, keywords_list, extract_keywords_from_text):
    """Check if Name/Description keywords match any keyword from the keywords list."""
    name_keywords = extract_keywords_from_text(name_text)
    desc_keywords = extract_keywords_from_text(description_text)
    all_material_keywords = set(name_keywords + desc_keywords)

    for csv_keyword in keywords_list:
        for mat_keyword in all_material_keywords:
            if csv_keyword in mat_keyword or mat_keyword in csv_keyword:
                return csv_keyword
    return None


def _find_description_by_keyword(name_text, description_text, master, master_col,
                                  desc_col_master, extract_keywords_from_text):
    """Search master data for a description using keywords from Name/Description."""
    import math
    name_keywords = extract_keywords_from_text(name_text)
    desc_keywords = extract_keywords_from_text(description_text)
    all_material_keywords = set(name_keywords + desc_keywords)

    keyword_matched_rows = pd.DataFrame()
    for mat_keyword in all_material_keywords:
        if not mat_keyword:
            continue
        temp = master[master[master_col].astype(str).str.contains(mat_keyword, case=False, na=False, regex=False)]
        if not temp.empty:
            keyword_matched_rows = pd.concat([keyword_matched_rows, temp]).drop_duplicates()
        for col in master.columns:
            if col != master_col and master[col].dtype == 'object':
                try:
                    temp = master[master[col].astype(str).str.contains(mat_keyword, case=False, na=False, regex=False)]
                    if not temp.empty:
                        keyword_matched_rows = pd.concat([keyword_matched_rows, temp]).drop_duplicates()
                except Exception:
                    pass

    if not keyword_matched_rows.empty and desc_col_master:
        val = keyword_matched_rows.iloc[0].get(desc_col_master, "")
        return "" if (isinstance(val, float) and math.isnan(val)) else str(val)
    return ""


# ---------------------------------------------------------------------------
# Core matching logic -> categorized format
# ---------------------------------------------------------------------------
def match_materials_for_rfp(excel_path, rfp_id, rfp_end_date, company,
                            master, master_col, master_code_set, keywords_list):
    """
    Extract materials from RFP Excel and match against master + keywords.
    Returns categorized dict: { summary, exact_matches, keyword_matches, not_matched }
    """
    from helpers.core_helper import (
        _find_other_content_sheet_name, find_column_name,
        extract_keywords_from_text, get_sharepoint_rfp_tds_path,
    )

    file_name = os.path.basename(excel_path)

    # Read the "Other Content" sheet (with column-based fallback)
    sheet = _find_other_content_sheet_name(excel_path)
    df = None

    if sheet:
        try:
            df = pd.read_excel(excel_path, sheet_name=sheet)
        except Exception as e:
            print(f"    [WARN] Cannot read sheet '{sheet}': {e}")

    # Fallback: find sheet containing expected columns
    if df is None:
        EXPECTED_COLUMNS = ["intend to respond", "currency", "material number", "price", "quantity"]
        try:
            all_sheets = pd.ExcelFile(excel_path).sheet_names
            for s in all_sheets:
                try:
                    sheet_df = pd.read_excel(excel_path, sheet_name=s)
                    sheet_cols_lower = [str(c).lower().strip() for c in sheet_df.columns]
                    matches = sum(1 for ec in EXPECTED_COLUMNS if any(ec in sc for sc in sheet_cols_lower))
                    if matches >= 2:
                        df = sheet_df
                        print(f"    [OK] Fallback sheet '{s}' matched ({matches} columns) in {file_name}")
                        break
                except Exception:
                    continue
        except Exception as e:
            print(f"    [WARN] Could not enumerate sheets in {file_name}: {e}")

    if df is None:
        print(f"    [WARN] No suitable sheet found in {file_name}")
        return None

    col_name = find_column_name(df.columns, "name")
    if not col_name:
        print(f"    [WARN] No 'Name' column found in {file_name}")
        return None

    col_desc = find_column_name(df.columns, "description")
    desc_col_master = find_column_name(master.columns, "description") or find_column_name(master.columns, "material description")

    exact_matches = []
    keyword_matches = []
    not_matched = []

    for idx, value in df[col_name].items():
        if pd.isna(value):
            continue

        name_text = str(value)
        description_text = str(df.iloc[idx][col_desc]) if col_desc and not pd.isna(df.iloc[idx][col_desc]) else ""

        material_codes = re.findall(r'\d{9}', name_text)

        if material_codes:
            # --- Rows WITH 9-digit material codes ---
            for mat in material_codes:
                base_item = {
                    "material_code": mat,
                    "excel_name": name_text,
                    "excel_description": description_text,
                    "row_number": idx + 2,
                    "column_name": col_name,
                }

                # Method 1: Exact Material Code Match
                matched_rows = master[master[master_col].astype(str) == mat]
                is_exact = not matched_rows.empty

                if is_exact:
                    mat_desc = ""
                    if not matched_rows.empty and desc_col_master:
                        val = matched_rows.iloc[0].get(desc_col_master, "")
                        mat_desc = "" if (isinstance(val, float) and math.isnan(val)) else str(val)

                    base_item["material_description"] = mat_desc
                    exact_matches.append(base_item)
                    continue

                # Method 2: Keyword Matching (only if exact match failed)
                matched_keyword = _try_keyword_match(
                    name_text, description_text, keywords_list, extract_keywords_from_text
                )

                if matched_keyword:
                    mat_desc = _find_description_by_keyword(
                        name_text, description_text, master, master_col,
                        desc_col_master, extract_keywords_from_text
                    )
                    base_item["matched_keyword"] = matched_keyword
                    base_item["material_description"] = mat_desc
                    keyword_matches.append(base_item)
                else:
                    not_matched.append(base_item)

        else:
            # --- Rows WITHOUT 9-digit codes: try keyword matching on Name + Description ---
            if not keywords_list:
                continue

            matched_keyword = _try_keyword_match(
                name_text, description_text, keywords_list, extract_keywords_from_text
            )

            if matched_keyword:
                mat_desc = _find_description_by_keyword(
                    name_text, description_text, master, master_col,
                    desc_col_master, extract_keywords_from_text
                )
                base_item = {
                    "material_code": "",
                    "excel_name": name_text,
                    "excel_description": description_text,
                    "row_number": idx + 2,
                    "column_name": col_name,
                    "matched_keyword": matched_keyword,
                    "material_description": mat_desc,
                }
                keyword_matches.append(base_item)
            # else: no code and no keyword match — skip (header/instruction row)

    total = len(exact_matches) + len(keyword_matches) + len(not_matched)
    matched_total = len(exact_matches) + len(keyword_matches)
    match_pct = round((matched_total / total * 100) if total > 0 else 0, 1)

    return {
        "rfp_id": rfp_id,
        "source_file": file_name,
        "rfp_end_date": rfp_end_date or "",
        "total_items": total,
        "summary": {
            "exact_match_count": len(exact_matches),
            "keyword_match_count": len(keyword_matches),
            "not_matched_count": len(not_matched),
            "match_percentage": match_pct,
        },
        "exact_matches": exact_matches,
        "keyword_matches": keyword_matches,
        "not_matched": not_matched,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    # Import order matters to avoid circular imports:
    # 1) config first, 2) common_imports to bootstrap everything, 3) then specific modules
    from config.config import (
        TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL,
        SHAREPOINT_HOSTNAME, SITE_PATH, DRIVE_NAME,
        OUTPUT_DIR,
    )
    import core.common_imports  # noqa: F401 — bootstraps all modules
    from helpers.dataverse_helper import DataverseClient
    from helpers.sharepoint_helper import GraphClient

    print("=" * 60)
    print("  Pre-fill Matched_Data for ALL RFPs (Categorized Format)")
    print("=" * 60)

    # 1. Init clients
    graph_client = GraphClient(
        CLIENT_ID, CLIENT_SECRET, TENANT_ID,
        SHAREPOINT_HOSTNAME, SITE_PATH, DRIVE_NAME
    )
    graph_client.auth()
    graph_client.resolve_site_and_drive()

    # Create Dataverse client directly (avoids circular import via core_helper)
    dv_client = DataverseClient(
        tenant_id=TENANT_ID,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        resource_url=RESOURCE_URL,
    )
    print("[AUTH] SharePoint + Dataverse ready.\n")

    # 2. Load materials & keywords from Dataverse (primary) or SharePoint CSV (fallback)
    from services.master_data_service import (
        get_all_materials_for_matching,
        get_all_keywords_for_matching,
    )

    sp_base = "RFP-logs"

    print("[1] Loading materials from Dataverse...")
    dv_materials = get_all_materials_for_matching()
    if dv_materials:
        master = pd.DataFrame({"material": dv_materials})
        master_col = "material"
        print(f"[OK] Loaded {len(dv_materials)} material codes from Dataverse")
    else:
        print("[WARN] Dataverse materials empty — falling back to SharePoint CSV...")
        master_csv_local = os.path.join(OUTPUT_DIR, "master_material.csv")
        graph_client.download_file_from_sharepoint(
            sp_path=f"{sp_base}/master-files/material.csv",
            local_path=master_csv_local
        )
        master = pd.read_csv(master_csv_local)
        def find_col(cols, target):
            for c in cols:
                if target.lower() in c.lower().replace(" ", "").replace("_", ""):
                    return c
            return None
        master_col = find_col(master.columns, "material")
        if not master_col:
            print("[FATAL] No 'material' column in master CSV!")
            sys.exit(1)
        print(f"[OK] Loaded {len(master)} materials from SharePoint CSV")

    master_code_set = set(master[master_col].astype(str))

    print("[2] Loading keywords from Dataverse...")
    keywords_list = get_all_keywords_for_matching()
    if keywords_list:
        print(f"[OK] Loaded {len(keywords_list)} keywords from Dataverse")
    else:
        print("[WARN] Dataverse keywords empty — falling back to SharePoint CSV...")
        keywords_csv_local = os.path.join(OUTPUT_DIR, "unique_keywords.csv")
        try:
            graph_client.download_file_from_sharepoint(
                sp_path=f"{sp_base}/master-files/unique_keywords.csv",
                local_path=keywords_csv_local
            )
            kw_df = pd.read_csv(keywords_csv_local)
            def find_col(cols, target):
                for c in cols:
                    if target.lower() in c.lower().replace(" ", "").replace("_", ""):
                        return c
                return None
            kw_col = find_col(kw_df.columns, "keyword") or kw_df.columns[0]
            keywords_list = [str(k).strip().upper() for k in kw_df[kw_col].dropna().tolist() if str(k).strip()]
        except Exception as e:
            print(f"[WARN] Could not load keywords from SharePoint: {e}")
            keywords_list = []
        print(f"[OK] Loaded {len(keywords_list)} keywords from SharePoint CSV")

    # 3. Query ALL RFPs from Dataverse
    print("\n[1/3] Fetching all RFPs from Dataverse...")
    all_rfps = dv_client.get_all_rows(
        table_api_name=TABLE_API,
        select_columns=["RFP_ID", "Matched_Data", "Company_Name", "RFP_End_Date"],
        table_logical_name=TABLE_LOGICAL,
        use_display_names=True,
    )
    print(f"       Total RFPs: {len(all_rfps)}")

    # Resolve PK display name once
    try:
        _colmap = dv_client.get_column_mapping(TABLE_LOGICAL)
        _logical_to_display = {v: k for k, v in _colmap.items()}
    except Exception:
        _logical_to_display = {}
    _pk_logical = f"{TABLE_LOGICAL}id"
    _pk_display = _logical_to_display.get(_pk_logical)

    # 4. Process each RFP (only those missing Matched_Data)
    print("[2/3] Processing RFPs...\n")
    updated = 0
    skipped_has_data = 0
    skipped_no_excel = 0
    skipped_no_materials = 0
    failed = 0

    for i, row in enumerate(all_rfps, 1):
        rfp_id = (row.get("RFP_ID") or "").strip()
        if not rfp_id:
            continue

        # Skip RFPs that already have Matched_Data
        existing = (row.get("Matched_Data") or "").strip()
        if existing:
            skipped_has_data += 1
            continue

        company = (row.get("Company_Name") or "").strip()
        rfp_end_date = (row.get("RFP_End_Date") or "").strip()
        record_id = (row.get(_pk_display) if _pk_display else None) or row.get(_pk_logical)

        if not record_id:
            failed += 1
            continue

        # Find Excel file
        excel_path, resolved_company = find_excel_file(rfp_id, company, graph_client)
        if not excel_path or not os.path.exists(excel_path):
            skipped_no_excel += 1
            continue

        # Run matching
        try:
            result = match_materials_for_rfp(
                excel_path, rfp_id, rfp_end_date, resolved_company or company,
                master, master_col, master_code_set, keywords_list
            )
        except Exception as e:
            failed += 1
            print(f"  [{i}/{len(all_rfps)}] FAILED {rfp_id}: {e}")
            continue

        if result is None or result["total_items"] == 0:
            skipped_no_materials += 1
            continue

        # Serialize and update Dataverse
        try:
            matched_data_json = json.dumps(result)
            dv_client.update_row(
                TABLE_API,
                record_id,
                {"Matched_Data": matched_data_json},
                table_logical_name=TABLE_LOGICAL
            )
            updated += 1
            if updated % 10 == 0:
                print(f"  [{i}/{len(all_rfps)}] Updated {updated} RFPs so far...")
        except Exception as e:
            failed += 1
            print(f"  [{i}/{len(all_rfps)}] Update FAILED {rfp_id}: {e}")

    print(f"\n{'=' * 60}")
    print(f"  Pre-fill complete!")
    print(f"  Updated:             {updated}")
    print(f"  Already had data:    {skipped_has_data}")
    print(f"  Skipped (no Excel):  {skipped_no_excel}")
    print(f"  Skipped (no items):  {skipped_no_materials}")
    print(f"  Failed:              {failed}")
    print(f"  Total RFPs:          {len(all_rfps)}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
