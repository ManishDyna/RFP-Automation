# RFP Automation System - Flow Design Document

---

## System Architecture Overview

```
+---------------------+       +---------------------+       +--------------------+
|   Frontend (UI)     |       |  FastAPI Backend     |       |  External Systems  |
|  Dashboard (8000)   |<----->|  Automation (8100)   |<----->|  Ariba Portal      |
|  Jinja2 Templates   |       |  Playwright Browser  |       |  Dataverse (D365)  |
|  JavaScript Polling  |       |  Async Task Runner   |       |  SharePoint (Graph)|
+---------------------+       +---------------------+       +--------------------+
```

**Tech Stack:** FastAPI | Playwright | Dataverse OData API | SharePoint Graph API | Jinja2 + JS

---

## Dataverse Tables

| Table                          | API Name                        | Purpose                      |
| ------------------------------ | ------------------------------- | ---------------------------- |
| `cr673_requestforproposal`     | `cr673_requestforproposals`     | Main RFP records & status    |
| `cr673_bahra_automation_log1`  | `cr673_bahra_automation_log1s`  | Automation run logs          |
| `cr673_bhara_rfp_status`       | `cr673_bhara_rfp_statuses`      | RFP status change history    |

## SharePoint Folder Structure

```
Documents/
  RFP-logs/
  ├── ALLRFPs/
  │   └── {Company}/
  │       └── {RFP_Title}/
  │           ├── downloaded-rfp/          <-- Downloaded Excel from portal
  │           │   └── {clean_title}.xls
  │           ├── rfp-upload-file/         <-- Filled Excel for submission
  │           │   └── {clean_title}.xls
  │           └── TDS-files/               <-- Technical Data Sheets
  │               └── {material_code}_TDS.pdf
  │
  ├── master-files/
  │   ├── material.csv                     <-- Master material list
  │   └── unique_keywords.csv             <-- Keywords for matching
  │
  └── LOGS/
      └── {operation}/{timestamp}/
          └── error_log.html               <-- Error logs for audit
```

---

# FLOW 1: DOWNLOAD RFP

