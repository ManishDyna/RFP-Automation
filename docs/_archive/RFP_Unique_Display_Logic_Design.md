# Unique RFP Display Logic - Design Document

---

## Overview: How Does a Unique RFP Appear in the System?

An RFP goes through **5 layers** before it appears on the Dashboard. Each layer has its own deduplication and uniqueness logic to ensure the same RFP is never shown twice.

```
┌────────────────────────────────────────────────────────────────────────┐
│                    JOURNEY OF A UNIQUE RFP                             │
│                                                                        │
│  LAYER 1         LAYER 2         LAYER 3         LAYER 4    LAYER 5   │
│  ┌──────┐       ┌──────┐       ┌──────┐       ┌──────┐    ┌──────┐   │
│  │Ariba │──────>│Insert│──────>│Query │──────>│Dedup │───>│Render│   │
│  │Portal│ Scrape│to DB │ Check │from  │ Pandas│& Norm│ JS │on    │   │
│  │Export │──────>│      │──────>│Datavs│──────>│      │───>│Dashbd│   │
│  └──────┘       └──────┘       └──────┘       └──────┘    └──────┘   │
│   HTML Parse     RFP_ID Match   OData Query    drop_dup    Tabs+Table │
└────────────────────────────────────────────────────────────────────────┘
```

---

# LAYER 1: Portal Scraping (Source of Truth)

**File:** `automation_logic.py` → `extract_rfp_data()` (lines 800-937)

### How RFPs Are Extracted from Ariba Portal

```
┌─────────────────────────────────────────────────────────────┐
│                   ARIBA PORTAL                               │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Open Events Table                                    │   │
│  │  ┌──────────┬──────────┬──────────┬────────────────┐ │   │
│  │  │ Title    │ Doc ID   │ End Date │ Event Type     │ │   │
│  │  ├──────────┼──────────┼──────────┼────────────────┤ │   │
│  │  │ C001697  │ Doc78923 │ 2026-03  │ RFP            │ │   │
│  │  │ C001698  │ Doc78924 │ 2026-04  │ RFP            │ │   │
│  │  └──────────┴──────────┴──────────┴────────────────┘ │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Participated Events Table                            │   │
│  │  ┌──────────┬──────────┬──────────┬────────────────┐ │   │
│  │  │ Title    │ Doc ID   │ End Date │ Status         │ │   │
│  │  ├──────────┼──────────┼──────────┼────────────────┤ │   │
│  │  │ C001695  │ Doc78921 │ 2026-02  │ Submitted      │ │   │
│  │  │ C001696  │ Doc78922 │ 2026-02  │ Declined       │ │   │
│  │  └──────────┴──────────┴──────────┴────────────────┘ │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                           │
                    Playwright exports HTML
                           │
                           ▼
                ┌──────────────────────┐
                │  extract_rfp_data()  │
                │  Parses HTML rows    │
                │  One row = One RFP   │
                │  (naturally unique)  │
                └──────────────────────┘
```

### Fields Extracted Per RFP

```python
{
    "Title":       "C001697262 - Pipes and Fittings for SEC",   # Full title
    "RFP_ID":      "C001697262 - Pipes and Fittings for SEC",   # Initially = Title
    "Link":        "https://service.ariba.com/Sourcing/...",    # Portal URL
    "Doc_ID":      "Doc78923",                                  # Portal document ID
    "End_Time":    "2026-03-15 15:00:00",                       # Deadline
    "Event_Type":  "RFP",                                       # Procurement type
    "Participated": "open",                                     # "open" | "submitted" | "declined"
    "StatusGroup": "open_events"                                # Which portal section
}
```

### RFP ID Normalization: `_derive_rfp_id()`

```
  Raw Title from Portal:
  "C001697262 - Pipes and Fittings for Saudi Electricity Company"
                │
                ▼
  ┌──────────────────────────────────────────────────┐
  │  _derive_rfp_id()                                │
  │                                                   │
  │  Regex 1: \bC\d{9,}\b  → tries "C001697262"     │
  │  Regex 2: \b\d{8,}\b   → fallback to digits      │
  │  Else:    use full title as ID                    │
  │                                                   │
  │  Result: "C001697262" (clean short ID)            │
  └──────────────────────────────────────────────────┘
```

