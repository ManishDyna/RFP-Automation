# 🔍 COMPLETE MATERIAL MATCHING LOGIC - RFP AUTOMATION SYSTEM

## 📋 OVERVIEW
This document explains the **complete matching logic** for how RFP materials are matched against the master material database.

---

## 📂 DATA SOURCES

### 1. Master Material CSV
- **Path**: `C:\Users\Manish.Soni\Downloads\material.csv`
- **SharePoint**: `SP_BASE_FOLDER/master-files/material.csv`
- **Cached Location**: `ALLRFPs/master_material.csv`
- **Total Records**: 539 materials
- **Columns**:
  - `Material` - 9-digit material code (e.g., 908101001)
  - `Material Description` - Full text description (e.g., "CNDCTR, BR, ACSR, QUAIL (2/0 AWG), 6AL, 1ALWLD, 67.44MM2")
  - `Sales department Email`
  - `Technical Department Email`
  - `Unnamed: 4` - Additional material codes (optional)

### 2. Unique Keywords CSV
- **Path**: `C:\Users\Manish.Soni\Downloads\unique_keywords.csv`
- **SharePoint**: `SP_BASE_FOLDER/master-files/unique_keywords.csv`
- **Cached Location**: `ALLRFPs/unique_keywords.csv`
- **Keywords List** (loaded and uppercased):
  - Elect, Power, Cables, Conductor, Wire, Grounding, Rod, Conduit
  - SWGR, TFMR, RMU, Arrester, CNDCTR, Joint kit, termination kit
  - Total: ~16 keywords

### 3. RFP Excel Files
- **Location**: `C:\python\bahar-electric\Bahra-SAP-E-bidding-automation\Playwright\ALLRFPs`
- **Folder Structure**:
  ```
  ALLRFPs/
    ├── Company_Name/
    │   ├── RFP_ID/
    │   │   ├── downloaded-rfp/
    │   │   │   └── RFP_ID.xlsx
  ```
- **Example**: `ALLRFPs/Aramco e-Marketplace/6201152020/downloaded-rfp/6201152020.xlsx`

### 4. RFP Activity Log (Dataverse)
- **Source**: Dataverse Table API
- **Table**: `RFP_ACTIVITY_LOG_TABLE_API`
- **Columns Used**:
  - `RFP_ID` - Unique RFP identifier
  - `Email_Status` - "sent" means already processed
  - `RFP_End_Date` - Deadline for RFP
  - `Company_Name`, `participated`, `Link`, `owner_name`, `publish_time`

---

## 🎯 MATERIAL EXTRACTION FROM RFP EXCEL FILES

### Step 1: Read "Other Content" Sheet
**File**: `rfp/download_rfp.py:315`

```python
df = pd.read_excel(excel_path, sheet_name="Other Content")
```

- Reads the **"Other Content"** sheet from RFP Excel file
- If sheet doesn't exist, file is marked as failed

### Step 2: Find "Name" Column
**File**: `rfp/download_rfp.py:325`

```python
col_name = find_column_name(df.columns, "name")
```

- Uses **fuzzy column matching** to find column containing "name" (case-insensitive)
- Function: `helpers/core_helper.py:find_column_name()`
- Checks if any column name contains "name"

### Step 3: Find "Description" Column (Optional)
**File**: `rfp/download_rfp.py:332`

```python
col_desc = find_column_name(df.columns, "description")
```

- Uses fuzzy matching to find "description" column
- Used for **keyword extraction** in fallback matching

### Step 4: Extract 9-Digit Material Codes
**File**: `rfp/download_rfp.py:342`

```python
for mat in re.findall(r'\d{9}', name_text):
```

- **Regex Pattern**: `\d{9}` (exactly 9 consecutive digits)
- Extracts ALL 9-digit codes from the "Name" field text
- **Example**:
  - Input: "Material 908101001 - CABLE, PWR, 600V/1KV"
  - Extracted: `908101001`

---

## ⚙️ TWO-TIER MATCHING ALGORITHM

### 🥇 TIER 1: EXACT MATERIAL CODE MATCH (Primary)

**File**: `rfp/download_rfp.py:345-346`

```python
matched_rows = master[master[master_col].astype(str) == mat]
is_matched = not matched_rows.empty
```

