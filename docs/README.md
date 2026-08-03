---
title: Bahra Electric RFP Automation — Documentation Hub
version: 2.0
last_updated: 2026-07-17
owner: Manish Soni (Manish.soni@dynatechconsultancy.com)
status: Complete — every document verified against the codebase on 2026-07-17
---

# Bahra Electric RFP Automation — Documentation Hub

This is the **single entry point** for all documentation about the RFP Automation system. Whether you're a new developer, an end user, or a stakeholder, start here and navigate to the document that matches your role.

> **Every document in this set was re-verified against the source code on 2026-07-17.** Where a document describes a limitation, a gap, or a broken feature, that is deliberate and accurate — not a draft that someone forgot to finish. See [Known issues](#known-issues-read-before-relying-on-a-feature) below.

---

## What is this system?

The **Bahra Electric RFP Automation Portal** automates the lifecycle of Requests for Proposals (RFPs):

- **Discovers** new RFPs by scraping the **SAP Ariba** supplier portal with Playwright
- **Downloads** Bill of Quantities (BOQ) Excel/PDF attachments and parses the line items
- **Matches** requested line items against the SAP Material Master and a Keyword Master
- **Routes** each RFP to the assigned internal Bidders via Adaptive-Card emails in Outlook
- **Captures** bidder responses (price, lead time, decline reasons) and persists them to Microsoft Dataverse
- **Tracks** the whole lifecycle with a full audit trail and role-based access control (RBAC)

**Tech stack:** FastAPI (Python) backend · React + TypeScript + Vite frontend · Microsoft Dataverse (OData v9.2) · SharePoint + Microsoft Graph · Playwright (Chromium) · Power Automate · Windows Task Scheduler

### Two things people usually get wrong

1. **There is one Ariba tenant, not four portals.** *Saudi Energy*, *Aramco e-Marketplace*, *HADEED - RAJHI STEEL*, and *Saudi Aramco Mobil Refinery* are **buyer organisations inside a single SAP Ariba supplier account**, selected via a dropdown in the portal UI. They are not separate systems or separate integrations.
2. **Material matching is not fuzzy.** There is no similarity score, no confidence percentage, and no tunable threshold — and no fuzzy-matching library anywhere in the codebase. It is a deterministic two-tier classifier: exact equality on a 9-digit SAP material code, otherwise substring keyword containment. Match quality is improved by editing **Material Master / Keyword Master data**, never by tuning a threshold. See the [HLD §3.3](02-architecture/05-HLD-High-Level-Design.md) and [LLD §4](02-architecture/06-LLD-Low-Level-Design.md).

---

## Known issues — read before relying on a feature

Two features are currently **not working**. They are documented in full in the [Operations Runbook](03-operations/10-Operations-Runbook.md) §7:

| Issue | What actually happens |
|---|---|
| **RFP reminder emails are not sending** | The reminder Power Automate flow calls a dev tunnel that no longer serves, and no Windows Scheduled Task replaces it. Reminders must be triggered manually. |
| **The Schedule Automation page is a silent no-op** | It writes to the Power Automate flow that the Task Scheduler migration retired. Saving shows a success message, but the real download cadence — now Windows Scheduled Tasks on the server — does not change. |

And one **unverified security item** that needs checking:

| Item | Why it matters |
|---|---|
| **The Entra App Proxy publish may be broader than the callback path** | The live callback is `…msappproxy.net/rfp/api/actionable-card/response`. For that `/rfp` prefix to survive, the publish must be rooted at the IIS site rather than scoped to the callback — which would also expose `/rfp/api/login`, `/rfp/health`, the upload page, and the **entirely unauthenticated** `/rfp/api/automation/*` to the public internet. **Verify from an off-LAN machine** and restrict if confirmed — see [Security & Compliance RR-21](03-operations/12-Security-and-Compliance.md#11-residual-risks). |

---

## Documentation Map

All 16 documents are written and verified. `Draft` below means the document is complete and accurate but has not been through formal sign-off — not that it is unfinished.

### A. Start Here

| Document | Audience | Status |
|---|---|---|
| **README.md** *(this file)* | Everyone | ✅ Complete |
| [CHANGELOG.md](CHANGELOG.md) | Everyone | ✅ Complete |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Devs · Ops · Admins | ✅ Living document |

### B. Business & Requirements — *for stakeholders and product owners*

| # | Document | Purpose | Status |
|---|---|---|---|
| 01 | [Business Requirements (BRD)](01-business/01-BRD-Business-Requirements.md) | The "why" — business problem, stakeholders, success metrics | Draft (verified) |
| 02 | [Software Requirements Specification (SRS)](01-business/02-SRS-Software-Requirements-Specification.md) | Functional + non-functional requirements, use cases | Draft (verified) |
| 03 | [Glossary & Acronyms](01-business/03-Glossary-and-Acronyms.md) | RFP, BOQ, Dataverse, SAP, Bidder — single source of truth | ✅ Complete |

### C. Architecture & Design — *for developers and architects*

| # | Document | Purpose | Status |
|---|---|---|---|
| 04 | [Software Architecture Document (SAD)](02-architecture/04-SAD-Software-Architecture-Document.md) | C4 context · container · component views; tech stack; integrations; risks | Draft (verified) |
| 05 | [High Level Design (HLD)](02-architecture/05-HLD-High-Level-Design.md) | Module design; data flow; sequence diagrams per workflow | Draft (verified) |
| 06 | [Low Level Design (LLD)](02-architecture/06-LLD-Low-Level-Design.md) | Function-level design of the matching engine, cards, RBAC, scheduling | Draft (verified) |
| 07 | [Data Dictionary & ER Diagram](02-architecture/07-Data-Dictionary-and-ER-Diagram.md) | All 18 Dataverse tables: columns, types, relationships, API paths | Draft (verified) |
| 08 | [API Documentation](02-architecture/08-API-Documentation.md) | Every mounted endpoint: path, method, params, auth | Draft (verified) |

### D. Operations — *for IT Ops, DevOps, and Admins*

| # | Document | Purpose | Status |
|---|---|---|---|
| 09 | [Deployment Guide](03-operations/09-Deployment-Guide.md) | Production topology, install, IIS, App Proxy, services, hardening | Draft (verified) |
| 10 | [Operations Runbook](03-operations/10-Operations-Runbook.md) | Start/stop, schedules, logs, known issues, incident triage | Draft (verified) |
| 11 | [RBAC Permissions Matrix](03-operations/11-RBAC-Permissions-Matrix.md) | All 42 permissions × roles, audit policy, role workflow | Draft (verified) |
| 12 | [Security & Compliance](03-operations/12-Security-and-Compliance.md) | Auth flow, secrets, audit logs, risk register, incident response | Draft (verified) |

### E. User Manuals — *for end users*

| # | Document | Audience | Status |
|---|---|---|---|
| 13 | [User Manual — Bidder](04-user-manuals/13-User-Manual-Bidder.md) | RFP Bidders | Draft (verified) |
| 14 | [User Manual — Admin](04-user-manuals/14-User-Manual-Admin.md) | System Admins | Draft (verified) |
| 15 | [User Manual — Approver](04-user-manuals/15-User-Manual-Approver.md) | RFP oversight roles | Draft (verified) |
| 16 | [Quick Start Guide](04-user-manuals/16-Quick-Start-Guide.md) | All roles — 1-page onboarding + FAQ | Draft (verified) |

> **Note:** the user manuals are Markdown only. There are no `.docx` versions — earlier revisions of this hub linked to some, but those files never existed.

---

## Find What You Need (by Role)

### 👤 I'm a **new developer** joining the project

1. Read this README (5 min)
2. Read the [Glossary](01-business/03-Glossary-and-Acronyms.md) — learn the domain language (10 min)
3. Read the [SAD](02-architecture/04-SAD-Software-Architecture-Document.md) — the big picture (20 min)
4. Follow the [Deployment Guide](03-operations/09-Deployment-Guide.md) to get it running locally (1 hour)
5. Skim the [HLD](02-architecture/05-HLD-High-Level-Design.md) and [Data Dictionary](02-architecture/07-Data-Dictionary-and-ER-Diagram.md) on demand

**Before you write a line of code**, internalise these four repo-specific rules — each has bitten someone:

- **The backend must run with its working directory set to `backend/`.** That is what puts `backend/` on `sys.path` (so the top-level `from config.config import ...` imports resolve) and what anchors the `os.getcwd()`-based data folders (`ALLRFPs/`, `LOGS/`) inside `backend/`.
- **Never guess a Dataverse EntitySetName.** Pluralization is genuinely unpredictable (`cr673_bahra_roles` → `cr673_bahra_role**ses**`, but `cr673_bahra_rfp_reminder_for_info` → `…info**s**`). Query the metadata and paste the result into the `_API` constant.
- **Playwright can't be driven directly from a request handler.** Uvicorn runs a `SelectorEventLoop`, which cannot spawn subprocesses on Windows. Automation must go through `_run_async_in_thread` in [routes/automation.py](../backend/routes/automation.py), which gives it a dedicated `ProactorEventLoop`.
- **`backend/config/config.py` is untracked and nothing re-reads it at runtime.** Changing it requires a service restart.

### 👤 I'm an **end user** (Bidder)

- Read the [Quick Start Guide](04-user-manuals/16-Quick-Start-Guide.md) (5 min)
- Refer to the [User Manual — Bidder](04-user-manuals/13-User-Manual-Bidder.md) for specific steps

### 👤 I'm a **system admin**

- Read the [User Manual — Admin](04-user-manuals/14-User-Manual-Admin.md)
- Keep the [RBAC Matrix](03-operations/11-RBAC-Permissions-Matrix.md) and [Operations Runbook](03-operations/10-Operations-Runbook.md) bookmarked
- Know that **permission changes only take effect after the affected user signs out and back in**

### 👤 I'm an **IT Ops / DevOps engineer**

- Start with the [Deployment Guide](03-operations/09-Deployment-Guide.md)
- Then the [Operations Runbook](03-operations/10-Operations-Runbook.md) and [Security & Compliance](03-operations/12-Security-and-Compliance.md)
- Production runs from `C:\Bahra-Automation-RFP-System` on `192.168.111.192` under the `rfp-api` service — **not** the developer path in this repo

### 👤 I'm a **business stakeholder / manager**

- Read the [BRD](01-business/01-BRD-Business-Requirements.md) for the "why"
- Skim the [SAD](02-architecture/04-SAD-Software-Architecture-Document.md) — the context diagram only

---

## Running it locally

The backend **must** be launched from inside `backend/`; the virtualenv stays at `env/` in the repo root.

```powershell
# Backend — Dashboard API + UI backend (port 8000), the primary entry point
cd backend
..\env\Scripts\python.exe dashboard_main.py

# Health check
curl http://localhost:8000/health
```

```powershell
# Frontend — dev server on port 3000, proxies /rfp/api, /rfp/dashboard, /rfp/upload to :8000
cd frontend
npm run dev
```

`dashboard_main.py` mounts **every** router and is the canonical entry point. `automation_main.py` (port 8100) exists as a standalone-automation deployment, mounts only the automation router, and is not used in production — don't add functionality to it.

> **There is no automated test suite** — no `pytest`, no `tests/` directory, no load-test tooling. Verification is manual.

---

## Folder Structure

```
docs/
├── README.md                    ← you are here
├── CHANGELOG.md                 Release history
├── TROUBLESHOOTING.md           Symptom → cause → fix
│
├── 01-business/                 Business + requirements docs
├── 02-architecture/             Architecture + design + API + data
├── 03-operations/               Deployment + ops + RBAC + security
├── 04-user-manuals/             Per-role user manuals + quick start
│
├── Application-ScreenShot/      UI screenshots used by the user manuals
├── _samples/                    Sample data files (.xlsx, .csv)
└── rfp-flow-diagram.html        Standalone interactive flow diagram
```

Two runbooks live at the **repo root** rather than here, because they are executable procedures tied to the deployment:

- [Azure-App-Proxy-Adaptive-Card-Setup.md](../Azure-App-Proxy-Adaptive-Card-Setup.md) — the current Adaptive-Card callback setup (**supersedes** the dev-tunnel approach)
- [HTTPS-NotSecure-Fix-Plan.md](../HTTPS-NotSecure-Fix-Plan.md) — the earlier IIS/HTTPS plan; its Phase-2 dev tunnel is what App Proxy retired

---

## Document Conventions

- **Format:** Markdown, rendered by GitHub / Azure DevOps / VS Code
- **Diagrams:** [Mermaid](https://mermaid.js.org/) — renders natively; no build step
- **Frontmatter:** every doc starts with YAML (`title`, `version`, `last_updated`, `owner`, `status`)
- **Cross-links:** relative Markdown links. Backend code is under `backend/`, so from `docs/02-architecture/` a code link looks like `../../backend/automation_logic.py`; the frontend is at the repo root (`../../frontend/src/App.tsx`)
- **Naming:** `NN-Title-In-Kebab-Case.md` — the numeric prefix gives a natural reading order
- **Style:** sentence-case headings · second person for user manuals · third person for technical docs
- **Honesty rule:** if the code doesn't do it, the docs don't claim it. Document limitations and known issues explicitly rather than omitting them.

---

## Maintainers

- **Owner / developer:** Manish Soni (Manish.soni@dynatechconsultancy.com)
- **For changes:** update the relevant document, bump its `version` and `last_updated` in the frontmatter, add a row to that document's revision-history table, and add an entry to [CHANGELOG.md](CHANGELOG.md).
- **Verification rule:** when you change behaviour, update the doc in the same commit. These docs drifted for three months once; the corrections took a full re-verification pass against the source to undo.
- **Questions / corrections:** open an issue in the project repository.
