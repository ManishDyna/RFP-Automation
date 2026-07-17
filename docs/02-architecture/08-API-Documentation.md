---
title: API Documentation — Bahra Electric RFP Automation
version: 1.1
last_updated: 2026-07-17
owner: Manish Soni (Manish.soni@dynatechconsultancy.com)
audience: Backend developers, Frontend developers, Integration partners
status: Draft
---

# API Documentation

REST API reference for the RFP Automation platform. All routes live on the **Dashboard service** ([dashboard_main.py](../../backend/dashboard_main.py), port 8000) unless explicitly noted.

FastAPI generates interactive OpenAPI docs at:
- **Swagger UI:** `/rfp/docs`
- **ReDoc:** `/rfp/redoc`
- **Raw OpenAPI JSON:** `/rfp/openapi.json`

Use this document as the narrative companion — authoritative schema comes from the FastAPI generator.

Related: [SAD](04-SAD-Software-Architecture-Document.md) · [RBAC Matrix](../03-operations/11-RBAC-Permissions-Matrix.md) · [Data Dictionary](07-Data-Dictionary-and-ER-Diagram.md)

---

## 1. Conventions

### 1.1 The `/rfp` root path — read this first

The app is created as `FastAPI(title="Bahra Dashboard API", root_path="/rfp")` ([dashboard_main.py:51](../../backend/dashboard_main.py)) because it shares a domain with the COA application.

**Every path in this document is the INTERNAL path that FastAPI matches.** The reverse proxy (IIS in production, the Vite dev proxy locally) strips the `/rfp` prefix before forwarding. So:

| Layer | Path |
|---|---|
| What you call from a browser / Outlook | `https://be-aramco-01.bahra-cables.com/rfp/api/login` |
| What FastAPI matches (documented here) | `/api/login` |

`root_path` only makes `request.base_url` and the generated OpenAPI docs reflect the external `/rfp` mount so links resolve. It does **not** change routing. The session cookie is `rfp_session` scoped to `path=/rfp`.

### 1.2 Base URLs

| Environment | Dashboard service |
|---|---|
| Local dev (backend direct) | `http://localhost:8000` |
| Local dev (through Vite, port 3000) | `http://localhost:3000/rfp/...` |
| Production | `https://be-aramco-01.bahra-cables.com/rfp` (IIS → `127.0.0.1:8000`) |

`automation_main.py` (port 8100) exists as a standalone-automation deployment. It mounts **only** the automation router — a strict subset of the Dashboard service, with **no SessionMiddleware** and narrower CORS. The same automation router is already included by `dashboard_main`, so port 8000 is the entry point for everything. Don't add functionality to `automation_main.py`.

### 1.3 Authentication — four mechanisms coexist

There is no single auth scheme. Four patterns are in use, and you must check per endpoint:

| # | Mechanism | Where | Behaviour |
|---|---|---|---|
| **a** | `Depends(require_permission("key"))` / `Depends(require_admin)` / `Depends(get_current_user)` | [middleware/auth.py](../../backend/middleware/auth.py) | The intended path. 401 if no session, 403 if the session lacks the key. |
| **b** | Inline `request.session.get("user")` → 401 | Much of [routes/dashboard.py](../../backend/routes/dashboard.py); profile + error-files in [routes/api.py](../../backend/routes/api.py) | Authentication only — **any logged-in user passes**, no permission check. |
| **c** | Inline `has_access_to_feature(user, "user_management")` via `services/role_service` | [routes/user_management.py](../../backend/routes/user_management.py) only | Legacy check, parallel to the permission system. |
| **d** | Token-based | [routes/actionable_cards.py](../../backend/routes/actionable_cards.py) (Entra bearer JWT, JWKS-verified); [routes/rfp_upload.py](../../backend/routes/rfp_upload.py) (HS256 JWT in a query/form param) | No session involved. |

**Permissions are frozen at login.** `require_permission` reads `key in user["permissions"]` straight from the session payload written by `POST /api/login`. A role change does **not** take effect until the user logs in again (or calls `POST /api/session/refresh`).

**`require_admin` is a hardcoded role-name check** (`role.lower() == "admin"`), bypassing the permission system entirely. Renaming the Admin role breaks every endpoint that uses it.