**Endpoint:** `GET /download-rfp?company={company}` or `GET /download-rfps-automation`

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          DOWNLOAD RFP - COMPLETE FLOW                           │
└─────────────────────────────────────────────────────────────────────────────────┘

  ┌──────────┐
  │  START   │  User clicks "Download RFP" on Dashboard (or scheduled trigger)
  └────┬─────┘
       │
       ▼
  ┌──────────────────────────────────┐
  │ 1. API REQUEST                   │
  │    POST /download-rfp            │
  │    Body: { company }             │
  │    Returns: 202 Accepted (async) │
  └────────────┬─────────────────────┘
               │
               ▼
  ┌──────────────────────────────────────────────┐
  │ 2. INITIALIZE AUTOMATION                      │
  │    - Check _RUN_STATE (prevent duplicate runs) │
  │    - Generate RUN_ID                           │
  │  ✦ DATABASE: INSERT automation_log             │
  │    Table: cr673_bahra_automation_log1s          │
  │    Data: { run_id, type:"download", status:     │
  │            "started", timestamp }               │
  └────────────┬───────────────────────────────────┘
               │
               ▼
  ┌──────────────────────────────────────────────┐
  │ 3. LAUNCH PLAYWRIGHT BROWSER                  │
  │    - Start headless Chromium                   │
  │    - Login to Ariba Portal (username/password) │
  │    - Select Company from dropdown              │
  └────────────┬───────────────────────────────────┘
               │
               ▼
  ┌──────────────────────────────────────────────┐
  │ 4. SCRAPE ALL RFPs FROM PORTAL                │
  │    - Navigate to Open Events & Participated    │
  │    - Extract: RFP_ID, Title, Link, Status,     │
  │              End Date, Owner                    │
  └────────────┬───────────────────────────────────┘
               │
               ▼
  ┌──────────────────────────────────────────────────┐
  │ 5. FILTER NEW RFPs                                │
  │  ✦ DATABASE: QUERY existing RFPs                  │
  │    Table: cr673_requestforproposals                │
  │    Filter: Company_Name eq '{company}'             │
  │    Select: RFP_ID, Email_Status, participated      │
  │                                                    │
  │    Compare portal list vs DB → identify NEW RFPs   │
  └────────────┬───────────────────────────────────────┘
               │
               ▼
       ┌───────┴──────────┐
       │  For Each NEW RFP │
       └───────┬──────────┘
               │
               ▼
  ┌──────────────────────────────────────────────────────┐
  │ 6. DOWNLOAD EXCEL FROM PORTAL                         │
  │    - Open RFP link in new browser page                │
  │    - Extract owner_name & publish_time                │
  │    - Click "Download" button                          │
  │    - Playwright captures file via expect_download()   │
  │                                                       │
  │  ✦ FILE CREATED (Local):                              │
  │    Path: ALLRFPs/{company}/{rfp_title}/               │
  │          downloaded-rfp/{clean_title}.xls              │
  └────────────┬─────────────────────────────────────────┘
               │
               ▼
  ┌──────────────────────────────────────────────────────┐
  │ 7. UPLOAD EXCEL TO SHAREPOINT                         │
  │  ✦ SHAREPOINT: Create folders (if missing)            │
  │    Path: RFP-logs/ALLRFPs/{company}/{rfp_title}/      │
  │          downloaded-rfp/                               │
  │                                                       │
  │  ✦ SHAREPOINT: Upload file                            │
  │    File: {clean_title}.xls                            │
  │    Destination: .../downloaded-rfp/{clean_title}.xls   │
  └────────────┬─────────────────────────────────────────┘
               │
               ▼
  ┌──────────────────────────────────────────────────────┐
  │ 8. LOG RFP TO DATABASE                                │
  │  ✦ DATABASE: INSERT new RFP record                    │
  │    Table: cr673_requestforproposals                    │
  │    Data: {                                            │
  │      RFP_ID: "...",                                   │
  │      Company_Name: "...",                              │
  │      Downloaded_At: "2026-02-18 10:30:00",            │
  │      participated: "no",                               │
  │      Link: "https://ariba.com/...",                    │
  │      RFP_End_Date: "2026-03-01",                      │
  │      owner_name: "John Smith",                         │
  │      publish_time: "2026-02-10 14:00:00"              │
  │    }                                                   │
  └────────────┬─────────────────────────────────────────┘
               │
               ▼
  ┌──────────────────────────────────────────────────────────────┐
  │ 9. PROCESS DOWNLOADED EXCEL (Material Matching)               │
  │                                                               │
  │  ✦ SHAREPOINT: Download master files                          │
  │    - material.csv    from RFP-logs/master-files/material.csv   │
  │    - keywords.csv    from RFP-logs/master-files/               │
  │      unique_keywords.csv                                       │
  │                                                               │
  │    Read Excel "Other Content" sheet:                           │
  │    - Extract material codes (regex: \d{9})                    │
  │    - Extract material names & descriptions                     │
  │                                                               │
  │    MATCHING LOGIC:                                            │
  │    ┌─────────────────────────────────────────┐                │
  │    │ For each material in RFP:               │                │
  │    │  1. Exact Match: code in material.csv?  │                │
  │    │     YES → use master row data           │                │
  │    │     NO  → go to step 2                  │                │
  │    │  2. Keyword Match: name/desc keywords   │                │
  │    │     vs unique_keywords.csv              │                │
  │    │     MATCH → use keyword-matched data    │                │
  │    │     NO MATCH → mark as unmatched        │                │
  │    └─────────────────────────────────────────┘                │
  │                                                               │
  │  ✦ FILE CREATED (Local):                                      │
  │    Path: ALLRFPs/{company}/matched_materials_{timestamp}.csv  │
  └────────────┬─────────────────────────────────────────────────┘
               │
               ▼
  ┌──────────────────────────────────────────────────────┐
  │ 10. UPLOAD MATCHED CSV TO SHAREPOINT                  │
  │  ✦ SHAREPOINT: Upload file                            │
  │    File: matched_materials_{timestamp}.csv            │
  │    Dest: RFP-logs/ALLRFPs/{company}/                  │
  └────────────┬─────────────────────────────────────────┘
               │
               ▼
  ┌──────────────────────────────────────────────────────┐
  │ 11. UPDATE DATABASE WITH MATCH RESULTS                │
  │  ✦ DATABASE: UPDATE RFP record                        │
  │    Table: cr673_requestforproposals                    │
  │    Fields: {                                          │
  │      Material_Matched: count,                          │
  │      Keyword_Matched: count,                           │
  │      Matched_Data: "csv data as text"                  │
  │    }                                                   │
  └────────────┬─────────────────────────────────────────┘
               │
               ▼
  ┌──────────────────────────────────────────────────────┐
  │ 12. SEND EMAIL NOTIFICATION                           │
  │  ✦ DATABASE: UPDATE Email_Status → "sent"             │
  │    Table: cr673_requestforproposals                    │
  │                                                       │
  │    Email contains:                                    │
  │    - RFP details (ID, company, deadline)              │
  │    - Material match summary                           │
  │    - Attached CSV file                                │
  │    (If no new RFPs: "No New RFP Available" email)     │
  └────────────┬─────────────────────────────────────────┘
               │
               ▼
  ┌──────────────────────────────────────────────────────┐
  │ 13. FINALIZE                                          │
  │  ✦ DATABASE: UPDATE automation_log                    │
  │    Table: cr673_bahra_automation_log1s                 │
  │    Data: { status: "completed", end_time }             │
  │                                                       │
  │    Close browser → Release _RUN_STATE                  │
  └────────────┬─────────────────────────────────────────┘
               │
               ▼
           ┌───────┐
           │  END  │
           └───────┘