**Uniqueness at this layer:** HTML table rows are naturally unique — each RFP appears once in "Open Events" or once in "Participated Events". No duplicates from portal.

---

# LAYER 2: Database Insert/Update (Uniqueness Enforcement)

**File:** `core/log_events.py` → `log_rfp_activity()` (lines 220-340)

### The Core Uniqueness Check

```
  New RFP scraped from portal
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│  log_rfp_activity(rfp_id, company, data)                     │
│                                                              │
│  STEP 1: Query Dataverse                                     │
│  ┌─────────────────────────────────────────────────┐        │
│  │  DATAVERSE.query_rows(                           │        │
│  │    table = "cr673_requestforproposals",           │        │
│  │    filter = "RFP_ID eq 'C001697262 - Pipes...'", │        │
│  │    top = 1                                        │        │
│  │  )                                                │        │
│  └────────────────────┬────────────────────────────┘        │
│                       │                                      │
│              ┌────────┴────────┐                             │
│              ▼                 ▼                              │
│        ┌──────────┐    ┌────────────┐                       │
│        │  FOUND   │    │ NOT FOUND  │                       │
│        │ (exists) │    │  (new RFP) │                       │
│        └────┬─────┘    └─────┬──────┘                       │
│             │                │                               │
│             ▼                ▼                                │
│  ┌──────────────────┐  ┌──────────────────────┐             │
│  │ Has Meaningful    │  │ INSERT new row       │             │
│  │ Updates?          │  │                      │             │
│  │                   │  │ All fields populated │             │
│  │ • Status changed? │  │ participated = "no"  │             │
│  │ • Email changed?  │  │ Email_Status = ""    │             │
│  │ • Match data new? │  │ Downloaded_At = now  │             │
│  └───┬──────────┬────┘  └──────────────────────┘             │
│      │          │                                            │
│    YES         NO                                            │
│      │          │                                            │
│      ▼          ▼                                            │
│  ┌────────┐  ┌────────┐                                     │
│  │ UPDATE │  │  SKIP  │                                     │
│  │ record │  │ (no-op)│                                     │
│  └────────┘  └────────┘                                     │
└─────────────────────────────────────────────────────────────┘
```

### What "Meaningful Update" Means

```
  Existing DB Record           Scraped Data from Portal
  ┌────────────────────┐      ┌────────────────────┐
  │ participated: "no" │  vs  │ participated: "submitted"│  → YES, update
  │ Email_Status: ""   │  vs  │ Email_Status: "sent"     │  → YES, update
  │ Matched_Data: null │  vs  │ Matched_Data: "{...}"    │  → YES, update
  │ participated: "no" │  vs  │ participated: "no"       │  → NO, skip
  └────────────────────┘      └────────────────────┘
```

**Key Rule:** `RFP_ID` (the full title string) is the unique identifier. If a record with the same `RFP_ID` exists → UPDATE only meaningful changes. If not → INSERT new record.

---

# LAYER 3: Fuzzy Matching (Portal ↔ Database Sync)

**File:** `automation_logic.py` → `sync_participation_with_db()` (lines 986-1074)

When the system needs to match a scraped RFP against the database (e.g., during Submit or Decline), the RFP IDs may not match exactly. The system uses a **2-step matching strategy**:

