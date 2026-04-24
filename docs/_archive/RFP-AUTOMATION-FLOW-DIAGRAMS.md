# RFP Automation - Flow Diagrams

> All diagrams use Mermaid syntax. View in VS Code (Mermaid extension), GitHub, or any Mermaid-compatible renderer.

---

## Table of Contents

1. [System Architecture](#1-system-architecture)
2. [Login Flow](#2-login-flow)
3. [Dashboard Data Loading](#3-dashboard-data-loading)
4. [Download RFP Flow](#4-download-rfp-flow)
5. [Submit Process + Email Lifecycle](#5-submit-process--email-lifecycle)
6. [Match Percentage 3-Phase Resolution](#6-match-percentage-3-phase-resolution)
7. [Material Breakdown Dialog](#7-material-breakdown-dialog)
8. [Analytics & Insights Data Flow](#8-analytics--insights-data-flow)
9. [Caching Architecture](#9-caching-architecture)
10. [Complete RFP Lifecycle (End-to-End)](#10-complete-rfp-lifecycle-end-to-end)

---

## 1. System Architecture

```mermaid
graph TB
    subgraph "User Layer"
        Browser["Browser (React + Vite)"]
        Outlook["Outlook (Adaptive Cards)"]
    end

    subgraph "Frontend (React + TypeScript)"
        Dashboard["Dashboard Page"]
        Analytics["Analytics Page"]
        Insights["RFP/Material Insights"]
        LoginPage["Login Page"]
        SubmitDialog["Submit RFP Dialog"]
        MaterialDialog["Material Breakdown Dialog"]
    end

    subgraph "Backend (FastAPI - Python)"
        AuthRoutes["routes/api.py<br/>Login, Session, RFP Details"]
        DashRoutes["routes/dashboard.py<br/>Match %, Materials, Submit"]
        AutoRoutes["routes/automation.py<br/>Download, Submit, Decline"]
        CardRoutes["routes/actionable_cards.py<br/>Adaptive Card Responses"]
        DashService["services/dashboard_service.py<br/>Caching + Processing"]
        UserService["services/user_service.py"]
        RoleService["services/dynamic_role_service.py"]
    end

    subgraph "Automation Layer"
        Playwright["Playwright Browser<br/>(automation_logic.py)"]
        AribaPortal["Ariba Procurement Portal"]
    end

    subgraph "Data Layer"
        Dataverse["Microsoft Dataverse<br/>(OData v9.2)<br/>cr673_ tables"]
        SharePoint["SharePoint<br/>(Graph API)<br/>Excel, TDS, Master CSVs"]
        LocalFS["Local File System<br/>ALLRFPs/ folder"]
    end

    subgraph "Email Layer"
        GraphMail["Microsoft Graph API<br/>(Mail.Send)"]
        PowerAutomate["Power Automate<br/>(Flow triggers)"]
    end

    Browser --> LoginPage & Dashboard & Analytics & Insights & SubmitDialog & MaterialDialog
    LoginPage --> AuthRoutes
    Dashboard --> AuthRoutes & DashRoutes
    Analytics --> AuthRoutes
    Insights --> AuthRoutes
    SubmitDialog --> DashRoutes & AutoRoutes
    MaterialDialog --> DashRoutes

    AuthRoutes --> UserService & RoleService
    AuthRoutes --> DashService
    DashRoutes --> DashService
    AutoRoutes --> Playwright
    CardRoutes --> Dataverse

    UserService --> Dataverse
    RoleService --> Dataverse
    DashService --> Dataverse
    Playwright --> AribaPortal
    Playwright --> SharePoint & LocalFS

    DashRoutes --> SharePoint & LocalFS
    AutoRoutes --> SharePoint

    CardRoutes --> GraphMail
    AutoRoutes --> GraphMail & PowerAutomate

    Outlook -->|"Card Response POST"| CardRoutes

    style Dataverse fill:#4472C4,color:#fff
    style SharePoint fill:#0078D4,color:#fff
    style AribaPortal fill:#E67E22,color:#fff
    style GraphMail fill:#D63384,color:#fff
    style Playwright fill:#2ECC71,color:#fff
```

---

## 2. Login Flow

```mermaid
sequenceDiagram
    autonumber
    participant U as User Browser
    participant R as React (login.tsx)
    participant Z as Zustand Store
    participant API as FastAPI (api.py)
    participant US as user_service.py
    participant UL as user_lifecycle_service.py
    participant RS as dynamic_role_service.py
    participant DV as Dataverse

    U->>R: Enter email + password
    R->>R: Zod validation (email format, password required)
    R->>API: POST /api/login {email, password}

    Note over API: Rate Limit Check
    API->>API: _check_rate_limit(email) [in-memory]
    API->>API: _check_rate_limit(ip) [in-memory]
    alt Rate limit exceeded
        API-->>R: 429 Too Many Requests
        R-->>U: "Too many attempts"
    end

    Note over API,DV: Step 1: Authenticate
    API->>US: authenticate_user(email, password)
    US->>DV: Query cr673_bahra_userses<br/>WHERE email=X AND password=Y
    DV-->>US: User record or empty
    alt User not found
        US-->>API: None
        API->>API: _record_failed_attempt(email)
        API->>DV: log_event(LOGIN_FAILED)
        API-->>R: 401 Unauthorized
        R-->>U: "Invalid credentials"
    end
    US-->>API: {name, email, role, mobile, record_id}

    Note over API,DV: Step 2: Check Account Status
    API->>UL: check_user_status_for_login(user_id)
    UL->>DV: Query cr673_bahra_user_statuses<br/>WHERE user_id=X
    DV-->>UL: Status record
    alt Account locked
        UL-->>API: {is_locked: true, minutes: 25}
        API-->>R: 423 Locked
        R-->>U: "Account locked for 25 min"
    end
    alt Account deactivated
        UL-->>API: {is_active: false}
        API-->>R: 403 Forbidden
        R-->>U: "Account deactivated"
    end
    UL-->>API: {is_locked: false, is_active: true}

    Note over API,DV: Step 3: Load Permissions
    API->>RS: get_user_permissions(user)
    RS->>RS: Check RBAC cache (300s TTL)
    alt Cache miss
        RS->>DV: Query cr673_bahra_role_permissionses<br/>WHERE role_name=X
        DV-->>RS: Permission keys
        RS->>RS: Cache permissions
    end
    RS-->>API: ["rfp.view", "dashboard.view", ...]

    Note over API: Step 4: Create Session
    API->>API: session["user"] = user + permissions
    API->>API: session["last_activity"] = now
    API->>DV: update_status_on_login() [clear failed_attempts]
    API->>DV: log_event(LOGIN_SUCCESS) [audit]
    API-->>R: {ok: true, redirect: "/dashboard"}

    Note over R,Z: Step 5: Frontend State
    R->>API: GET /api/session/status
    API-->>R: {valid: true, user: {...}}
    R->>Z: setUser(user), isAuthenticated=true
    Z->>Z: Persist to localStorage
    R->>U: navigate('/dashboard')
```

---

## 3. Dashboard Data Loading

```mermaid
sequenceDiagram
    autonumber
    participant U as Browser
    participant D as Dashboard (React)
    participant RQ as React Query
    participant API as FastAPI
    participant DS as dashboard_service.py
    participant C as Cache (in-memory)
    participant DV as Dataverse
    participant BP as Batch Match %

    U->>D: Navigate to /dashboard
    D->>RQ: useQuery(['dashboardData'])
    RQ->>API: GET /api/dashboard/data?refresh=0

    Note over API: require_permission("dashboard.view")
    API->>DS: get_dashboard_data_cached(force_refresh=false)

    DS->>C: Check _DASHBOARD_CACHE
    alt Cache valid (ts + 300s > now)
        C-->>DS: Cached data
        DS-->>API: Return cached
    else Cache expired or empty
        Note over DS: Double-checked locking
        DS->>DS: Acquire threading.Lock()

        par Fetch Data Sources
            DS->>DV: Automation logs<br/>cr673_bahra_automation_log1s<br/>(last 30 days)
            DS->>DV: RFP activity data<br/>cr673_requestforproposals
        end

        DV-->>DS: Automation logs
        DV-->>DS: RFP activity rows

        Note over DS: Pandas Processing
        DS->>DS: Deduplicate by RFP_ID
        DS->>DS: Normalize Company_Name
        DS->>DS: Filter expired RFPs (End_Date < now)
        DS->>DS: Aggregate Material/Keyword Matched
        DS->>DS: Categorize: open/submitted/declined/saved_draft
        DS->>DS: Company-wise breakdown

        DS->>C: Store in _DASHBOARD_CACHE (ts=now)
        DS-->>API: Fresh data
    end

    API-->>RQ: JSON response
    RQ-->>D: Data available

    Note over D: Render Dashboard
    D->>D: Metric cards (total, submitted, declined)
    D->>D: Company tabs + status sub-tabs
    D->>D: RFP table rows

    Note over D,BP: Lazy Load Match Percentages
    D->>BP: getBatchMatchPercentages(visibleRfpIds)
    BP->>API: GET /dashboard/rfp/batch-match-percentages
    API-->>BP: {rfp_id: {match_percentage, total, matched}}
    BP-->>D: Update table rows with match %
```

---

## 4. Download RFP Flow

```mermaid
flowchart TD
    A["User clicks 'Download RFPs'"] --> B["GET /api/download-rfp<br/>(returns 202 Accepted)"]
    B --> C{"Thread-safe check:<br/>_try_start_operation('download')"}
    C -->|"Already running"| D["Return 409 Conflict"]
    C -->|"OK"| E["Background Thread:<br/>run_automation_download()"]

    E --> F["Initialize GraphClient<br/>(SharePoint auth)"]
    F --> G["Launch Playwright Browser<br/>(headless=false)"]
    G --> H["Login to Ariba Portal<br/>login_and_select_company()"]
    H --> I["Scrape Open RFPs<br/>scrape_open_rfps()"]
    I --> J{"New RFPs found?"}

    J -->|"No"| K["Send 'No New RFPs' email"]
    J -->|"Yes"| L["For Each New RFP"]

    L --> M["Download Excel via Playwright<br/>(capture download event)"]
    M --> N["Save to Local:<br/>ALLRFPs/{Company}/{RFP}/downloaded-rfp/"]
    N --> O["Upload to SharePoint:<br/>RFP-logs/ALLRFPs/{Company}/{RFP}/downloaded-rfp/"]
    O --> P["Extract Materials<br/>extract_materials_from_excel()<br/>(9-digit codes from 'Other Content' sheet)"]

    P --> Q["Match Against Master Data"]
    Q --> R["Exact Code Match<br/>(O(1) set lookup)"]
    R --> S["Keyword Fallback<br/>(substring matching)"]
    S --> T["Store Matched_Data JSON<br/>in Dataverse Activity Log"]

    T --> U["Send Adaptive Card Email<br/>send_actionable_rfp_emails()"]
    U --> V["Get Team from Dataverse"]
    V --> W["Group by Email<br/>(1 email per person)"]
    W --> X["Build Adaptive Card:<br/>Products|Email|Results*|Remarks*<br/>(indexed fields: results_0, remarks_0)"]
    X --> Y["Attach: RFP Excel + Matched CSV"]
    Y --> Z["Send via Graph API MIME"]

    Z --> AA["Log to Dataverse<br/>Automation Log"]
    AA --> AB["_finish_operation('download')"]

    M -->|"Download Failed"| AC["Screenshot + Error Log"]
    AC --> AD["Send Error Notification Email"]
    AD --> AB

    style A fill:#4CAF50,color:#fff
    style Z fill:#2196F3,color:#fff
    style T fill:#4472C4,color:#fff
    style AC fill:#F44336,color:#fff
```

---

## 5. Submit Process + Email Lifecycle

```mermaid
flowchart TD
    subgraph "Phase 1: Upload"
        A["User opens Submit Dialog"] --> B["Enter RFP ID + Upload Excel + TDS PDFs"]
        B --> C["Validate RFP<br/>GET /dashboard/validate-rfp"]
        C -->|"Valid"| D["POST /dashboard/submit-rfp<br/>(FormData)"]
        D --> E["Upload Excel to SharePoint<br/>(2 locations: downloaded-rfp + rfp-upload-file)"]
        E --> F["Upload TDS PDFs to SharePoint<br/>(TDS-files/ folder)"]
        F --> G["Save copies locally"]
    end

    subgraph "Phase 2: Portal Automation"
        G --> H["run_automation_submit()"]
        H --> I["Playwright: Login to Ariba"]
        I --> J["Find matching RFP"]
        J --> K["Read Excel from rfp-upload-file/"]
        K --> L["Fill form + Click Submit"]
        L --> M["Update Dataverse:<br/>participated = 'submitted'"]
    end

    subgraph "Phase 3: Team Email"
        M --> N["Build Adaptive Card per team member"]
        N --> O["Send via Graph API MIME"]
        O --> P["Each person receives email in Outlook"]
    end

    subgraph "Phase 4: Response Collection"
        P --> Q["Team member fills Results + Remarks"]
        Q --> R["Click 'Submit All Responses'"]
        R --> S["POST /api/actionable-card/response"]
        S --> T["Verify bearer token<br/>(substrate.office.com)"]
        T --> U["Parse indexed form data<br/>(results_0, remarks_0, etc.)"]
        U --> V["Upsert to Dataverse<br/>RFP_RESPONSE_TABLE"]
        V --> W{"All team members<br/>responded?"}
    end

    subgraph "Phase 5: Consolidation"
        W -->|"No"| X["Return updated card<br/>(shows partial responses)"]
        W -->|"Yes"| Y["send_consolidated_response_email()"]
        Y --> Z["Build read-only card<br/>with all responses"]
        Z --> AA{"All results = 'No'?"}
        AA -->|"Yes"| AB["Include Decline button<br/>(for authorized emails)"]
        AA -->|"No"| AC["Send without Decline"]
        AB --> AD["Send to all team + admins"]
        AC --> AD
    end

    subgraph "Phase 6: Decline (Optional)"
        AD --> AE["Admin clicks Decline"]
        AE --> AF["run_automation_decline()"]
        AF --> AG["Playwright: Login → Decline on portal"]
        AG --> AH["Update Dataverse:<br/>participated = 'declined'"]
        AH --> AI["Send decline notification"]
    end

    style A fill:#4CAF50,color:#fff
    style O fill:#2196F3,color:#fff
    style Y fill:#9C27B0,color:#fff
    style AF fill:#F44336,color:#fff
```

### Email Response Sequence (Detailed)

```mermaid
sequenceDiagram
    autonumber
    participant O as Outlook
    participant AC as Actionable Card API
    participant DV as Dataverse
    participant EM as Email Service

    Note over O: Email opens in Outlook
    O->>AC: Auto-invoke: POST /response/refresh
    AC->>DV: Query latest responses for RFP
    DV-->>AC: Current response count
    AC-->>O: Updated card (X/5 responses)<br/>Header: CARD-UPDATE-IN-BODY: true

    Note over O: User fills form
    O->>O: Fill Results + Remarks per product

    O->>AC: POST /response<br/>(Bearer token + form data)
    AC->>AC: Verify token (substrate.office.com)
    AC->>AC: Parse: results_0, remarks_0, results_1...
    AC->>DV: Upsert cr673_bahra_rfp_responses<br/>(cr673_response_data = JSON)
    AC->>DV: Update activity log<br/>(response_count++, timestamps)

    AC->>DV: Query all responses for RFP
    DV-->>AC: All response records

    alt All team responded
        AC->>EM: send_consolidated_response_email()
        EM->>EM: Build read-only Adaptive Card
        EM->>EM: Attach RFP file + matched CSV
        EM->>O: Send to all team + admins
        Note over O: Consolidated email received
    end

    AC-->>O: Return updated card<br/>(own responses shown, status updated)
```

---

## 6. Match Percentage 3-Phase Resolution

```mermaid
flowchart TD
    A["GET /dashboard/rfp/batch-match-percentages<br/>rfp_ids=RFP-001,RFP-002,...,RFP-050"] --> B["Initialize shared resources"]

    B --> B1["GraphClient.auth()"]
    B --> B2["get_cached_master_data()<br/>(master_material.csv, 5min TTL)"]
    B --> B3["get_cached_keywords()<br/>(unique_keywords.csv, 5min TTL)"]
    B --> B4["master_code_set = set(master[col])<br/>(O(1) lookup)"]

    B1 & B2 & B3 & B4 --> C["Phase A: Memory Cache Check"]

    C --> D{"For each RFP:<br/>In _MATCH_PERCENTAGE_CACHE<br/>AND cache_version == 3?"}
    D -->|"Yes"| E["Add to results<br/>(O(1), instant)"]
    D -->|"No"| F["Add to uncached_ids"]

    F --> G["Phase B: Batch Dataverse Query"]
    G --> H["Chunk uncached_ids into groups of 15<br/>(OData URL length limit)"]
    H --> I["For each chunk:<br/>Query cr673_requestforproposals<br/>SELECT RFP_ID, Matched_Data<br/>WHERE RFP_ID eq 'X' or RFP_ID eq 'Y'..."]
    I --> J{"Matched_Data<br/>JSON exists?"}
    J -->|"Yes"| K["Parse JSON → extract stats<br/>Cache in memory"]
    J -->|"No"| L["Add to fallback_ids"]

    L --> M["Phase C: Parallel Excel Fallback<br/>ThreadPoolExecutor(max_workers=5)"]
    M --> N["Per RFP (parallel):"]
    N --> O["Download Excel from SharePoint"]
    O --> P["extract_materials_from_excel()<br/>(all items, no intent filter)"]
    P --> Q["For each material:"]
    Q --> R{"mat_code in<br/>master_code_set?"}
    R -->|"Yes"| S["is_matched=True<br/>method='exact_code'"]
    R -->|"No"| T["Extract keywords from name+desc"]
    T --> U{"Keyword substring<br/>match found?"}
    U -->|"Yes"| V["is_matched=True<br/>method='keyword'"]
    U -->|"No"| W["is_matched=False"]

    S & V & W --> X["Calculate:<br/>match% = matched/total * 100"]
    X --> Y["Cache result in memory"]

    E & K & Y --> Z["Return aggregated results<br/>{rfp_id: {match_percentage, total, matched}}"]

    style C fill:#4CAF50,color:#fff
    style G fill:#2196F3,color:#fff
    style M fill:#FF9800,color:#fff
    style Z fill:#9C27B0,color:#fff
```

### Performance Comparison

```mermaid
gantt
    title Match % Resolution Time per RFP
    dateFormat X
    axisFormat %Lms

    section Phase A (Cache)
    Memory lookup    :done, 0, 1

    section Phase B (Dataverse)
    OData query      :active, 0, 400

    section Phase C (Excel)
    Download file    :crit, 0, 2000
    Extract materials:crit, 2000, 3500
    Match algorithm  :crit, 3500, 4500
```

---

## 7. Material Breakdown Dialog

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant D as Dashboard
    participant DLG as MaterialBreakdownDialog
    participant RQ as React Query
    participant API as FastAPI (dashboard.py)
    participant DV as Dataverse
    participant SP as SharePoint

    U->>D: Click "View Breakdown" on RFP row
    D->>DLG: open=true, rfpId="RFP-001", company="Company A"

    DLG->>RQ: useQuery(['rfpMaterials', rfpId, company])
    Note over RQ: staleTime: 5 minutes
    RQ->>API: GET /dashboard/rfp/RFP-001/materials?company=Company%20A

    Note over API: Primary Path: Dataverse
    API->>DV: Query cr673_requestforproposals<br/>WHERE RFP_ID='RFP-001'<br/>SELECT Matched_Data
    DV-->>API: Matched_Data JSON

    alt Matched_Data found (fast path ~300ms)
        API->>API: Parse JSON array
        API->>API: Transform: is_matched, match_method, master_description
        API-->>RQ: Materials response
    else No Matched_Data (fallback ~3-8s)
        API->>SP: Download RFP Excel
        SP-->>API: Excel file
        API->>API: extract_materials_from_excel()
        API->>SP: get_cached_master_data() + get_cached_keywords()
        SP-->>API: Master CSV + Keywords
        API->>API: Match each material:<br/>1. Exact code (set lookup)<br/>2. Keyword (substring)
        API-->>RQ: Materials response
    end

    RQ-->>DLG: Data loaded

    Note over DLG: Render Dialog
    DLG->>DLG: Summary: 75% match (green badge)
    DLG->>DLG: Progress bar: 75/100 matched
    DLG->>DLG: Filter tabs: All(100) | Matched(75) | Not Matched(25)
    DLG->>DLG: Search box
    DLG->>DLG: Table: Code | Description | Status | Method | Master Desc

    U->>DLG: Click "Matched" tab
    DLG->>DLG: Filter: materials.filter(m => m.is_matched)

    U->>DLG: Type in search box
    DLG->>DLG: Filter by code/name/description/master_description
```

---

## 8. Analytics & Insights Data Flow

```mermaid
flowchart LR
    subgraph "Analytics Page"
        A1["analytics.tsx"] -->|"getRfpDetails(limit:10000)"| A2["GET /api/dashboard/rfp-details"]
        A2 --> A3["Backend: Load all RFP data<br/>(cached 300s)"]
        A3 --> A4["Return 10K RFPs"]
        A4 --> A5["Client-side JS:<br/>Calculate all stats"]
        A5 --> A6["Donut: Status Distribution"]
        A5 --> A7["Bar: Top 5 Companies"]
        A5 --> A8["Stacked: Participation"]
    end

    subgraph "Material Insights Page"
        B1["material-insights.tsx"] -->|"useInfiniteQuery<br/>50 items/page"| B2["GET /dashboard/material-insights-grouped"]
        B2 --> B3["Backend: Group by code<br/>Calculate stats<br/>Paginate"]
        B3 --> B4["Return page + has_more"]
        B4 --> B5["Top 10 Bar Charts"]
        B4 --> B6["Expandable Group Table"]
        B4 --> B7["Scroll → fetchNextPage"]
    end

    subgraph "RFP Insights Page"
        C1["rfp-insights.tsx"] -->|"useInfiniteQuery<br/>50 items/page"| C2["GET /api/dashboard/rfp-details"]
        C2 --> C3["Backend: Apply filters<br/>Paginate"]
        C3 --> C4["Return page + counts"]
        C4 --> C5["Stat Cards"]
        C4 --> C6["Filterable Table"]
        C4 --> C7["Export CSV/Excel"]
        C4 --> C8["Scroll → fetchNextPage"]
    end

    style A5 fill:#F44336,color:#fff
    style B3 fill:#4CAF50,color:#fff
    style C3 fill:#4CAF50,color:#fff
```

> **Note**: Red = performance bottleneck (analytics client-side computation), Green = properly paginated

---

## 9. Caching Architecture

```mermaid
flowchart TB
    subgraph "Layer 1: Browser"
        RQ["React Query Cache<br/>staleTime: 5 min<br/>Per queryKey"]
        ZS["Zustand + localStorage<br/>Auth state persistence"]
        LS["localStorage<br/>Column visibility prefs"]
    end

    subgraph "Layer 2: FastAPI In-Memory"
        DC["Dashboard Cache<br/>TTL: 300s<br/>Lock: threading.Lock()"]
        ARC["All RFP Cache<br/>TTL: 300s"]
        MC["Material Insights Cache<br/>TTL: 300s"]
        MGC["Material Grouped Cache<br/>TTL: 300s"]
        MPC["Match % Cache<br/>No TTL, version-based<br/>_MATCH_CACHE_VERSION=3"]
        RBAC["RBAC Permission Cache<br/>TTL: 300s"]
        LC["Logs Cache<br/>TTL: 300s"]
    end

    subgraph "Layer 3: File System"
        MF["Master CSV<br/>TTL: 300s + mtime check"]
        KF["Keywords CSV<br/>TTL: 300s + mtime check"]
        EF["Local Excel files<br/>(mirrored from SharePoint)"]
    end

    subgraph "Layer 4: Source of Truth"
        DV["Microsoft Dataverse<br/>(OData API v9.2)"]
        SP["SharePoint<br/>(Graph API)"]
    end

    RQ -->|"Cache miss"| DC & ARC & MC & MGC & MPC
    DC -->|"Cache miss"| DV
    ARC -->|"Cache miss"| DV
    MC -->|"Cache miss"| DV
    MGC -->|"Cache miss"| DV
    MPC -->|"Phase B miss"| DV
    MPC -->|"Phase C miss"| EF
    RBAC -->|"Cache miss"| DV
    MF -->|"Download if stale"| SP
    KF -->|"Download if stale"| SP
    EF -->|"Download if missing"| SP

    DC -.->|"invalidate_dashboard_caches()"| ARC & MC & MGC

    style DV fill:#4472C4,color:#fff
    style SP fill:#0078D4,color:#fff
    style MPC fill:#FF9800,color:#fff
```

### Cache Invalidation Flow

```mermaid
flowchart LR
    A["Status Change<br/>(submit/decline)"] --> B["invalidate_dashboard_caches()"]
    B --> C["Clear _DASHBOARD_CACHE"]
    B --> D["Clear _ALL_RFP_CACHE"]
    B --> E["Clear _MATERIAL_CACHE"]
    B --> F["Clear _MATERIAL_GROUPED_CACHE"]

    G["New RFP Download"] --> B
    H["Cache version bump"] --> I["_MATCH_CACHE_VERSION++"]
    I --> J["All match % cache entries invalid<br/>(checked per-read)"]

    K["Master CSV updated<br/>on SharePoint"] --> L["File mtime changes"]
    L --> M["Next get_cached_master_data()<br/>detects mtime change"]
    M --> N["Re-download from SharePoint"]
```

---

## 10. Complete RFP Lifecycle (End-to-End)

```mermaid
flowchart TD
    START["New RFPs Published on Ariba Portal"] --> DL

    subgraph DL["1. DOWNLOAD"]
        DL1["Playwright automation<br/>scrapes Ariba portal"]
        DL2["Download Excel files"]
        DL3["Save: Local + SharePoint"]
        DL1 --> DL2 --> DL3
    end

    DL --> EX

    subgraph EX["2. EXTRACT & MATCH"]
        EX1["Extract materials from Excel<br/>(9-digit codes, 'Other Content' sheet)"]
        EX2["Match vs master_material.csv<br/>(exact code O(1) + keyword fallback)"]
        EX3["Store Matched_Data JSON<br/>in Dataverse Activity Log"]
        EX1 --> EX2 --> EX3
    end

    EX --> EM

    subgraph EM["3. NOTIFY TEAM"]
        EM1["Build Adaptive Card<br/>per team member"]
        EM2["Products|Email|Results*|Remarks*<br/>(editable own products only)"]
        EM3["Send via Graph API MIME<br/>+ RFP Excel attachment"]
        EM1 --> EM2 --> EM3
    end

    EM --> RS

    subgraph RS["4. COLLECT RESPONSES"]
        RS1["Each member responds in Outlook"]
        RS2["POST /api/actionable-card/response"]
        RS3["Verify token → Save to Dataverse"]
        RS4{"All responded?"}
        RS1 --> RS2 --> RS3 --> RS4
        RS4 -->|"No"| RS5["Return updated card<br/>(partial responses)"]
        RS4 -->|"Yes"| RS6["Send consolidated email"]
    end

    RS --> DB

    subgraph DB["5. DASHBOARD VIEW"]
        DB1["Dashboard shows RFP with status"]
        DB2["Lazy load match %<br/>(3-phase: cache → Dataverse → Excel)"]
        DB3["Click 'View Breakdown'<br/>→ Material Dialog"]
        DB1 --> DB2 --> DB3
    end

    RS6 --> DC

    subgraph DC["6. DECISION"]
        DC1{"Admin Decision"}
        DC1 -->|"Submit"| DC2["Upload Excel + TDS<br/>→ Playwright submits on portal"]
        DC1 -->|"Decline"| DC3["Playwright declines on portal"]
        DC1 -->|"Save Draft"| DC4["Status: saved_draft"]
    end

    DC2 --> FN1["Status: submitted"]
    DC3 --> FN2["Status: declined"]

    FN1 & FN2 & DC4 --> AN

    subgraph AN["7. ANALYTICS & INSIGHTS"]
        AN1["Analytics: Portfolio overview charts"]
        AN2["Material Insights: Top materials/keywords"]
        AN3["RFP Insights: Filterable table + export"]
    end

    style DL fill:#4CAF50,color:#fff
    style EX fill:#2196F3,color:#fff
    style EM fill:#9C27B0,color:#fff
    style RS fill:#FF9800,color:#fff
    style DB fill:#00BCD4,color:#fff
    style DC fill:#F44336,color:#fff
    style AN fill:#607D8B,color:#fff
```

---

## Appendix: Dataverse Entity Relationship

```mermaid
erDiagram
    USERS ||--o{ USER_STATUS : "has status"
    USERS ||--o{ AUDIT_LOGS : "generates"
    USERS }o--|| ROLES : "has role"
    ROLES ||--o{ ROLE_PERMISSIONS : "has permissions"

    RFP_ACTIVITY_LOG ||--o{ RFP_RESPONSES : "receives"
    RFP_ACTIVITY_LOG ||--o{ RFP_STATUS_HISTORY : "tracks changes"
    RFP_ACTIVITY_LOG ||--o{ AUTOMATION_LOGS : "logged by"

    USERS {
        string name
        string email
        string password
        string role
        string mobile_number
        guid record_id
    }

    USER_STATUS {
        string user_id
        string is_active
        string failed_attempts
        string locked_until
        string last_login
    }

    ROLES {
        string name
        string description
        string is_active
        string is_system
    }

    ROLE_PERMISSIONS {
        string role_name
        string permission_key
    }

    RFP_ACTIVITY_LOG {
        string RFP_ID
        string Company_Name
        string Owner_Name
        string RFP_End_Date
        string participated
        string Material_Matched
        string Keyword_Matched
        text Matched_Data
        string Link
    }

    RFP_RESPONSES {
        string rfp_id
        string name
        string email
        string product
        string results
        string remarks
        text response_data
        datetime submitted_at
    }

    AUTOMATION_LOGS {
        string RunID
        string Timestamp
        string Category
        string RFP_ID
        string Action
        string automation_status
        string Message
    }

    AUDIT_LOGS {
        string user_id
        string action
        string details
        datetime timestamp
    }
```
