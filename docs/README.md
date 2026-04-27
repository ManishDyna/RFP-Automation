---
title: Bahra Electric RFP Automation — Documentation Hub
version: 1.0
last_updated: 2026-04-22
owner: Samir Tak (samir.tak@dynatechconsultancy.com)
status: In Progress (Phase 1 of 4)
---

# Bahra Electric RFP Automation — Documentation Hub

Welcome. This is the **single entry point** for all documentation about the RFP Automation system. Whether you're a new developer, an end user, or a stakeholder, start here and navigate to the document that matches your role.

---

## What is this system?

The **Bahra Electric RFP Automation Portal** is an end-to-end platform that automates the lifecycle of Requests for Proposals (RFPs):

- **Discovers** new RFPs from email and SharePoint
- **Extracts** Bill of Quantities (BOQ) line items from Excel/PDF
- **Matches** requested materials against the SAP Material Master using a fuzzy-matching engine
- **Routes** RFPs to assigned Bidders via dashboard and adaptive-card emails
- **Captures** bidder responses (price, lead time, decline reasons) and persists them in Microsoft Dataverse
- **Tracks** the complete audit trail with role-based access control (RBAC)

**Tech stack:** FastAPI (Python) backend · React + TypeScript + Vite frontend · Microsoft Dataverse (OData) · SharePoint · SAP · Power Automate · Microsoft Graph (Email)

---

## Documentation Map

> **Status legend:** ✅ Complete · 🚧 In Progress · ⏳ Planned

### A. Start Here

| Document | Audience | Status |
|---|---|---|
| **README.md** *(this file)* | Everyone | ✅ |
| [CHANGELOG.md](CHANGELOG.md) | Everyone | ⏳ |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Devs · Ops · Admins | ⏳ |

### B. Business & Requirements — *for stakeholders and product owners*

| # | Document | Purpose | Status |
|---|---|---|---|
| 01 | [Business Requirements (BRD)](01-business/01-BRD-Business-Requirements.md) | The "why" — business problem, stakeholders, success metrics | ⏳ |
| 02 | [Software Requirements Specification (SRS)](01-business/02-SRS-Software-Requirements-Specification.md) | Functional + non-functional requirements, use cases | ⏳ |
| 03 | [Glossary & Acronyms](01-business/03-Glossary-and-Acronyms.md) | RFP, BOQ, Dataverse, SAP, Bidder — single source of truth | ⏳ |

### C. Architecture & Design — *for developers and architects*

| # | Document | Purpose | Status |
|---|---|---|---|
| 04 | [Software Architecture Document (SAD)](02-architecture/04-SAD-Software-Architecture-Document.md) | C4 model: Context · Container · Component diagrams; tech stack; integrations | ⏳ |
| 05 | [High Level Design (HLD)](02-architecture/05-HLD-High-Level-Design.md) | Module-level design; data flow; sequence diagrams per workflow | ⏳ |
| 06 | [Low Level Design (LLD)](02-architecture/06-LLD-Low-Level-Design.md) | Class/function design for matching engine, dashboard, automation | ⏳ |
| 07 | [Data Dictionary & ER Diagram](02-architecture/07-Data-Dictionary-and-ER-Diagram.md) | All Dataverse tables: columns, types, relationships, API paths | ⏳ |
| 08 | [API Documentation](02-architecture/08-API-Documentation.md) | All FastAPI endpoints: path, method, params, request/response, auth | ⏳ |

### D. Operations — *for IT Ops, DevOps, and Admins*

| # | Document | Purpose | Status |
|---|---|---|---|
| 09 | [Deployment Guide](03-operations/09-Deployment-Guide.md) | Step-by-step setup: env vars, deps, Dataverse setup, Power Automate flows | ⏳ |
| 10 | [Operations Runbook](03-operations/10-Operations-Runbook.md) | Daily operations: start/stop, logs, monitoring, common errors | ⏳ |
| 11 | [RBAC Permissions Matrix](03-operations/11-RBAC-Permissions-Matrix.md) | Roles × permissions grid, audit policy, role-creation workflow | ⏳ |
| 12 | [Security & Compliance](03-operations/12-Security-and-Compliance.md) | Auth flow, secrets, audit logs, DR/backup, incident response | ⏳ |

### E. User Manuals — *for end users*