```
┌──────────────────────────────────────────────────────────────────────┐
│            MATCHING SCRAPED RFP → DATABASE RECORD                    │
│                                                                      │
│  Scraped from Portal:                                                │
│  Title = "C001697262 - Pipes and Fittings for SEC"                  │
│                                                                      │
│  ┌──────────────────────────────────────────┐                       │
│  │  METHOD 1: Exact RFP_ID Match             │                       │
│  │                                           │                       │
│  │  Scraped RFP_ID: "C001697262"             │                       │
│  │  DB RFP_ID:      "C001697262"             │                       │
│  │                                           │                       │
│  │  Match? ─────── YES → Use this record     │                       │
│  │           │                                │                       │
│  │           NO                               │                       │
│  │           ▼                                │                       │
│  └──────────────────────────────────────────┘                       │
│                                                                      │
│  ┌──────────────────────────────────────────┐                       │
│  │  METHOD 2: Fuzzy Title Match              │                       │
│  │  (rfp_ids_match function)                 │                       │
│  │                                           │                       │
│  │  normalize_filename("C001697262")         │                       │
│  │  → "c001697262"                           │                       │
│  │                                           │                       │
│  │  normalize_filename(                      │                       │
│  │    "C001697262 - Pipes and Fittings")     │                       │
│  │  → "c001697262 - pipes and fittings"      │                       │
│  │                                           │                       │
│  │  "c001697262" in "c001697262 - pipes..."  │                       │
│  │  → TRUE → MATCH FOUND                     │                       │
│  └──────────────────────────────────────────┘                       │
│                                                                      │
│  If STILL no match → { result: "db_not_found" }                     │
│  (RFP exists on portal but not yet in our database)                  │
└──────────────────────────────────────────────────────────────────────┘
```

---

# LAYER 4: Query + Deduplication for Display

**Files:**
- `routes/api.py` → `/api/dashboard/rfp-details` (lines 311-458)
- `dashboard_service.py` → `get_all_rfp_data()` (line 310)
- `core_helper.py` → `get_rfp_activity_data_from_db()` (line 223)

### Step-by-Step: From Database to Dashboard Data

```
┌──────────────────────────────────────────────────────────────────────┐
│  STEP A: FETCH ALL RFPs FROM DATAVERSE                               │
│                                                                      │
│  DATAVERSE.get_all_rows(                                             │
│    table = "cr673_requestforproposals",                              │
│    select = [                                                        │
│      "RFP_ID",              ← Primary identifier                    │
│      "Company_Name",        ← Company filter                        │
│      "RFP_End_Date",        ← Deadline                              │
│      "owner_name",          ← RFP owner from portal                 │
│      "publish_time",        ← When published                        │
│      "participated",        ← Status (raw value)                    │
│      "Link",                ← Portal URL                            │
│      "Email_Status",        ← Email sent?                           │
│      "Material_Matched",    ← Material match flag                   │
│      "Keyword_Matched",     ← Keyword match flag                    │
│      "Matched_Data"         ← Match details (JSON)                  │
│    ],                                                                │
│    use_display_names = True                                          │
│  )                                                                   │
│                                                                      │
│  Returns: ALL rows (with OData pagination handled internally)        │
│  Example: 200 rows (some may be duplicates from re-downloads)        │
└──────────────────────┬───────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────────┐
│  STEP B: CONVERT TO PANDAS DATAFRAME                                 │
│                                                                      │
│  rfp_df = pd.DataFrame(all_rows)                                    │
│                                                                      │
│  BEFORE dedup:                                                       │
│  ┌──────────────────────┬──────────────┬──────────────┐             │
│  │ RFP_ID               │ Company      │ participated │             │
│  ├──────────────────────┼──────────────┼──────────────┤             │
│  │ C001697262 - Pipes   │ SEC          │ no           │  ← row 1   │
│  │ C001697262 - Pipes   │ SEC          │ submitted    │  ← row 2   │
│  │ C001698001 - Cables  │ Aramco       │ open         │  ← row 3   │
│  │ C001698001 - Cables  │ Aramco       │ open         │  ← row 4   │
│  └──────────────────────┴──────────────┴──────────────┘             │
│  (4 rows, but only 2 unique RFPs)                                    │
└──────────────────────┬───────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────────┐
│  STEP C: DEDUPLICATE                                                 │
│                                                                      │
│  rfp_df = rfp_df.drop_duplicates(subset=["RFP_ID"], keep="first")   │
│                                                                      │
│  AFTER dedup:                                                        │
│  ┌──────────────────────┬──────────────┬──────────────┐             │
│  │ RFP_ID               │ Company      │ participated │             │
│  ├──────────────────────┼──────────────┼──────────────┤             │
│  │ C001697262 - Pipes   │ SEC          │ no           │  ← kept    │
│  │ C001698001 - Cables  │ Aramco       │ open         │  ← kept    │
│  └──────────────────────┴──────────────┴──────────────┘             │
│  (2 rows = 2 unique RFPs)                                            │
└──────────────────────┬───────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────────┐
│  STEP D: AGGREGATE MATCH FLAGS                                       │
│                                                                      │
│  If ANY row for an RFP_ID has Material_Matched = "Yes",              │
│  then ALL rows for that RFP_ID get Material_Matched = "Yes"          │
│                                                                      │
│  for col in ["Material_Matched", "Keyword_Matched"]:                 │
│      yes_rfps = set(df.loc[df[col] == "Yes", "RFP_ID"])             │
│      df.loc[df["RFP_ID"].isin(yes_rfps), col] = "Yes"              │
└──────────────────────┬───────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────────┐
│  STEP E: NORMALIZE STATUS                                            │
│                                                                      │
│  Raw DB Value          →  Normalized Status  →  Display Label        │
│  ─────────────────────────────────────────────────────────────       │
│  "" (empty)            →  "open"             →  "Open"               │
│  "no"                  →  "open"             →  "Open"               │
│  "open"                →  "open"             →  "Open"               │
│  "not participated"    →  "open"             →  "Open"               │
│  "submitted"           →  "submitted"        →  "Submitted"          │
│  "yes"                 →  "submitted"        →  "Submitted"          │
│  "declined"            →  "declined"         →  "Declined"           │
│  "saved_draft"         →  "saved_draft"      →  "Saved Draft"       │
│  (anything else)       →  "other"            →  "Other"              │
│                                                                      │
│  Function: _normalize_participation(raw_status)                      │
│  Location: routes/api.py (lines 86-96)                               │
└──────────────────────┬───────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────────┐
│  STEP F: FILTER BY DEADLINE                                          │
│                                                                      │
│  Only show RFPs where:                                               │
│    RFP_End_Date >= current_datetime                                  │
│                                                                      │
│  (Expired RFPs are hidden from default view)                         │
└──────────────────────┬───────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────────┐
│  STEP G: CACHE RESULT (300 seconds TTL)                              │
│                                                                      │
│  Cached in memory with lock-based stampede prevention                │
│  Invalidated on: status update, new download, sync completion        │
└──────────────────────────────────────────────────────────────────────┘
```