```

### Download RFP - Summary Table

| Step | Action                      | Database              | SharePoint              | File Created (Local)                                  |
| ---- | --------------------------- | --------------------- | ----------------------- | ----------------------------------------------------- |
| 2    | Initialize                  | INSERT automation_log | -                       | -                                                     |
| 5    | Filter new RFPs             | QUERY RFPs            | -                       | -                                                     |
| 6    | Download Excel from portal  | -                     | -                       | `ALLRFPs/{co}/{rfp}/downloaded-rfp/{title}.xls`       |
| 7    | Upload Excel                | -                     | UPLOAD .xls             | -                                                     |
| 8    | Log RFP record              | INSERT RFP            | -                       | -                                                     |
| 9    | Material matching           | -                     | DOWNLOAD master CSVs    | `ALLRFPs/{co}/matched_materials_{ts}.csv`             |
| 10   | Upload matched CSV          | -                     | UPLOAD .csv             | -                                                     |
| 11   | Update match results        | UPDATE RFP            | -                       | -                                                     |
| 12   | Send email                  | UPDATE Email_Status   | -                       | -                                                     |
| 13   | Finalize                    | UPDATE automation_log | -                       | -                                                     |

---

# FLOW 2: SUBMIT RFP

**Endpoint:** `POST /dashboard/submit-rfp` (with file upload) or `POST /submit-rfp` (RFP ID only)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           SUBMIT RFP - COMPLETE FLOW                            │
└─────────────────────────────────────────────────────────────────────────────────┘

  ┌──────────┐
  │  START   │  User clicks "Submit RFP" on Dashboard
  └────┬─────┘
       │
       ▼
  ┌──────────────────────────────────────────────────────────┐
  │ 1. USER UPLOADS FILES ON DASHBOARD                        │
  │    - Select RFP from dropdown                              │
  │    - Upload filled Excel file (.xls)                       │
  │    - Upload TDS PDF files (per material)                   │
  │    - Select company                                        │
  │    - Click "Submit"                                        │
  │                                                            │
  │    Frontend sends:                                        │
  │    POST /dashboard/submit-rfp                              │
  │    Content-Type: multipart/form-data                       │
  │    Body: { rfp_id, company, excel_file, technical_files[] }│
  │    Returns: 202 Accepted (async)                           │
  └────────────┬───────────────────────────────────────────────┘
               │
               ▼
  ┌──────────────────────────────────────────────────────────┐
  │ 2. SAVE FILES LOCALLY (Temp)                               │
  │  ✦ FILE CREATED (Local):                                   │
  │    Excel: ALLRFPs/{company}/{rfp_title}/                   │
  │           rfp-upload-file/{clean_title}.xls                │
  │    TDS:   ALLRFPs/{company}/{rfp_title}/                   │
  │           TDS-files/{material_code}_TDS.pdf                │
  └────────────┬───────────────────────────────────────────────┘
               │
               ▼
  ┌──────────────────────────────────────────────────────────────────┐
  │ 3. UPLOAD FILES TO SHAREPOINT (Pre-automation backup)            │
  │                                                                  │
  │  ✦ SHAREPOINT: Create folder paths (if missing)                  │
  │    - RFP-logs/ALLRFPs/{company}/{rfp_title}/downloaded-rfp/      │
  │    - RFP-logs/ALLRFPs/{company}/{rfp_title}/rfp-upload-file/     │
  │    - RFP-logs/ALLRFPs/{company}/{rfp_title}/TDS-files/           │
  │                                                                  │
  │  ✦ SHAREPOINT: Upload Excel (2 copies)                           │
  │    Copy 1: .../downloaded-rfp/{clean_title}.xls  (backup)        │
  │    Copy 2: .../rfp-upload-file/{clean_title}.xls (for automation)│
  │                                                                  │
  │  ✦ SHAREPOINT: Upload TDS PDFs                                   │
  │    Each: .../TDS-files/{material_code}_TDS.pdf                   │
  └────────────┬─────────────────────────────────────────────────────┘
               │
               ▼
  ┌──────────────────────────────────────────────┐
  │ 4. INITIALIZE AUTOMATION                      │
  │    - Check _RUN_STATE                          │
  │    - Generate RUN_ID                           │
  │  ✦ DATABASE: INSERT automation_log             │
  │    Table: cr673_bahra_automation_log1s          │
  │    Data: { run_id, type:"submit",               │
  │            status:"started" }                   │
  └────────────┬───────────────────────────────────┘
               │
               ▼
  ┌──────────────────────────────────────────────┐
  │ 5. LAUNCH PLAYWRIGHT BROWSER                  │
  │    - Start headless Chromium                   │
  │    - Login to Ariba Portal                     │
  │    - Select Company                            │
  │    - Scrape RFPs → find target RFP             │
  └────────────┬───────────────────────────────────┘
               │
               ▼
  ┌──────────────────────────────────────────────┐
  │ 6. OPEN RFP & NAVIGATE                        │
  │    Step 1: Open RFP link                       │
  │    Step 2: Click "I intend to respond"         │
  │            Accept terms/agreement              │
  └────────────┬───────────────────────────────────┘
               │
               ▼
  ┌──────────────────────────────────────────────────────┐
  │ 7. PRICING STEP (Step 3 on portal)                    │
  │    - Select currency → SAR                            │
  │    - Click "Select Using Excel"                       │
  │    - Download blank template from portal               │
  │                                                       │
  │  ✦ FILE CREATED (Local - Temp):                       │
  │    Blank template downloaded by Playwright              │
  └────────────┬─────────────────────────────────────────┘
               │
               ▼
  ┌──────────────────────────────────────────────────────┐
  │ 8. UPLOAD FILLED EXCEL TO PORTAL                      │
  │                                                       │
  │  ✦ SHAREPOINT: Download filled Excel                  │
  │    (fetch from rfp-upload-file/ if not local)          │
  │                                                       │
  │    - Upload filled .xls file to portal form            │
  │    - Portal processes & imports bidding data            │
  │    - Wait for import confirmation                      │
  └────────────┬─────────────────────────────────────────┘
               │
               ▼
  ┌──────────────────────────────────────────────────────┐
  │ 9. ATTACH TDS FILES (Step 4 - per material code)      │
  │                                                       │
  │    For each material row in the RFP:                   │
  │    ┌─────────────────────────────────────────────┐    │
  │    │ - Locate material row on portal              │    │
  │    │ - Click "Add Attachment"                      │    │
  │    │ - Upload matching TDS PDF from local path     │    │
  │    │   ALLRFPs/{co}/{rfp}/TDS-files/              │    │
  │    │   {material_code}_TDS.pdf                     │    │
  │    └─────────────────────────────────────────────┘    │
  └────────────┬─────────────────────────────────────────┘
               │
               ▼
  ┌──────────────────────────────────────────────────────┐
  │ 10. SAVE DRAFT ON PORTAL                              │
  │    - Click "Save Draft" button (NOT final submit)      │
  │    - Wait for confirmation message                     │
  │    - Portal status changes to "Saved Draft"            │
  └────────────┬─────────────────────────────────────────┘
               │
               ▼
  ┌──────────────────────────────────────────────────────┐
  │ 11. UPDATE DATABASE                                    │
  │  ✦ DATABASE: UPDATE RFP participation status           │
  │    Table: cr673_requestforproposals                     │
  │    Filter: RFP_ID eq '{rfp_id}'                        │
  │    Update: { participated: "saved_draft" }              │
  │                                                        │
  │  ✦ DATABASE: INSERT status history                     │
  │    Table: cr673_bhara_rfp_statuses                     │
  │    Data: { rfp_id, old:"no", new:"saved_draft",        │
  │            timestamp }                                  │
  └────────────┬─────────────────────────────────────────┘
               │
               ▼
  ┌──────────────────────────────────────────────────────┐
  │ 12. SEND SUCCESS EMAIL                                 │
  │  ✦ DATABASE: UPDATE Email_Status                       │
  │    Email flag: "rfp_saved_draft"                       │
  │    Content: RFP ID, company, status confirmation       │
  └────────────┬─────────────────────────────────────────┘
               │
               ▼
  ┌──────────────────────────────────────────────────────┐
  │ 13. FINALIZE                                          │
  │  ✦ DATABASE: UPDATE automation_log                    │
  │    Data: { status: "completed", end_time }             │
  │    Close browser → Release _RUN_STATE                  │
  └────────────┬─────────────────────────────────────────┘
               │
               ▼
           ┌───────┐
           │  END  │
           └───────┘
```

