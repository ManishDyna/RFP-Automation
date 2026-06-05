---
title: API Documentation — Bahra Electric RFP Automation
version: 1.0
last_updated: 2026-04-22
owner: Samir Tak (samir.tak@dynatechconsultancy.com)
audience: Backend developers, Frontend developers, Integration partners
status: Draft
---

# API Documentation

REST API reference for the RFP Automation platform. All routes live on the **Dashboard service** (`http://<host>:8000`) unless explicitly noted as running on the Automation service (`:8100`).

FastAPI generates interactive OpenAPI docs at:
- **Swagger UI:** `http://<host>:8000/docs`
- **ReDoc:** `http://<host>:8000/redoc`
- **Raw OpenAPI JSON:** `http://<host>:8000/openapi.json`

Use this document as the narrative companion — authoritative schema comes from the FastAPI generator.

Related: [SAD](04-SAD-Software-Architecture-Document.md) · [RBAC Matrix](../03-operations/11-RBAC-Permissions-Matrix.md) · [Data Dictionary](07-Data-Dictionary-and-ER-Diagram.md)

---

## 1. Conventions

### 1.1 Base URLs

| Environment | Dashboard | Automation |
|---|---|---|
| Local dev | `http://localhost:8000` | `http://localhost:8100` |
| Production | `https://rfp.bahra-example.com` | (internal) `http://<auto-host>:8100` |

### 1.2 Authentication

- **User-scoped routes:** require a valid server-side session (cookie `session=...`). Issued by `POST /api/login`.
- **Service-to-service / Power Automate callbacks:** signed-token headers (see §11, §12).
- **Actionable-card callbacks:** Microsoft substrate JWT in the `Authorization: Bearer ...` header (see §12).

All protected routes return `401 Unauthorized` when the session is missing/expired, and `403 Forbidden` when the session is valid but lacks the required permission (see [RBAC Matrix](../03-operations/11-RBAC-Permissions-Matrix.md)).

### 1.3 Content types

- Request bodies: `application/json` unless stated otherwise. Multipart is used for file uploads.
- Responses: `application/json`, except file/export endpoints which return `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` or `image/png`.

### 1.4 Error envelope

```json
{
  "detail": "Human-readable message",
  "error_id": "ERR-5f8e3c1a",
  "code": "VALIDATION_ERROR"
}
```

- `detail` — shown to the user
- `error_id` — correlate with server logs
- `code` — machine-readable (optional)

Common HTTP codes:

| Code | Meaning |
|---|---|
| 200 | OK |
| 201 | Created |
| 204 | Deleted — no body |
| 400 | Validation error |
| 401 | Not authenticated |
| 403 | Forbidden (RBAC) |
| 404 | Resource not found |
| 409 | Conflict (e.g., duplicate name) |
| 429 | Rate limited (Dataverse throttling) |
| 500 | Unhandled server error |

### 1.5 Pagination

List endpoints accept `?top=<N>&skip=<M>`; default `top=100`, max `top=1000`. Responses include `{"items": [...], "total": N, "top": 100, "skip": 0}` where the underlying query is OData-paginated.

### 1.6 Dataverse EntitySetName quirk

Column names returned from list endpoints are **display names** (e.g., `name`, `email`, `role`). Custom columns originally logical-named `cr673_xxx` are already mapped. See [Data Dictionary §1](07-Data-Dictionary-and-ER-Diagram.md) for details.

---

## 2. Endpoint index

Grouped by router (tag). Total: ~90 endpoints.