| # | Document | Audience | Status |
|---|---|---|---|
| 13 | [User Manual — Bidder](04-user-manuals/13-User-Manual-Bidder.md) ([.docx](04-user-manuals/13-User-Manual-Bidder.docx)) | RFP Bidders | ⏳ |
| 14 | [User Manual — Admin](04-user-manuals/14-User-Manual-Admin.md) ([.docx](04-user-manuals/14-User-Manual-Admin.docx)) | System Admins | ⏳ |
| 15 | [User Manual — Approver](04-user-manuals/15-User-Manual-Approver.md) ([.docx](04-user-manuals/15-User-Manual-Approver.docx)) | RFP Approvers | ⏳ |
| 16 | [Quick Start Guide](04-user-manuals/16-Quick-Start-Guide.md) ([.docx](04-user-manuals/16-Quick-Start-Guide.docx)) | All roles — 1-pager onboarding + FAQ | ⏳ |

---

## Find What You Need (by Role)

### 👤 I'm a **new developer** joining the project
1. Read this README (5 min)
2. Read [Glossary](01-business/03-Glossary-and-Acronyms.md) — learn the domain language (10 min)
3. Read [SAD](02-architecture/04-SAD-Software-Architecture-Document.md) — understand the big picture (20 min)
4. Follow [Deployment Guide](03-operations/09-Deployment-Guide.md) to get the system running locally (1 hour)
5. Skim [HLD](02-architecture/05-HLD-High-Level-Design.md) and [Data Dictionary](02-architecture/07-Data-Dictionary-and-ER-Diagram.md) on demand

### 👤 I'm an **end user** (Bidder)
- Read the [Quick Start Guide](04-user-manuals/16-Quick-Start-Guide.md) (5 min)
- Refer to [User Manual — Bidder](04-user-manuals/13-User-Manual-Bidder.md) when you need specific steps

### 👤 I'm a **system admin**
- Read [User Manual — Admin](04-user-manuals/14-User-Manual-Admin.md)
- Keep [RBAC Matrix](03-operations/11-RBAC-Permissions-Matrix.md) and [Operations Runbook](03-operations/10-Operations-Runbook.md) bookmarked

### 👤 I'm an **IT Ops / DevOps engineer**
- Start with [Deployment Guide](03-operations/09-Deployment-Guide.md)
- Then [Operations Runbook](03-operations/10-Operations-Runbook.md) and [Security & Compliance](03-operations/12-Security-and-Compliance.md)

### 👤 I'm a **business stakeholder / manager**
- Read [BRD](01-business/01-BRD-Business-Requirements.md) for the "why"
- Skim [SAD](02-architecture/04-SAD-Software-Architecture-Document.md) — Section 1 (Context Diagram) only

---

## Folder Structure

```
docs/
├── README.md                    ← you are here
├── CHANGELOG.md                 (planned)
├── TROUBLESHOOTING.md           (planned)
│
├── 01-business/                 Business + requirements docs
├── 02-architecture/             Architecture + design + API + data
├── 03-operations/               Deployment + ops + RBAC + security
├── 04-user-manuals/             Per-role user manuals + quick start
│
├── _assets/                     Diagrams (Mermaid sources, images), screenshots
└── _samples/                    Sample data files (.xlsx, .csv) for testing
```

---

## Document Conventions

- **Format:** Markdown for technical docs · Word (`.docx`) generated via Pandoc for end-user manuals
- **Diagrams:** [Mermaid](https://mermaid.js.org/) (architecture, sequence, ER, flowcharts) — renders natively in GitHub, Azure DevOps, and VS Code
- **Frontmatter:** Each doc starts with YAML frontmatter (`title`, `version`, `last_updated`, `owner`, `status`)
- **Cross-links:** Use relative markdown links between docs
- **Naming:** `NN-Title-In-Kebab-Case.md` (numeric prefix gives natural reading order)
- **Style:** Sentence-case headings · second-person ("you click...") for user manuals · third-person for technical docs

---

## Roadmap

This documentation is being built in **4 phases**. See the plan at `C:\Users\Manish.Soni\.claude\plans\check-i-already-have-glittery-kazoo.md`.

| Phase | Scope | Status |
|---|---|---|
| **Phase 1 — Foundation** | README · Glossary · SAD · Data Dictionary | 🚧 In Progress |
| **Phase 2 — Operations Critical** | Deployment · Runbook · RBAC · Security · API | ⏳ Planned |
| **Phase 3 — Design Depth** | HLD · LLD · BRD · SRS | ⏳ Planned |
| **Phase 4 — End-User Polish** | Bidder · Admin · Approver manuals · Quick Start · CHANGELOG · TROUBLESHOOTING | ⏳ Planned |

---

## Maintainers

- **Owner:** Samir Tak — samir.tak@dynatechconsultancy.com
- **For changes:** Update the relevant document, bump its `version` and `last_updated` in the frontmatter, and add an entry to [CHANGELOG.md](CHANGELOG.md) once available.
- **Questions / corrections:** Open an issue in the project repository.