**Session:** Starlette `SessionMiddleware`, cookie `rfp_session`, `path="/rfp"`, `max_age = SESSION_TIMEOUT_SECONDS = 7200` (flat 2-hour absolute expiry). **No idle timeout is enforced** despite `IDLE_TIMEOUT_SECONDS` existing in config — nothing reads it.

> **Unauthenticated endpoints.** All **10 automation endpoints** have no auth of any kind. Also open: `GET /api/company-options`, `GET /api/actionable-card/responses/{rfp_id}`, `GET /health`, and the login / logout / forgot / reset-password set. See [§7](#7-automation) and [§15](#15-miscellaneous). These are LAN-only in production via IIS — never publish them on the App Proxy.

### 1.4 Content types

- Request bodies: `application/json` unless stated otherwise. Multipart is used for file uploads and for `POST /dashboard/submit-rfp`.
- Responses: `application/json`, except file/export endpoints (`.xlsx`), `image/png` screenshots, and the two HTML pages (`GET /upload`, `GET /reset-password`).

### 1.5 Error envelope

`HTTPException` responses carry FastAPI's default shape:

```json
{ "detail": "Human-readable message" }
```

Unhandled exceptions are caught by the global handler ([dashboard_main.py:128](../../backend/dashboard_main.py)), which logs a correlation id and returns:

```json
{ "detail": "Internal server error", "error_id": "3f8e1a2b" }
```

- `error_id` — the first **8 characters** of a UUID4. Grep the server log for it.
- The handler deliberately re-raises `StarletteHTTPException` and `RequestValidationError` so FastAPI handles those normally.
- There is no `code` field.

Common HTTP codes:

| Code | Meaning |
|---|---|
| 200 | OK |
| 202 | Accepted — async automation job started on a background thread |
| 400 | Validation error |
| 401 | Not authenticated (no/expired session, or bad token) |
| 403 | Forbidden — session valid but lacks the permission |
| 404 | Resource not found |
| 409 | An operation with that `_RUN_STATE` key is already running (see [§7](#7-automation)); or duplicate role name |
| 500 | Unhandled server error (carries `error_id`) |
| 502 | Upstream failure (SharePoint / Graph lookup) |
| 503 | `/health` only — Dataverse unreachable |

### 1.6 Pagination

**Pagination is not uniform** — there is no shared envelope. Check each endpoint:

| Style | Endpoints |
|---|---|
| `?page=&page_size=` | `GET /api/dashboard/view-logs`, `GET /api/audit-logs` |
| `?limit=&offset=` | `GET /api/dashboard/material-insights-grouped` |
| `?top=` | Master-data list endpoints |
| None (returns everything) | `GET /api/open-rfp/list`, `GET /api/permissions/list` |

### 1.7 Dataverse display-name quirk

Values returned from list endpoints use **display-name keys** (e.g. `Sub Section`), not logical names, because the project queries with `use_display_names=True`. Note that this also **rewrites the primary-key column** to its display label — see [Data Dictionary §1](07-Data-Dictionary-and-ER-Diagram.md).

---

## 2. Endpoint index

12 routers are mounted. `automation.router` is included **twice** (see [§7](#7-automation)), so its endpoints appear at two paths each.

| Tag | Internal prefix | Source | Auth style |
|---|---|---|---|
| [API (auth, session, dashboards, users)](#3-auth--session) | `/api` | [routes/api.py](../../backend/routes/api.py) | (a) mostly, (b) for profile + error-files, none for login/forgot/reset/company-options |
| [Password Reset (HTML page)](#3-auth--session) | `/` | [routes/api.py](../../backend/routes/api.py) `reset_router` | none (token in body) |
| [Dashboard (RFP operations)](#6-dashboard-rfp-operations) | `/dashboard` | [routes/dashboard.py](../../backend/routes/dashboard.py) | mix of (a) and (b) |
| [Automation](#7-automation) | `/api` **and** `/` (double-mounted) | [routes/automation.py](../../backend/routes/automation.py) | **none** |
| [Roles](#8-roles) | `/api` | [routes/role_routes.py](../../backend/routes/role_routes.py) | (a) |
| [Users (legacy)](#9-users-admin) | `/users` | [routes/user_management.py](../../backend/routes/user_management.py) | (c) |
| [Master Data](#10-master-data) | `/api/master-data` | [routes/master_data_routes.py](../../backend/routes/master_data_routes.py) | (a) |
| [System Settings](#11-system-settings) | `/api/system-settings` | [routes/system_settings_routes.py](../../backend/routes/system_settings_routes.py) | (a) |
| [Actionable Cards](#12-actionable-cards-email-callbacks) | `/api/actionable-card` | [routes/actionable_cards.py](../../backend/routes/actionable_cards.py) | (d) Entra JWT — except `responses/{rfp_id}` |
| [Open RFP](#13-open-rfp-reminder-tracker) | `/api/open-rfp` | [routes/open_rfp.py](../../backend/routes/open_rfp.py) | (a) |
| [RFP Upload](#14-rfp-upload-bidder-file-drop) | `/` and `/api` | [routes/rfp_upload.py](../../backend/routes/rfp_upload.py) | (d) HS256 JWT |
| [SharePoint](#141-sharepoint-folder-resolver) | `/api/sharepoint` | [routes/sharepoint.py](../../backend/routes/sharepoint.py) | (a) |

> **`routes/error_analysis_routes.py` is NOT mounted.** The file defines a router with 6 endpoints under `/api/error-analysis`, but `dashboard_main.py` never includes it — the only `include_router` call is commented out at the bottom of the file itself. **Those endpoints are unreachable dead code and are not part of the API.** They are intentionally not documented below. Do not build against them; if you need them, mount the router first.

---

## 3. Auth & session

### `POST /api/login`

Authenticate a portal user and create a server session. **Auth:** none (public).

**Request:** `{ "email": "bidder@example.com", "password": "•••" }`

**Response 200:** `{ "ok": true, "user": { "email", "name", "role", "permissions": [...], "record_id", ... } }`

The session payload — including the **frozen permission list** — is written here. See [§1.3](#13-authentication--four-mechanisms-coexist).

**Rate limiting is enforced in-app for this endpoint** ([routes/api.py](../../backend/routes/api.py)): an in-memory counter keyed by email/IP allows **5 failed attempts per 5-minute window**, then locks that identifier out for **5 minutes**. It is process-local (not shared across workers) and resets on restart. Client IP is taken from `x-forwarded-for` when present.

**Failure modes:** `401` bad credentials · `403` user deactivated · `429`/`403` during lockout.

### `POST /api/logout`
Clear the session. **Auth:** none.

### `GET /api/session/status`
Returns the current session payload, or an unauthenticated marker if none. Used by the frontend on page load.

### `POST /api/session/refresh`
Re-reads role & permissions from Dataverse and rewrites the session — the only way to pick up a role change **without** re-login.

### `POST /api/forgot`
Start password reset; emails a signed one-time token. **Auth:** none. **Request:** `{ "email": "..." }`.

### `POST /api/reset-password`
Consume a reset token and set a new password. **Auth:** none (the token *is* the auth). **Request:** `{ "token": "...", "new_password": "..." }`.

### `GET /reset-password` · `POST /reset-password`
Root-level (`reset_router`, no `/api` prefix). Serves and submits the server-rendered HTML reset page that the email link opens. **Auth:** none.

---

## 4. Profile (self-service)

All three use inline session checks — **authenticated user only, no permission key**.

| Endpoint | Notes |
|---|---|
| `GET /api/profile` | Returns name, email, mobile, role, record_id from the session |
| `POST /api/profile/update` | Update own profile |
| `POST /api/profile/change-password` | `{ "current_password": "...", "new_password": "..." }` |

---

## 5. Main dashboard (aggregates)

Served from `api.py` under `/api/dashboard/*`.

| Endpoint | Permission | Key params |
|---|---|---|
| `GET /api/dashboard/data` | `dashboard.view` | `refresh` (0/1 — bust the cache) |
| `GET /api/dashboard/rfp-details` | `rfp.view` | `status` (default `downloaded`), `search`, `start_date`, `end_date`, `company` |
| `GET /api/dashboard/rfp-details/export` | `rfp.view` | same filters + `format` (default `csv`), `material_match` |
| `GET /api/dashboard/rfp-details/export-full-analysis` | `rfp.view` | `refresh`. Always exports **all** RFPs — page filters are intentionally ignored so the 3-sheet workbook (Material_List / RFP-List / RFP-Count) is canonical |
| `GET /api/dashboard/material-insights` | `material_insights.view` | `rfp_id`, `company`, `material_match`, `keyword_match`, `participated`, `search` |
| `GET /api/dashboard/material-insights-grouped` | `material_insights.view` | `tab` (default `materials`), `company`, `search`, `participated`, `limit` (50), `offset` |
| `GET /api/dashboard/view-logs` | `logs.view` | `page`, `page_size` (50), `force_refresh`, `search` |
| `GET /api/dashboard/sap-password-logs` | `sap_password.view` | — |
| `POST /api/sap/change-password` | `sap_password.change` | — |
| `GET /api/audit-logs` | `audit_logs.view` | `page`, `page_size`, `category`, `action`, `actor_email`, `date_from`, `date_to` |

> `view-logs` browse mode loads only the newest rows; **`?search=` is handled server-side** against the whole table, so use it rather than filtering client-side when hunting old runs.

---

## 6. Dashboard (RFP operations)

Prefix `/dashboard` (no `/api` — kept for the older UI). **Auth is mixed here — check the column.**

| Endpoint | Auth |
|---|---|
| `GET /dashboard/clear-cache` | **`require_admin`** (hardcoded role-name check, not a permission) |
| `POST /dashboard/rfp/status` | `get_current_user` — **any authenticated user**; there is no per-status permission branch |
| `GET /dashboard/rfp-status/{rfp_id}` | `get_current_user` |
| `POST /dashboard/download-all-rfps` | `rfp.download` |
| `POST /dashboard/profile` | inline session check (legacy mirror of `/api/profile/update`) |
| `POST /dashboard/sap-password` | `sap_password.change` |
| `GET /dashboard/schedule-automation/latest` | `schedule_automation.manage` |
| `POST /dashboard/schedule-automation` | `schedule_automation.manage` |
| `GET /dashboard/view-excel/{rfp_id}` | inline session check · `?company=` |
| `POST /dashboard/save-excel/{rfp_id}` | inline session check · multipart `file` · `?company=` |
| `GET /dashboard/rfp/{rfp_id}/materials` | inline session check · `?company=` |
| `GET /dashboard/rfp/{rfp_id}/dynamic-form-structure` | inline session check · `?company=` |
| `GET /dashboard/rfp/batch-match-percentages` | inline session check · `?rfp_ids=a,b,c&companies=` |
| `POST /dashboard/submit-rfp-final` | `rfp.submit` |

### Schedule endpoints — a caveat

`POST /dashboard/schedule-automation` persists to `cr673_bahra_automation_scheduleses`, then calls `sync_schedule_to_power_automate` ([helpers/power_automate_helper.py](../../backend/helpers/power_automate_helper.py)), which patches the flow's Recurrence trigger by writing the `workflow` table in the same Dataverse environment. Sync failure is **non-fatal** — the row still saves and the UI still reports success.

> The flow it targets (`POWER_AUTOMATE_FLOW_NAME`) is the one the Task Scheduler migration retires. Once that flow is turned off, this page **saves successfully but changes nothing** — the real download cadence is Windows Task Scheduler. See the deployment/operations docs before relying on it.

---

## 7. Automation

**These 10 endpoints have NO authentication** — no session dependency, no permission check, no token. They are reachable by anything that can hit the port. In production they are LAN-only behind IIS and are deliberately **not** published on the Entra App Proxy.

### Double mounting

`dashboard_main.py` includes the same router twice:

```python
app.include_router(automation.router, prefix="/api")   # line 92
app.include_router(automation.router)                  # line 93
```

**Every endpoint below is live at both `/api/<path>` and `/<path>`.** Both are real; neither is deprecated. This also produces duplicate operation IDs in the generated OpenAPI document — expect warnings and duplicate entries in a generated client.

### Async contract: 202 / 409

Playwright must launch Chromium, but uvicorn runs on a Windows `SelectorEventLoop`, which cannot spawn subprocesses. So each automation job is dispatched to a **new daemon thread with its own `ProactorEventLoop`** (`_run_async_in_thread`), and the handler returns immediately:

- **`202 Accepted`** → `{"ok": true, "started": true}`. The work is *running*, not finished. Poll `GET /automation/status`.
- **`409 Conflict`** → `{"ok": false, "message": "... already running"}`. An operation with that `_RUN_STATE` key is in flight.

`_RUN_STATE` + `_STATE_LOCK` guard concurrency via an atomic check-and-set inside the lock; `_finish_operation(key)` clears the flag in a `finally`. **State is in-memory and process-local** — it does not survive a restart and assumes a single uvicorn worker.

> **Different keys do not exclude each other.** `download` and `sync` can run concurrently against the same Ariba account. Collision avoidance relies on schedule offsets, not on these flags.

### Endpoints

| Method | Path (also at `/api/…`) | Key | Params | Returns |
|---|---|---|---|---|
| GET | `/automation/status` | — | — | 200 snapshot: `status`, `progress`, `*_running` flags, `last`, `submitting_rfps`, `progress_details` |
| GET | `/download-rfp` | `download` | `?company=` | 202 / 409 |
| GET | `/download-rfps-automation` | `download` | — | 202 `{"mode":"all_companies"}` / 409 — all companies; **this is what the scheduler calls** |
| POST | `/dashboard/submit-rfp` | `submit` | **multipart**: `rfp_id`, `excel_file`, `technical_files[]`, `existing_tds_files[]`, `company` | 202 / 409 |
| GET | `/dashboard/list-tds-files` | — | `?rfp_id=` (required), `?company=` | 200 |
| POST | `/submit-rfp` | `submit` | JSON body (prepared payload) | 202 / 409 |
| GET | `/sync_portal_data` | `sync` | `?rfp_ids=a,b,c` — omit to sync **all** | 202 / 409 |
| GET | `/sync-sharepoint-dataverse` | `sync_sp_dv` | `?company=` | 202 / 409 |
| POST | `/decline-rfp` | `decline` | JSON `{ "rfp_id" \| "rfp_title", "company" }` | 202 / 409 · 400 if neither id given |
| GET | `/rfp-reminder` | — | — | **200, synchronous** |

> `GET /rfp-reminder` is the odd one out: **no run-state guard and no background thread**. It awaits `run_automation_reminder()` inline and blocks until the emails are sent, then returns the result. It touches no browser — it is a pure Dataverse read + email send.

`_RUN_STATE` also exposes a `sync_all` flag in `/automation/status`. **No route ever sets it** — it is permanently `false`. Don't build UI on it.

---

## 8. Roles

All under `/api`. Source: [routes/role_routes.py](../../backend/routes/role_routes.py).

| Method | Path | Permission |
|---|---|---|
| GET | `/api/roles/list` | `role_management.view` |
| GET | `/api/roles/{record_id}` | `role_management.view` |
| POST | `/api/roles/create` | `role_management.create` |
| PUT | `/api/roles/update/{record_id}` | `role_management.edit` |
| DELETE | `/api/roles/delete/{record_id}` | `role_management.delete` — soft delete |
| PATCH | `/api/roles/toggle-status/{record_id}` | `role_management.edit` |
| DELETE | `/api/roles/hard-delete/{record_id}` | `role_management.delete` — removes the role and its permission rows |
| GET | `/api/roles/{record_id}/permissions` | `role_management.view` |
| PUT | `/api/roles/{record_id}/permissions` | `role_management.edit` — **replace semantics** |
| GET | `/api/permissions/list` | `role_management.view` — catalogue of all **42** keys in [services/permission_definitions.py](../../backend/services/permission_definitions.py) |
| POST | `/api/roles/seed` | **`require_admin`** — re-seeds `Admin` + `RFP Bidder`; idempotent |

**Create payload:** `{ "name": "Auditor", "description": "...", "permissions": ["dashboard.view", "audit_logs.view"] }` → `409` on duplicate name. `Admin` is blocked from delete / hard-delete / toggle.

> **`PUT /{record_id}/permissions` silently drops** any key not present in `PERMISSIONS`. A typo'd key returns 200 and is simply not stored — verify with a follow-up GET.
>
> **Renaming a role orphans its permission rows** — they store `role_name` denormalized and are queried by it. See [Data Dictionary §5.3](07-Data-Dictionary-and-ER-Diagram.md).

---

## 9. Users (admin)

Two parallel surfaces exist with **different auth mechanisms**. Prefer `/api/users/*`.

### `/api/users/*` — permission-gated (from `api.py`)

| Method | Path | Permission |
|---|---|---|
| GET | `/api/users/user-list` | `user_management.view` (`?refresh=`) |
| POST | `/api/users/create` | `user_management.create` |
| PUT | `/api/users/update/{record_id}` | `user_management.edit` |
| DELETE | `/api/users/delete/{record_id}` | `user_management.delete` |
| POST | `/api/users/{record_id}/activate` | **`user_management.activate`** |
| POST | `/api/users/{record_id}/deactivate` | **`user_management.activate`** |
| POST | `/api/users/{record_id}/unlock` | **`user_management.activate`** |
| GET | `/api/users/{record_id}/status` | `user_management.view` |

Create-user payload: `{ "email", "name", "role", "password", "mobile" }`.

### `/users/*` — legacy, feature-gated (from `user_management.py`)

`GET /users/detail/{record_id}` · `POST /users` · `PUT /users/{record_id}` · `DELETE /users/{record_id}`

These do **not** use `require_permission`. Each handler inline-checks `has_access_to_feature(user, "user_management")` via `services/role_service` — a separate legacy path that does not consult the 42-key permission catalogue. Treat as deprecated.

---

## 10. Master Data

Prefix `/api/master-data`. 21 endpoints, all `require_permission`.

### Material Master — `material_master.view/create/edit/delete`

`GET /materials/list` · `POST /materials/create` · `PUT /materials/update/{record_id}` · `DELETE /materials/delete/{record_id}` · `POST /materials/import` *(multipart CSV/XLSX — requires `material_master.create`)*

### Keyword Master — `keyword_master.view/create/edit/delete`

`GET /keywords/list` · `POST /keywords/create` · `PUT /keywords/update/{record_id}` · `DELETE /keywords/delete/{record_id}` · `POST /keywords/import` *(multipart — requires `keyword_master.create`)*

### RFP Team Columns (dynamic form schema) — `column_config.view/create/edit/delete`

`GET /rfp-team-columns/list` (active only) · `GET /rfp-team-columns/all` (incl. inactive) · `POST /rfp-team-columns/create` · `PUT /rfp-team-columns/update/{record_id}` · `DELETE /rfp-team-columns/delete/{record_id}` · `POST /rfp-team-columns/reorder` *(requires `column_config.edit`)*

### RFP Team (bidder routing) — `rfp_team.view/create/edit/delete`

`GET /rfp-team/list` · `POST /rfp-team/create` · `PUT /rfp-team/update/{record_id}` · `DELETE /rfp-team/delete/{record_id}` · `POST /rfp-team/import` *(multipart — requires `rfp_team.create`)*

> Both `.../import` and `.../create` map to the same `*.create` permission — there is no separate bulk-import permission.

---

## 11. System Settings

Prefix `/api/system-settings`. Settings live in `cr673_bahra_system_settings` behind a TTL cache.

| Method | Path | Permission |
|---|---|---|
| GET | `/list` | `system_settings.view` — sensitive values masked |
| GET | `/{key}/reveal` | `system_settings.edit` — returns the clear value; **writes a `SETTING_REVEALED` audit row** |
| PUT | `/{key}` | `system_settings.edit` — body `{ "value": "..." }` |
| POST | `/reload-cache` | `system_settings.edit` |
| POST | `/seed` | **`require_admin`** — idempotent re-seed |

> There is **no separate reveal permission**. `system_settings.edit` alone is sufficient to read every masked secret. The reveal is audited, not gated.

---

## 12. Actionable cards (email callbacks)

Prefix `/api/actionable-card`. Called by Microsoft's Outlook **Actions** service, not by users. In production this prefix is the **only** path published through the Entra Application Proxy (Passthrough mode).

### Token validation

`_verify_actionable_message_token` ([routes/actionable_cards.py:60](../../backend/routes/actionable_cards.py)) expects `Authorization: Bearer <jwt>` and checks:

- **Signature** — RS256 via `jwt.PyJWKClient` against the tenant's **v2.0 JWKS**, discovered from `{tenant}/v2.0/.well-known/openid-configuration`. The client is cached globally.
- **`aud`** — must equal `ACTIONABLE_CARD_APP_ID_URI`; the bare client id is also accepted. **Fails closed** if the setting is unconfigured (returns 500 `"APP_ID_URI not configured"`).
- **`iss`** — verified **manually after decode** (`verify_iss: False` is passed deliberately) because **both issuer versions are accepted**: `https://login.microsoftonline.com/{tenant}/v2.0` *and* `https://sts.windows.net/{tenant}/`. Microsoft sends either depending on the resource app's token-version setting.
- **`azp`** (falling back to `appid` on v1.0 tokens) — must equal `ACTIONABLE_CARD_ACTIONS_APP_ID`, Microsoft's **fixed** Actions app id `48af08dc-…`. This is *not* our app id. It stops any other caller holding a token for our audience.
- **`exp`** — verified.

On failure the token is re-decoded **unverified** purely to log actual vs expected `aud`/`iss`/`azp`. Responder identity comes from `preferred_username` / `upn` / `unique_name` / `email` — **not** `sub`, which is an opaque pairwise id.

> `ACTIONABLE_CARD_CALLBACK_URL` lives in `config/config.py` and is in `REMOVED_KEYS` in the seed script — it is deliberately **not** read from Dataverse System Settings. Editing it **requires a service restart** (`net stop rfp-api` / `net start rfp-api`).

### Endpoints

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/api/actionable-card/response` | Entra JWT | Bidder submits results/remarks inline from Outlook. First response wins per team row |
| POST | `/api/actionable-card/response/refresh` | Entra JWT | Outlook `autoInvokeAction` fires this on card open. **Must respond within ~2 s or Outlook times out** and shows the static fallback |
| POST | `/api/actionable-card/decline` | Entra JWT | Inline decline |
| GET | `/api/actionable-card/responses/{rfp_id}` | **NONE** | Returns every response for an RFP. **No token check and no session check — currently unauthenticated.** |

---

## 13. Open RFP (reminder tracker)

Prefix `/api/open-rfp`. Source: [routes/open_rfp.py](../../backend/routes/open_rfp.py).

| Method | Path | Permission | Body |
|---|---|---|---|
| GET | `/list` | `rfp.open.view` | — |
| GET | `/{rfp_id}/status` | `rfp.open.view` | — |
| POST | `/{rfp_id}/remind` | `rfp.open.remind` | `{ "emails": ["..."] }` — 400 if empty |
| POST | `/{rfp_id}/delegate` | `rfp.open.delegate` | `{ "product", "original_email", "new_email", "new_name" }` |

Actor email/name are taken from the session and recorded on the reminder / delegation row.

> `rfp.open.remind` is **not** granted to the default `RFP Bidder` role.

---

## 14. RFP Upload (bidder file drop)

Source: [routes/rfp_upload.py](../../backend/routes/rfp_upload.py). Reached from the Upload button inside an RFP email — **no session, no permission**. Auth is a **HS256 JWT** signed with `UPLOAD_TOKEN_SECRET`, carrying `rfp_id`, `email`, `product`, `company_name`. `verify_upload_token` returns 401 on expiry or tamper.

| Method | Path | Token passed as |
|---|---|---|
| GET | `/upload` | `?token=` — renders the HTML upload form (400 if missing) |
| POST | `/api/rfp-upload` | `token` **form field** — multipart: `pricing_files[]` (required), `tir_files[]`, `tir_mode` (`tir` \| `material`), `material_files[]`, `material_codes[]` |
| GET | `/api/rfp-upload/materials` | `?token=` — material codes for the bidder's RFP, to populate the material-wise dropdown |

A reserved `PREVIEW_TOKEN` short-circuits verification and returns mock claims/data so the page can be previewed without a live email.

### 14.1 SharePoint folder resolver

`GET /api/sharepoint/rfp-folder` — **Permission:** `rfp.sharepoint.view`.

**Query:** `rfp_id` (required), `company` (optional — resolved from Dataverse when omitted).
**Returns:** `200 {"ok": true, "url": "<webUrl>", "company": "..."}` · `400` no rfp_id · `404` company unresolvable or folder not created yet · `502` Graph lookup failed.

---

## 15. Miscellaneous

### `GET /health`
**Auth:** none. Not a mere liveness ping — it **probes Dataverse** by issuing `query_rows(USERS_TABLE_API, top=1)`.

- `200 {"status": "healthy", "dataverse": "connected"}`
- `503 {"status": "unhealthy", "dataverse": "disconnected", "error": "<exception text>"}`

> It returns 503 whenever Dataverse is unreachable, even though the process itself is fine — do not wire this to a restart action. It also echoes the raw exception text; keep it off any public surface.

### `GET /api/company-options`
**Auth: none.** Returns the configured company list for filter dropdowns.

### `GET /api/validate-rfp`
Inline session check. **Query:** `rfp_id` (required).

### `POST /api/schedule/save`
**Permission:** `schedule_automation.manage`. Alias of `POST /dashboard/schedule-automation`; carries the same Power Automate caveat ([§6](#6-dashboard-rfp-operations)).

### Error log files
Three endpoints, all **inline session check only** (any authenticated user — no `logs.view` enforcement):

| Method | Path | Notes |
|---|---|---|
| GET | `/api/error-files/list` | `?rfp_id=` / `?run_id=` (`run_id` wins). Scans `FAILURE_LOGS_DIR`, top level + subfolders |
| GET | `/api/error-files/content/{filename:path}` | `.json` / `.txt` only (400 otherwise). Falls back to SharePoint when not present locally |
| GET | `/api/error-files/screenshot/{filename:path}` | `.png` only (404 otherwise). Same SharePoint fallback |

---

## 16. Rate-limiting & throttling

The app enforces rate limiting **only on `POST /api/login`** (5 failures / 5 min / identifier → 5-min lockout, in-memory, per-process — see [§3](#3-auth--session)). No other endpoint is limited at the app layer.

Recommended reverse-proxy rules to add:

- `/api/forgot` and `/api/reset-password`: password-reset flooding is currently unbounded
- `/api/actionable-card/*`: the only publicly-reachable prefix
- A global per-session ceiling

Dataverse applies its own throttling; `helpers/dataverse_helper.py` surfaces those responses to callers.

---

## 17. Versioning

This is v1 of the API. There is no version prefix in the paths today. Breaking changes should be introduced via a new prefix (`/api/v2/...`) while keeping `/api/*` stable through a deprecation window. Minor non-breaking changes (new fields, new endpoints) do not bump the version.

---

## 18. Generating an OpenAPI client

The backend must be launched with the working directory set to `backend/` (see [CLAUDE.md](../../CLAUDE.md)):

```powershell
cd backend
..\env\Scripts\python.exe -c "from dashboard_main import app; import json, sys; json.dump(app.openapi(), sys.stdout, indent=2)" > ..\openapi.json

# Generate TypeScript client
npx openapi-typescript openapi.json -o frontend/src/api/types.ts
```

> The generated document contains **duplicate operations for all 10 automation endpoints** because the router is mounted twice ([§7](#7-automation)). Deduplicate, or accept two client methods per automation call.
>
> New endpoints belong in `frontend/src/lib/api.ts` with URLs in `frontend/src/lib/endpoints.ts` — not inline in components.

---

## 19. Change history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-04-22 | Manish Soni | Initial API reference |
| 1.1 | 2026-07-17 | Manish Soni | Verified against code; removed unmounted `error_analysis` router (dead code), documented `root_path="/rfp"`, automation router double-mounting, the unauthenticated automation surface, the four coexisting auth mechanisms, 202/409 async contract, and corrected auth/permissions per endpoint |
