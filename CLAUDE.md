# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this system is

End-to-end automation for the Bahra Electric RFP (Request for Proposal) lifecycle: discovers RFPs from supplier portals (SAP Ariba / Saudi Energy / Aramco / HADEED), downloads BOQ (Bill of Quantities) Excel/PDF files, fuzzy-matches line items against the SAP Material Master, routes RFPs to internal Bidders via Adaptive-Card emails, and persists bidder responses (price, lead time, declines) into Microsoft Dataverse with full RBAC audit. See [docs/README.md](docs/README.md) for the documentation hub.

## Commands

The Python virtualenv lives at `env/` in the repo root. Always invoke Python through it on Windows:

```powershell
env\Scripts\python.exe <script.py>
```

### Backend (FastAPI)
```powershell
# Dashboard API + UI backend (port 8000) — primary entry point
env\Scripts\python.exe dashboard_main.py

# Standalone automation API (port 8100) — rarely used; automation routes are
# already mounted into dashboard_main on port 8000
env\Scripts\python.exe automation_main.py

# Health check
curl http://localhost:8000/health
```

### Frontend (Vite + React)
```powershell
cd frontend
npm run dev        # dev server on port 3000, proxies /api /dashboard /upload to :8000
npm run build      # tsc -b && vite build → frontend/dist
npm run lint       # eslint .
npm run preview    # serve built bundle
```

### Performance / load tests
```powershell
cd tests\performance
.\run-tests.ps1 smoke          # 5 users, 1 min
.\run-tests.ps1 load           # 50–150 users, 21 min
.\run-tests.ps1 stress         # find breaking point
.\run-tests.ps1 all
```
There is no Python test suite — `tests/` contains only k6 performance scripts.

### Dataverse / setup utilities
One-off setup and migration scripts live in `Support-Files/`. They are **idempotent** and safe to re-run. Each `setup_*_table.py` prints the resolved EntitySetName after `PublishXml` — paste it into the matching `*_API` constant in [config/config.py](config/config.py).

```powershell
env\Scripts\python.exe Support-Files\setup_rfps_v2_table.py
env\Scripts\python.exe Support-Files\setup_open_rfp_reminder_table.py
env\Scripts\python.exe Support-Files\setup_delegation_table.py
env\Scripts\python.exe Support-Files\seed_system_settings.py
env\Scripts\python.exe check_settings.py     # dump current System Settings rows
```

## Architecture

### Big picture

```
┌──────────────────┐   HTTPS    ┌──────────────────────────────┐
│ React + Vite UI  │ ─────────► │  FastAPI (dashboard_main.py) │
│   (port 3000)    │   /api/*   │       (port 8000)            │
└──────────────────┘            └──────────────┬───────────────┘
                                               │
            ┌────────────────────┬─────────────┼──────────────────┬──────────────┐
            ▼                    ▼             ▼                  ▼              ▼
     ┌──────────────┐   ┌──────────────┐  ┌────────────┐   ┌──────────────┐  ┌──────────┐
     │ Microsoft    │   │  Playwright  │  │ MS Graph   │   │ Power        │  │ SAP      │
     │ Dataverse    │   │  (Ariba      │  │ (SharePoint│   │ Automate     │  │ Material │
     │ (OData v9.2) │   │   portals)   │  │  + Email)  │   │ (cron, mail) │  │ Master   │
     └──────────────┘   └──────────────┘  └────────────┘   └──────────────┘  └──────────┘
```

`dashboard_main.py` is the canonical entry point — it mounts **every** router (api, dashboard, automation, role, actionable_cards, master_data, system_settings, open_rfp, rfp_upload, sharepoint, user_management). `automation_main.py` exists as a standalone-automation deployment but the same automation router is also included by `dashboard_main`. Don't add functionality to `automation_main.py`.

### Backend layout