### Submit RFP - Summary Table

| Step | Action                        | Database               | SharePoint                        | File Created (Local)                             |
| ---- | ----------------------------- | ---------------------- | --------------------------------- | ------------------------------------------------ |
| 2    | Save files locally            | -                      | -                                 | `.../rfp-upload-file/{title}.xls`                |
| 2    | Save TDS locally              | -                      | -                                 | `.../TDS-files/{code}_TDS.pdf`                   |
| 3    | Upload Excel (backup)         | -                      | UPLOAD .xls (2 copies)            | -                                                |
| 3    | Upload TDS PDFs               | -                      | UPLOAD .pdf (per material)        | -                                                |
| 4    | Initialize automation         | INSERT automation_log  | -                                 | -                                                |
| 7    | Download blank template       | -                      | -                                 | temp template .xls                               |
| 8    | Fetch filled Excel            | -                      | DOWNLOAD .xls (if needed)         | -                                                |
| 11   | Update RFP status             | UPDATE participated    | -                                 | -                                                |
| 11   | Log status change             | INSERT status_history  | -                                 | -                                                |
| 12   | Send email                    | UPDATE Email_Status    | -                                 | -                                                |
| 13   | Finalize                      | UPDATE automation_log  | -                                 | -                                                |

---

# FLOW 3: DECLINE RFP

