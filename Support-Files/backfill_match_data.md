# Backfill Match Data for Old RFPs

## Context

The `bahra_rfps` table (`cr673_requestforproposal`) currently has mixed data:
- **Automation rows**: 1 row per RFP with `Matched_Data` JSON (old RFPs have it empty)
- **Manual rows**: Multiple rows per RFP with individual `Material_Code`, `Material_Description`

We're standardizing on **Single Row Per RFP** — all material data in `Matched_Data` JSON + summary in direct columns.

---

## Table Columns (from Dataverse)

### 6 Target Columns for Backfill:

| Column | Schema Name | Current State | After Backfill |
|--------|-------------|--------------|----------------|
| `Matched_Data` | cr673_matchedd... | Empty for old RFPs | JSON array of ALL materials (matched + unmatched) |
| `Material_Code` | cr6db_Material_C... | **Always empty** (never written by code) | Comma-separated matched codes: `"123456789,987654321"` |
| `Material_Description` | cr6db_Material_... | **Always empty** (never written by code) | Comma-separated matched descriptions |
| `Material_Matched` | cr6db_Material_... | Empty for old RFPs | `"Yes"` or `"No"` |
| `Keyword_Matched` | cr6db_Keyword_... | Empty for old RFPs | `"Yes"` or `"No"` |
| `Matched_Keywords` | cr6db_Matched_... | **Always empty** (never written by code) | Comma-separated keywords: `"CABLE,XLPE"` |

### Columns NOT in the table (code writes silently fail):
- `no_of_matched_materials` — does NOT exist in Dataverse
- `no_of_matched_keywords` — does NOT exist in Dataverse

### Columns that exist but are never read:
- `match_rate_pct`, `exact_match_count`, `keyword_match_count`, `total_line_items` — written during download but no route/frontend reads them

---

## How Data Is Stored Currently (process_folder)

During RFP download, `rfp/download_rfp.py` → `process_folder()`:
1. Extracts 9-digit material codes from RFP Excel
2. Matches against master (exact code) + keywords (fallback)
3. Builds DataFrame, converts to JSON
4. `log_rfp_activity()` writes:
   - `Matched_Data` = JSON of all materials
   - `Material_Matched` / `Keyword_Matched` = "Yes"/"No"
   - Does **NOT** write: `Material_Code`, `Material_Description`, `Matched_Keywords`

### Matched_Data JSON Format (per item):
```json
{
  "Material": "123456789",
  "Material Description": "Cable 3x150mm",
  "SourceFile": "RFP_file.xls",
  "RFP_Title": "DOC123456",
  "RFP_End_Date": "3/15/2026",
  "TDS_file_path": "https://...",
  "RowNumber": 5,
  "ColumnName": "Items",
  "ExtractedMaterial": "123456789",
  "MatchMethod": "exact" | "keyword" | null,
  "is_matched": true | false,
  "ExcelName": "Cable 3x150mm",
  "ExcelDescription": "Power cable..."
}
```

---

## How Data Will Be Stored After Backfill

Same JSON format in `Matched_Data`, PLUS 3 new columns populated:

| Column | Example Value | Derived From |
|--------|--------------|-------------|
| `Material_Code` | `"123456789,987654321"` | `ExtractedMaterial` where `is_matched=true` |
| `Material_Description` | `"Power Cable,Conductor ACSR"` | `Material Description` where `is_matched=true` |
| `Matched_Keywords` | `"CABLE,XLPE,CONDUCTOR"` | Keywords from master list that matched |

---

## Script: `Support-Files/backfill_match_data.py`

1. Initialize DataverseClient + GraphClient
2. Load master materials + keywords
3. Query RFPs where `Matched_Data` is empty
4. For each RFP:
   - Find Excel via SharePoint
   - Extract materials from Excel
   - Match against master (exact + keyword)
   - Update Dataverse: all 6 columns
5. Log progress, skip errors, print summary

**Idempotent**: only processes RFPs with empty `Matched_Data`.

---

## Files Involved

| File | Action |
|------|--------|
| `Support-Files/backfill_match_data.py` | **NEW** — backfill script |
| `helpers/core_helper.py` | **MODIFY** — add `match_materials_against_master()` shared function |
| `core/log_events.py` | **MODIFY** — add Material_Code/Description/Keywords params, remove non-existent column writes |
| `rfp/download_rfp.py` (~line 630) | **MODIFY** — compute & pass new column values |
| `routes/dashboard.py` (line 2302) | **REFACTOR** — use shared matching function |

---

## Verification

1. Run `python Support-Files/backfill_match_data.py`
2. Check Dataverse: old RFPs now have all 6 columns populated
3. Dashboard: progress bars work without live Excel fallback
4. Dialog: shows correct matched/unmatched materials
5. Material insights: uses direct columns (primary path)
6. Re-run: skips already-filled RFPs
7. New RFP download: all 6 columns populated automatically