| Tag | Prefix | Source |
|---|---|---|
| [API (auth, session, dashboard)](#3-auth-session) | `/api` | [routes/api.py](../../routes/api.py) |
| [Dashboard (RFP detail, Excel)](#6-dashboard-rfp-operations) | `/dashboard` | [routes/dashboard.py](../../routes/dashboard.py) |
| [Automation](#7-automation) | `/` (mixed) | [routes/automation.py](../../routes/automation.py) |
| [Roles](#8-roles) | `/api` | [routes/role_routes.py](../../routes/role_routes.py) |
| [Users (admin)](#9-users-admin) | `/users` and `/api/users` | [routes/user_management.py](../../routes/user_management.py), `api.py` |
| [Master Data](#10-master-data) | `/api/master-data` | [routes/master_data_routes.py](../../routes/master_data_routes.py) |
| [System Settings](#11-system-settings) | `/api/system-settings` | [routes/system_settings_routes.py](../../routes/system_settings_routes.py) |
| [Actionable Cards](#12-actionable-cards) | `/api/actionable-card` | [routes/actionable_cards.py](../../routes/actionable_cards.py) |
| [Error Analysis](#13-error-analysis) | `/api/error-analysis` | [routes/error_analysis_routes.py](../../routes/error_analysis_routes.py) |

---

## 3. Auth & session

### `POST /api/login`

Authenticate a portal user and create a server session.

**Permission:** none (public).

**Request:**
```json
{ "email": "bidder@example.com", "password": "•••" }
```

**Response 200:**
```json
{
  "ok": true,
  "user": { "id": "...", "email": "...", "name": "...", "role": "RFP Bidder", "permissions": ["rfp.view", "rfp.submit"] }
}
```

**Failure modes:** `401` bad credentials · `403` user deactivated · `429` brute-force throttle (if enabled).

### `POST /api/logout`

Invalidate the current session. Response `200 {"ok": true}`.

### `GET /api/session/status`

Returns the current session payload or `{"authenticated": false}` if none. Used by the frontend on page load.

### `POST /api/session/refresh`

Re-reads role & permissions from Dataverse, updates the session. Useful after a role change without forcing re-login.

### `POST /api/forgot`

Start password reset. Email a one-time token.

**Request:** `{ "email": "..." }` → always returns `200` (never reveals whether the email exists).

### `POST /api/reset-password`

Consume a reset token and set a new password.

**Request:** `{ "token": "...", "new_password": "..." }` → `200 {"ok": true}`.

---

## 4. Profile (self-service)

### `GET /api/profile`
Return the current user's profile.

### `POST /api/profile/update`
Update display name / phone. **Permission:** authenticated (self).

### `POST /api/profile/change-password`
Change own password. **Request:** `{ "current_password": "...", "new_password": "..." }`.

---

## 5. Main dashboard (aggregates)

### `GET /api/dashboard/data`

KPI tiles for the main dashboard.

**Permission:** `dashboard.view`

**Query params:** `?from=YYYY-MM-DD&to=YYYY-MM-DD&company=<name>` (all optional).

**Response (abbreviated):**
```json
{
  "total_rfps": 142,
  "open_rfps": 38,
  "submitted_rfps": 79,
  "declined_rfps": 25,
  "by_company": {"SEC": 42, "Aramco": 33, ...},
  "by_status": {"New": 12, "In Progress": 26, ...}
}
```

Cached 300 s per query key.

### `GET /api/dashboard/rfp-details`

Paginated RFP list with filters.

**Permission:** `rfp.view`

**Query params:** `?top=100&skip=0&status=New&company=SEC&search=<text>&from=...&to=...`

### `GET /api/dashboard/rfp-details/export`

Same filters, returns XLSX download (`.xlsx`).

### `GET /api/dashboard/material-insights`

Material-level analytics (matched vs unmatched counts per material code).

### `GET /api/dashboard/material-insights-grouped`

Same data grouped by RFP company.

### `GET /api/dashboard/view-logs`

Automation activity log list. **Permission:** `logs.view`.

### `GET /api/dashboard/sap-password-logs`

SAP credential-change audit. **Permission:** `sap_password.view`.

### `GET /api/audit-logs`

Full audit trail with filters `?user=...&module=...&action=...&from=...&to=...`. **Permission:** `audit_logs.view`.

---

## 6. Dashboard (RFP operations)

These live under the `/dashboard` prefix (no `/api` — kept for backward compatibility with the older UI).

### `GET /dashboard/clear-cache`

Clear all in-memory caches (RBAC, settings, dashboard). **Permission:** `system_settings.edit`.

### `POST /dashboard/rfp/status`

Update an RFP's status.

**Body:** `{ "rfp_id": "...", "status": "Submitted", "notes": "..." }`

**Permission:** `rfp.submit` for `Submitted`, `rfp.decline` for `Declined`, otherwise `rfp.view`.

### `GET /dashboard/rfp-status/{rfp_id}`

Read current status.

### `POST /dashboard/download-all-rfps`

Bulk-download selected RFP attachments as a ZIP.

**Body:** `{ "rfp_ids": ["...", "..."] }`

**Permission:** `rfp.download`.

### `GET /dashboard/view-excel/{rfp_id}`

Stream the BOQ Excel file for an RFP (rendered client-side via SheetJS).

### `POST /dashboard/save-excel/{rfp_id}`

Persist an edited BOQ back to Dataverse and SharePoint. Body is multipart with the file blob.

### `GET /dashboard/rfp/{rfp_id}/materials`

Per-row material match data (the fuzzy-match engine's output).

### `GET /dashboard/rfp/{rfp_id}/dynamic-form-structure`

Returns the dynamic form schema (from `cr673_bahra_rfp_team_columns`) used to render the bidder-response form.

### `GET /dashboard/rfp/batch-match-percentages`

Batch endpoint: `?ids=rfp1,rfp2,...` → `{ "rfp1": 87.4, "rfp2": 61.2, ... }`.

### `POST /dashboard/submit-rfp-final`

Final bidder submission — validates payload, writes to `rfp_team.response_data`, triggers SAP push and email notification.

**Body:**
```json
{
  "rfp_id": "...",
  "bidder_email": "...",
  "line_items": [
    { "material_code": "MC-001", "unit_price": 123.45, "lead_time_days": 14, ... }
  ],
  "notes": "..."
}
```

**Permission:** `rfp.submit`.

### `POST /dashboard/profile`

Legacy profile update (mirrors `/api/profile/update`).

### `POST /dashboard/sap-password`

Log a SAP password change. **Permission:** `sap_password.change`.

### `GET /dashboard/schedule-automation/latest`
### `POST /dashboard/schedule-automation`

Read/write the automation schedule. Writes call [helpers/power_automate_helper.py](../../helpers/power_automate_helper.py)`.sync_schedule_to_power_automate`. **Permission:** `schedule_automation.manage`.

---

## 7. Automation

Mostly runs on the Automation service (`:8100`) but some sync-trigger endpoints are exposed from the Dashboard service for UI convenience.

### `GET /automation/status`

Is the automation engine idle, running, or failed? **Permission:** `logs.view`.

### `GET /download-rfp`

Trigger a single-RFP download. **Query:** `?rfp_id=...`.

### `GET /download-rfps-automation`

Trigger batch download of all new RFPs (Ariba, SharePoint, Email).

### `POST /dashboard/submit-rfp`

Programmatic submit (used by the portal automation, not end users). Validates and pushes to Ariba via Playwright.

### `POST /submit-rfp`

Lower-level variant; expects a prepared payload.

### `GET /sync_portal_data`

Sync the latest participant/portal state from Ariba into `rfps_v2`.

### `GET /sync-sharepoint-dataverse`

Reconcile SharePoint folder against `rfps_v2` rows — add missing, flag orphans.

### `POST /decline-rfp`

**Body:** `{ "rfp_id": "...", "reason": "..." }` → updates status and notifies assignees.

### `GET /rfp-reminder`

Manually trigger reminder emails for open RFPs past their cadence. **Permission:** `rfp.view` + `schedule_automation.manage`.

---

## 8. Roles

### `GET /api/roles/list`
List all roles with permission counts (single query, no N+1). **Permission:** `role_management.view`.

### `GET /api/roles/{record_id}`
Fetch one role + its permissions.

### `POST /api/roles/create`
**Body:** `{ "name": "Auditor", "description": "...", "permissions": ["dashboard.view", "audit_logs.view"] }`
**Permission:** `role_management.create`. Returns `409` on duplicate name (case-insensitive).

### `PUT /api/roles/update/{record_id}`
Update name, description, active flag. **Permission:** `role_management.edit`.

### `DELETE /api/roles/delete/{record_id}`
Soft delete (sets `is_active = false`). **Permission:** `role_management.delete`. Blocks `Admin`.

### `PATCH /api/roles/toggle-status/{record_id}`
Flip active/inactive. Blocks `Admin`.

### `DELETE /api/roles/hard-delete/{record_id}`
Permanent delete — removes role and all its permission rows. Blocks `Admin`.

### `GET /api/roles/{record_id}/permissions`
### `PUT /api/roles/{record_id}/permissions`
Read / replace the permission set for a role. Replace semantics: the given list becomes the new complete set.

### `GET /api/permissions/list`
Catalogue of all available permissions (the contents of [services/permission_definitions.py](../../services/permission_definitions.py)).

### `POST /api/roles/seed`
Re-seed the `Admin` and `RFP Bidder` default roles. Safe to re-run. **Permission:** `role_management.create`.

---

## 9. Users (admin)

Admin-only user-management endpoints. There are two prefixes in use (`/api/users/...` and `/users/...`) for historical reasons; prefer `/api/users/*`.

### `GET /api/users/user-list`
### `POST /api/users/create`
### `PUT /api/users/update/{record_id}`
### `DELETE /api/users/delete/{record_id}`
### `POST /api/users/{record_id}/activate`
### `POST /api/users/{record_id}/deactivate`
### `POST /api/users/{record_id}/unlock`
### `GET /api/users/{record_id}/status`

Standard CRUD + lifecycle. **Permissions:** `user_management.view/create/edit/delete`. Activate/deactivate require `user_management.edit`.

Create-user payload:
```json
{ "email": "...", "name": "...", "role": "RFP Bidder", "password": "initial-password", "phone": "..." }
```

### Forgot / reset flow
- `POST /api/forgot` → sends email
- `POST /api/reset-password` → consumes token

---

## 10. Master Data

### Material Master

`GET /api/master-data/materials/list`
`POST /api/master-data/materials/create`
`PUT /api/master-data/materials/update/{id}`
`DELETE /api/master-data/materials/delete/{id}`
`POST /api/master-data/materials/import` *(multipart CSV / XLSX)*

**Permissions:** `material_master.view/create/edit/delete`.

### Keyword Master

`GET /api/master-data/keywords/list`
`POST /api/master-data/keywords/create`
`PUT /api/master-data/keywords/update/{id}`
`DELETE /api/master-data/keywords/delete/{id}`
`POST /api/master-data/keywords/import` *(multipart)*

**Permissions:** `keyword_master.*`.

### RFP Team Columns (dynamic form schema)

`GET /api/master-data/rfp-team-columns/list` — active columns
`GET /api/master-data/rfp-team-columns/all` — all (incl. inactive)
`POST /api/master-data/rfp-team-columns/create`
`PUT /api/master-data/rfp-team-columns/update/{id}`
`DELETE /api/master-data/rfp-team-columns/delete/{id}`
`POST /api/master-data/rfp-team-columns/reorder`

Column payload:
```json
{
  "name": "lead_time_days",
  "label": "Lead Time (days)",
  "data_type": "number",
  "is_required": "true",
  "dropdown_options": "",
  "display_order": "3",
  "is_active": "true"
}
```

**Permissions:** `column_config.*`.

### RFP Team (bidder assignments)

`GET /api/master-data/rfp-team/list`
`POST /api/master-data/rfp-team/create`
`PUT /api/master-data/rfp-team/update/{id}`
`DELETE /api/master-data/rfp-team/delete/{id}`
`POST /api/master-data/rfp-team/import` *(multipart)*

**Permissions:** `rfp_team.*`.

---

## 11. System Settings

Settings live in `cr673_bahra_system_settings` with a TTL cache.

### `GET /api/system-settings/list`
List non-sensitive settings. Passwords masked. **Permission:** `system_settings.view`.

### `GET /api/system-settings/{key}/reveal`
Return the clear value for a sensitive setting (logged in the audit trail). **Permission:** `system_settings.edit`.

### `PUT /api/system-settings/{key}`
Update a setting. **Body:** `{ "value": "..." }`. **Permission:** `system_settings.edit`.

### `POST /api/system-settings/reload-cache`
Force refresh the in-process settings cache. No body.

### `POST /api/system-settings/seed`
Run `seed_system_settings.py` idempotently. Useful after adding new keys in code.

---

## 12. Actionable cards (email callbacks)

Base: `/api/actionable-card` — called by the Outlook substrate service, not directly by users.

**Authentication:** Microsoft-issued JWT in `Authorization: Bearer ...`. Verified against:
- Microsoft public JWKs
- Issuer `https://substrate.office.com/sts/`
- Our registered Originator ID

### `POST /api/actionable-card/response`

Bidder submits prices inline from an Outlook actionable message.

**Headers:** `Authorization: Bearer <substrate-jwt>`, `CARD-ACTION-STATUS: ...` (response back to Outlook).

**Body** (adaptive-card `Action.Submit` data):
```json
{ "rfp_id": "...", "line_items": [...], "notes": "..." }
```

### `POST /api/actionable-card/response/refresh`

The card auto-refreshes on open; this endpoint returns the latest data to re-render it.

### `POST /api/actionable-card/decline`

Inline decline. **Body:** `{ "rfp_id": "...", "reason": "..." }`.

### `GET /api/actionable-card/responses/{rfp_id}`

Admin-side: view all adaptive-card responses for an RFP. **Permission:** `rfp.view`.

---

## 13. Error analysis

AI-assisted analysis of scraper failures and activity logs. Wraps an LLM call (separate service) and returns structured diagnostics.

### `POST /api/error-analysis/analyze-logs`
### `POST /api/error-analysis/analyze-logs/formatted`
### `POST /api/error-analysis/analyze-rfp`
### `POST /api/error-analysis/analyze-rfp/formatted`
### `POST /api/error-analysis/quick-analysis`
### `GET /api/error-analysis/health`

**Permissions:** `logs.view`.

---

## 14. Error log files

### `GET /api/error-files/list`

List error-artifact folders under `FAILURE_LOGS_DIR`.

**Permission:** `logs.view`. Constrained to the configured directory — path-traversal blocked.

### `GET /api/error-files/content/{filename:path}`

Returns the text file contents (HTML dumps, JSON captures).

### `GET /api/error-files/screenshot/{filename:path}`

Returns a PNG screenshot inline.

---

## 15. Miscellaneous

### `GET /health`
Liveness probe. Always returns `{"status":"ok"}`. **No auth required.**

### `GET /api/company-options`
Returns the list of distinct company values from `rfps_v2` — for filter dropdowns.

### `GET /api/validate-rfp`
Server-side RFP validation (used before submission). Returns structured issues array.

### `POST /api/schedule/save`
Save automation schedule (legacy alias for `/dashboard/schedule-automation`).

---

## 16. Rate-limiting & throttling

The application **does not enforce rate limits at the app layer**. Place a rate-limit rule at the reverse proxy:

- Login endpoint: 10 requests/min/IP
- Password-reset: 5 requests/hour/IP
- All endpoints: 300 requests/min/session

Dataverse applies its own throttling; clients see `429` with a `Retry-After` header from `helpers/dataverse_helper.py`.

---

## 17. Versioning

This is v1 of the API. Breaking changes will be introduced via a new route prefix (`/api/v2/...`) while keeping `/api/*` routes stable until a deprecation window elapses. Minor non-breaking changes (new fields, new endpoints) do not bump the version.

---

## 18. Generating an OpenAPI client

```bash
# From project root
python -c "from dashboard_main import app; import json, sys; json.dump(app.openapi(), sys.stdout, indent=2)" > openapi.json

# Generate TypeScript client
npx openapi-typescript openapi.json -o frontend/src/api/types.ts
```

Regenerate the typed client whenever API contracts change.