#### How It Works:
1. Compares extracted 9-digit code **exactly** against master CSV `Material` column
2. **Comparison Type**: String exact match (case-sensitive)
3. **Match Condition**: `master['Material'] == '908101001'`

#### Example:
- **RFP Material Code**: `908101001`
- **Master CSV has**: `908101001` → ✅ **MATCH**
- **Result**: Use this row from master CSV with all details

#### What Gets Matched:
- ✅ `908101001` matches `908101001`
- ❌ `90810100` (8 digits) - not extracted
- ❌ `9081010011` (10 digits) - not extracted
- ❌ `908101002` vs `908101001` - no match

---

### 🥈 TIER 2: KEYWORD-BASED MATCHING (Fallback)

**File**: `rfp/download_rfp.py:349-363`

**Trigger**: Only when **Tier 1 exact match fails** (`if not is_matched and keywords_list:`)

#### Step 2.1: Extract Keywords from RFP Material

**File**: `rfp/download_rfp.py:351-353`

```python
name_keywords = extract_keywords_from_text(name_text)
desc_keywords = extract_keywords_from_text(description_text)
all_material_keywords = set(name_keywords + desc_keywords)
```

**Function**: `helpers/core_helper.py:extract_keywords_from_text()`

**Logic**:
1. Splits text by **comma delimiter** (`,`)
2. Converts to **UPPERCASE**
3. Strips whitespace
4. Removes empty values

**Example**:
- **Name**: `"CABLE,POWER,15KV,CU,3C,70MM2,XLPE"`
- **Extracted Keywords**: `['CABLE', 'POWER', '15KV', 'CU', '3C', '70MM2', 'XLPE']`
- **Description**: `"Joint kit for 15KV cables"`
- **Extracted Keywords**: `['JOINT KIT FOR 15KV CABLES']`
- **Combined Set**: `{'CABLE', 'POWER', '15KV', 'CU', '3C', '70MM2', 'XLPE', 'JOINT KIT FOR 15KV CABLES'}`

#### Step 2.2: Match Against Unique Keywords CSV

**File**: `rfp/download_rfp.py:356-363`

```python
for csv_keyword in keywords_list:
    for mat_keyword in all_material_keywords:
        if csv_keyword in mat_keyword or mat_keyword in csv_keyword:
            is_matched = True
            break
```

**Matching Logic**:
- **Type**: **Substring matching** (bi-directional)
- **Check 1**: Is CSV keyword a substring of material keyword?
  - Example: `"CABLE"` in `"CABLE_ASSEMBLY"` → ✅ Match
- **Check 2**: Is material keyword a substring of CSV keyword?
  - Example: `"CAB"` in `"CABLE"` → ✅ Match
- **Case Sensitivity**: **Case-sensitive** (both converted to UPPERCASE beforehand)

**Example Matches**:
| CSV Keyword | Material Keyword | Match? | Reason |
|-------------|------------------|--------|--------|
| `CABLE` | `CABLE,POWER,15KV` | ✅ Yes | "CABLE" is substring of "CABLE,POWER,15KV" |
| `POWER` | `POWER` | ✅ Yes | Exact match (substring works) |
| `CNDCTR` | `CONDUCTOR` | ❌ No | "CNDCTR" not in "CONDUCTOR" |
| `ELECT` | `ELECTRICAL` | ✅ Yes | "ELECT" in "ELECTRICAL" |
| `Joint kit` | `JOINT KIT FOR 15KV CABLES` | ✅ Yes | After uppercase: "JOINT KIT" in keyword |

#### Step 2.3: Search Master CSV for Matching Keywords

**File**: `rfp/download_rfp.py:373-401`

**Trigger**: When keyword match found BUT no exact material code match

```python
# Search in material column
temp_matches = master[master[master_col].astype(str).str.contains(
    mat_keyword, case=False, na=False
)]
```

**Logic**:
1. Takes the **matched keywords** from Step 2.1
2. Searches in **Master CSV Material column** for rows containing those keywords
3. **Case-insensitive** substring search (`.str.contains(..., case=False)`)
4. Also searches in **other text columns** (Material Description, etc.)
5. Returns **first matching row** (`.head(1)`)

**Example**:
- Material keywords: `['CABLE', 'POWER', '15KV']`
- Searches master CSV for rows where:
  - `Material` column contains "CABLE" (case-insensitive)
  - OR `Material Description` contains "CABLE"
  - OR any other text column contains "CABLE"
