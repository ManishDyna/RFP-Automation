# Bahra Electric — RFP Automation

End-to-end automation for the Bahra Electric RFP (Request for Proposal) lifecycle: discovers RFPs from the SAP Ariba supplier portal, downloads and parses BOQ (Bill of Quantities) files, matches line items against the SAP Material Master, routes each RFP to internal Bidders via Adaptive-Card emails in Outlook, and persists bidder responses into Microsoft Dataverse with a full RBAC audit trail.

**📚 [Full documentation lives in `docs/`](docs/README.md)** — start there. This file is only enough to get you running.

**Owner / developer:** Manish Soni (Manish.soni@dynatechconsultancy.com)

---

## Quick start

The backend **must** be launched with its working directory set to `backend/` — that is what puts `backend/` on `sys.path` (so the top-level `from config.config import ...` imports resolve) and what anchors the `os.getcwd()`-based data folders (`ALLRFPs/`, `LOGS/`) inside `backend/`. The virtualenv stays at `env/` in the repo root.

```powershell
# Backend — Dashboard API + UI backend (port 8000). The canonical entry point.
cd backend
..\env\Scripts\python.exe dashboard_main.py

# Health check (probes Dataverse, not just liveness)
curl http://localhost:8000/health
```

```powershell
# Frontend — Vite dev server on port 3000
cd frontend
npm run dev        # proxies /rfp/api, /rfp/dashboard, /rfp/upload to :8000
npm run build      # tsc -b && vite build → frontend/dist
npm run lint       # eslint .
```

`dashboard_main.py` mounts **every** router and is the only entry point used in production. `automation_main.py` (port 8100) is a standalone-automation deployment that mounts just the automation router — it is not deployed, and new functionality should not be added to it.

> **There is no automated test suite** — no `pytest`, no `tests/` directory, no load-test tooling. Verification is manual.

---

## Architecture at a glance

```
┌──────────────────┐   HTTPS    ┌──────────────────────────────┐
│ React + Vite UI  │ ─────────► │  FastAPI (dashboard_main.py) │
│   (port 3000)    │  /rfp/*    │       (port 8000)            │
└──────────────────┘            └──────────────┬───────────────┘
                                               │
            ┌────────────────────┬─────────────┼──────────────────┬──────────────┐
            ▼                    ▼             ▼                  ▼              ▼
     ┌──────────────┐   ┌──────────────┐  ┌────────────┐   ┌──────────────┐  ┌──────────┐
     │ Microsoft    │   │  Playwright  │  │ MS Graph   │   │  Windows     │  │ SAP      │
     │ Dataverse    │   │  (SAP Ariba  │  │ (SharePoint│   │  Task        │  │ Material │
     │ (OData v9.2) │   │   portal)    │  │  + Email)  │   │  Scheduler   │  │ Master   │
     └──────────────┘   └──────────────┘  └────────────┘   └──────────────┘  └──────────┘
```

| Path | What lives there |
|---|---|
| `backend/` | FastAPI app. `dashboard_main.py` (entry), `routes/`, `services/`, `helpers/`, `rfp/` (Playwright portal flows), `automation_logic.py` (orchestration), `config/` |
| `frontend/` | React + TypeScript + Vite SPA |
| `scripts/` | `Register-RfpSchedules.ps1` / `Invoke-RfpAutomation.ps1` — the Windows Task Scheduler jobs |
| `docs/` | The documentation set — architecture, operations, RBAC, user manuals |
| `env/` | Python virtualenv (repo root, one level above `backend/`) |

---

## Four rules that will save you a day

1. **Run the backend from `backend/`.** Launching from the repo root fails at import, or silently writes runtime data to the wrong place.
2. **Never guess a Dataverse EntitySetName.** Pluralization is genuinely unpredictable — `cr673_bahra_roles` → `cr673_bahra_role`**`ses`**, but `cr673_bahra_rfp_reminder_for_info` → `…info`**`s`**. Query the metadata and paste the result into the matching `_API` constant in `backend/config/config.py`.
3. **Playwright cannot be driven directly from a request handler.** Uvicorn runs a `SelectorEventLoop`, which can't spawn subprocesses on Windows. Automation must go through `_run_async_in_thread` in `backend/routes/automation.py`, which provides a dedicated `ProactorEventLoop`.
4. **`backend/config/config.py` is untracked, and nothing re-reads it at runtime.** It holds the secrets, it is gitignored, and changing it requires a service restart (`Restart-Service rfp-api`).

---

## Two things people usually get wrong

- **There is one Ariba tenant, not four portals.** *Saudi Energy*, *Aramco e-Marketplace*, *HADEED - RAJHI STEEL*, and *Saudi Aramco Mobil Refinery* are **buyer organisations inside a single SAP Ariba supplier account**, switched via a dropdown.
- **Material matching is not fuzzy.** No similarity score, no confidence value, no threshold, and no fuzzy-matching library anywhere in the codebase. It is a deterministic two-tier classifier: exact equality on a 9-digit SAP material code, otherwise substring keyword containment. You improve matching by editing **Material/Keyword Master data**, never by tuning a threshold.

---

## Production

Production runs from `C:\Bahra-Automation-RFP-System` on `192.168.111.192` under the `rfp-api` service (WinSW), behind IIS at `https://be-aramco-01.bahra-cables.com/rfp`. That host also serves an unrelated COA application — don't touch it. The Outlook Adaptive-Card callback reaches the backend through Microsoft Entra Application Proxy.

Details: [Deployment Guide](docs/03-operations/09-Deployment-Guide.md) · [Operations Runbook](docs/03-operations/10-Operations-Runbook.md) · [Azure App Proxy setup](Azure-App-Proxy-Adaptive-Card-Setup.md)

### Known issues

Two features are currently **not working** — see [Operations Runbook §7](docs/03-operations/10-Operations-Runbook.md):

- **RFP reminder emails are not sending** — the Power Automate flow calls a retired dev tunnel and no Scheduled Task replaces it.
- **The Schedule Automation page is a silent no-op** — it writes to the flow that the Task Scheduler migration retired, so saving succeeds while the real cadence is unchanged.

Plus one **unverified security item**: the Entra App Proxy publish may be broader than the callback path — if so, the unauthenticated `/rfp/api/automation/*` endpoints are internet-reachable. Verify from off-LAN; see [Security & Compliance RR-21](docs/03-operations/12-Security-and-Compliance.md#11-residual-risks).

---

## Where to go next

| You are… | Read |
|---|---|
| A new developer | [Glossary](docs/01-business/03-Glossary-and-Acronyms.md) → [SAD](docs/02-architecture/04-SAD-Software-Architecture-Document.md) → [Deployment Guide](docs/03-operations/09-Deployment-Guide.md) |
| An end user (Bidder) | [Quick Start](docs/04-user-manuals/16-Quick-Start-Guide.md) → [Bidder manual](docs/04-user-manuals/13-User-Manual-Bidder.md) |
| A system admin | [Admin manual](docs/04-user-manuals/14-User-Manual-Admin.md) → [RBAC Matrix](docs/03-operations/11-RBAC-Permissions-Matrix.md) |
| On call | [Operations Runbook](docs/03-operations/10-Operations-Runbook.md) → [Troubleshooting](docs/TROUBLESHOOTING.md) |
| Integrating with the API | [API Documentation](docs/02-architecture/08-API-Documentation.md) |
