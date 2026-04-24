# RFP Automation System - Deep Flow Analysis

> **Generated**: March 2026 | **Project**: Bahra Electric RFP Automation Portal
> **Stack**: FastAPI (Python) + React/TypeScript + Microsoft Dataverse + SharePoint + Playwright

---

## Table of Contents

1. [System Architecture Overview](#1-system-architecture-overview)
2. [Flow 1: Login](#2-flow-1-login)
3. [Flow 2: Dashboard Data Loading](#3-flow-2-dashboard-data-loading)
4. [Flow 3: Download RFP](#4-flow-3-download-rfp)
5. [Flow 4: Submit Process](#5-flow-4-submit-process)
6. [Flow 5: Matching Percentage](#6-flow-5-matching-percentage)
7. [Flow 6: Material Breakdown Dialog](#7-flow-6-material-breakdown-dialog)
8. [Flow 7: Analytics & Insights Pages](#8-flow-7-analytics--insights-pages)
9. [Caching Architecture](#9-caching-architecture)
10. [Optimization Analysis (Before vs After)](#10-optimization-analysis-before-vs-after)

---

## 1. System Architecture Overview

### Components

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | React + TypeScript + Vite | SPA with TanStack Query, Zustand, Recharts |
| **Backend** | FastAPI (Python) | REST API, session management, business logic |
| **Database** | Microsoft Dataverse (OData v9.2) | Primary data store, publisher prefix `cr673_` |
| **File Storage** | SharePoint (Graph API) | RFP Excel files, TDS PDFs, master CSVs |
| **Automation** | Playwright (headless browser) | Ariba portal scraping, RFP download/submit |
| **Email** | Microsoft Graph API + Adaptive Cards | Outlook actionable emails for team responses |
| **Auth** | Azure AD (MSAL client credentials) | Token-based Dataverse/SharePoint/Graph access |

### Dataverse Tables

| Table | Logical Name | API Name | Purpose |
|-------|-------------|----------|---------|
| Users | `cr673_bahra_users` | `cr673_bahra_userses` | User accounts |
| User Status | `cr673_bahra_user_status` | `cr673_bahra_user_statuses` | Lock/active status |
| Roles | `cr673_bahra_roles` | `cr673_bahra_roleses` | RBAC roles |
| Role Permissions | `cr673_bahra_role_permissions` | `cr673_bahra_role_permissionses` | Permission keys per role |
| RFP Activity Log | `cr673_requestforproposal` | `cr673_requestforproposals` | RFP metadata + Matched_Data |
| Automation Logs | `cr673_bahra_automation_log1` | `cr673_bahra_automation_log1s` | Run history |
| Audit Logs | `cr673_bahra_audit_logs` | `cr673_bahra_audit_logses` | User action tracking |
| RFP Responses | `cr673_bahra_rfp_responses` | `cr6db_cr673_bahra_rfp_responses` | Per-email adaptive card responses |
| System Settings | `cr673_bahra_system_settings` | `cr673_bahra_system_settingses` | Email recipients, config |

### File Storage Structure

```
SharePoint: RFP-logs/
  └── ALLRFPs/
      └── {CompanyName}/
          └── {RFP_ID}/
              ├── downloaded-rfp/     ← Original RFP Excel
              ├── rfp-upload-file/    ← Modified Excel for submission
              └── TDS-files/          ← Technical Data Sheet PDFs

Local: ALLRFPs/
  └── (mirrors SharePoint structure)

Master Files (SharePoint):
  ├── master-files/material.csv        ← Master material codes
  └── master-files/unique_keywords.csv ← Industry keywords
```

---

## 2. Flow 1: Login

### Business Process
User authenticates with email/password. System verifies credentials against Dataverse, checks account status (locked/deactivated), loads role-based permissions, creates a server-side session, and redirects to dashboard.

### Technical Process

#### Frontend (`frontend/src/pages/login.tsx`)

1. **Form Validation** (Zod schema):
   - Email: required, valid email format
   - Password: required, min 1 character

2. **onSubmit Handler** (Lines 47-58):
   ```
   → useAuth().login(email, password)
   → On success: toast("Login successful") → navigate('/dashboard', { replace: true })
   → On error: toast(error.message)
   ```

3. **Auth Store** (`frontend/src/hooks/use-auth.ts`, Lines 25-93):
   ```
   login(email, password):
     → api.login(email, password)           // POST /api/login
     → api.getSessionStatus()               // GET /api/session/status
     → set({ user, isAuthenticated: true }) // Zustand + localStorage
   ```

4. **API Client** (`frontend/src/lib/api.ts`):
   - `login()` (Lines 34-42): POST /api/login, `credentials: 'include'`
   - `getSessionStatus()` (Lines 78-83): GET /api/session/status
   - `refreshSession()` (Lines 70-76): POST /api/session/refresh

#### Backend (`routes/api.py:98-191`)

**Step 1 - Input Validation** (Lines 99-105):
- Parse JSON body → extract email, password
- Trim + lowercase email
- Return 400 if either missing

**Step 2 - Rate Limiting** (Lines 107-122):
- Per-email: `_check_rate_limit(email)`
- Per-IP: `_check_rate_limit(f"ip:{client_ip}")`
- Config: 5 attempts in 300s window → 300s lockout
- Return 429 (Too Many Requests) if exceeded

**Step 3 - Authentication** (Lines 124-139):
- `authenticate_user(email, password)` → `services/user_service.py:197-213`
- Dataverse query: `cr673_bahra_userses` WHERE email = X AND password = Y
- Returns: `{ name, email, role, mobile, record_id }` or None
- On failure: `_record_failed_attempt()`, audit log, return 401

**Step 4 - Account Status Check** (Lines 141-157):
- `check_user_status_for_login(user_id)` → `services/user_lifecycle_service.py:246-281`
- Dataverse query: `cr673_bahra_user_statuses` WHERE user_id = X
- Checks:
  - `locked_until > now` → return 423 (Locked) with minutes remaining
  - `is_active == false` → return 403 (Forbidden)

**Step 5 - Success** (Lines 170-189):
- Clear rate limits: `_clear_failed_attempts(email)`, `_clear_failed_attempts(ip)`
- Update status: `update_status_on_login()` → set failed_attempts=0, last_login=now
- Load permissions: `get_user_permissions(user)` → `services/dynamic_role_service.py:358-370`
  - Query: `cr673_bahra_role_permissionses` WHERE role_name = X
  - Returns: `["rfp.view", "rfp.submit", "dashboard.view", ...]`
  - Cached for 300s (RBAC_CACHE_TTL_SECONDS)
- Create session:
  ```python
  request.session["user"] = user  # includes permissions array
  request.session["last_activity"] = int(time.time())
  ```
- Audit: `log_event(AuditAction.LOGIN)` → Dataverse audit table
- Return: `{ "ok": True, "redirect": "/dashboard" }`

#### Session Configuration (`config/config.py:167-173`)

| Setting | Value | Purpose |
|---------|-------|---------|
| `SESSION_TIMEOUT_SECONDS` | 7200 (2h) | Absolute session lifetime |
| `IDLE_TIMEOUT_SECONDS` | 1800 (30m) | Inactivity timeout |
| `SESSION_WARNING_SECONDS` | 300 (5m) | Warning before expiry |
| `SESSION_REFRESH_INTERVAL` | 300 (5m) | Auto-refresh interval |
| `ACCOUNT_LOCKOUT_THRESHOLD` | 5 | Failed attempts before lock |
| `ACCOUNT_LOCKOUT_DURATION_MINUTES` | 30 | Lock duration |

#### Session Expiry Detection
1. Frontend makes any API call → backend returns 401
2. `handleResponse()` in api.ts throws ApiError(401)
3. `checkSession()` called → clears Zustand store
4. Route guard redirects to `/login`

### Data Flow Summary

```
Browser → POST /api/login (email, password)
  → Rate limit check (in-memory)
  → Dataverse: cr673_bahra_userses (auth)
  → Dataverse: cr673_bahra_user_statuses (status)
  → Dataverse: cr673_bahra_role_permissionses (permissions)
  → Dataverse: cr673_bahra_audit_logses (audit log)
  → Session cookie set
  → Return { redirect: "/dashboard" }
Browser → GET /api/session/status
  → Return { valid: true, user: {...} }
Browser → Zustand store updated → navigate('/dashboard')
```

### Error Paths

| Status | Condition | User Experience |
|--------|-----------|----------------|
| 400 | Missing email/password | Form validation error |
| 401 | Invalid credentials | "Invalid email or password" |
| 403 | Account deactivated | "Account has been deactivated" |
| 423 | Account locked | "Account locked for X minutes" |
| 429 | Rate limit exceeded | "Too many attempts, try again later" |

---

## 3. Flow 2: Dashboard Data Loading

### Business Process
After login, the dashboard displays RFP statistics, company-wise RFP lists with status tabs, and lazy-loaded material match percentages. Data is cached for 5 minutes with thread-safe invalidation.

### Technical Process

#### Frontend (`frontend/src/pages/dashboard.tsx`)

**Data Loading** (Lines 493-496):
```typescript
useQuery({
  queryKey: ['dashboardData'],
  queryFn: () => api.getDashboardData()  // GET /api/dashboard/data?refresh=0
})
```

**Rendering**:
- Metric cards: total RFPs, submitted, declined, last automation run
- Company tabs with status sub-tabs (Open/Submitted/Draft/Declined)
- RFP table with columns: RFP ID, Company, Owner, End Date, Material Match, Keyword Match
- Match percentages loaded lazily per visible rows

**Lazy Match % Loading** (Lines 160-173):
```typescript
api.getBatchMatchPercentages(rfpIds, companiesMap)
// GET /dashboard/rfp/batch-match-percentages?rfp_ids=...&companies=...
```

#### Backend

**Endpoint** (`routes/api.py:560-565`):
```python
@router.get("/dashboard/data")
async def get_dashboard_data_endpoint(request, refresh: int = 0,
                                       user = Depends(require_permission("dashboard.view"))):
    return get_dashboard_data_cached(force_refresh=bool(refresh))
```

**Caching** (`services/dashboard_service.py:44-104`):
- Cache: `_DASHBOARD_CACHE = {"data": None, "ts": 0}`
- TTL: 300 seconds
- Thread-safe: `threading.Lock()` with double-checked locking pattern
- Stampede prevention: only one thread rebuilds cache, others wait

**Data Processing** (`services/dashboard_service.py:124-346`):

**Step 1 - Fetch Automation Logs**:
- Table: `cr673_bahra_automation_log1s`
- Filter: last 30 days
- Columns: RunID, Timestamp, Category, RFP_ID, Action, automation_status, Message
- Method: `DATAVERSE.get_rows_from_dataverse()` with display names

**Step 2 - Fetch RFP Activity**:
- `get_rfp_activity_data_from_db()` from `helpers/core_helper.py`
- Queries Dataverse: `cr673_requestforproposals`
- Returns: RFP_ID, RFP_End_Date, Company_Name, Owner_Name, Publish_Time, participated, Material_Matched, Keyword_Matched, Link

**Step 3 - Pandas Processing**:
```python
# Deduplicate by RFP_ID (keep first)
df = df.drop_duplicates(subset=['RFP_ID'], keep='first')

# Normalize Company_Name (default: "Saudi Electricity Company")
df['Company_Name'] = df['Company_Name'].fillna("Saudi Electricity Company")

# Filter expired RFPs
df = df[df['RFP_End_Date'] >= current_datetime]

# Aggregate Material_Matched/Keyword_Matched (ANY "Yes" → all "Yes")
# Categorize: open/submitted/declined/saved_draft by participated column
```

**Step 4 - Build Response**:
```python
{
  "rfp": { "total_rfps", "downloaded_rfps", "prev_total_rfps", "prev_downloaded_rfps" },
  "automation": { "total_runs", "successful_runs", "failed_runs", "last_run_time", "last_run_id" },
  "downloaded_rfps": [...],
  "open_rfps": [...],
  "submitted_rfps": [...],
  "declined_rfps": [...],
  "saved_draft_rfps": [...],
  "total_submitted_rfps": int,
  "total_declined_rfps": int,
  "companies_rfps": {
    "Company A": { "open": [...], "submitted": [...], "saved_draft": [...], "declined": [...] }
  },
  "unique_companies": ["Company A", "Company B"]
}
```

### Data Sources

| Data | Source | Cache |
|------|--------|-------|
| RFP metadata | Dataverse `cr673_requestforproposals` | 300s in-memory |
| Automation logs | Dataverse `cr673_bahra_automation_log1s` | 300s in-memory |
| Match percentages | Separate batch endpoint | Per-RFP in-memory |

### Performance Profile
- **Cache hit**: ~0ms backend processing
- **Cache miss**: 2 Dataverse queries + pandas processing = ~2-5s
- **Frontend**: staleTime not set → refetches on component mount

---

## 4. Flow 3: Download RFP

### Business Process
The system automates RFP download from the Ariba procurement portal using browser automation (Playwright). For each company, it logs into the portal, scrapes open RFPs, downloads Excel files, extracts material codes, matches them against the master catalog, and sends notification emails to the team.

### Technical Process

#### Frontend Trigger
- Dashboard "Download RFPs" button → GET /api/download-rfp or /api/download-rfps-automation
- Returns **202 Accepted** immediately (non-blocking)
- UI polls `/automation/status` for real-time progress

#### Backend Entry Points (`routes/automation.py`)

| Endpoint | Line | Purpose |
|----------|------|---------|
| `GET /download-rfp?company=X` | 189 | Single company download |
| `GET /download-rfps-automation` | 207 | All companies download |
| `GET /dashboard/download-all-rfps` | 231 | Dashboard trigger |

**Thread-Safe State** (Lines 60-187):
```python
_RUN_STATE = {
    "download": False,   # Prevents concurrent downloads
    "submit": False,
    "decline": False,
    "submitting_rfps": set()
}
_STATE_LOCK = threading.Lock()
```

#### Automation Logic (`automation_logic.py`)

**`run_automation_download()`** (Lines 520-567):

1. **Initialize**:
   - Generate unique RUN_ID via `start_new_run()`
   - Authenticate GraphClient for SharePoint
   - Resolve company name

2. **Browser Setup** (`common_flow()`, Lines 476-517):
   ```python
   async def common_flow(p, graph_client, profile_label, company):
       browser = await p.chromium.launch(headless=False)
       context = await browser.new_context(user_data_dir=temp_profile)
       page = await context.new_page()
       await login_and_select_company(page, target_company)
       open_rfps = await scrape_open_rfps(page, company=target_company)
       return open_rfps, page, browser
   ```

3. **Download RFPs** (`download_rfp()`, Lines 404-474):
   - For each RFP: click download → capture Playwright download event
   - Save locally: `ALLRFPs/{Company}/{RFP_ID}/downloaded-rfp/`
   - Upload to SharePoint: `RFP-logs/ALLRFPs/{Company}/{RFP_ID}/downloaded-rfp/`

4. **Material Extraction** (`helpers/core_helper.py`):
   ```python
   extract_materials_from_excel(excel_path, include_details=True, filter_by_intent=True)
   # Reads "Other Content" sheet → finds "name" column
   # Extracts 9-digit material codes
   # Filters by "Intend To Respond" = "Yes"
   # Returns: [{ material_code, name, description }, ...]
   ```

5. **Material Matching**:
   - Load master CSV from SharePoint: `master_material.csv`
   - Match by exact material code (O(1) set lookup)
   - Keyword fallback: substring matching against `unique_keywords.csv`
   - Store Matched_Data JSON in Dataverse RFP activity log

6. **Email Notification**:
   - **New RFPs found**: Send per-RFP Adaptive Card email
   - **No new RFPs**: Send "no new RFP" notification
   - **Download failures**: Send error email with failed list

#### Email Construction (`helpers/email_helper.py`)

**`send_actionable_rfp_emails()`** (Lines 452-643):

1. Fetch team table from Dataverse → group by email
2. Download RFP file + matched CSV from SharePoint as attachments
3. Build Adaptive Card per person:
   - ColumnSet table: **Products | Email | Results* | Remarks*** (editable only for own products)
   - Indexed input fields: `results_0`, `remarks_0`, `results_1`, `remarks_1`...
   - "Submit All Responses" button → POST to callback URL
   - "Refresh Status" button → auto-invoked when email opens
4. Send via Graph API MIME endpoint (preserves `<script type="application/adaptivecard+json">`)

### Data Flow

```
User clicks "Download RFPs"
  → GET /api/download-rfp (returns 202)
  → Background thread:
    → Playwright: Launch browser → Login to Ariba portal
    → Scrape open RFPs (title, end date, link, document ID)
    → For each new RFP:
      → Download Excel file via Playwright
      → Save to local folder + Upload to SharePoint
      → Extract materials from Excel (9-digit codes)
      → Match against master CSV + keywords
      → Store Matched_Data JSON in Dataverse
      → Send Adaptive Card email to team
    → Log automation result to Dataverse
  → UI polls /automation/status for progress
```

### Error Handling
- Screenshot capture on failure: `_take_error_screenshot(page, "download_rfp")`
- Failure log to Dataverse: `record_failure_log(e, context, graph_client, screenshot_path)`
- Email notification: `_notify_failure_via_email("Download RFP", failure_info)`
- State cleanup: `_finish_operation("download")` always runs

---

## 5. Flow 4: Submit Process

### Business Process
Complete RFP submission lifecycle:
1. User uploads filled Excel + TDS PDFs via dialog
2. Files uploaded to SharePoint
3. Playwright automates portal submission
4. Adaptive Card emails sent to team for per-product responses
5. Each team member submits their response via Outlook
6. When all respond, consolidated email sent
7. Admin can decline RFP if all results are "No"

### Technical Process

#### Phase 1: File Upload

**Frontend** (`frontend/src/components/dialogs/submit-rfp-dialog.tsx`):
- Form: RFP ID (validated), Company (auto-select), Excel file (.xls/.xlsx), TDS PDFs
- Validation: `api.validateRfp()` → GET /dashboard/validate-rfp
- Submit: `api.submitRfp(formData)` → POST /dashboard/submit-rfp

**Validation** (`routes/api.py:540-630`):
- Check RFP exists in Dataverse activity log
- Check status is "downloaded"
- Check company matches

**Upload** (`routes/automation.py:226-407`):
```python
# 1. Upload Excel to TWO SharePoint locations:
#    - downloaded-rfp/ (original location)
#    - rfp-upload-file/ (automation checks this first)
# 2. Upload TDS PDFs to TDS-files/
# 3. Save copies locally
# 4. Trigger: run_automation_submit(rfp_id, company)
```

#### Phase 2: Portal Automation

**`run_automation_submit()`** (`automation_logic.py:644-761`):
1. Launch Playwright → Login to Ariba portal
2. Find matching RFP from scraped list
3. Read Excel from `rfp-upload-file/` (first) or `downloaded-rfp/` (fallback)
4. Fill RFP form with data from Excel
5. Click Submit button
6. Update Dataverse status: `participated = "submitted"`

**Final Submit** (`routes/dashboard.py:2573-2870`):
```python
# POST /submit-rfp-final
# Parse: materials_data (JSON), dynamic_fields (JSON), TDS files
# Save TDS to local folder
# Unprotect Excel if needed
# Update Excel sheets:
#   - Write dynamic form fields to yellow-highlighted cells
#   - Update "Other Content" sheet with material responses
# Save to rfp-upload-file/
```

#### Phase 3: Email & Response Handling

**Adaptive Card Response** (`routes/actionable_cards.py:298-578`):

```python
@router.post("/response")
async def receive_card_response(request):
    # 1. Verify bearer token (substrate.office.com)
    claims = _verify_actionable_message_token(auth_header)

    # 2. Parse indexed form data
    for idx, product in enumerate(products):
        results = body.get(f"results_{idx}")
        remarks = body.get(f"remarks_{idx}")

    # 3. Upsert to Dataverse RFP_RESPONSE_TABLE
    row_data = {
        "cr673_rfp_id": rfp_id,
        "cr673_response_data": json.dumps({"products": per_product_responses}),
        "cr673_submitted_at": datetime.now(),
    }

    # 4. Update activity log metrics (response_count, first_response_at)

    # 5. Check if ALL team members responded
    all_responded = team_emails.issubset(responded_emails)

    # 6. If all responded → send consolidated email
    if all_responded:
        send_consolidated_response_email(rfp_id, responses, company, rfp_end_date)

    # 7. Return updated card (CARD-UPDATE-IN-BODY: true header)
```

**Consolidated Email** (`helpers/email_helper.py:646-907`):
- All team responses compiled into read-only Adaptive Card
- Table: Product | Name | Results | Remarks
- Decline button visible only if:
  - Recipient in `DECLINE_BUTTON_EMAILS` config AND all results = "No"
- Sent to all team + EMAIL_TO_NEW_RFP recipients

**Decline Flow** (`routes/automation.py:483-502`):
- Triggered from Decline button in consolidated email
- Playwright: Login → Find RFP → Click Decline
- Update Dataverse: `participated = "declined"`
- Send decline notification email

#### Phase 4: Status Tracking

**Status Update** (`routes/dashboard.py:191-220`):
```python
@router.post("/dashboard/rfp/status")
# Normalizes: submitted, declined, saved_draft, open
# Updates Dataverse RFP_ACTIVITY_LOG_TABLE
# Logs change to RFP_STATUS_TABLE
```

**Dataverse Tables for Tracking**:

| Table | Columns | Purpose |
|-------|---------|---------|
| RFP Activity Log | `Participation_Status`, `response_count`, `first_response_at`, `all_responses_at` | Overall RFP status |
| RFP Response | `cr673_rfp_id`, `cr673_email`, `cr673_response_data` (JSON), `cr673_submitted_at` | Per-email responses |
| RFP Status | `rfp_id`, `from_status`, `to_status`, `category`, `changed_at` | Status change history |

### Complete Lifecycle

```
1. User uploads Excel + TDS → SharePoint (2 locations)
2. Playwright submits on portal → Status: "submitted"
3. Adaptive Card emails sent → One per team member
4. Each member responds via Outlook:
   → POST /api/actionable-card/response
   → Verify token → Save to Dataverse
   → Return updated card (inline refresh)
5. When all respond:
   → Consolidated email to all + admins
   → Decline button if all "No"
6. Optional: Admin clicks Decline
   → Playwright declines on portal
   → Status: "declined"
```

---

## 6. Flow 5: Matching Percentage

### Business Process
Each RFP shows what percentage of its requested materials match the company's master material catalog. Two matching methods: exact material code match (primary, O(1)) and keyword substring match (fallback). Results are color-coded: Green (>=80%), Amber (>=50%), Red (<50%).

### Technical Process

#### Frontend (`frontend/src/pages/dashboard.tsx:160-173`)

```typescript
// Batch fetch for visible RFP rows
api.getBatchMatchPercentages(rfpIds, companiesMap)
// GET /dashboard/rfp/batch-match-percentages?rfp_ids=X,Y,Z&companies={...}

// Display: Progress bar + percentage + color badge
// Green: >=80%, Amber: >=50%, Red: <50%
```

#### Backend 3-Phase Resolution (`routes/dashboard.py:2441-2559`)

**Pre-initialization** (done once per batch request):
```python
graph_client = GraphClient(...)  # SharePoint access
master = get_cached_master_data(graph_client, master_csv_local)  # 5-min TTL
keywords_list = get_cached_keywords(graph_client, keywords_csv_local)  # 5-min TTL
master_code_set = set(master[master_col].astype(str))  # O(1) lookup set
```

**Phase A - Memory Cache** (Lines 2493-2505):
```python
for rfp_id in rfp_id_list:
    if rfp_id in _MATCH_PERCENTAGE_CACHE:
        cached = _MATCH_PERCENTAGE_CACHE[rfp_id]
        if cached.get("cache_version") == _MATCH_CACHE_VERSION:  # v3
            results[rfp_id] = cached  # O(1), instant
            continue
    uncached_ids.append(rfp_id)
```

**Phase B - Batch Dataverse Query** (Lines 2507-2524):
```python
dv_results = _batch_get_match_percentages_from_dataverse(uncached_ids)
# Chunks of 15 RFPs per query (OData URL length limit)
# Filter: RFP_ID eq 'X' or RFP_ID eq 'Y' or ...
# Select: RFP_ID, Matched_Data
# Parse Matched_Data JSON → extract match stats
# Cache result in _MATCH_PERCENTAGE_CACHE
```

**Phase C - Parallel Excel Fallback** (Lines 2526-2557):
```python
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {
        executor.submit(
            calculate_match_percentage_optimized,
            rfp_id, master, master_col, keywords_list,
            company=company_map.get(rfp_id),
            graph_client=graph_client,
            master_code_set=master_code_set,
            skip_dataverse=True
        ): rfp_id
        for rfp_id in fallback_ids
    }
```

#### Matching Algorithm (`routes/dashboard.py:811-900`)

```python
def calculate_match_percentage_optimized(rfp_id, master, master_col, keywords_list, ...):
    # 1. Extract ALL materials from Excel (no intent filter)
    materials_data = extract_materials_from_excel(excel_path, filter_by_intent=False)

    # 2. For each material:
    for mat in materials_data:
        mat_code = mat['material_code']

        # Method 1: Exact code match (O(1) set lookup)
        if mat_code in master_code_set:
            mat['is_matched'] = True
            mat['match_method'] = 'exact_code'
            continue

        # Method 2: Keyword matching (fallback)
        mat_keywords = extract_keywords(mat['name'] + ' ' + mat['description'])
        for csv_keyword in keywords_list:
            if csv_keyword in mat_keyword or mat_keyword in csv_keyword:
                mat['is_matched'] = True
                mat['match_method'] = 'keyword'
                break

    # 3. Calculate percentage
    matched_count = sum(1 for m in materials_data if m['is_matched'])
    match_percentage = round(matched_count / len(materials_data) * 100, 1)
```

### Data Sources

| Data | Source | Cache TTL |
|------|--------|-----------|
| Pre-computed match data | Dataverse `Matched_Data` JSON column | In-memory (no TTL, version-based) |
| Master material codes | SharePoint `master_material.csv` | 300s + file mtime check |
| Keywords | SharePoint `unique_keywords.csv` | 300s + file mtime check |
| RFP Excel materials | SharePoint/Local files | Not cached (extracted per request) |

### Performance Profile

| Phase | Latency | Condition |
|-------|---------|-----------|
| Phase A (cache hit) | <1ms per RFP | RFP previously loaded, same cache version |
| Phase B (Dataverse) | 200-500ms per batch of 15 | Matched_Data exists in Dataverse |
| Phase C (Excel fallback) | 2-5s per RFP | No Dataverse data, must download + parse Excel |

---

## 7. Flow 6: Material Breakdown Dialog

### Business Process
User clicks "View Breakdown" on any RFP row to see a detailed material-by-material breakdown showing which materials matched, the match method (exact code vs keyword), and allowing filtering/search.

### Technical Process

#### Frontend (`frontend/src/components/dialogs/material-breakdown-dialog.tsx`)

**Query** (Lines 58-63):
```typescript
useQuery({
  queryKey: ['rfpMaterials', rfpId, company],
  queryFn: () => api.getRfpMaterials(rfpId!, company || undefined),
  enabled: open && !!rfpId,
  staleTime: 5 * 60 * 1000,  // 5-minute cache
})
```

**UI Components**:
1. **Summary Header**: Match % badge (color-coded) + progress bar + matched/total counts
2. **Filter Tabs**: All | Matched (count) | Not Matched (count)
3. **Search**: Real-time filter by material_code, name, description, master_description
4. **Table**: Material Code | Description | Status Badge | Match Method | Master Description
5. **Color Coding**: Green rows = matched, Red rows = not matched

#### Backend (`routes/dashboard.py:2229-2399`)

**Primary Path** - Dataverse Lookup (`_try_materials_from_dataverse()`):
```python
# Query: RFP_ACTIVITY_LOG_TABLE WHERE RFP_ID = X
# Select: Matched_Data column
# Parse JSON array → transform to materials list
# Return if found (fast path, ~300ms)
```

**Fallback Path** - Live Excel Extraction:
```python
# 1. Download RFP Excel from SharePoint (if not local)
# 2. extract_materials_from_excel(excel_path, include_details=True, filter_by_intent=False)
# 3. Download master CSV + keywords (cached 5 min)
# 4. Match each material:
#    a. Exact code match: mat_code in master_code_set
#    b. Keyword match: substring overlap
# 5. Return materials array (slow path, ~3-8s)
```

**Response Structure**:
```json
{
  "ok": true,
  "rfp_id": "RFP-001",
  "total_materials": 100,
  "matched_count": 75,
  "unmatched_count": 25,
  "exact_code_matches": 60,
  "keyword_matches": 15,
  "match_percentage": 75.0,
  "materials": [
    {
      "material_code": "123456789",
      "name": "Steel Cable 3x50mm",
      "description": "Armoured power cable",
      "is_matched": true,
      "match_method": "exact_code",
      "master_description": "Steel Cable - Industrial Grade",
      "master_data": { ... },
      "selected": false,
      "reason": ""
    }
  ]
}
```

### Performance Profile
- **Dataverse path**: ~300-500ms (single OData query + JSON parse)
- **Excel fallback**: ~3-8s (download + extract + match)
- **Frontend cache**: 5-minute stale time on React Query

---

## 8. Flow 7: Analytics & Insights Pages

### 8A. Analytics Page

#### Business Process
High-level RFP portfolio overview with charts: status distribution, top companies, participation rates.

#### Technical Process (`frontend/src/pages/analytics.tsx`)

**Data Fetching** (Line 175):
```typescript
api.getRfpDetails({ limit: 10000 })  // Fetches ALL RFP data
// GET /api/dashboard/rfp-details?limit=10000
```

**Client-Side Calculations** (Lines 181-227):
- Total/Submitted/Material Matched/Keyword Matched counts
- Donut chart: RFP Status Distribution (Submitted/Open/Declined)
- Bar chart: Top 5 Companies by RFP Count
- Stacked bar: Participation by Company

**Backend** (`routes/api.py:567-690`):
- Loads all RFP data from `get_all_rfp_data_cached()` (300s TTL)
- Applies filters: status, company, dates, material/keyword match, participation
- Returns paginated results with status counts

**Performance Issue**: Fetches 10,000 RFPs in single request, all chart calculations happen in JavaScript client-side. Load time: **3-8 seconds**.

### 8B. Material Insights Page

#### Business Process
Shows which materials and keywords appear most frequently across RFPs, grouped by code with expandable RFP details.

#### Technical Process (`frontend/src/pages/material-insights.tsx`)

**Data Fetching** (Lines 71-93):
```typescript
useInfiniteQuery({
  queryKey: ['materialInsightsGrouped', activeTab, appliedFilters],
  queryFn: ({ pageParam = 0 }) => api.getMaterialInsightsGrouped({
    tab: activeTab,        // 'materials' or 'keywords'
    ...appliedFilters,
    limit: 50,
    offset: pageParam,
  }),
  getNextPageParam: (lastPage) => lastPage.has_more ? lastPage.offset + lastPage.limit : undefined,
})
```

**Backend** (`routes/api.py:930-1020`):
- Groups materials/keywords by code
- Calculates per-group statistics
- Pagination: 50 items per page
- Returns: materials list, stats, chart data (top 10)

**UI Features**:
- Tabs: Materials / Keywords
- Bar charts: Top 10 Materials/Keywords by RFP count
- Expandable rows: click group → see individual RFPs
- Filters: company, participation, search
- Infinite scroll pagination

**Performance**: Good - proper pagination, ~1-2s load.

### 8C. RFP Insights Page

#### Business Process
Detailed filterable, exportable table of all RFPs with advanced filtering and column customization.

#### Technical Process (`frontend/src/pages/rfp-insights.tsx`)

**Data Fetching**:
```typescript
useInfiniteQuery({
  queryKey: ['rfpDetails', appliedFilters],
  queryFn: ({ pageParam = 0 }) => api.getRfpDetails({
    ...filters,
    limit: 50,
    offset: pageParam,
  }),
})
```

**Filters** (Advanced):
| Filter | Options |
|--------|---------|
| Status | open, submitted, declined, not_participant, downloaded |
| Company | Dropdown from unique companies |
| Date Range | start_date, end_date (YYYY-MM-DD) |
| Material Match | matched / not_matched |
| Keyword Match | matched / not_matched |
| Participation | participated / not_participated / declined |
| Search | RFP ID / Company / Owner name |

**Features**:
- Column visibility toggle (persisted in localStorage)
- Export: CSV or Excel (applies current filters)
- Stat cards: Total, Submitted, Declined, Not Participant, Open
- Infinite scroll: 50 items per page

**Backend** (`routes/api.py:567-690`):
- Status normalization via `_normalize_participation()`
- Company + date + match filtering
- Pagination with total counts

**Performance**: Good - proper pagination, ~1-2s load.

---

## 9. Caching Architecture

### Cache Layers

| Layer | Location | TTL | Invalidation | Scope |
|-------|----------|-----|-------------|-------|
| **React Query** | Browser memory | 5min stale | queryKey change | Per-component |
| **Zustand** | localStorage | Session | Logout / checkSession | Auth state |
| **Dashboard Cache** | `dashboard_service.py:46` | 300s | `invalidate_dashboard_caches()` | All dashboard data |
| **All RFP Cache** | `dashboard_service.py:467` | 300s | Same invalidation | Full RFP dataset |
| **Material Cache** | `dashboard_service.py:614` | 300s | Same invalidation | Material insights |
| **Material Grouped** | `dashboard_service.py:890` | 300s | Same invalidation | Grouped insights |
| **Master CSV** | `dashboard.py:608` | 300s + mtime | File change detection | Material codes |
| **Keywords CSV** | `dashboard.py:609` | 300s + mtime | File change detection | Industry keywords |
| **Match %** | `dashboard.py:610` | No TTL | Version bump (`_MATCH_CACHE_VERSION`) | Per-RFP match results |
| **RBAC Permissions** | `dynamic_role_service.py` | 300s | Manual | Role→permissions |
| **Logs** | `dashboard_service.py:954` | 300s | Explicit | Automation logs |

### Cache Validation Strategies

1. **Time-based (TTL)**: Most caches use 300-second TTL
2. **File-based (mtime)**: Master CSV and keywords check file modification time
3. **Version-based**: Match percentage cache uses `_MATCH_CACHE_VERSION = 3`
4. **Double-checked locking**: Dashboard cache uses `threading.Lock()` to prevent stampede

### Cache Invalidation

```python
def invalidate_dashboard_caches():
    """Clears ALL backend caches - called after status changes, new data"""
    _DASHBOARD_CACHE["data"] = None
    _DASHBOARD_CACHE["ts"] = 0
    _ALL_RFP_CACHE["data"] = None
    _ALL_RFP_CACHE["ts"] = 0
    _MATERIAL_CACHE["data"] = None
    _MATERIAL_CACHE["ts"] = 0
    _MATERIAL_GROUPED_CACHE.clear()
```

---

## 10. Optimization Analysis (Before vs After)

### Priority 1 - HIGH IMPACT

| # | Flow | Optimization | Before | After | Effort |
|---|------|-------------|--------|-------|--------|
| 1 | **Analytics Page** | Create backend aggregation API `/api/analytics/summary` that returns pre-computed stats instead of dumping 10K RFPs | **3-8s** (fetch all + JS compute) | **<500ms** (backend aggregates) | Medium |
| 2 | **Dashboard** | Parallel Dataverse queries with `asyncio.gather()` for automation logs + RFP activity | **2-5s** (sequential, cache miss) | **1-3s** (parallel) | Low |
| 3 | **Match %** | Backfill Matched_Data in Dataverse for all existing RFPs (one-time migration script) | **2-5s per RFP** (Excel fallback) | **300ms** (Dataverse lookup) | Medium |
| 4 | **Login** | Parallel fetch: status check + permissions load after auth with `asyncio.gather()` | **1.5-3s** (3 sequential Dataverse calls) | **0.8-1.5s** (auth + parallel) | Low |
| 5 | **Material Dialog** | Prefetch data on row hover (before dialog opens) | **300ms-8s** perceived | **<100ms** perceived | Low |

### Priority 2 - MEDIUM IMPACT

| # | Flow | Optimization | Before | After | Effort |
|---|------|-------------|--------|-------|--------|
| 6 | **Dashboard** | Include top-N match percentages in dashboard response (from Dataverse Matched_Data) | Extra batch API call after render | Single load, no second call | Medium |
| 7 | **Dashboard** | Use `staleWhileRevalidate` pattern (show stale cache, refresh in background) | Wait for fresh data | Instant stale → background refresh | Low |
| 8 | **Login** | Async audit logging (fire-and-forget background task) | +200ms synchronous write | 0ms (non-blocking) | Low |
| 9 | **Submit** | Parallel SharePoint uploads with `asyncio.gather()` for Excel + TDS files | Sequential uploads | Concurrent uploads (~50% faster) | Low |

### Priority 3 - LOWER IMPACT

| # | Flow | Optimization | Before | After | Effort |
|---|------|-------------|--------|-------|--------|
| 10 | **Match %** | Add 10-min TTL to memory cache (prevent stale data) | No TTL (version-only invalidation) | Fresh within 10min | Trivial |
| 11 | **Material Dialog** | Virtualize long material lists with react-virtual | Janky scroll for 500+ materials | Smooth always | Low |
| 12 | **Download** | Parallel company downloads (multiple Playwright contexts) | Sequential per company | Concurrent (~2-3x faster) | High |
| 13 | **Match %** | Increase Dataverse batch chunk size using POST $batch | 15 RFPs per query | 50+ per query | Medium |
| 14 | **Analytics** | Cache aggregated analytics stats server-side (5-min TTL) | Recompute every page load | Near-instant repeated loads | Low |

### Estimated Total Impact

| Page/Flow | Current Load | After P1 Optimizations | After All |
|-----------|-------------|----------------------|-----------|
| Login | 1.5-3s | 0.8-1.5s | 0.6-1s |
| Dashboard (cold) | 2-5s | 1-3s | 0.5-1.5s |
| Dashboard (warm) | <100ms | <100ms | <100ms |
| Match % (batch) | 1ms-5s/RFP | 1ms-500ms/RFP | 1ms-300ms/RFP |
| Material Dialog | 300ms-8s | 300ms-500ms | <100ms (prefetch) |
| Analytics | 3-8s | <500ms | <200ms |
| Material Insights | 1-2s | 1-2s | <1s |
| RFP Insights | 1-2s | 1-2s | <1s |

---

## Appendix: Key File Reference

| Component | File Path | Key Functions/Lines |
|-----------|-----------|---------------------|
| Login Page | `frontend/src/pages/login.tsx` | onSubmit (47-58) |
| Auth Store | `frontend/src/hooks/use-auth.ts` | login (32-44), checkSession (55-79) |
| API Client | `frontend/src/lib/api.ts` | login (34-42), getDashboardData (86-91), getBatchMatchPercentages (267-278) |
| Dashboard Page | `frontend/src/pages/dashboard.tsx` | useQuery (493-496), RfpTableRow (189) |
| Analytics Page | `frontend/src/pages/analytics.tsx` | getRfpDetails limit:10000 (175) |
| Material Insights | `frontend/src/pages/material-insights.tsx` | useInfiniteQuery (71-93) |
| RFP Insights | `frontend/src/pages/rfp-insights.tsx` | Filters, export, pagination |
| Material Dialog | `frontend/src/components/dialogs/material-breakdown-dialog.tsx` | useQuery (58-63), filters (71-84) |
| Login Endpoint | `routes/api.py` | POST /api/login (98-191) |
| Dashboard Endpoint | `routes/api.py` | GET /dashboard/data (560-565) |
| RFP Details | `routes/api.py` | GET /dashboard/rfp-details (567-690) |
| Material Insights | `routes/api.py` | GET /dashboard/material-insights-grouped (930-1020) |
| Batch Match % | `routes/dashboard.py` | GET /rfp/batch-match-percentages (2441-2559) |
| Material Breakdown | `routes/dashboard.py` | GET /rfp/{id}/materials (2229-2399) |
| Match Algorithm | `routes/dashboard.py` | calculate_match_percentage_optimized (811-900) |
| Submit RFP Final | `routes/dashboard.py` | POST /submit-rfp-final (2573-2870) |
| Download Automation | `routes/automation.py` | download-rfp (189), download-rfps-automation (207) |
| Submit Automation | `routes/automation.py` | submit-rfp (226-407) |
| Decline | `routes/automation.py` | decline (483-502) |
| Adaptive Card Response | `routes/actionable_cards.py` | POST /response (298-578) |
| Dashboard Service | `services/dashboard_service.py` | get_dashboard_data (124-346), caching (44-104) |
| User Auth | `services/user_service.py` | authenticate_user (197-213) |
| User Lifecycle | `services/user_lifecycle_service.py` | check_user_status_for_login (246-281) |
| Permissions | `services/dynamic_role_service.py` | get_user_permissions (358-370) |
| Excel Extraction | `helpers/core_helper.py` | extract_materials_from_excel, path helpers |
| Email Helper | `helpers/email_helper.py` | send_actionable_rfp_emails (452-643), consolidated (646-907) |
| Dataverse Client | `helpers/dataverse_helper.py` | DataverseClient class |
| SharePoint Client | `helpers/sharepoint_helper.py` | GraphClient class |
| Auth Middleware | `middleware/auth.py` | get_current_user (9-22), require_permission (33-56) |
| Configuration | `config/config.py` | All table names, timeouts, paths |