- Takes the **first match found**

#### Step 2.4: Create Record if No Master Row Found

**File**: `rfp/download_rfp.py:424-450`

If keyword matched but **no row found in master CSV**:
- Creates a new record with extracted material code
- Marks with `"MatchMethod": "keyword"`
- Includes all metadata but empty master CSV columns

---

## 📊 MATCHING FLOW DIAGRAM

```
┌──────────────────────────────────────────────────────────┐
│ 1. Read "Other Content" sheet from RFP Excel file       │
└────────────────────┬─────────────────────────────────────┘
                     │
┌────────────────────▼─────────────────────────────────────┐
│ 2. Find "Name" and "Description" columns (fuzzy match)   │
└────────────────────┬─────────────────────────────────────┘
                     │
┌────────────────────▼─────────────────────────────────────┐
│ 3. Extract 9-digit material codes: regex \d{9}          │
└────────────────────┬─────────────────────────────────────┘
                     │
         ┌───────────▼────────────┐
         │ 🥇 TIER 1: EXACT MATCH │
         │ master['Material'] ==  │
         │ extracted_code?        │
         └───────┬────────────────┘
                 │
        ┌────────┴────────┐
        │                 │
    ✅ YES              ❌ NO
        │                 │
        │         ┌───────▼──────────────────┐
        │         │ 🥈 TIER 2: KEYWORD MATCH │
        │         │ Extract keywords from    │
        │         │ Name & Description       │
        │         └───────┬──────────────────┘
        │                 │
        │         ┌───────▼──────────────────┐
        │         │ Match keywords against   │
        │         │ unique_keywords.csv      │
        │         │ (substring matching)     │
        │         └───────┬──────────────────┘
        │                 │
        │        ┌────────┴────────┐
        │        │                 │
        │    ✅ YES              ❌ NO
        │        │                 │
        │        │                 │
        │        │         ┌───────▼──────────┐
        │        │         │ ❌ NOT MATCHED   │
        │        │         │ Add to           │
        │        │         │ not_matched_files│
        │        │         └──────────────────┘
        │        │
        │  ┌─────▼─────────────────────┐
        │  │ Search master CSV for     │
        │  │ rows containing keywords  │
        │  │ (case-insensitive)        │
        │  └─────┬─────────────────────┘
        │        │
        │  ┌─────┴─────┐
        │  │           │
        │ Found     Not Found
        │  │           │
        │  │     ┌─────▼──────────────┐
        │  │     │ Create new record  │
        │  │     │ with material code │
        │  │     │ Mark: "keyword"    │
        │  │     └─────┬──────────────┘
        │  │           │
        ▼  ▼           ▼
┌────────────────────────────────────┐
│ ✅ MATCHED: Create output record  │
│ - SourceFile                       │
│ - RFP_Title                        │
│ - RFP_End_Date                     │
│ - ExtractedMaterial                │
│ - All master CSV columns           │
│ - Excel columns 2,7,13,14,17,19,22 │
└────────────────────────────────────┘
```

---

## 📝 MATCHING CRITERIA SUMMARY

### Exact Match (Tier 1)
| Criteria | Value |
|----------|-------|
| Pattern | `\d{9}` (9-digit code) |
| Comparison | String exact match |
| Case Sensitivity | Case-sensitive |
| Column | Master `Material` column |
| Success Rate | High precision |

### Keyword Match (Tier 2)
| Criteria | Value |
|----------|-------|
| Trigger | Exact match fails |
| Extraction | Comma-separated keywords |
| Comparison | Substring (bi-directional) |
| Case Sensitivity | Case-sensitive (after UPPERCASE conversion) |
| Keyword Source | `unique_keywords.csv` (16 keywords) |
| Master Search | Case-insensitive substring |
| Ranking | First match wins (no scoring) |

---

## 🔧 KEY ALGORITHMS & FUNCTIONS

### 1. Fuzzy Column Name Matching
**File**: `helpers/core_helper.py:find_column_name()`

```python
def find_column_name(columns, search_term):
    for col in columns:
        if search_term.lower() in str(col).lower():
            return col
    return None
```

**Usage**:
- Find "name" column: checks if "name" is in column name (case-insensitive)
- Find "description" column: checks if "description" is in column name
- Find "material" column in master CSV