---

# LAYER 5: Dashboard Rendering & Filtering

### API Endpoint: `GET /api/dashboard/rfp-details`

**All Available Query Parameters:**

| Parameter        | Type   | Default      | Options                                            | Purpose                        |
| ---------------- | ------ | ------------ | -------------------------------------------------- | ------------------------------ |
| `status`         | str    | `downloaded` | `downloaded`, `open`, `submitted`, `saved_draft`, `declined` | Filter by participation status |
| `company`        | str    | `""`         | Any company name                                   | Filter by company              |
| `search`         | str    | `""`         | Any text                                           | Search in RFP_ID, Company, Owner |
| `start_date`     | str    | `""`         | `YYYY-MM-DD`                                       | Deadline >= this date          |
| `end_date`       | str    | `""`         | `YYYY-MM-DD`                                       | Deadline <= this date          |
| `material_match` | str    | `""`         | `matched`, `not_matched`                           | Filter by material match       |
| `keyword_match`  | str    | `""`         | `matched`, `not_matched`                           | Filter by keyword match        |
| `participation`  | str    | `""`         | `participated`, `not_participated`, `declined`     | Filter by bid status           |
| `limit`          | int    | `50`         | `10` - `500`                                       | Rows per page                  |
| `offset`         | int    | `0`          | `>= 0`                                             | Pagination offset              |
| `refresh`        | int    | `0`          | `0` or `1`                                         | Force cache refresh            |

### Filter Pipeline (Applied Sequentially)

