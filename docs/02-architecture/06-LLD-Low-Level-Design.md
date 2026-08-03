---
title: Low Level Design (LLD) — Bahra Electric RFP Automation
version: 1.1
last_updated: 2026-07-17
owner: Manish Soni (Manish.soni@dynatechconsultancy.com)
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
7. [Scheduling & Power Automate Integration](#7-scheduling--power-automate-integration)
8. [Frontend auth & permissions](#8-frontend-auth--permissions)
9. [Shared concerns](#9-shared-concerns)

---

## 1. DataverseClient

**Location:** [helpers/dataverse_helper.py](../../backend/helpers/dataverse_helper.py)

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

**There is no rule table, and you must not write one.** Dataverse's EntitySetName pluralization is genuinely unpredictable — it appends `es`, or `s`, or changes the stem, depending on the name ending:

| Logical name | EntitySetName |
|---|---|
| `cr673_bahra_roles` | `cr673_bahra_roleses` (+`es`) |
| `cr673_bahra_rfp_reminder_for_info` | `cr673_bahra_rfp_reminder_for_infos` (+`s`) |
| `cr673_bahra_user_status` | `cr673_bahra_user_statuses` (stem change) |

Confirm the real value with `EntityDefinitions(LogicalName='...')?$select=EntitySetName` and pin it in `config/config.py` as the `_API` half of a `_LOGICAL` + `_API` pair. Each `setup_*_table.py` script prints the resolved name after `PublishXml` for exactly this reason. **Never derive it.**

### 1.5 The display-name PK trap

`use_display_names=True` (the project default) does more than rename ordinary columns — it **also rewrites the primary-key column** from `<table>id` to its display label (e.g. `cr673_bahra_material_masterid` → `Bahra Material Master`). The consequence is silent and expensive: `row.get(pk_logical)` returns `None`, so every lookup keyed on the PK misses without raising. Resolve the PK through the logical→display reverse map instead.

Two related quirks:
- **Mixed publisher prefixes inside one table** are normal — e.g. `cr673_bahra_material_master` contains `cr6db_bahra_item_code`. The display-name map still resolves these; an unexpected prefix is not a reason to bypass `use_display_names=True`.
- **`$filter` with short display names**: tables created with short display labels need filter expressions written in those short names. The helper's substring replacement will otherwise turn `cr673_rfp_id` into `cr673_cr673_rfp_id` and break the query silently.

---

## 2. RBAC — dynamic_role_service

**Location:** [services/dynamic_role_service.py](../../backend/services/dynamic_role_service.py) + [services/permission_definitions.py](../../backend/services/permission_definitions.py)

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
- **The two TTLs are not driven by the same knob.** Per-role permissions read their TTL from `get_setting('RBAC_CACHE_TTL_SECONDS', 300)`; the roles-list cache uses a **hardcoded** `_ROLES_CACHE_TTL = 300`. Changing the setting moves one and not the other.
- `set_role_permissions` **silently drops** any key not present in `PERMISSIONS` — a typo'd permission key is not an error, it just never applies.
- **Role names are load-bearing.** `role_permissions` rows store `role_name` denormalized and are queried by it, so **renaming a role orphans its permission rows**.

### 2.4 Session-carried permissions

`require_permission(key)` in [middleware/auth.py](../../backend/middleware/auth.py) checks `key in user["permissions"]`, read **straight from the session**, which is populated once at login (`routes/api.py`).

**Therefore: permission changes require a re-login.** Neither a cache TTL nor a role edit propagates into a live session — the cookie holds a snapshot. The 300 s cache is about Dataverse load, not about revocation latency.

Sessions are `SessionMiddleware` cookies named `rfp_session`, scoped `path="/rfp"`, `max_age = SESSION_TIMEOUT_SECONDS = 7200`. **That 2-hour absolute cap is the only timeout that exists** — `IDLE_TIMEOUT_SECONDS`, `SESSION_WARNING_SECONDS` and `SESSION_REFRESH_INTERVAL` are defined in `config.py` but **read by no code**; `last_activity` is written and echoed but never compared to anything.

### 2.5 Seeding invariant

`seed_default_roles()` is **idempotent**. For existing roles, permission lists are *resynced* to the code-defined set each time the seed runs. Custom roles added via UI are left alone.

`DEFAULT_ROLES` defines two `is_system: True` roles:
- **Admin** — `list(PERMISSIONS.keys())`, computed dynamically, so it always holds all **42**.
- **RFP Bidder** — exactly **10**: `rfp.view`, `rfp.download`, `rfp.submit`, `rfp.decline`, `rfp.open.view`, `rfp.open.delegate`, `rfp.sharepoint.view`, `dashboard.view`, `logs.view`, `material_insights.view`. Notably **absent**: `rfp.open.remind`, `analytics.view`, and every admin / master-data key.

### 2.6 Admin protection

Mutating functions check `name.lower() == "admin"` and reject, in the service layer rather than only the UI.

`require_admin` uses the **same hardcoded name check** and **bypasses the permission system entirely** — it does not consult `PERMISSIONS` at all. Renaming the Admin role therefore breaks `require_admin`, `useIsAdmin()` on the frontend, and the Admin delete/toggle guards simultaneously.

---

## 3. System Settings Service

**Location:** [services/system_settings_service.py](../../backend/services/system_settings_service.py)

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
ttl = int(get_setting("RBAC_CACHE_TTL_SECONDS", 300))
debug = get_setting("DEBUG_MODE", "false").lower() == "true"
```

Note that some keys are deliberately **not** served from here. `ACTIONABLE_CARD_CALLBACK_URL` is listed in `REMOVED_KEYS` in `Support-Files/seed_system_settings.py`, so `config.py` remains its single source of truth — which is also why changing it requires a service restart rather than a settings save.

### 3.3 Sensitive settings

`is_sensitive = true` → list endpoint returns `"***"`. The `/{key}/reveal` endpoint returns the clear value and writes an `AUDIT: SYSTEM_SETTING_REVEALED` row.

### 3.4 Safety

`set_setting` never writes an empty string where the previous value was non-empty unless the caller passes `allow_empty=True` (prevents accidental blanking of, e.g., `CLIENT_SECRET`).

---

## 4. Matching Engine

**Location:** [rfp/download_rfp.py](../../backend/rfp/download_rfp.py) — `process_folder(...)`, with keyword extraction (`extract_keywords_from_text`) in [helpers/core_helper.py](../../backend/helpers/core_helper.py).

> **There is no fuzzy matching, and there never was.** No similarity library is present anywhere in `backend/` — `rapidfuzz`, `fuzzywuzzy`, `python-Levenshtein`, `difflib`/`SequenceMatcher` all return zero hits. The only tools in play are `re` and pandas `str.contains`. **No similarity score, no confidence value, no threshold, no weights, no ranking.** `MatchMethod` is a categorical label — `"exact"`, `"keyword"` or `None` — not a number. Earlier revisions of this document described a `fuzzy_score()` function returning a `confidence` percentage; **no such function exists** and that section has been removed.

### 4.1 Input

Each BOQ row carries a `Name` and `Description` (plus quantity and other columns kept verbatim). The SAP material code is not a separate trusted field — it is **extracted from text**:

```python
re.findall(r'\d{9}', name_text)     # literal 9-digit code, from the Name column
# fallback order on the same row: Name → "Material Number" → "Material Code"
```

Reference data, via `get_all_materials_for_matching()` / `get_all_keywords_for_matching()` in [services/master_data_service.py](../../backend/services/master_data_service.py) — Dataverse-first with a SharePoint CSV fallback (`RFP-logs/master-files/material.csv`, `unique_keywords.csv`), **5-minute TTL cache**.

### 4.2 Algorithm — two tiers

**Branch A — the row has a 9-digit code:**

1. **Exact** — pure string equality against the master code column:
   ```python
   master[master[col].astype(str) == mat]     # → MatchMethod = "exact"
   ```
2. **Keyword** — only if exact found nothing: `_try_keyword_match(name, description)`.
3. Otherwise `is_matched = False`, `MatchMethod = None`.

**Branch B — no 9-digit code:** the keyword path only.

**The keyword path** splits `Name` + `Description` into keywords, then for every (master keyword × row keyword) pair tests **bidirectional substring containment**:

```python
if csv_keyword in mat_keyword or mat_keyword in csv_keyword:
    ...     # → MatchMethod = "keyword"
```

`_find_master_rows_by_keyword` then re-searches the master with `str.contains(case=False, regex=False)` and takes **`.head(1)`**.

Keyword extraction (`extract_keywords_from_text`) splits on **comma and semicolon**, uppercases, and strips. That is the whole of the "tokenisation" — there is no stemming, no stop-word removal, and no expansion step.

### 4.3 What this means in practice

Characterise the engine accurately: a **deterministic two-tier exact/substring classifier**. Its limitations are structural, not tuning problems:

- **Substring containment is aggressive and unranked.** A short master keyword like `CU` matches *any* row whose text contains that substring anywhere — inside an unrelated word included.
- **`.head(1)` picks arbitrarily.** Where several master rows contain the keyword, the engine takes the first row pandas happens to return. There is **no best-match selection and no tie-break**.
- **Nothing is tunable in code.** There is no threshold to raise and no weight to shift. Match quality moves only by editing **data** — Material Master and Keyword Master rows in Dataverse (or the CSV fallbacks).
- **A wrong keyword match is indistinguishable from a right one** in the output, because no score is recorded.

### 4.4 Output contract

Matched data persists on `rfps_v2.Matched_Data`. Each line carries `is_matched` and `MatchMethod` (`"exact"` / `"keyword"` / `None`) — **not** a confidence figure. Do not add a `confidence` field to consumers; there is no value to populate it with.

### 4.5 Deterministic behaviour

The engine is **pure** except for reading reference data: same inputs ⇒ same outputs. Note the caveat that `.head(1)` makes the *choice among equally-eligible candidates* dependent on master-row ordering — stable for a given master snapshot, but not meaningfully "the best match".

---

## 5. Automation Orchestrator

**Location:** [automation_logic.py](../../backend/automation_logic.py), driven by [routes/automation.py](../../backend/routes/automation.py). (`automation_main.py` is an undeployed standalone variant — ignore it.)

### 5.1 Entry points

There are **eight** top-level orchestrators — not a generic pipeline abstraction:

| Function | Notes |
|---|---|
| `run_automation_download(company=None)` | |
| `run_automation_download_open_rfps()` | **the function the scheduler actually calls** |
| `run_automation_submit(rfp_id, company=None, allowed_tds_filenames=None)` | |
| `run_automation_decline(rfp_id, company=None)` | |
| `run_automation_reminder()` | **no Playwright** — Dataverse read + email only |
| `run_automation_sync_portal(rfp_ids=None)` | |
| `run_automation_download_all_rfps(selected_company="")` | |
| `run_sync_sharepoint_dataverse(company=None)` | |

Supporting modules under `backend/rfp/`: `download_rfp.py` (owns the matching engine), `submit_rfp.py` (Ariba wizard driver), `decline_rfp.py`, `rfp_reminder.py` (no browser; 3-day/1-day cadence with `Reminder_3Day_Sent` / `Reminder_1Day_Sent` idempotency flags).

Runs log to `cr673_bahra_automation_log1`; failures produce a bundle under `backend/LOGS/` (screenshot + context), uploaded to SharePoint by `failure_logger`, plus a failure email.

### 5.2 Playwright (Ariba)

**Chromium runs HEADED.** `common_flow` hardcodes `headless_mode = False` — this is the deployed behaviour, not a debug toggle:

```python
headless_mode = False        # automation_logic.py — hardcoded
# each run gets an isolated profile so runs can overlap:
user_data_dir = temp / f"pw-profile-{label}-{uuid4().hex[:8]}"
```

Consequences worth internalising:
- The service host must be able to render a browser. "No visible browser window" is **not** a valid health signal.
- **Playwright installs browsers per-user.** If the service identity changes (e.g. to LocalSystem), it will look under that profile's `ms-playwright` directory and fail with *"Executable doesn't exist at …\config\systemprofile\…"* — while manual runs under a developer login keep working. This failure mode has bitten this system before; it is the first thing to check when scheduled runs process 0 companies but manual runs succeed.
- Buyer-organisation switching is a DOM interaction (`select_company_from_portal`), not a separate session: click Ariba's "more…" link, wait for the org picker, click the company anchor, re-check login.

### 5.3 Concurrency

The backend is a **single Uvicorn worker** — mandatory, because `_RUN_STATE` lives in memory.

```python
_RUN_STATE  # keys: download, submit, decline, sync, sync_sp_dv,
            #       sync_all, last, submitting_rfps (a set)
_STATE_LOCK # threading lock
```

- `_run_async_in_thread(coro, ...)` runs each automation on a **new daemon thread with its own `asyncio.ProactorEventLoop`**, because uvicorn's `SelectorEventLoop` **cannot spawn subprocesses on Windows** and Playwright must launch Chromium. The route returns **202** immediately. Calling `await some_playwright_func()` directly from a handler raises `NotImplementedError`.
- `_try_start_operation(key)` check-and-sets **inside** the lock (no TOCTOU); a duplicate returns **409**. `_finish_operation(key)` clears in a `finally`.
- **Different keys do not exclude each other** — `download` and `sync` can run concurrently against the same Ariba account. They are separated **by schedule offset only** (§7).
- `sync_all` is dead: read, never set, permanently `False`.
- `/rfp-reminder` has **no guard and no thread** — it awaits directly and returns 200 after blocking.
- Per-RFP work inside a run is sequential; BOQ parsing is not parallelised (volume is low).

### 5.4 Failure isolation

- One bad BOQ does not kill a run
- A Playwright crash kills only that run — but note it shares a **process** with the dashboard (there is no separate automation service), so isolation comes from exception handling, not from an OS boundary
- The next scheduled trigger retries; nothing is re-queued in-process

---

## 6. Actionable-Card Verification

**Location:** [routes/actionable_cards.py](../../backend/routes/actionable_cards.py)

### 6.1 Token verification

Legacy Actionable-Message (EAT) auth was retired; the callback now validates **Microsoft Entra** tokens. `_verify_actionable_message_token`:

```python
# 1. Discover JWKS from {tenant}/v2.0/.well-known/openid-configuration
#    (jwt.PyJWKClient, cached globally)
# 2. jwt.decode(token, key, algorithms=["RS256"],
#               audience=ACTIONABLE_CARD_APP_ID_URI,
#               options={"verify_iss": False})     # ← deliberate, see below
# 3. Check iss MANUALLY against BOTH accepted issuers
# 4. Assert azp (or appid on v1.0) == ACTIONABLE_CARD_ACTIONS_APP_ID
# 5. exp verified by decode; return claims
```

The four things that are easy to get wrong here:

- **`aud`** must equal `ACTIONABLE_CARD_APP_ID_URI`, and the check **fails closed** if that is unconfigured. Both the AppIdUri and the bare client id are accepted.
- **`iss` is verified manually** — `verify_iss: False` is passed to `jwt.decode` **on purpose**, because **both v1.0 and v2.0 issuers are legitimate**: `login.microsoftonline.com/{tenant}/v2.0` **and** `sts.windows.net/{tenant}/`. Microsoft's Actions service sends either depending on the resource app's token-version setting. Do not "fix" this by re-enabling issuer verification against a single value.
- **`azp`** (falling back to `appid` for v1.0) must equal `ACTIONABLE_CARD_ACTIONS_APP_ID` — **Microsoft's fixed Actions app id `48af08dc-…`, not our application's id**. This is the check that stops any other caller who holds a token for our audience.
- **Identity** comes from `preferred_username` / `upn` / `unique_name` / `email`. **Never `sub`** — it is an opaque pairwise id, not an email.

On failure the token is re-decoded **unverified** purely to log actual vs expected `aud`/`iss`/`azp`, then `HTTPException(401)`. Note that card actions are **not** written to the audit log — no RFP operation is (see [SAD §7.3](04-SAD-Software-Architecture-Document.md)).

### 6.1.1 Endpoints

| Endpoint | Notes |
|---|---|
| `POST /response` | main submit path |
| `POST /response/refresh` | Outlook `autoInvokeAction` on open — **must respond within ~2 s** or Outlook times out |
| `POST /decline` | |
| `GET /responses/{rfp_id}` | **no token verification, no session — currently unauthenticated** |

First response wins per team row (`_first_response_per_row`).

### 6.2 Response storage

`response_data` on `cr673_bahra_rfp_team` is a JSON object keyed by dynamic-column name:

```json
{
  "unit_price": 123.45,
  "lead_time_days": 14,
  "remarks": "Pending stock confirmation",
  "submitted_at": "2026-04-22T10:05:00Z",
  "submitted_via": "adaptive_card"
}
```

> **Do not confuse the originator with the submitter.** `ACTIONABLE_CARD_ORIGINATOR_ID` is a **GUID** (`f3c4b0f4-…`) issued by the Actionable Messages provider registration — it identifies the *sending application*, never a person. An earlier revision of this document showed `"originator": "samir.tak@…"`, which is wrong on both counts: an originator is not an email address, and the submitting user's identity comes from the **token claims** (`preferred_username` / `upn` / `unique_name` / `email`), not from the card payload.

### 6.3 Decline path

A decline sets `response_data.declined = true` and appends a reason. No SAP push.

---

## 7. Scheduling & Power Automate Integration

**Location:** [helpers/power_automate_helper.py](../../backend/helpers/power_automate_helper.py), [routes/dashboard.py](../../backend/routes/dashboard.py), `scripts/`

### 7.1 Outbound: schedule push

There is **no HTTP call to Power Automate and no shared-secret signature.** `api.flow.microsoft.com` is unsupported for this, so the helper patches the flow's **Recurrence trigger by writing the `workflow` table in the same Dataverse environment**, reusing the existing `DataverseClient` — no separate auth.

Flow: `GET /dashboard/schedule-automation/latest` and `POST /dashboard/schedule-automation` (both `require_permission("schedule_automation.manage")`) persist to `cr673_bahra_automation_scheduleses`, then call `sync_schedule_to_power_automate`, which is **non-fatal on failure** — the save succeeds regardless.

> **The Schedule Automation page is a silent no-op after the scheduling migration.** `POWER_AUTOMATE_FLOW_NAME = "Bahra-E-binding-cron-job"` is the exact flow `Register-RfpSchedules.ps1` instructs you to turn off. The Dataverse row saves, the recurrence updates, a success toast appears — and the real download cadence (now Task Scheduler) **does not change**. If that flow is ever re-enabled, downloads fire from **both** sources. Do not treat this page as the control surface for scheduling.

### 7.2 Inbound: how scheduled runs actually arrive

Production schedules `download` and `sync` from **Windows Task Scheduler on the VM**, via `scripts/Invoke-RfpAutomation.ps1` — a trigger-and-poll runner so "Last Run Result" reflects completion, not just acceptance:

| `-Job` | Endpoint | Status flag | Async |
|---|---|---|---|
| `download` | `/api/download-rfps-automation` | `download_running` | yes |
| `sync` | `/api/sync_portal_data` | `sync_running` | yes |
| `sync-sp-dv` | `/api/sync-sharepoint-dataverse` | `sync_sp_dv_running` | yes |
| `reminder` | `/api/rfp-reminder` | none | no |

Params: `-BaseUrl http://127.0.0.1:8000`, `-StartupWaitSeconds 120`, `-TimeoutMinutes 60`, `-PollSeconds 15`, `-SkipIfRunning`, `-LogDir C:\Bahra-Automation-RFP-System\backend\LOGS\scheduler`.

Exit codes: `0` finished · `1` API unreachable · `2` already running (409) · `3` timeout (**the run is not killed**; it continues server-side).

> **Exit 0 means the job FINISHED, not that it SUCCEEDED.** The run flag clears in a `finally`, so a crashed run also reports 0. Do not build alerting on the exit code alone — failures surface through `backend\LOGS\` bundles and the `EMAIL_TO_AUTOMATION_FAILURE` email.

`scripts/Register-RfpSchedules.ps1` (run **elevated** on 192.168.111.192; idempotent; `-WhatIf` supported) registers under `\Bahra-RFP\`. **Times are server-local (Riyadh):**

| Task | Job | Daily triggers | Timeout |
|---|---|---|---|
| `RFP-Download-OpenRFPs` | `download` | 00:00, 06:00, 12:00, 18:00 | 90 min |
| `RFP-Sync-Portal` | `sync` | 03:00, 09:00, 15:00, 21:00 | 60 min |

Tasks run as SYSTEM (`-UseSystem`, RunLevel Highest). That is safe **because the task only makes a localhost HTTP call and writes a log — it does not run Playwright; the `rfp-api` service does, under its own identity** (§5.2). The 3-hour offset between sync and download is deliberate: the `_RUN_STATE` flags use different keys and would **not** stop the two colliding.

Note the timezone correction embedded in this migration: the retired Power Automate flows ran on **India Standard Time** (UTC+5:30), so a "12:00" recurrence fired at **09:30 Riyadh** (UTC+3).

### 7.3 Known gap

**Reminder emails are not sending.** `Bahra-RFP-Reminder-Emails-Cron-job` still targets the dead dev tunnel; no scheduled task replaces it, and App Proxy publishes only `/api/actionable-card/`, not `/api/rfp-reminder`. `Invoke-RfpAutomation.ps1 -Job reminder` exists for manual runs but nothing invokes it on a schedule.

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

The Zustand store uses `persist` and writes to **`localStorage`** under the key **`auth-storage`** — not `sessionStorage`, so it survives closing the tab.

> **This means the user's own permission list is client-editable.** Anyone can open devtools, edit `auth-storage`, and unlock UI that `useHasPermission` gates. That is acceptable **only** because the frontend check is cosmetic: the backend's `require_permission` is the real security boundary, and it reads permissions from the signed server-side session, never from the client. Never move an authorization decision into the frontend.

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

`PermissionGuard` renders the children or an `<AccessDenied />` fallback. All 14 pages are lazy-loaded and guarded, with two deliberate exceptions: `/dashboard/profile` has **no guard** (any authenticated user) and `/login` is public. `/` redirects to `/dashboard`.

**Array semantics are ANY-of, not ALL-of** — the guard uses `.some()`. `/admin/master-data` relies on this: `['material_master.view', 'keyword_master.view', 'rfp_team.view', 'column_config.view']` grants access if the user holds **any one** of the four.

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

- **Dataverse datetimes are Saudi local time, despite the `Z` suffix.** A value like `2026-05-21T03:13:00Z` is *already* wall-clock Riyadh time — the `Z` is a lie of the serializer, not an assertion of UTC.
- **Therefore: never pass one through `new Date()`** in the frontend — that reinterprets it as UTC and shifts it by the browser's offset. Parse the wall-clock components as-is with `formatDateMDY` in [frontend/src/lib/utils.ts](../../frontend/src/lib/utils.ts).
- Dates are written **MDY**: `2/23/2026 8:10 PM`, via Windows strftime `%#m/%#d/%Y %#I:%M %p` (the `#` suppresses leading zeros; this is Windows-specific and will not port to Linux unchanged).
- Never subtract naïve `datetime` values without establishing which convention each side is in.

### 9.4 ID generation

- Primary keys generated by Dataverse (GUID, server-side)
- Run IDs: `uuid4().hex` (32 chars)
- Error IDs: `ERR-<8-char-uuid>` (short, human-friendly)

### 9.5 Feature flags

We don't use a feature-flag system. Toggles live in `system_settings` and are read once per request. For slow-rollout features, prefer environment-scoped settings over per-user flags.

---

## 10. Test touchpoints

> **There is no automated test suite of any kind** — verified 2026-07-17. There is no `tests/` directory, no `pytest` suite, and no load-test tooling in the repository. The only test-named file is [backend/Support-Files/test_adaptive_card.py](../../backend/Support-Files/test_adaptive_card.py), a one-off manual script that belongs to no suite. Earlier revisions of this document listed `tests/test_matching.py`, `tests/test_rbac.py` and similar; **none of those files exist**, and no coverage target is enforced anywhere.

Verification today is entirely manual:

| Area | What exists | How it is exercised |
|---|---|---|
| Performance / load | *(none)* | No load-test tooling is present in the repository |
| Backend health | `GET /health` | Probes Dataverse with a live table read; 200 healthy / 503 unhealthy |
| Automation runs | `backend/LOGS/` bundles + `automation_log1` rows | Screenshots and failure emails on error |
| Everything else | — | Manual |

The matching engine (§4) and the RBAC helpers (§2) are the highest-value candidates for a first unit-test suite: both are pure functions over data that is cheap to fabricate.