### 2. Keyword Extraction
**File**: `helpers/core_helper.py:extract_keywords_from_text()`

```python
def extract_keywords_from_text(
    text: str,
    delimiter: str = ',',
    to_upper: bool = True,
    strip_whitespace: bool = True
) -> list:
    if not text:
        return []
    keywords = text.split(delimiter)
    if to_upper:
        keywords = [kw.upper() for kw in keywords]
    if strip_whitespace:
        keywords = [kw.strip() for kw in keywords]
    return [kw for kw in keywords if kw]
```

**Parameters**:
- `delimiter`: `,` (comma)
- `to_upper`: `True` (converts to uppercase)
- `strip_whitespace`: `True` (removes leading/trailing spaces)

**Example**:
- Input: `"CABLE,POWER, 15KV , CU "`
- Output: `['CABLE', 'POWER', '15KV', 'CU']`

### 3. Material Code Extraction
**Regex**: `r'\d{9}'`

**Examples**:
| Input Text | Extracted Codes |
|------------|-----------------|
| `"Material 908101001 for project"` | `['908101001']` |
| `"Codes: 908101001, 905890616"` | `['908101001', '905890616']` |
| `"No code here"` | `[]` |
| `"12345678 (8 digits)"` | `[]` |
| `"1234567890 (10 digits)"` | `[]` |

---

## 📈 OUTPUT RECORDS

### Matched Material Record Structure

**File**: `rfp/download_rfp.py:407-423`

```python
record.update({
    "SourceFile": file_name,                    # RFP Excel filename
    "RFP_Title": rfp_id,                        # RFP identifier
    "RFP_End_Date": RFP_End_Date,               # Deadline from Dataverse
    "TDS_file_path": get_sharepoint_rfp_tds_path(rfp_id, mat),  # SharePoint path
    "RowNumber": idx + 2,                       # Excel row number (1-indexed)
    "ColumnName": col_name,                     # Source column name
    "ExtractedMaterial": mat                    # The 9-digit code
})
```

**Additional Columns Captured** (from RFP Excel):
- Column 2, 7, 13, 14, 17, 19, 22 from the "Other Content" sheet

**Master CSV Columns** (all included in record):
- `Material`
- `Material Description`
- `Sales department Email`
- `Technical Department Email`
- `Unnamed: 4`

### Output CSV File

**Path**: `ALLRFPs/matched_materials_YYYYMMDD_HHMMSS.csv`

**Uploaded To**: `SP_BASE_FOLDER/ALLRFPs/` (SharePoint)

**Contains**:
- All matched materials from all RFP files processed
- Combined records from Tier 1 and Tier 2 matches
- Metadata columns for tracking source

---

## ⚠️ SKIP CONDITIONS

### 1. RFP Already Processed
**File**: `rfp/download_rfp.py:303-309`

```python
if email_status == "sent":
    files_skipped += 1
    continue
```

- Checks RFP Activity Log from Dataverse
- If `Email_Status == "sent"`, skips processing
- Prevents duplicate email notifications

### 2. Sheet Not Found
**File**: `rfp/download_rfp.py:318-323`

```python
except Exception as e:
    files_failed += 1
    continue
```

- If "Other Content" sheet doesn't exist
- Marks as failed and skips to next file

### 3. Column Not Found
**File**: `rfp/download_rfp.py:326-329`

```python
if not col_name:
    files_failed += 1
    continue
```

- If "Name" column not found in sheet
- Marks as failed and skips to next file

---

## 📊 STATISTICS TRACKED

**File**: `rfp/download_rfp.py:299-301, 311, 317, 322, 328, 452`

```python
files_processed = 0      # Successfully read Excel files
files_skipped = 0        # Already sent, skipped
files_failed = 0         # Could not read or parse
all_matches = []         # All matched material records
not_mateched_files = []  # RFP files with no matches
```

**Summary Report**:
```
✅ Files Processed: 45
⏭️ Files Skipped: 12 (already sent)
❌ Files Failed: 3 (read errors)
📊 Total Matches: 234 materials
⚠️ Not Matched: 5 RFP files
```

---

## 🎯 KEY CHARACTERISTICS