```
  All RFPs from cache (e.g., 200 unique RFPs)
       │
       ▼
  ┌──────────────────────────────────────────┐
  │ FILTER 1: Status                          │
  │ status=open → keep only "open" RFPs       │
  │ status=downloaded → keep ALL (no filter)  │
  │ Result: 80 RFPs                           │
  └──────────┬───────────────────────────────┘
             │
             ▼
  ┌──────────────────────────────────────────┐
  │ FILTER 2: Company                         │
  │ company="Saudi Electricity Company"       │
  │ Exact match on Company_Name column        │
  │ Result: 45 RFPs                           │
  └──────────┬───────────────────────────────┘
             │
             ▼
  ┌──────────────────────────────────────────┐
  │ FILTER 3: Search Text                     │
  │ search="C001697"                          │
  │ Case-insensitive search in:               │
  │   - RFP_ID                                │
  │   - Company_Name                          │
  │   - Owner_Name                            │
  │ Result: 3 RFPs                            │
  └──────────┬───────────────────────────────┘
             │
             ▼
  ┌──────────────────────────────────────────┐
  │ FILTER 4: Date Range                      │
  │ start_date="2026-02-01"                   │
  │ end_date="2026-03-31"                     │
  │ Compare against RFP_End_Date              │
  │ Result: 2 RFPs                            │
  └──────────┬───────────────────────────────┘
             │
             ▼
  ┌──────────────────────────────────────────┐
  │ FILTER 5: Material Match                  │
  │ material_match="matched"                  │
  │ Keep where Material_Matched = "Yes"       │
  │ Result: 1 RFP                             │
  └──────────┬───────────────────────────────┘
             │
             ▼
  ┌──────────────────────────────────────────┐
  │ FILTER 6: Keyword Match                   │
  │ keyword_match="matched"                   │
  │ Keep where Keyword_Matched = "Yes"        │
  │ Result: 1 RFP                             │
  └──────────┬───────────────────────────────┘
             │
             ▼
  ┌──────────────────────────────────────────┐
  │ PAGINATION                                │
  │ offset=0, limit=50                        │
  │ paginated = filtered[0:50]                │
  │ Result: 1 RFP (final page)                │
  └──────────────────────────────────────────┘
```

### API Response Structure

```json
{
  "rfps": [
    {
      "RFP_ID":           "C001697262 - Pipes and Fittings for SEC",
      "Company_Name":     "Saudi Electricity Company",
      "RFP_End_Date":     "2026-03-15 15:00",
      "Owner_Name":       "Mohammed Al-Harbi",
      "Publish_Time":     "2026-02-01 09:30",
      "participated":     "submitted",
      "status_key":       "submitted",
      "Link":             "https://service.ariba.com/Sourcing/...",
      "Material_Matched": "Yes",
      "Keyword_Matched":  "No",
      "Matched_Data":     "{...}"
    }
  ],
  "status_counts": {
    "open": 45,
    "submitted": 12,
    "saved_draft": 3,
    "declined": 8
  },
  "total_status_counts": {
    "downloaded": 200,
    "open": 80,
    "submitted": 50,
    "saved_draft": 10,
    "declined": 60
  },
  "total": 200,
  "total_filtered": 1,
  "shown_rows": 1,
  "offset": 0,
  "limit": 50,
  "has_more": false,
  "unique_companies": [
    "Saudi Electricity Company",
    "Aramco e-Marketplace",
    "SABIC - Saudi Basic Industries Corp.",
    "HADEED - RAJHI STEEL"
  ]
}
```

### Dashboard UI Layout

