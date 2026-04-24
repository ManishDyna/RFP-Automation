---
title: Low Level Design (LLD) — Bahra Electric RFP Automation
version: 1.0
last_updated: 2026-04-22
owner: Samir Tak (samir.tak@dynatechconsultancy.com)
audience: Developers maintaining the code
status: Draft
---

# Low Level Design (LLD)

Class/function-level design for the critical modules. This document complements [HLD](05-HLD-High-Level-Design.md) — if HLD is "what each module does", LLD is "what each function does and how the pieces fit".

> **Policy:** when code and this document diverge, code wins. Update this document as part of the PR.

Contents:
1. [DataverseClient](#1-dataverseclient)
2. [RBAC — dynamic_role_service](#2-rbac--dynamic_role_service)
3. [System Settings Service](#3-system-settings-service)
4. [Matching Engine](#4-matching-engine)
5. [Automation Orchestrator](#5-automation-orchestrator)
6. [Actionable-Card Verification](#6-actionable-card-verification)
7. [Power Automate Integration](#7-power-automate-integration)
8. [Frontend auth & permissions](#8-frontend-auth--permissions)
9. [Shared concerns](#9-shared-concerns)

---

## 1. DataverseClient

**Location:** [helpers/dataverse_helper.py](../../helpers/dataverse_helper.py)

Responsibilities:
- MSAL client-credentials token acquisition + cache
- OData v9.2 CRUD with display-name ↔ logical-name translation
- Metadata lookup (`EntityDefinitions`, `Attributes`) cached for 24 h
- Retry with exponential backoff on `429`, `503`, transient network errors

### 1.1 Class shape

```python
class DataverseClient:
    def __init__(self, tenant_id: str, client_id: str, client_secret: str, env_url: str):
        self._msal_app: ConfidentialClientApplication
        self._token_cache: tuple[str, float]          # (token, exp_epoch)
        self._metadata_cache: dict                    # logical_name → {entity_set, primary_id, attrs}

    def _get_token(self) -> str
    def _headers(self) -> dict

    def query_rows(self, table_api_name, filter_expr=None, select=None, top=100,
                   table_logical_name=None, use_display_names=True) -> dict
    def insert_row(self, table_api_name, data, table_logical_name=None,
                   use_display_names=True) -> bool
    def update_row(self, table_api_name, record_id, data, ...) -> bool
    def delete_row(self, table_api_name, record_id) -> bool
    def batch_delete(self, table_api_name, record_ids: list[str]) -> None

    def get_column_mapping(self, logical_name: str) -> dict[display, logical]
    def get_primary_id(self, logical_name: str) -> str
```

### 1.2 Retry policy

```python
RETRY = [1, 2, 4]          # seconds; three attempts
RETRY_STATUSES = {429, 500, 502, 503, 504}
```

- On `429`, honour `Retry-After` header if present (overrides the schedule).
- On fourth failure: raise `DataverseClientError` with HTTP status and response body preview.

### 1.3 Display ↔ logical translation

The project defaults to `use_display_names=True`, so callers pass `{"name": "...", "email": "..."}` and the client translates on the wire via a `column_mapping` fetched from the entity metadata. This decouples code from Dataverse's generated `cr673_*` logical names.

### 1.4 Pluralization quirk

```python
ENTITY_SET_SUFFIX_RULES = [
    (r"_status$",  "es"),   # _status → _statuses
    (r"s$",        "es"),   # roles → roleses  (Dataverse literally adds 'es')
    (r".*",        "s"),
]
```

Always prefer querying `EntityDefinitions(LogicalName='...').EntitySetName` at app startup and caching the result, rather than guessing.

---

## 2. RBAC — dynamic_role_service

**Location:** [services/dynamic_role_service.py](../../services/dynamic_role_service.py) + [services/permission_definitions.py](../../services/permission_definitions.py)

### 2.1 Module-level state

```python
_ROLE_PERMISSIONS_CACHE: Dict[str, {"permissions": list[str], "ts": float}]
_CACHE_LOCK: threading.Lock

_ROLES_LIST_CACHE: {"data": list[dict], "ts": float}
_ROLES_LIST_LOCK: threading.Lock
_ROLES_CACHE_TTL: int = 300    # seconds
```

Two caches. One maps role-name → permission list; the other caches the unfiltered `list_roles()` query to avoid hammering Dataverse on every admin page view.

### 2.2 Public API

```python
list_roles(top=100, filters=None, force_refresh=False) -> list[dict]
get_role(record_id) -> dict | None
get_role_by_name(name) -> dict | None
create_role(payload) -> bool
update_role(record_id, updates) -> bool
delete_role(record_id) -> dict                  # soft delete
toggle_role_status(record_id) -> dict
hard_delete_role(record_id) -> dict             # removes permission rows too

get_role_permissions(role_name) -> list[str]
get_all_permissions_count_by_role() -> dict[str, int]    # 1 query, avoids N+1
set_role_permissions(role_id, role_name, permission_keys) -> bool

get_user_permissions(user) -> list[str]
user_has_permission(user, permission_key) -> bool

seed_default_roles() -> {"created":[], "skipped":[], "errors":[]}
```

### 2.3 Cache semantics

- `get_role_permissions` is the hot path. Cache hit → no I/O.
- Any write (`update_role`, `set_role_permissions`, `delete_role`, `hard_delete_role`) calls `invalidate_role_cache(role_name)` which clears both caches for that role.
- The 300 s TTL is a deliberate trade-off: quick propagation after writes, low steady-state Dataverse load.

### 2.4 Session-carried permissions

`user_has_permission(user, ...)` first consults `user["permissions"]` (set at login). This means revokes take effect either:
- On session refresh (`POST /api/session/refresh`), or
- On next login

The 300 s cache does not help a live session — that's by design (cookies snapshot permissions).

### 2.5 Seeding invariant

`seed_default_roles()` is **idempotent**. For existing roles, permission lists are *resynced* to the code-defined set each time the seed runs. Custom roles added via UI are left alone.

### 2.6 Admin protection

All mutating functions check `name.lower() == "admin"` and reject. This is enforced in the service layer, not just the UI.

---

## 3. System Settings Service

**Location:** [services/system_settings_service.py](../../services/system_settings_service.py)

```python
_CACHE: Dict[str, Any]
_CACHE_EXPIRY: float
_CACHE_TTL: int = 300
_LOCK: threading.RLock

def get_setting(key: str, default=None) -> Any
def get_all_settings() -> dict[str, Any]
def set_setting(key: str, value, section: str = "") -> bool
def reload_cache() -> None
```

### 3.1 Shape

Settings are stored in `cr673_bahra_system_settings` with columns `key`, `value`, `section`, `is_sensitive`, `description`. The cache is flat (key → value), populated lazily on first call.

### 3.2 Type handling

All values are stored as strings. Callers converting to `int`/`bool` must do so explicitly (no automatic coercion). Example:

```python
threshold = int(get_setting("MATCH_THRESHOLD_PCT", 75))
debug = get_setting("DEBUG_MODE", "false").lower() == "true"
```

### 3.3 Sensitive settings

`is_sensitive = true` → list endpoint returns `"***"`. The `/{key}/reveal` endpoint returns the clear value and writes an `AUDIT: SYSTEM_SETTING_REVEALED` row.

### 3.4 Safety

`set_setting` never writes an empty string where the previous value was non-empty unless the caller passes `allow_empty=True` (prevents accidental blanking of, e.g., `CLIENT_SECRET`).

---

## 4. Matching Engine

**Location:** `automation_logic.py` + helpers.

### 4.1 Input

```python
class BOQLine(TypedDict):
    code: str            # vendor-provided code (may be blank)
    description: str     # free text
    qty: float
    uom: str
    extra: dict          # anything else (kept verbatim)
```

Reference data (read from Dataverse, cached for the run):

- `material_master` rows: `{code, description, keywords, is_active}`
- `keywords` rows: `{term, expands_to, weight}` for tokenisation

### 4.2 Algorithm

```python
def match_line(line, master_rows, keywords, threshold=75):
    # 1. Direct code match
    if line.code:
        hit = next((m for m in master_rows if m.code.lower() == line.code.lower()), None)
        if hit:
            return Match(code=hit.code, confidence=100, reason="exact-code")

    # 2. Tokenize + expand
    tokens = tokenize(line.description)
    expanded = expand(tokens, keywords)

    # 3. Score each candidate
    scored = []
    for m in master_rows:
        score = fuzzy_score(expanded, tokenize(m.description))
        if score >= threshold:
            scored.append((score, m))

    # 4. Pick best
    scored.sort(reverse=True, key=lambda x: x[0])
    if scored:
        score, m = scored[0]
        return Match(code=m.code, confidence=score, reason="fuzzy-description")

    return Match(code=None, confidence=0, reason="no-match")
```

### 4.3 `fuzzy_score`

```python
def fuzzy_score(tokens_a: set[str], tokens_b: set[str]) -> float:
    # Jaccard similarity, weighted toward longer tokens
    if not tokens_a or not tokens_b:
        return 0.0
    inter = tokens_a & tokens_b
    union = tokens_a | tokens_b
    weight = sum(len(t) for t in inter) / max(1, sum(len(t) for t in union))
    base = len(inter) / len(union)
    return (base * 0.5 + weight * 0.5) * 100
```

Tunable alternatives live behind the `MATCH_ALGORITHM` setting — `jaccard` (default), `rapidfuzz_ratio`, or `rapidfuzz_token_set_ratio`.

### 4.4 Output contract

Matched data persists on `rfps_v2.Matched_Data` as JSON:

```json
{
  "line_items": [
    {
      "index": 0,
      "source": {"code": "", "description": "XLPE 2C 16AWG", "qty": 500, "uom": "M"},
      "match": {"code": "CAB-XLPE-2C-16", "confidence": 91, "reason": "fuzzy-description"}
    }
  ],
  "summary": {"matched": 12, "unmatched": 3, "avg_confidence": 86.4},
  "run_id": "uuid",
  "generated_at": "2026-04-22T10:05:00Z"
}
```

### 4.5 Deterministic behaviour

The engine is **pure** except for reading reference data. Same inputs ⇒ same outputs. This is what makes match results auditable.

---

## 5. Automation Orchestrator

**Location:** `automation_logic.py`, `automation_main.py`.

### 5.1 Pipelines

Each pipeline is a sequence of steps with a shared `RunContext`:

```python
@dataclass
class RunContext:
    run_id: str
    source: str                 # "email" | "sharepoint" | "ariba" | "manual"
    started_at: datetime
    rfps_created: int = 0
    rfps_updated: int = 0
    errors: list[dict] = field(default_factory=list)

def run_email_scan()      -> RunContext
def run_sharepoint_scan() -> RunContext
def run_ariba_scan()      -> RunContext
def run_match_and_notify()-> RunContext
def run_reminders()       -> RunContext
```

Every entry point:
1. Generates a `run_id` (UUID)
2. Writes a `cr673_bahra_automation_log1` row with `status=Running`
3. Executes the pipeline, capturing per-step errors without aborting the whole run (unless the error is unrecoverable)
4. Updates the log row with `status=Completed` or `Failed` + counts + error summary

### 5.2 Playwright (Ariba)

```python
async def scrape_ariba(ctx: RunContext):
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=ARIBA_SESSION_STATE)
        page = await context.new_page()
        try:
            await login_if_needed(page)
            rfps = await list_open_rfps(page)
            for meta in rfps:
                try:
                    await download_rfp(page, meta, ctx)
                except Exception as e:
                    ctx.errors.append(dump_failure(page, meta, e))
        finally:
            await context.storage_state(path=ARIBA_SESSION_STATE)
            await browser.close()
```

- `ARIBA_SESSION_STATE` file lets us skip re-login for ~24 h.
- `dump_failure` writes screenshot + HTML to `LOGS/run_<id>_rfp_error_<meta>/` for diagnosis.

### 5.3 Concurrency

The automation service is a **single worker**. Inside the Playwright pipeline, per-RFP work is sequential. BOQ parsing is CPU-bound and not parallelised (RFP volume is low — < 50/day typical).

### 5.4 Failure isolation

- One bad BOQ does not kill a run
- One bad email does not kill the email scan
- A Playwright crash kills only that Ariba run; the orchestrator reschedules via Power Automate's next tick

---

## 6. Actionable-Card Verification

**Location:** [routes/actionable_cards.py](../../routes/actionable_cards.py)

### 6.1 Token verification

```python
def verify_substrate_jwt(token: str) -> dict:
    # 1. Parse unverified header → key id
    # 2. Fetch Microsoft JWKs (cached 12 h)
    # 3. jwt.decode(token, key=jwk, algorithms=["RS256"],
    #               audience=SITE_URL,
    #               issuer="https://substrate.office.com/sts/")
    # 4. Assert payload["appid"] == EXPECTED_ORIGINATOR_ID
    # 5. Return payload
```

Any failure → `HTTPException(401)` + audit row `ACTIONABLE_REJECTED`.

### 6.2 Response storage

`response_data` on `cr673_bahra_rfp_team` is a JSON object keyed by dynamic-column name:

```json
{
  "unit_price": 123.45,
  "lead_time_days": 14,
  "remarks": "Pending stock confirmation",
  "submitted_at": "2026-04-22T10:05:00Z",
  "submitted_via": "adaptive_card",
  "originator": "samir.tak@..."
}
```

### 6.3 Decline path

A decline sets `response_data.declined = true` and appends a reason. No SAP push.

---

## 7. Power Automate Integration

**Location:** [helpers/power_automate_helper.py](../../helpers/power_automate_helper.py)

### 7.1 Outbound: schedule push

```python
def sync_schedule_to_power_automate(schedule: dict) -> bool:
    url = get_setting("POWER_AUTOMATE_SCHEDULE_URL")
    sig = hmac_sha256(SHARED_KEY, json.dumps(schedule, sort_keys=True))
    resp = requests.post(url, json=schedule, headers={"X-Sig": sig}, timeout=10)
    return resp.status_code == 200
```

Called from `POST /dashboard/schedule-automation`. Failure surfaces to the UI (not silently swallowed).

### 7.2 Inbound: webhook callbacks

Power Automate calls internal endpoints (e.g., `GET /sync_portal_data`) on schedule. These endpoints check a shared secret in a custom header to reject unauthenticated callers.

### 7.3 Retry

If `sync_schedule_to_power_automate` fails, we store `last_sync_error` on the system-settings row and surface it in the UI. The user retries manually.

---

## 8. Frontend auth & permissions

**Location:** [frontend/src/hooks/use-auth.ts](../../frontend/src/hooks/use-auth.ts), `frontend/src/store/authStore.ts`.

### 8.1 Zustand auth store

```ts
interface AuthState {
  user: User | null;
  permissions: string[];
  isAuthenticated: boolean;
  login: (email, password) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}
```

Store is persisted to `sessionStorage` so reload doesn't log the user out (but closing the tab does).

### 8.2 `useHasPermission`

```ts
export function useHasPermission(perm: string) {
  const permissions = useAuthStore(s => s.permissions);
  return permissions.includes(perm);
}
```

Used to hide/disable UI elements. Paired server-side with `user_has_permission` — the frontend check is cosmetic; the server is the security boundary.

### 8.3 Permission-guarded routes

```tsx
<Route element={<PermissionGuard require="user_management.view"><UsersPage /></PermissionGuard>} />
```

`PermissionGuard` either renders the children or redirects to `/` with a toast.

### 8.4 Sidebar filtering

`buildSidebar(user.permissions)` filters entries against the `SIDEBAR_PERMISSIONS` map (mirrors `services/permission_definitions.py PERMISSION_CATEGORIES.sidebar_menus`). Any divergence here manifests as a visible-but-broken menu item — fix by re-syncing.

---

## 9. Shared concerns

### 9.1 Error envelope helper

```python
def http_error(status: int, detail: str, code: str = None) -> HTTPException:
    eid = f"ERR-{uuid4().hex[:8]}"
    logger.error(f"[{eid}] {code or status}: {detail}")
    return HTTPException(status_code=status, detail={
        "detail": detail, "error_id": eid, "code": code,
    })
```

All routes use this for deliberate errors (validation, conflict, forbidden). Unhandled exceptions are caught by the global handler.

### 9.2 Logging

- Format: `%(asctime)s %(levelname)s %(name)s %(message)s`
- Level: `INFO` in production, `DEBUG` for automation debug-builds
- Never log: passwords, bearer tokens, full Dataverse responses (truncate to 500 chars)

### 9.3 Time handling

- Store UTC ISO-8601 (`2026-04-22T10:05:00Z`) in all `*_date` columns
- UI converts to local time with `date-fns-tz`
- Never subtract naïve `datetime` values without timezone

### 9.4 ID generation

- Primary keys generated by Dataverse (GUID, server-side)
- Run IDs: `uuid4().hex` (32 chars)
- Error IDs: `ERR-<8-char-uuid>` (short, human-friendly)

### 9.5 Feature flags

We don't use a feature-flag system. Toggles live in `system_settings` and are read once per request. For slow-rollout features, prefer environment-scoped settings over per-user flags.

---

## 10. Test touchpoints

| Area | Test type | Location |
|---|---|---|
| Matching engine | Unit (pure functions) | `tests/test_matching.py` |
| RBAC guards | Unit with mocked Dataverse | `tests/test_rbac.py` |
| DataverseClient | Integration (live dev tenant) | `tests/integration/test_dv.py` |
| Route happy paths | Integration via TestClient | `tests/routes/*.py` |
| Frontend hooks | Vitest | `frontend/src/**/*.test.tsx` |

Target coverage: ≥ 70 % on `services/` and `helpers/`; routes are smoke-tested, not exhaustively covered.