| Characteristic | Details |
|----------------|---------|
| **Precision** | High for exact match, Lower for keyword match |
| **Recall** | Medium (only 9-digit codes extracted) |
| **Case Sensitivity** | Mixed (exact: sensitive, keyword: insensitive in master search) |
| **Fuzzy Matching** | None (no typo tolerance, no similarity scoring) |
| **Ranking** | None (first match wins) |
| **Performance** | Fast for exact match, Slower for keyword search |
| **Scalability** | Good (uses pandas vectorized operations) |
| **False Positives** | Possible in keyword matching (e.g., "CAB" matches "CABINET" and "CABLE") |
| **False Negatives** | Possible (e.g., 8-digit codes not extracted, typos not handled) |

---

## 🔍 EXAMPLE MATCHING SCENARIOS

### Scenario 1: Exact Match Success
**RFP Material**:
- Name: `"Material 908101001 - CABLE, PWR, 600V/1KV, CU, 1C, 35MM2, XLPE"`
- Description: `"Power cable for electrical distribution"`

**Processing**:
1. Extract code: `908101001`
2. Exact match in master CSV: ✅ FOUND
3. Result: Use master row with all details

**Output Record**:
```
Material: 908101001
Material Description: "CABLE, PWR, 600V/1KV, CU, 1C, 35MM2, XLPE"
ExtractedMaterial: 908101001
MatchMethod: [not set] (exact match)
```

---

### Scenario 2: Keyword Match Success
**RFP Material**:
- Name: `"Material 999999999 - CABLE, POWER, 15KV, AL, 3C, 500MM2"`
- Description: `"Cable for power distribution"`