```
┌────────────────────────────────────────────────────────────────────────┐
│                        RFP AUTOMATION DASHBOARD                        │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  ┌─── Company Tabs ────────────────────────────────────────────────┐  │
│  │ [Saudi Electricity (68)] [Aramco (45)] [SABIC (52)] [HADEED (35)]│  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│  ┌─── Status Sub-Tabs ─────────────────────────────────────────────┐  │
│  │ [All Downloaded (68)] [Open (30)] [Submitted (15)]               │  │
│  │ [Saved Draft (5)]     [Declined (18)]                            │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│  ┌─── Filters Bar ─────────────────────────────────────────────────┐  │
│  │ Search: [________]  From: [____]  To: [____]                     │  │
│  │ Material: [All ▼]   Keyword: [All ▼]                             │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│  ┌─── RFP Table ───────────────────────────────────────────────────┐  │
│  │ ┌────────────┬──────────┬──────────┬────────┬────────┬────────┐ │  │
│  │ │ RFP ID     │ Owner    │ Deadline │ Status │ Match  │ Action │ │  │
│  │ ├────────────┼──────────┼──────────┼────────┼────────┼────────┤ │  │
│  │ │ C001697262 │ Mohammed │ Mar 15   │🟡 Open │ ✅ Mat │[Submit]│ │  │
│  │ │ C001698001 │ Ahmed    │ Apr 01   │🟢 Sent │ ✅ Key │  ---   │ │  │
│  │ │ C001698500 │ Khalid   │ Mar 20   │🔴 Decl │ ❌ No  │  ---   │ │  │
│  │ │ C001699000 │ Faisal   │ Apr 10   │🟡 Open │ ✅ Mat │[Submit]│ │  │
│  │ │ C001699200 │ Saeed    │ Mar 25   │⚪ Draft│ ✅ Key │[Final] │ │  │
│  │ └────────────┴──────────┴──────────┴────────┴────────┴────────┘ │  │
│  │                                                                   │  │
│  │  Showing 1-50 of 68 RFPs          [← Prev] [Page 1] [Next →]    │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│  Status Badge Colors:                                                  │
│  🟡 Open (bg-warning)    🟢 Submitted (bg-success)                    │
│  ⚪ Saved Draft (bg-secondary)    🔴 Declined (bg-danger)             │
└────────────────────────────────────────────────────────────────────────┘
```

### Status Badge Mapping (from code)

```python
_RFP_STATUS_META = {
    "open":        { "label": "Open",        "badge": "bg-warning"   },  # Yellow
    "submitted":   { "label": "Submitted",   "badge": "bg-success"   },  # Green
    "saved_draft": { "label": "Saved Draft", "badge": "bg-secondary" },  # Gray
    "declined":    { "label": "Declined",    "badge": "bg-danger"    },  # Red
    "other":       { "label": "Other",       "badge": "bg-info"      },  # Blue
}
```

### Frontend Polling (real-time progress)

```
Dashboard (JavaScript)              Backend
       │                               │
       │  Every 2 seconds:             │
       │  GET /automation/status       │
       │──────────────────────────────>│
       │                               │
       │  { running: true,             │
       │    progress: 65,              │
       │    step: "Downloading..." }   │
       │<──────────────────────────────│
       │                               │
       │  Update progress bar          │
       │  ██████████████░░░░░░ 65%     │
       │                               │
       │  When complete → refresh list │
       │  GET /api/dashboard/rfp-details│
       │──────────────────────────────>│
```

---

# DATABASE SCHEMA: Complete Column Reference

## Main Table: `cr673_requestforproposals`

| #  | Display Name      | Logical Name              | Type         | Example Value                                    | Set By         |
| -- | ----------------- | ------------------------- | ------------ | ------------------------------------------------ | -------------- |
| 1  | `RFP_ID`          | `cr673_rfpid`             | Text (PK)    | `"C001697262 - Pipes and Fittings for SEC"`      | Download Flow  |
| 2  | `Company_Name`    | `cr673_companyname`       | Text         | `"Saudi Electricity Company"`                    | Download Flow  |
| 3  | `RFP_End_Date`    | `cr673_rfpenddate`        | DateTime     | `"2026-03-15 15:00:00"`                          | Download Flow  |
| 4  | `owner_name`      | `cr673_ownername`         | Text         | `"Mohammed Al-Harbi"`                            | Download Flow  |
| 5  | `publish_time`    | `cr673_publishtime`       | DateTime     | `"2026-02-01 09:30:00"`                          | Download Flow  |
| 6  | `participated`    | `cr673_participated`      | Text/Choice  | `"no"` / `"submitted"` / `"declined"` / `"saved_draft"` | All Flows |
| 7  | `Link`            | `cr673_link`              | Text         | `"https://service.ariba.com/Sourcing/..."`       | Download Flow  |
| 8  | `Downloaded_At`   | `cr673_downloadedat`      | DateTime     | `"2026-02-18 10:30:00"`                          | Download Flow  |
| 9  | `Email_Status`    | `cr673_emailstatus`       | Text         | `""` / `"sent"` / `"pending"` / `"failed"`      | Email Trigger  |
| 10 | `Material_Matched`| `cr673_materialmatched`   | Choice       | `"Yes"` / `"No"`                                 | Download Flow  |
| 11 | `Keyword_Matched` | `cr673_keywordmatched`    | Choice       | `"Yes"` / `"No"`                                 | Download Flow  |
| 12 | `Matched_Data`    | `cr673_matcheddata`       | Text (JSON)  | `'[{"code":"123456789","name":"Cable"}]'`        | Download Flow  |