| Layer | Path | Purpose |
|---|---|---|
| Entry | `dashboard_main.py` | FastAPI app, CORS, SessionMiddleware, router mounting, global exception handler, `/health` |
| Routes | `routes/` | One file per feature area. Each exposes an `APIRouter`. `routes/automation.py` owns the global `_RUN_STATE` lock for concurrent-job protection |
| Services | `services/` | Business logic. `dashboard_service.py` (cached), `dynamic_role_service.py` (RBAC), `audit_service.py`, `system_settings_service.py`, `open_rfp_service.py`, `rfp_team_columns_service.py`, etc. |
| Automation logic | `automation_logic.py` | Top-level orchestration funcs (`run_automation_download`, `run_automation_submit`, `run_automation_decline`, `run_automation_reminder`, `run_automation_sync_portal`, `run_sync_sharepoint_dataverse`). These are launched in dedicated threads with their own `ProactorEventLoop` (see `_run_async_in_thread` in `routes/automation.py`) |
| RFP workflows | `rfp/` | `download_rfp.py`, `submit_rfp.py`, `decline_rfp.py`, `rfp_reminder.py` — the actual Playwright browser interactions against supplier portals |
| Helpers | `helpers/` | `dataverse_helper.py` (the `DataverseClient`), `core_helper.py` (exports the global `DATAVERSE` client + Playwright utilities), `sharepoint_helper.py` (Graph client), `email_helper.py`, `failure_logger.py`, `progress_helper.py` |
| Core | `core/` | `common_imports.py` (a "star" import bundle reused by automation code), `common_process.py`, `log_events.py` (writes to RFP activity log table), `local_log.py` |
| Middleware | `middleware/auth.py` | `get_current_user`, `require_permission(key)`, `require_admin` FastAPI dependencies |
| Config | `config/config.py` | All table names, secrets, URLs, email recipients, session timeouts. `config/runtime_config.py` exposes `USERNAME`/`PASSWORD` resolved at import time from Dataverse via `helpers/credentials_provider.py` |

### Frontend layout

| Path | Purpose |
|---|---|
| `frontend/src/App.tsx` | React Router setup; pages are lazy-loaded; routes guarded by `PermissionGuard` + `useAuth` |
| `frontend/src/pages/` | Top-level routes: `dashboard`, `rfp-insights`, `open-rfps`, `logs`, `analytics`, `material-insights`, `profile`, `login`, plus `admin/{users,roles,audit-logs,master-data,sap-logs,system-settings}` |
| `frontend/src/lib/api.ts` | All HTTP calls. **Add new endpoints here**, not inline in components |
| `frontend/src/lib/endpoints.ts` | URL constants consumed by `api.ts` |
| `frontend/src/hooks/use-auth.ts` | Zustand store with persistence; exposes `useHasPermission()` |
| `frontend/src/components/ui/` | shadcn/Radix primitives |
| `frontend/src/components/dialogs/` | Modal dialogs orchestrated via `DialogProvider` in `contexts/dialog-context.tsx` |

State: TanStack Query for server state, Zustand for auth/UI state. Forms: react-hook-form + zod. Tables: TanStack Table + Virtual. Styling: Tailwind + tailwind-merge.

### How the dashboard talks to the backend

In dev, Vite proxies `/api`, `/dashboard`, and `/upload` from port 3000 → port 8000 (see `frontend/vite.config.ts`). In prod, the built bundle is served separately and CORS in `dashboard_main.py` permits the React origin.

## Key conventions specific to this repo

### Dataverse (the most important conventions)

- **EntitySetName pluralization is not predictable.** Each table is declared in `config/config.py` as a `_LOGICAL` + `_API` pair. After creating a new table, the setup script prints the resolved `EntitySetName` (e.g. `cr673_bahra_roles` → `cr673_bahra_roleses`, but `cr673_bahra_rfp_reminder_for_info` → `cr673_bahra_rfp_reminder_for_infos`). Paste it into the `_API` constant. Never guess.
- **All column values are strings.** The project uses `use_display_names=True` on `DataverseClient.query_rows` — display labels (e.g. `"Sub Section"`) are returned as keys, not logical names.
- **`use_display_names=True` rewrites the PK column**, so `row.get(pk_logical)` returns None — see the existing memory at `project_dataverse_pk_display_remap.md` and resolve via the logical→display reverse map.
- **Dates are MDY** (`%#m/%#d/%Y %#I:%M %p` on Windows). Datetimes coming back as `…Z` are already Saudi local time — do NOT shift them with `new Date()` in the frontend; use `formatDateMDY` in `frontend/src/lib/utils.ts`.
- **Use `helpers/core_helper.DATAVERSE`** (the shared, already-authenticated `DataverseClient` singleton). Construct a new client only inside `credentials_provider.py` where settings are loaded dynamically.