**Processing**:
1. Extract code: `999999999`
2. Exact match in master CSV: ❌ NOT FOUND (code doesn't exist)
3. Extract keywords from Name: `['CABLE', 'POWER', '15KV', 'AL', '3C', '500MM2']`
4. Extract keywords from Description: `['CABLE FOR POWER DISTRIBUTION']`
5. Check against unique_keywords.csv:
   - `"CABLE"` in `"CABLE"` → ✅ MATCH
   - `"POWER"` in `"POWER"` → ✅ MATCH
6. Search master CSV for "CABLE":
   - Found: `908111002 - "CABLE, PWR, 600V/1KV, CU, 1C, 120MM2, XLPE"`
7. Result: Use this row as match

**Output Record**:
```
Material: 908111002 (from master CSV, not 999999999)
Material Description: "CABLE, PWR, 600V/1KV, CU, 1C, 120MM2, XLPE"
ExtractedMaterial: 999999999
MatchMethod: [not set or implicit keyword match]
```

---

### Scenario 3: Keyword Match, No Master Row
**RFP Material**:
- Name: `"Material 888888888 - TRANSFORMER, 11KV, 500KVA"`
- Description: `"Transformer for substation"`

**Processing**:
1. Extract code: `888888888`
2. Exact match: ❌ NOT FOUND
3. Extract keywords: `['TRANSFORMER', '11KV', '500KVA']`, `['TRANSFORMER FOR SUBSTATION']`
4. Check against unique_keywords.csv:
   - `"TFMR"` in `"TRANSFORMER"` → ❌ NO MATCH (substring not found)
   - No other keywords match
5. Result: ❌ NOT MATCHED

**Output**: Added to `not_mateched_files` list

**Alternative** (if TFMR was in keyword):
- If keyword matched but no master row found
- Create new record with material code `888888888`
- Mark with `MatchMethod: "keyword"`

---

### Scenario 4: Multiple Material Codes in Name
**RFP Material**:
- Name: `"Materials 908101001 and 908111002 required for project"`

**Processing**:
1. Extract codes: `['908101001', '908111002']`
2. For `908101001`:
   - Exact match: ✅ FOUND
   - Create record 1
3. For `908111002`:
   - Exact match: ✅ FOUND
   - Create record 2

**Output**: 2 separate matched records

---

## 🚀 COMPLETE PROCESSING PIPELINE

```
1. download_rfp_files()
   ├─ Login to RFP portal
   ├─ Download new RFP Excel files
   └─ Save to ALLRFPs/Company/RFP_ID/downloaded-rfp/

2. process_folder()
   ├─ Load master_material.csv from SharePoint
   ├─ Load unique_keywords.csv from SharePoint
   ├─ Load RFP activity log from Dataverse
   │
   ├─ For each RFP Excel file:
   │  ├─ Check if already processed (Email_Status == "sent")
   │  ├─ Read "Other Content" sheet
   │  ├─ Find "Name" and "Description" columns
   │  │
   │  ├─ For each row:
   │  │  ├─ Extract 9-digit material codes (regex)
   │  │  │
   │  │  ├─ For each material code:
   │  │  │  ├─ 🥇 Try exact match in master CSV
   │  │  │  │  └─ If found → create record
   │  │  │  │
   │  │  │  ├─ 🥈 If not found, try keyword matching:
   │  │  │  │  ├─ Extract keywords from Name & Description
   │  │  │  │  ├─ Match against unique_keywords.csv
   │  │  │  │  ├─ If keyword matches:
   │  │  │  │  │  ├─ Search master CSV for keyword
   │  │  │  │  │  ├─ If found in master → use that row
   │  │  │  │  │  └─ If not found → create record with code + "keyword" marker
   │  │  │  │  └─ If no keyword match → add to not_matched_files
   │
   ├─ Combine all matched records
   ├─ Create CSV: matched_materials_YYYYMMDD_HHMMSS.csv
   ├─ Upload to SharePoint: SP_BASE_FOLDER/ALLRFPs/
   └─ Return results

3. trigger_email()
   ├─ Read matched materials CSV
   ├─ Send email with attachment
   └─ Update RFP activity log in Dataverse (Email_Status = "sent")
```

---

## 📌 IMPORTANT NOTES

1. **9-Digit Requirement**: Only extracts material codes that are exactly 9 digits
   - 8 digits: ❌ Not extracted
   - 10 digits: ❌ Not extracted
   - Other formats: ❌ Not extracted

2. **Sheet Name**: Must be exactly **"Other Content"**
   - Case-sensitive in code but Excel may be case-insensitive
   - If sheet doesn't exist → file fails

3. **No Similarity Scoring**:
   - No fuzzy matching (e.g., "CABLE" won't match "CABL" typo)
   - No confidence scores
   - No ranking of multiple matches

4. **Substring Matching Risks**:
   - "CAB" matches "CABLE" and "CABINET"
   - "ELECT" matches "ELECTRICAL" and "ELECTROLYTE"
   - "ROD" matches "GROUNDING ROD" and "ELECTRODE"

5. **Performance**:
   - Exact match: Very fast (O(n) lookup)
   - Keyword match: Slower (nested loops + DataFrame searches)
   - Large RFP files: May take several minutes

6. **Data Quality Dependencies**:
   - Master CSV must be up-to-date
   - Unique keywords CSV must cover common material types
   - RFP Excel files must have consistent column names

---

## 🎓 REFERENCES

### Code Files
- `rfp/download_rfp.py:184-504` - Main processing logic
- `helpers/core_helper.py:644-681` - Keyword extraction
- `helpers/core_helper.py:51-54` - Fuzzy column matching
- `rfp/submit_rfp.py:316` - Material extraction for submission

### Data Files
- `C:\Users\Manish.Soni\Downloads\material.csv` - Master material database
- `C:\Users\Manish.Soni\Downloads\unique_keywords.csv` - Keywords for matching
- `C:\Users\Manish.Soni\Downloads\RFP-Analysis.xlsx` - Analysis output
- `C:\python\bahar-electric\Bahra-SAP-E-bidding-automation\Playwright\ALLRFPs` - RFP files

---

## ✅ SUMMARY

The RFP Material Matching System uses a **two-tier approach**:

1. **Tier 1 (Primary)**: Exact 9-digit material code matching
   - Fast, precise, high confidence
   - Direct lookup in master CSV

2. **Tier 2 (Fallback)**: Keyword-based matching
   - Extracts keywords from Name & Description
   - Matches against curated keyword list
   - Searches master CSV for related materials
   - Lower precision but higher recall

**Key Strengths**:
- Simple, fast exact matching
- Fallback ensures some materials don't get missed
- Leverages existing master database

**Key Limitations**:
- No fuzzy matching (typos fail)
- Only 9-digit codes extracted
- Substring matching can cause false positives
- No ranking/scoring of matches
- Keyword list requires manual maintenance

---

*Generated: 2026-02-14*
*System: RFP Automation - Material Matching Logic v1.0*