**Endpoint:** `POST /decline-rfp` with `{ rfp_id, company }`

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          DECLINE RFP - COMPLETE FLOW                            │
└─────────────────────────────────────────────────────────────────────────────────┘

  ┌──────────┐
  │  START   │  User clicks "Decline RFP" on Dashboard
  └────┬─────┘
       │
       ▼
  ┌──────────────────────────────────────────────────────────┐
  │ 1. API REQUEST                                            │
  │    POST /decline-rfp                                      │
  │    Body: { rfp_id: "...", company: "..." }                │
  │    Returns: 202 Accepted (async)                          │
  └────────────┬─────────────────────────────────────────────┘
               │
               ▼
  ┌──────────────────────────────────────────────┐
  │ 2. INITIALIZE AUTOMATION                      │
  │    - Check _RUN_STATE                          │
  │    - Generate RUN_ID                           │
  │  ✦ DATABASE: INSERT automation_log             │
  │    Table: cr673_bahra_automation_log1s          │
  │    Data: { run_id, type:"decline",              │
  │            status:"started" }                   │
  └────────────┬───────────────────────────────────┘
               │
               ▼
  ┌──────────────────────────────────────────────┐
  │ 3. PRE-CHECK DATABASE                         │
  │  ✦ DATABASE: QUERY RFP status                 │
  │    Table: cr673_requestforproposals            │
  │    Filter: RFP_ID eq '{rfp_id}'               │
  │            AND participated ne 'declined'      │
  │                                               │
  │    If already declined → SKIP & return         │
  └────────────┬───────────────────────────────────┘
               │ (not yet declined)
               ▼
  ┌──────────────────────────────────────────────┐
  │ 4. LAUNCH PLAYWRIGHT BROWSER                  │
  │    - Start headless Chromium                   │
  │    - Login to Ariba Portal                     │
  │    - Select Company                            │
  │    - Scrape RFPs → find target RFP             │
  └────────────┬───────────────────────────────────┘
               │
               ▼
  ┌──────────────────────────────────────────────────────┐
  │ 5. CHECK PORTAL STATUS                                │
  │    - Verify RFP is not already declined/submitted      │
  │      on the portal side                                │
  │    - If already actioned on portal → SKIP              │
  └────────────┬─────────────────────────────────────────┘
               │ (open on portal)
               ▼
  ┌──────────────────────────────────────────────────────┐
  │ 6. OPEN RFP ON PORTAL                                 │
  │    - Open RFP link in new browser page                 │
  │    - Wait for page to load                             │
  └────────────┬─────────────────────────────────────────┘
               │
               ▼
  ┌──────────────────────────────────────────────────────┐
  │ 7. FILL DECLINE REASON                                │
  │    - Navigate to Step 1 (Decline section)              │
  │    - Locate decline reason textarea                    │
  │    - Fill via JavaScript execution:                    │
  │      "We Don't Know Right Now"                        │
  │    - Wait 10 seconds for portal to process             │
  │                                                       │
  │    *** NO FILES CREATED ***                            │
  │    *** NO SHAREPOINT OPERATIONS ***                    │
  └────────────┬─────────────────────────────────────────┘
               │
               ▼
  ┌──────────────────────────────────────────────────────┐
  │ 8. UPDATE DATABASE                                     │
  │  ✦ DATABASE: UPDATE RFP participation status           │
  │    Table: cr673_requestforproposals                     │
  │    Filter: RFP_ID eq '{rfp_id}'                        │
  │    Update: { participated: "declined" }                 │
  │                                                        │
  │  ✦ DATABASE: INSERT status history                     │
  │    Table: cr673_bhara_rfp_statuses                     │
  │    Data: { rfp_id, old_status, new:"declined",         │
  │            timestamp }                                  │
  └────────────┬─────────────────────────────────────────┘
               │
               ▼
  ┌──────────────────────────────────────────────────────┐
  │ 9. SEND EMAIL NOTIFICATION                             │
  │  ✦ DATABASE: UPDATE Email_Status                       │
  │    Email flag: "rfp_decline"                           │
  │    Content: RFP ID, company, decline confirmation      │
  └────────────┬─────────────────────────────────────────┘
               │
               ▼
  ┌──────────────────────────────────────────────────────┐
  │ 10. FINALIZE                                          │
  │  ✦ DATABASE: UPDATE automation_log                    │
  │    Data: { status: "completed", end_time }             │
  │    Close browser → Release _RUN_STATE                  │
  └────────────┬─────────────────────────────────────────┘
               │
               ▼
           ┌───────┐
           │  END  │
           └───────┘