## Status History Table: `cr673_bhara_rfp_statuses`

| Display Name           | Type     | Example                     | Purpose                    |
| ---------------------- | -------- | --------------------------- | -------------------------- |
| `cr673_rfpreference`   | Text     | `"C001697262"`              | Which RFP                  |
| `cr673_currentstatus`  | Text     | `"saved_draft"`             | New status value           |
| `cr673_submissioncode` | DateTime | `"2026-02-18 14:00:00"`     | When status changed        |
| `cr673_submissioncategory` | Text | `"submit"` / `"decline"`    | What operation caused it   |

## Automation Log Table: `cr673_bahra_automation_log1s`

| Display Name    | Type     | Example                     | Purpose                    |
| --------------- | -------- | --------------------------- | -------------------------- |
| Run ID          | Text     | `"RUN-20260218-103000"`     | Unique automation run ID   |
| Type            | Text     | `"download"` / `"submit"`   | Operation type             |
| Status          | Text     | `"started"` / `"completed"` | Run status                 |
| Start Time      | DateTime | `"2026-02-18 10:30:00"`     | When started               |
| End Time        | DateTime | `"2026-02-18 10:45:00"`     | When finished              |
| Error Message   | Text     | `"Timeout on step 5"`       | Error details (if failed)  |

---

# COMPLETE DEDUPLICATION SUMMARY

```
┌────────────────────────────────────────────────────────────────────────────┐
│                 5 LAYERS OF UNIQUENESS ENFORCEMENT                         │
├────────┬──────────────────────┬──────────────────────┬─────────────────────┤
│ Layer  │ Where                │ Mechanism            │ What It Prevents     │
├────────┼──────────────────────┼──────────────────────┼─────────────────────┤
│   1    │ Portal HTML Parse    │ One row per RFP in   │ Duplicate scraping   │
│        │ (extract_rfp_data)   │ export table         │                      │
├────────┼──────────────────────┼──────────────────────┼─────────────────────┤
│   2    │ DB Insert            │ Query RFP_ID before  │ Duplicate DB rows    │
│        │ (log_rfp_activity)   │ INSERT; UPDATE only  │ from re-downloads    │
│        │                      │ if meaningful change │                      │
├────────┼──────────────────────┼──────────────────────┼─────────────────────┤
│   3    │ Portal↔DB Sync       │ Exact ID match then  │ Mismatched IDs       │
│        │ (sync_participation) │ fuzzy title match    │ between systems      │
├────────┼──────────────────────┼──────────────────────┼─────────────────────┤
│   4    │ Query Processing     │ Pandas drop_dup on   │ Any remaining        │
│        │ (dashboard_service)  │ RFP_ID column        │ duplicates in DB     │
├────────┼──────────────────────┼──────────────────────┼─────────────────────┤
│   5    │ Display Rendering    │ Group by company     │ Visual duplicates    │
│        │ (dashboard.html)     │ then by status tab   │ across tabs          │
└────────┴──────────────────────┴──────────────────────┴─────────────────────┘
```

---

# RFP LIFECYCLE: Status Transitions

