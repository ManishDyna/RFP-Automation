# RFP Automation - Full Codebase Optimization Plan

**Date:** 2026-03-15
**Scope:** Backend (FastAPI/Python) + Frontend (React/TypeScript) + Infrastructure

---

## Table of Contents

1. [Priority 1: Critical (Security + Breaking Issues)](#priority-1-critical)
2. [Priority 2: High (Performance Bottlenecks)](#priority-2-high)
3. [Priority 3: Medium (Code Organization)](#priority-3-medium)
4. [Priority 4: Frontend Optimizations](#priority-4-frontend)
5. [Priority 5: Infrastructure](#priority-5-infrastructure)
6. [Impact Summary Matrix](#impact-summary-matrix)
7. [Recommended Execution Order](#recommended-execution-order)

---

## Priority 1: Critical

### 1.1 Duplicate Auth Endpoints (Route Conflict)

**Problem:**
Both `routes/auth.py` AND `routes/api.py` define identical endpoints:
- `POST /login`
- `POST /logout`
- `GET /session/status`
- `POST /session/refresh`

Both are registered in `dashboard_main.py` (lines 52 and 62). This causes **unpredictable routing** — FastAPI may serve the wrong handler.

**Fix:**
- Remove duplicate endpoints from `routes/auth.py`
- Keep the more complete versions in `routes/api.py` (which includes rate limiting)
- Or consolidate into a single `routes/auth_routes.py`

**Files Affected:**
- `routes/auth.py`
- `routes/api.py`
- `dashboard_main.py`

**Flow After Optimization:**
Single auth path → predictable login behavior → no shadowed routes → easier debugging

---

### 1.2 Hardcoded Session Secret

**Problem:**
`dashboard_main.py:31` uses `secret_key="change-me-please"` — anyone who reads the source code can forge session cookies.

**Fix:**
```python
# Before (INSECURE)
app.add_middleware(SessionMiddleware, secret_key="change-me-please", max_age=SESSION_TIMEOUT_SECONDS)

# After (SECURE)
SESSION_SECRET = os.environ.get("SESSION_SECRET_KEY")
if not SESSION_SECRET:
    raise RuntimeError("SESSION_SECRET_KEY environment variable must be set")
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, max_age=SESSION_TIMEOUT_SECONDS)
```

**Files Affected:**
- `dashboard_main.py`
- `config/config.py`
- New `.env` file

---

### 1.3 Secrets in Source Code

**Problem:**
`config/config.py` contains sensitive data committed to git:
- Line 76: `CLIENT_SECRET = "pDN8Q~kLKXRoOmEB5PvLRDo-zVH2o91IjRtaJagr"`
- Lines 156-157: Power Automate Flow URLs with embedded API signatures
- Line 159: Forgot Password Flow URL with embedded signatures
- Line 5: Ariba portal URL

**Fix:**
1. Create `.env` file (git-ignored) with all secrets
2. Create `.env.example` with placeholder values for documentation
3. Load via `os.environ.get()` with validation
4. Add `.env*` patterns to `.gitignore`

**Files Affected:**
- `config/config.py`
- `.gitignore`
- New `.env` and `.env.example`

---

## Priority 2: High

### 2.1 Sync Blocking in Async Routes

**Problem:**
FastAPI routes are declared as `async def` but call synchronous `requests.get/post` (Dataverse API). This **blocks the entire event loop** — only one request can be processed at a time, defeating FastAPI's async architecture.

**Fix (Option A - Best):**
Switch `DataverseClient` from `requests` to `httpx.AsyncClient`:
```python
# Before (BLOCKING)
import requests
resp = requests.get(url, headers=headers)

# After (NON-BLOCKING)
import httpx
async with httpx.AsyncClient() as client:
    resp = await client.get(url, headers=headers)
```

**Fix (Option B - Quick):**
Change all route handlers from `async def` to `def`. FastAPI will automatically run them in a thread pool:
```python
# Before
@router.get("/api/dashboard")
async def get_dashboard(request: Request):  # blocks event loop
    data = DATAVERSE.query_rows(...)

# After
@router.get("/api/dashboard")
def get_dashboard(request: Request):  # runs in thread pool
    data = DATAVERSE.query_rows(...)
```

**Files Affected:**
- `helpers/dataverse_helper.py` (Option A)
- All route files (both options)

**Impact:** **3-5x throughput improvement** for concurrent users
**Flow After:** Multiple API requests processed simultaneously instead of sequentially

---

### 2.2 Repeated Metadata API Calls (N+1 Pattern)

**Problem:**
`_get_primary_id()` is duplicated in 3 services, each making a Dataverse metadata API call every time:
- `services/dynamic_role_service.py:67`
- `services/master_data_service.py:29`
- `services/user_service.py:25` (named `_get_primary_id_attribute`)
- Also in `services/user_lifecycle_service.py:100-102`

**Fix:**
1. Create shared `helpers/metadata_cache.py`:
```python
_primary_id_cache = {}

def get_primary_id(table_logical_name: str) -> str:
    if table_logical_name in _primary_id_cache:
        return _primary_id_cache[table_logical_name]

    url = f"{DATAVERSE.api_url}EntityDefinitions(LogicalName='{table_logical_name}')?$select=PrimaryIdAttribute"
    resp = requests.get(url, headers=DATAVERSE._headers())
    primary_id = resp.json().get("PrimaryIdAttribute", "")
    _primary_id_cache[table_logical_name] = primary_id
    return primary_id
```
2. Replace all 3+ duplicate functions with the shared one

**Files Affected:**
- New `helpers/metadata_cache.py`
- `services/dynamic_role_service.py`
- `services/master_data_service.py`
- `services/user_service.py`
- `services/user_lifecycle_service.py`

**Impact:** Eliminates ~3 redundant API calls per service operation
**Flow After:** First call fetches metadata → cached forever (metadata doesn't change at runtime)

---

### 2.3 N+1 Queries in Role Listing

**Problem:**
`role_routes.py` calls `get_role_permissions(role_name)` for EACH role in a loop:
```python
for role in roles:
    perms = get_role_permissions(role["name"])  # 1 API call per role!
    role["permission_count"] = len(perms)
```

**Fix:**
Fetch all permissions in one query, group by role in Python:
```python
all_perms = DATAVERSE.query_rows(PERMISSIONS_TABLE, select="role_name,permission_name")
perms_by_role = defaultdict(list)
for p in all_perms:
    perms_by_role[p["role_name"]].append(p)

for role in roles:
    role["permission_count"] = len(perms_by_role.get(role["name"], []))
```

**Files Affected:**
- `routes/role_routes.py`
- `services/dynamic_role_service.py`

**Impact:** 1 API call instead of N (where N = number of roles)

---

### 2.4 No Batching for Bulk Deletes

**Problem:**
`dynamic_role_service.py:296-300` deletes rows one-by-one in a loop:
```python
for row in rows:
    rid = row.get(primary_id)
    if rid:
        url = f"{DATAVERSE.api_url}{table}({rid})"
        requests.delete(url, headers=DATAVERSE._headers())  # N API calls!
```

**Fix:**
Use Dataverse `$batch` endpoint for bulk operations:
```python
def batch_delete(self, table_api_name: str, ids: list[str]):
    batch_id = str(uuid.uuid4())
    body = build_batch_body(batch_id, table_api_name, ids)
    resp = requests.post(f"{self.api_url}$batch", headers={...}, data=body)
```

**Files Affected:**
- `helpers/dataverse_helper.py` (add `batch_delete` method)
- `services/dynamic_role_service.py`

**Impact:** N API calls → 1 batch call

---

### 2.5 Missing Caching for Static/Semi-Static Data

**Problem:**
These functions hit Dataverse on every call with no caching:
- `list_materials()` — material master data (rarely changes)
- `list_roles()` — role definitions (rarely changes)
- `list_keywords()` — keyword data

Meanwhile, `dashboard_service.py` already has a good TTL cache pattern (5-minute).

**Fix:**
Add TTL-based caching (5-minute) to list operations:
```python
import time

_materials_cache = {"data": None, "expires": 0}

def list_materials():
    now = time.time()
    if _materials_cache["data"] and now < _materials_cache["expires"]:
        return _materials_cache["data"]

    data = DATAVERSE.query_rows(MATERIALS_TABLE, ...)
    _materials_cache["data"] = data
    _materials_cache["expires"] = now + 300
    return data
```

**Files Affected:**
- `services/master_data_service.py`
- `services/dynamic_role_service.py`

**Impact:** Dashboard and admin pages load significantly faster
**Flow After:** First load fetches from Dataverse → subsequent loads serve from cache for 5 minutes

---

### 2.6 No Retry Logic for Dataverse Calls

**Problem:**
Any transient network error or Dataverse throttle response crashes the endpoint. No retries anywhere.

**Fix:**
Add retry decorator with exponential backoff to `DataverseClient` methods:
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10))
def query_rows(self, table, ...):
    ...
```

**Files Affected:**
- `helpers/dataverse_helper.py`

**Impact:** Eliminates transient failure crashes

---

## Priority 3: Medium

### 3.1 Split Monolithic Route Files

**Problem:**
- `routes/dashboard.py` — **3,066 lines** (RFP CRUD + downloads + analytics + state)
- `routes/api.py` — **1,499 lines** (auth + profile + SAP + audit + validation)

**Proposed Split:**

| Current File | Split Into | Responsibility | ~Lines |
|---|---|---|---|
| `dashboard.py` (3,066) | `routes/rfp_routes.py` | RFP CRUD, status management | ~1,200 |
| | `routes/download_routes.py` | Excel/PDF download endpoints | ~800 |
| | `routes/analytics_routes.py` | Charts, insights, metrics | ~1,000 |
| `api.py` (1,499) | `routes/auth_routes.py` | Login, logout, session, rate limiting | ~400 |
| | `routes/profile_routes.py` | User profile, password changes | ~300 |
| | `routes/api.py` (slimmed) | SAP, audit, validation, scheduling | ~800 |

**Files Affected:**
- `routes/dashboard.py` → 3 new files
- `routes/api.py` → 3 new files
- `dashboard_main.py` (update router imports)

**Flow After:** Each file has single responsibility → easier navigation, testing, and code reviews

---

### 3.2 Consolidate Dual Lockout Systems

**Problem:**
Two separate, conflicting lockout mechanisms:
1. **In-memory rate limiter** in `routes/api.py` (lines 39-88) — lost on server restart
2. **Dataverse-persistent lockout** in `services/user_lifecycle_service.py` — survives restarts

They can disagree: in-memory says "locked" but Dataverse says "unlocked" (or vice versa).

**Fix:**
- Keep only the Dataverse-persistent lockout (reliable, survives restarts)
- Remove in-memory `_login_attempts` and `_ip_attempts` dictionaries
- Add IP tracking to Dataverse lockout if needed

**Files Affected:**
- `routes/api.py` (remove in-memory rate limiter)
- `services/user_lifecycle_service.py` (enhance if needed)

---

### 3.3 Remove Unused Dependencies

**Problem:**
`requirements.txt` has **126 packages**, ~30 of which are unused:

| Package | Why Unused |
|---|---|
| Flask, Flask-Cors, Flask-Login, Flask-WTF | Project uses FastAPI, not Flask |
| Flask-SQLAlchemy, Flask-Migrate | No Flask ORM needed |
| SQLAlchemy, Alembic | No SQL database (uses Dataverse) |
| Selenium, selenium-stealth, selenium-wire | Replaced by Playwright |
| Streamlit | Not used anywhere |

**Fix:**
```bash
pip uninstall flask flask-cors flask-login flask-wtf flask-sqlalchemy flask-migrate sqlalchemy alembic selenium selenium-stealth selenium-wire streamlit
pip freeze > requirements.txt
```

**Files Affected:**
- `requirements.txt`

**Impact:** Faster installs, smaller attack surface, less confusion

---

### 3.4 Add Global Error Handling

**Problem:**
Only 7 try-catch blocks in 1,499-line `api.py`. Most endpoints have zero error handling. Unhandled exceptions return raw 500 errors.

**Fix:**
Add global exception handler in `dashboard_main.py`:
```python
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error_id": str(uuid.uuid4())}
    )
```

**Files Affected:**
- `dashboard_main.py` (global handler)
- Route files (add specific try-catch for business logic errors)

---

### 3.5 Add Pydantic Request/Response Models

**Problem:**
Routes use raw `await request.json()` with no validation:
```python
body = await request.json()
email = body.get("email", "")  # No type checking, no required fields
```

**Fix:**
Define Pydantic models:
```python
from pydantic import BaseModel, EmailStr

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

@router.post("/api/login")
async def login(request: Request, body: LoginRequest):
    # body.email is guaranteed to be valid email
    # body.password is guaranteed to be string
```

**Files Affected:**
- New `models/` directory with request/response models
- Route files (update endpoint signatures)

---

## Priority 4: Frontend

### 4.1 Replace `any` Types with Proper Interfaces

**Problem:**
**318 instances of `any` type** across the frontend codebase. API responses have no type safety:
```typescript
// Current (UNSAFE)
getDashboardData: async () => { return handleResponse<any>(response) }

// RfpTableRow props
interface RfpTableRowProps {
    rfp: any  // No type safety!
}
```

**Fix:**
Create TypeScript interfaces for all API responses:
```typescript
// frontend/src/types/api.ts
interface DashboardData {
    rfps: RfpItem[]
    metrics: DashboardMetrics
    lastUpdated: string
}

interface RfpItem {
    id: string
    title: string
    company: string
    status: RfpStatus
    dueDate: string
    // ...
}
```

**Files Affected:**
- New `frontend/src/types/` directory
- `frontend/src/lib/api.ts` (type all responses)
- All page components (use proper types)

**Impact:** Catches bugs at compile time, better IDE autocomplete, self-documenting code

---

### 4.2 Extract Duplicate Components

**Problem:**
Same components defined in multiple files:
- `StatCard` — defined in both `rfp-insights.tsx` (line 109) AND `material-insights.tsx` (line 53)
- `StatusBadge` — defined in both `dashboard.tsx` AND `rfp-insights.tsx`

**Fix:**
Move to shared location:
```
frontend/src/components/shared/
  stat-card.tsx      ← extracted from rfp-insights + material-insights
  status-badge.tsx   ← extracted from dashboard + rfp-insights
```

**Files Affected:**
- `frontend/src/pages/rfp-insights.tsx`
- `frontend/src/pages/material-insights.tsx`
- `frontend/src/pages/dashboard.tsx`
- New shared component files

---

### 4.3 Memoize Table Row Components

**Problem:**
`RfpTableRow` component in `dashboard.tsx` is NOT wrapped in `React.memo()`. Every parent state change (e.g., opening a dialog, changing a filter) causes ALL table rows to re-render.

**Fix:**
```typescript
// Before
function RfpTableRow({ rfp, ... }: RfpTableRowProps) { ... }

// After
const RfpTableRow = React.memo(function RfpTableRow({ rfp, ... }: RfpTableRowProps) { ... })
```

**Files Affected:**
- `frontend/src/pages/dashboard.tsx`

**Impact:** Noticeable performance improvement with 50+ rows in the table

---

### 4.4 Consolidate Dialog State Management

**Problem:**
5 dialogs use separate `useState` in `ProtectedLayout` (App.tsx lines 70-74):
```typescript
const [declineRfpOpen, setDeclineRfpOpen] = useState(false)
const [downloadCompanyOpen, setDownloadCompanyOpen] = useState(false)
const [scheduleOpen, setScheduleOpen] = useState(false)
const [sapPasswordOpen, setSapPasswordOpen] = useState(false)
const [downloadMode, setDownloadMode] = useState("")
```
Only `SubmitRfpDialog` uses the `DialogContext`.

**Fix:**
Extend `DialogContext` to manage all 6 dialogs:
```typescript
type DialogType = 'submitRfp' | 'declineRfp' | 'downloadCompany' | 'schedule' | 'sapPassword'

interface DialogState {
    openDialog: DialogType | null
    dialogData: Record<string, any>
    openDialog: (type: DialogType, data?: any) => void
    closeDialog: () => void
}
```

**Files Affected:**
- `frontend/src/contexts/dialog-context.tsx`
- `frontend/src/App.tsx`
- Dialog components

---

### 4.5 Split Large Page Components

**Problem:**
- `dashboard.tsx` — 957 lines
- `rfp-insights.tsx` — 823 lines
- `material-insights.tsx` — 768 lines

**Proposed Split:**

| Page | Extract Into |
|---|---|
| `dashboard.tsx` | `components/dashboard/filters.tsx`, `components/dashboard/rfp-table.tsx`, `components/dashboard/metrics.tsx` |
| `rfp-insights.tsx` | `components/insights/rfp-filters.tsx`, `components/insights/rfp-table.tsx`, `components/insights/rfp-stats.tsx` |
| `material-insights.tsx` | `components/insights/material-tabs.tsx`, `components/insights/material-table.tsx` |

**Impact:** Easier testing, reduced re-renders (only changed section re-renders), better code navigation

---

### 4.6 Add Error Boundaries + Missing Error States

**Problem:**
- No global error boundary component
- Most queries don't show error UI — only loading/success states
- No retry UI for failed requests

**Fix:**
1. Add React Error Boundary at app level:
```typescript
// frontend/src/components/error-boundary.tsx
class ErrorBoundary extends React.Component {
    state = { hasError: false }
    static getDerivedStateFromError() { return { hasError: true } }
    render() {
        if (this.state.hasError) return <ErrorFallback />
        return this.props.children
    }
}
```

2. Add `isError` checks to all query-using pages:
```typescript
const { data, isLoading, isError, refetch } = useQuery(...)
if (isError) return <ErrorState onRetry={refetch} />
```

**Files Affected:**
- New `frontend/src/components/error-boundary.tsx`
- All page components

---

### 4.7 Bundle Size Optimization

**Problem:**
- No bundle analysis tool configured
- Recharts (heavy library) loaded eagerly
- No explicit code splitting beyond route-level lazy loading

**Fix:**
1. Add bundle analyzer:
```bash
npm install -D rollup-plugin-visualizer
```
2. Lazy-import heavy libraries:
```typescript
const Recharts = React.lazy(() => import('recharts'))
```
3. Verify tree-shaking in Vite config

**Files Affected:**
- `frontend/vite.config.ts`
- `frontend/package.json`
- Analytics page components

---

## Priority 5: Infrastructure

### 5.1 Add Health Check Endpoint

**Fix:**
```python
@app.get("/health")
async def health_check():
    try:
        DATAVERSE.query_rows("cr673_bahra_logins", top=1)
        return {"status": "healthy", "dataverse": "connected"}
    except Exception:
        return JSONResponse(status_code=503, content={"status": "unhealthy"})
```

**Files Affected:** `dashboard_main.py`

---

### 5.2 CORS from Environment Variables

**Fix:**
```python
# Before (hardcoded)
allow_origins=["http://localhost:8000", "http://localhost:3000", ...]

# After (configurable)
ALLOWED_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")
allow_origins=ALLOWED_ORIGINS
```

**Files Affected:** `dashboard_main.py`, `config/config.py`

---

### 5.3 Create Test Infrastructure

**Problem:** `tests/` directory exists but is completely empty. Zero tests.

**Fix:**
1. Add `pytest.ini` with basic config
2. Create `tests/conftest.py` with fixtures
3. Write initial tests for critical paths:
   - `tests/test_auth.py` — login, session, lockout
   - `tests/test_dashboard_service.py` — caching, data transformation
   - `tests/test_dataverse_client.py` — token refresh, error handling

**Files Affected:** `tests/` directory (new files)

---

### 5.4 Add Structured Logging

**Problem:** Uses `print()` statements for debugging. No structured logging, no log levels, no log files.

**Fix:**
```python
import logging
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s'
)
logger = logging.getLogger(__name__)

# Replace print() with logger calls
logger.info("Dashboard data refreshed", extra={"cache_ttl": 300})
logger.error("Dataverse query failed", extra={"table": table, "status": resp.status_code})
```

**Files Affected:** All service and route files

---

## Impact Summary Matrix

| # | Module | Optimization | Speed Impact | Files | Effort |
|---|---|---|---|---|---|
| 1.1 | Backend Routes | Remove duplicate auth endpoints | Eliminates route bugs | 3 | Small |
| 1.2 | Config | Fix session secret | Security | 2 | Small |
| 1.3 | Config | Move secrets to .env | Security | 3 | Small |
| 2.1 | DataverseClient | Async HTTP or def routes | **3-5x throughput** | Many | Large |
| 2.2 | Services | Cache metadata/primary keys | **Eliminates N API calls** | 5 | Small |
| 2.3 | Services | Batch role permission fetch | **N→1 API calls** | 2 | Small |
| 2.4 | Services | Batch delete operations | **N→1 API calls** | 2 | Medium |
| 2.5 | Services | Cache list operations | **Faster page loads** | 2 | Small |
| 2.6 | DataverseClient | Add retry logic | Reliability | 1 | Small |
| 3.1 | Routes | Split monolithic files | Maintainability | 6+ | Medium |
| 3.2 | Auth | Consolidate lockout systems | Consistency | 2 | Small |
| 3.3 | Dependencies | Remove 30 unused packages | Install speed | 1 | Small |
| 3.4 | Routes | Global error handling | Reliability | All | Medium |
| 3.5 | Routes | Pydantic models | Type safety | New + routes | Medium |
| 4.1 | Frontend | Type API responses | Dev experience | 10+ | Medium |
| 4.2 | Frontend | Extract duplicate components | Maintainability | 4 | Small |
| 4.3 | Frontend | Memoize table rows | **Fewer re-renders** | 1 | Small |
| 4.4 | Frontend | Consolidate dialog state | Clean architecture | 3 | Small |
| 4.5 | Frontend | Split large pages | Maintainability | 3→9 | Medium |
| 4.6 | Frontend | Error boundaries | UX reliability | 5+ | Small |
| 4.7 | Frontend | Bundle optimization | **Faster load** | 2 | Small |
| 5.1 | Infra | Health check endpoint | Monitoring | 1 | Small |
| 5.2 | Infra | CORS from env vars | Flexibility | 2 | Small |
| 5.3 | Infra | Test infrastructure | Quality | New files | Large |
| 5.4 | Infra | Structured logging | Debugging | All | Medium |

---

## Recommended Execution Order

### Phase 1: Quick Security Wins (Day 1)
1. Fix hardcoded session secret (1.2)
2. Move secrets to .env (1.3)
3. Remove duplicate auth endpoints (1.1)

### Phase 2: Quick Performance Wins (Day 1-2)
4. Cache metadata/primary keys (2.2) — eliminates redundant API calls
5. Batch role permission fetch (2.3) — N→1 API calls
6. Cache list operations (2.5) — faster page loads
7. Add retry logic (2.6) — reliability

### Phase 3: Major Performance (Day 2-3)
8. Fix sync blocking — change `async def` to `def` in routes (2.1 Option B) — **biggest throughput gain**
9. Batch delete operations (2.4)

### Phase 4: Code Organization (Day 3-4)
10. Split `dashboard.py` into 3 files (3.1)
11. Split `api.py` into 3 files (3.1)
12. Remove unused dependencies (3.3)
13. Consolidate lockout systems (3.2)

### Phase 5: Frontend (Day 4-5)
14. Extract duplicate components (4.2)
15. Memoize table rows (4.3)
16. Consolidate dialog state (4.4)
17. Add error boundaries (4.6)

### Phase 6: Polish (Day 5+)
18. Add Pydantic models (3.5)
19. Type API responses (4.1)
20. Split large pages (4.5)
21. Add health check (5.1)
22. Structured logging (5.4)
23. Test infrastructure (5.3)

---

## Verification Checklist

- [ ] Run `uvicorn dashboard_main:app` — all auth endpoints work, no duplicates
- [ ] Login/logout flow works end-to-end
- [ ] Dashboard loads with cached data on second request (check backend logs)
- [ ] Multiple concurrent browser tabs don't block each other
- [ ] Role listing loads in single API call (check Network tab)
- [ ] `npx tsc --noEmit` passes with no errors
- [ ] `npx vite-bundle-visualizer` shows no unexpected large chunks
- [ ] All existing functionality unchanged (regression check)