```

### Decline RFP - Summary Table

| Step | Action                   | Database                 | SharePoint | File Created |
| ---- | ------------------------ | ------------------------ | ---------- | ------------ |
| 2    | Initialize               | INSERT automation_log    | -          | -            |
| 3    | Pre-check status         | QUERY RFP                | -          | -            |
| 8    | Update RFP status        | UPDATE participated      | -          | -            |
| 8    | Log status change        | INSERT status_history    | -          | -            |
| 9    | Send email               | UPDATE Email_Status      | -          | -            |
| 10   | Finalize                 | UPDATE automation_log    | -          | -            |

**Note:** Decline flow has **NO file operations** and **NO SharePoint operations** - it is purely a portal action + database update.

---

# ERROR HANDLING FLOW (All Operations)

```
┌──────────────────────────────────┐
│  ERROR OCCURS DURING ANY STEP    │
└────────────┬─────────────────────┘
             │
             ▼
┌───────────────────────────────────────────────┐
│ 1. CAPTURE ERROR CONTEXT                       │
│    - Take browser screenshot                    │
│  ✦ FILE CREATED (Local):                       │
│    LOGS/screenshot_{timestamp}.png              │
│                                                 │
│    - Generate error log HTML                    │
│  ✦ FILE CREATED (Local):                       │
│    LOGS/error_log_{timestamp}.html              │
└────────────┬──────────────────────────────────┘
             │
             ▼
┌───────────────────────────────────────────────┐
│ 2. UPLOAD ERROR LOG                             │
│  ✦ SHAREPOINT: Upload error log                 │
│    Path: RFP-logs/LOGS/{operation}/{timestamp}/ │
│    File: error_log.html                         │
└────────────┬──────────────────────────────────┘
             │
             ▼
┌───────────────────────────────────────────────┐
│ 3. LOG TO DATABASE                              │
│  ✦ DATABASE: UPDATE automation_log              │
│    Data: { status: "failed", error_message,     │
│            end_time }                            │
└────────────┬──────────────────────────────────┘
             │
             ▼