### Windows / asyncio

Playwright needs `WindowsProactorEventLoopPolicy`, but uvicorn runs on `SelectorEventLoop`. Any code path that drives Playwright from inside a request handler MUST be invoked via `_run_async_in_thread(coro, ...)` from [routes/automation.py](routes/automation.py) — that helper spins up a dedicated `ProactorEventLoop` on a background thread. Calling `await some_playwright_func()` directly from a FastAPI handler will fail with `NotImplementedError` on subprocess.

The Windows UTF-8 stdout shim at the top of `dashboard_main.py` is required for emoji in `print()` calls used by the automation scripts.

### Concurrent automation jobs

`routes/automation.py` keeps an in-memory `_RUN_STATE` dict + `_STATE_LOCK` mutex. Long-running jobs (`download`, `submit`, `decline`, `sync`, etc.) acquire the lock via `_try_start_operation(key)` and release with `_finish_operation(key)`. Per-RFP submit status is tracked in `_RUN_STATE["submitting_rfps"]` (a set). Front-end polls `/api/automation/state` to reflect button-disabled UI.

### Auth & RBAC

- Login sets `request.session["user"]` (Starlette `SessionMiddleware`, signed cookie, 2-hour timeout).
- Protect endpoints with `Depends(get_current_user)` for any auth, or `Depends(require_permission("module.action"))` for granular checks.
- Permission keys are the source of truth in [services/permission_definitions.py](services/permission_definitions.py). Roles & their permission grants live in Dataverse tables `cr673_bahra_roles` and `cr673_bahra_role_permissions` (managed via `services/dynamic_role_service.py`).
- Frontend mirrors this with the `useHasPermission()` hook + `<PermissionGuard>` route wrapper.

### Email & SharePoint

- `config.config.EMAIL_MODE = "dev"` routes ALL outgoing email to `DEV_EMAIL`. Production recipients live in the `cr673_bahra_system_settings` Dataverse table (managed from the System Settings page in the portal) — `config.py` constants are only fallbacks for when Dataverse is unreachable.
- Production recipients per category (`EMAIL_TO_NEW_RFP`, `EMAIL_TO_RFP_REMINDER`, etc.) are looked up at send time, not at import time.
- Adaptive Card responses (the "Submit / Decline" buttons in Outlook emails) hit `ACTIONABLE_CARD_CALLBACK_URL`, which currently points at a devtunnel — update this in `config.py` before each new dev session if tunnels change.
- SharePoint folder layout under `RFP-logs/` is canonical; helpers in `core_helper.get_sharepoint_rfp_*_path` compute per-RFP paths.

### Company aliasing

Frontend uses short company labels (`SEC`, `Aramco`, `HADEED`); backend normalizes via `config.config.resolve_company_name()` and `COMPANY_ALIASES`. When the portal renames a company, add an alias rather than migrating historical data (see memory `project_company_aliases.md`).

### Logging

- `LOGS/` — automation logs + Playwright error screenshots
- `automation-error-logs/` — failure bundles uploaded to SharePoint under `SP_FAILURE_LOGS_FOLDER`
- `ALLRFPs/` — downloaded RFP bundles (auto-created)
- `core/log_events.py` writes RFP activity rows into `cr673_bahra_rfps_v2` (the v2 activity table — the v1 table is deprecated)

### Support-Files/

Throwaway / one-off scripts (audits, migrations, table-setup) live here. They are **not** imported by the running application — many of the analysis scripts have been deleted in the current working branch. Don't import from `Support-Files/` in new code.