```
                    ┌──────────────────────┐
                    │   RFP Downloaded     │
                    │   from Ariba Portal  │
                    │                      │
                    │   participated: "no" │
                    └──────────┬───────────┘
                               │
                    ┌──────────┴───────────┐
                    │    Normalized as:    │
                    │      "open"          │
                    │    (shown in Open    │
                    │     tab on Dashboard)│
                    └──────────┬───────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
     ┌─────────────┐  ┌──────────────┐  ┌────────────┐
     │   SUBMIT    │  │  SAVE DRAFT  │  │  DECLINE   │
     │             │  │              │  │            │
     │ participated│  │ participated │  │participated│
     │ ="submitted"│  │ ="saved_draft│  │ ="declined"│
     │             │  │              │  │            │
     │  Badge:     │  │  Badge:      │  │  Badge:    │
     │  🟢 Green   │  │  ⚪ Gray     │  │  🔴 Red    │
     └─────────────┘  └──────┬───────┘  └────────────┘
                              │
                              │  (User can later
                              │   finalize draft)
                              ▼
                     ┌─────────────┐
                     │   SUBMIT    │
                     │ participated│
                     │ ="submitted"│
                     │  🟢 Green   │
                     └─────────────┘

  Valid status values in DB:
  ┌────────────────────┬──────────────────┬────────────────┐
  │ Raw DB Value       │ Normalized       │ Display Label  │
  ├────────────────────┼──────────────────┼────────────────┤
  │ "" / "no" / "open" │ "open"           │ Open (🟡)      │
  │ "not participated" │ "open"           │ Open (🟡)      │
  │ "submitted" / "yes"│ "submitted"      │ Submitted (🟢) │
  │ "saved_draft"      │ "saved_draft"    │ Saved Draft(⚪)│
  │ "declined"         │ "declined"       │ Declined (🔴)  │
  │ (anything else)    │ "other"          │ Other (🔵)     │
  └────────────────────┴──────────────────┴────────────────┘
```

---

# COMPANY FILTERING: How RFPs Are Grouped

```
  ┌──────────────────────────────────────────────────────────────┐
  │  Supported Companies (from config.py):                        │
  │                                                               │
  │  1. Saudi Electricity Company                                 │
  │  2. Aramco e-Marketplace                                      │
  │  3. SABIC - Saudi Basic Industries Corp.                      │
  │  4. HADEED - RAJHI STEEL                                      │
  └──────────────────────────────────────────────────────────────┘
                               │
                    Set during Download Flow
                    (Company_Name column)
                               │
                               ▼
  ┌──────────────────────────────────────────────────────────────┐
  │  Database: Each RFP row has Company_Name                      │
  │                                                               │
  │  ┌──────────────────┬──────────────────────────────────────┐ │
  │  │ RFP_ID           │ Company_Name                         │ │
  │  ├──────────────────┼──────────────────────────────────────┤ │
  │  │ C001697262       │ Saudi Electricity Company            │ │
  │  │ C001698001       │ Aramco e-Marketplace                 │ │
  │  │ C001698500       │ Saudi Electricity Company            │ │
  │  │ C001699000       │ SABIC - Saudi Basic Industries Corp. │ │
  │  └──────────────────┴──────────────────────────────────────┘ │
  └──────────────────────────────────────────────────────────────┘
                               │
                    Query: unique companies
                    unique_companies = set(df["Company_Name"].unique())
                               │
                               ▼
  ┌──────────────────────────────────────────────────────────────┐
  │  Dashboard generates one tab per company:                     │
  │                                                               │
  │  [SEC (68)]  [Aramco (45)]  [SABIC (52)]  [HADEED (35)]     │
  │      ↑            ↑              ↑             ↑              │
  │   count of     count of      count of      count of          │
  │   RFPs where   RFPs where    RFPs where    RFPs where        │
  │   Company =    Company =     Company =     Company =          │
  │   "Saudi..."   "Aramco..."   "SABIC..."    "HADEED..."       │
  └──────────────────────────────────────────────────────────────┘
```

---

*Document Generated: 2026-02-18 | RFP Unique Display Logic v1.0*