┌───────────────────────────────────────────────┐
│ 4. SEND FAILURE EMAIL                           │
│    Email flag:                                  │
│    - "error_in_rfp_submission" (Submit)          │
│    - "error_in_rfp_decline" (Decline)            │
│    - "error_in_rfp_download" (Download)          │
│                                                 │
│    Content: Error details + SharePoint log path  │
└────────────┬──────────────────────────────────┘
             │
             ▼
┌───────────────────────────────────────────────┐
│ 5. CLEANUP                                      │
│    Close browser → Release _RUN_STATE            │
└───────────────────────────────────────────────┘
```

---

# FRONTEND POLLING FLOW (Dashboard Real-time Updates)

```
┌──────────────┐     POST /submit-rfp      ┌──────────────┐
│   Dashboard  │ ────────────────────────>  │   FastAPI     │
│   (Browser)  │     202 Accepted           │   Backend     │
│              │ <────────────────────────   │              │
└──────┬───────┘                            └──────────────┘
       │
       │  Every 2 seconds:
       │  GET /automation/status
       │
       ▼
┌──────────────────────────────────────┐
│  Response:                            │
│  {                                    │
│    "running": true,                   │
│    "type": "submit",                  │
│    "progress": 65,                    │
│    "current_step": "Uploading Excel", │
│    "rfp_id": "RFP-12345"             │
│  }                                    │
│                                       │
│  Frontend updates:                    │
│  ┌────────────────────────────┐       │
│  │ ██████████████░░░░░░ 65%   │       │
│  │ Uploading Excel...         │       │
│  └────────────────────────────┘       │
│                                       │
│  When progress = 100 or running=false │
│  → Stop polling                       │
│  → Show success/error notification     │
│  → Refresh RFP list                   │
└──────────────────────────────────────┘
```

---

# CROSS-FLOW COMPARISON

| Aspect                | Download RFP                  | Submit RFP                      | Decline RFP              |
| --------------------- | ----------------------------- | ------------------------------- | ------------------------ |
| **Trigger**           | Scheduled / Manual            | Manual (with file upload)       | Manual                   |
| **Files Created**     | Excel + Matched CSV           | Excel + TDS PDFs (user upload)  | None                     |
| **SharePoint Upload** | Excel + Matched CSV           | Excel (2 copies) + TDS PDFs    | None                     |
| **SharePoint Download** | Master CSVs (material + keywords) | Filled Excel (if needed)   | None                     |
| **DB Inserts**        | RFP record + automation_log   | automation_log + status_history | automation_log + status_history |
| **DB Updates**        | Email_Status + match data     | participated + Email_Status     | participated + Email_Status |
| **Portal Action**     | Download file                 | Fill form + Upload + Save Draft | Fill decline reason      |
| **Email Sent**        | Match results / No new RFP    | Draft saved confirmation        | Decline confirmation     |
| **Final DB Status**   | `participated: "no"`          | `participated: "saved_draft"`   | `participated: "declined"` |
| **Complexity**        | High (matching logic)         | High (multi-step form)          | Low (single action)      |

---

# DATA FLOW DIAGRAM

```
                    ┌─────────────┐
                    │  Ariba      │
                    │  Portal     │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │ Download   │ Submit     │ Decline
              │ Excel      │ Fill Form  │ Fill Reason
              ▼            ▼            ▼
        ┌───────────────────────────────────┐
        │         Playwright Browser         │
        │       (Headless Automation)        │
        └───────────────┬───────────────────┘
                        │
            ┌───────────┼───────────┐
            ▼           ▼           ▼
    ┌──────────┐  ┌──────────┐  ┌──────────┐
    │  Local   │  │ SharePt  │  │ Dataverse│
    │  Files   │  │ (Graph)  │  │ (OData)  │
    │          │  │          │  │          │
    │ ALLRFPs/ │  │ RFP-logs/│  │ RFP Table│
    │ ├ .xls   │  │ ├ .xls   │  │ ├ Status │
    │ ├ .csv   │  │ ├ .csv   │  │ ├ Dates  │
    │ └ .pdf   │  │ ├ .pdf   │  │ ├ Links  │
    │          │  │ └ master/ │  │ └ Match  │
    └──────────┘  └──────────┘  └──────────┘
         │              │              │
         └──────────────┼──────────────┘
                        ▼
                ┌──────────────┐
                │    Email     │
                │ Notification │
                └──────────────┘
```

---

*Document Generated: 2026-02-18 | RFP Automation System v1.0*
