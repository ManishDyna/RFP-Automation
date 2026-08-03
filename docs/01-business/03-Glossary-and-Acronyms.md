---
title: Glossary & Acronyms
version: 1.1
last_updated: 2026-07-17
owner: Manish Soni (Manish.soni@dynatechconsultancy.com)
audience: Everyone (devs, end-users, stakeholders, ops)
status: Complete
---

# Glossary & Acronyms

This document is the **single source of truth** for terminology used across the Bahra Electric RFP Automation system. Whenever a new term is introduced in any other document (SAD, HLD, User Manual, Runbook), it should be defined here first.

**How to use this glossary:**
- Reading another doc and hit an unknown term? Search this file (Ctrl+F).
- Writing a new doc? Use the exact spelling and capitalization defined here.
- Adding a new term? Add it here in alphabetical order, then reference it from your doc.

---

## Table of Contents

- [A. Business / Domain Terms](#a-business--domain-terms)
- [B. Technical Terms](#b-technical-terms)
- [C. Acronyms (Quick Reference)](#c-acronyms-quick-reference)
- [D. System Roles](#d-system-roles)
- [E. Permission Vocabulary](#e-permission-vocabulary)
- [F. Naming Conventions](#f-naming-conventions)

---

## A. Business / Domain Terms

### Actionable Card
An interactive email rendered as a Microsoft Actionable Message (Adaptive Card) that lets approved recipients respond directly from Outlook — for example, declining an RFP without opening the portal. See also: *Adaptive Card*, *Originator ID*.

### Approver
A **business role, not a system role.** Managers who oversee bidding use read-only screens (Dashboard, RFP Insights, Analytics, Audit Logs) via a custom role an Admin creates. The system has **no approve/reject workflow** — an RFP goes from open to `submitted` or `declined` with no sign-off step in between. Distinct from *Bidder* (who prices the RFP) and *Admin* (who manages the system).

### Ariba Portal
SAP's e-procurement platform (`service.ariba.com`). Bahra has **one Ariba supplier account**; the automation signs in to it with a single service login and downloads published RFPs. See *Buyer* for how the different customer organisations relate to that one account.

### Bahra Cables / Bahra Electric
The customer organization (Saudi-based cable manufacturer) for whom this RFP automation system is built. Internal SharePoint host: `bahracables.sharepoint.com`.

### Bid / Bid Response
A Bidder's commercial answer to an RFP — typically containing unit price, lead time, currency, and remarks for each requested material line item. Stored in the RFP Response table.

### Bidder
A user role authorized to view assigned RFPs, download attachments, and submit bid responses (price, lead time, decline reasons). Default role granted to most operational users. See [RBAC Permissions Matrix](../03-operations/11-RBAC-Permissions-Matrix.md).

### BOQ — Bill of Quantities
A structured list (usually Excel or PDF) inside an RFP attachment that itemizes every material the buyer wants quoted: description, quantity, unit, and sometimes specifications. The matching engine extracts BOQ rows and aligns them with internal Material Master entries.

### Buyer
The customer organisation that issues an RFP. All four buyers live **inside Bahra's single Ariba supplier account** and are switched between using Ariba's company selector (a "more…" dropdown) — they are *not* separate portals, separate logins, or separate integrations. Listed in `COMPANY_OPTIONS` ([config/config.py](../../backend/config/config.py)):

- **Saudi Energy** (the default)
- **Aramco e-Marketplace**
- **HADEED - RAJHI STEEL**
- **Saudi Aramco Mobil Refinery Company Limited**

The portal UI shows short labels (`SEC`, `Aramco`, `HADEED`); the backend maps these to the canonical Ariba names via `COMPANY_ALIASES`.

### Cron Schedule
A time-based recurrence pattern that defines when the automation polls Ariba for new RFPs. **The live schedule now runs as Windows Scheduled Tasks on the application server** (registered by `scripts/Register-RfpSchedules.ps1`), not from the portal. The portal's Schedule & Automation dialog still writes to the retired Power Automate flow and **no longer changes the real cadence** — see [Operations Runbook](../03-operations/10-Operations-Runbook.md).

### Decline / Declined
The action a Bidder takes when they choose **not** to bid on an RFP. Captures a reason and removes the RFP from the active worklist. One of the four valid RFP statuses (`no`, `saved_draft`, `submitted`, `declined`).

### Delegate
Handing one product line of an RFP to a different recipient — done from the **Open RFP** page and requires `rfp.open.delegate`. The delegated line shows who it went to, who delegated it, and when; the original recipient stops being chased for it.

### Keyword / Keyword Master
The list of product terms used by tier 2 of *Material Matching* — when a BOQ line has no 9-digit SAP code, the system compares these keywords against the line's Name and Description. Maintained via **Master Data → Keywords**. Adding a keyword is the supported way to make a commonly-quoted item start matching.

### Match %
Shown per RFP on the Dashboard. It is **coverage, not confidence**: the share of that RFP's BOQ lines that matched a Material Master entry at all (matched lines ÷ total lines). A low Match % means more lines need manual attention — it does not mean the matches that *were* found are weak.

### Material Code
The unique SAP identifier for an item Bahra Electric sells (e.g., a specific cable type and gauge). Stored in the Material Master table; used by the matching engine to link BOQ line items to internal SKUs.

### Material Master
The reference catalog of all SAP-known materials Bahra Electric can supply. Source of truth for the matching engine.

### Material Matching
The process that links each BOQ line to a Material Master entry. It works in **two tiers, in order**:

1. **Exact code match.** If the BOQ line contains a 9-digit SAP material code, the system looks for that exact code in the Material Master. An identical string is a match; anything else is not. Result label: **Exact**.
2. **Keyword match.** Only if tier 1 finds nothing. The system splits the line's Name and Description into keywords and looks for a Material Master keyword that is contained in one of them (or contains one of them). Result label: **Keyword**.

If neither tier hits, the line is left **unmatched** for a human to handle.

Two things this is **not**:

- **It is not fuzzy matching.** There is no similarity score, no confidence percentage, and no tunable threshold. A line either satisfies one of the two rules or it does not.
- **It does not pick a "best" match.** When keyword matching finds several candidate materials, the system takes the **first row it encounters** — it does not rank them. Keyword matching is deliberately broad, so a short keyword can pull in a loosely related material. Treat a **Keyword** result as a suggestion to check, and an **Exact** result as reliable.

The practical lever for improving matching is **data, not settings**: keep the Material Master aligned with SAP and add Keyword Master entries for terms buyers actually use.

Implementation: `process_folder` in [rfp/download_rfp.py](../../backend/rfp/download_rfp.py). Reference data is loaded from Dataverse (with a SharePoint CSV fallback) by [services/master_data_service.py](../../backend/services/master_data_service.py).

### RFP — Request for Proposal
A formal procurement document issued by a buyer asking suppliers to quote pricing, lead time, and terms for a list of materials. The unit of work this entire system revolves around.

### RFP Insights
The searchable list of every RFP, with filters (status, company, date range, free-text search, material/keyword match, participation), count tiles across the top, and CSV / Excel / full-analysis exports. Frontend page: [rfp-insights.tsx](../../frontend/src/pages/rfp-insights.tsx). Requires `rfp.view`.

### RFP Status
The lifecycle state of an RFP for a given Bidder. Valid values:
- `no` — not yet acted on
- `saved_draft` — partial response saved, not yet submitted
- `submitted` — bid response sent
- `declined` — Bidder explicitly declined to bid

Defined in `VALID_RFP_STATUSES` in [config/config.py](../../backend/config/config.py).

### RFP Team
The mapping of products (e.g., "Cables", "Wires") to the specific Bidders/emails responsible for those product lines. Stored in the RFP Team table; drives email routing.

### Saved Draft
A Bidder's in-progress bid that has been saved but not yet submitted. The Bidder can return later and complete it.

### SEC — Saudi Electricity Company
The primary buyer, shown in the portal UI as **SEC**. Inside Ariba the organisation is named **Saudi Energy**, which is the default value of `COMPANY_NAME` in [config/config.py](../../backend/config/config.py).

### Submission
A completed bid response that has been sent (state: `submitted`). Triggers downstream notifications.

Adaptive-card responses are **first-response-wins per team row**: once someone answers a given product line, that line is settled and a later answer from a colleague on the same line is not applied.

### TDS — Technical Data Sheet
Product datasheet PDFs attached to bid responses to document technical specs of the offered material. Stored in SharePoint at `RFP-logs/TDS-files/`.

---

## B. Technical Terms

### Adaptive Card
A platform-agnostic JSON UI format from Microsoft used to render interactive content inside Outlook, Teams, and other hosts. The actionable email cards (decline/submit-from-email) are Adaptive Cards.

### Audit Log
An append-only Dataverse table (`cr673_bahra_audit_logs`) capturing who did what and when. It covers **authentication, user lifecycle, role changes, master-data changes, and system-setting edits** (including an entry every time a masked secret is revealed). It does **not** currently record RFP operations — downloads, submissions, declines, reminders, and delegations are not written to the audit log. To reconstruct RFP activity, use the **Activity Logs** page instead.

### Azure AD — Microsoft Entra ID
The identity provider for both portal users and service-to-service authentication. Tenant ID + Client ID + Client Secret in `config.py` authorize the backend to call Microsoft Graph and Dataverse.

### Cache TTL — Time-To-Live
How long a cached value stays valid before being re-fetched. Examples in this project:
- `RBAC_CACHE_TTL_SECONDS = 300` (5 min)
- `DASHBOARD_TTL_SECONDS = 300` (5 min)

### Cloud Flow
A workflow built in Microsoft Power Automate that runs in the cloud (vs. desktop flows). Historically the flow `Bahra-E-binding-cron-job` triggered the RFP download on a schedule. **That flow is retired** — the download and portal-sync schedules now run as Windows Scheduled Tasks on the application server.

### Dataverse
Microsoft's low-code business database (formerly "Common Data Service" / "CDS"). Hosts every table this system uses. Accessed via the OData Web API at `https://operations-bahrauat-1.crm11.dynamics.com` (note: a **UAT** organisation is configured as the default — confirm this is intended before relying on it for production reporting).

### EntitySetName
The plural form of a Dataverse table's logical name, used in OData URLs. **Dataverse's pluralisation is not predictable** — it sometimes appends `es`, sometimes `s`, sometimes reshapes the ending (`cr673_bahra_roles` → `cr673_bahra_roleses`, but `cr673_bahra_rfp_reminder_for_info` → `cr673_bahra_rfp_reminder_for_infos`, and `cr673_bahra_user_status` → `cr673_bahra_user_statuses`). Never guess — always confirm via `EntityDefinitions(LogicalName='...')?$select=EntitySetName`.

### FastAPI
The Python web framework powering the backend (`dashboard_main.py`, `automation_main.py`). Provides automatic OpenAPI docs at `/docs` (per-endpoint schema, request/response examples).

### Idle Timeout
**Not enforced.** `IDLE_TIMEOUT_SECONDS = 1800` exists in `config.py` but no code reads it, so sitting idle never signs you out. The only timeout that takes effect is *Session Timeout* — a flat 2 hours from login. The name is misleading; do not rely on an idle timeout for security.

### Logical Name
The internal schema name of a Dataverse entity or column (e.g., `cr673_bahra_roles`). Used for metadata operations; the API plural (EntitySetName) is used for CRUD.

### MetadataId
The GUID Dataverse assigns to each entity definition. Required for adding/modifying columns. Can become stale during column operations — re-fetch on HTTP 404.

### Microsoft Graph
The unified Microsoft 365 REST API. This system uses it for SharePoint file operations and email sending via the configured app registration's `https://graph.microsoft.com/.default` scope.

### OData
The REST query protocol Dataverse exposes (`$select`, `$filter`, `$expand`, `$top`). All Dataverse calls in [helpers/dataverse_helper.py](../../backend/helpers/dataverse_helper.py) use OData.

### Originator ID
A trusted-sender GUID Microsoft assigns when registering an Actionable Message provider. Embedded in every actionable card so Outlook will render it as interactive (not just a static image).

### Power Automate
Microsoft's no-code workflow engine. Its remaining live use in this system is the **Forgot Password flow**, which sends password-reset emails. The recurrence flows that used to drive the RFP download and portal sync have been replaced by Windows Scheduled Tasks — see *Cron Schedule*.

### Publisher Prefix
The 5–8 char namespace prefix on all custom Dataverse objects in a solution. This project uses `cr673_` (e.g., `cr673_bahra_users`).

### RBAC — Role-Based Access Control
The pattern where users are assigned Roles, Roles bundle Permissions, and the app checks `useHasPermission("rfp.submit")`-style calls before allowing actions. See [RBAC Permissions Matrix](../03-operations/11-RBAC-Permissions-Matrix.md).

### Recurrence Trigger
The Power Automate action that fires a flow on a fixed cadence (every X minutes/hours/days). The portal's Schedule & Automation dialog still patches this trigger on the retired download flow — which is why saving a schedule there reports success but changes nothing that actually runs.

### Scheduled Task
The Windows Task Scheduler entry that now drives automation on the application server. Two tasks live under the `\Bahra-RFP\` folder — `RFP-Download-OpenRFPs` and `RFP-Sync-Portal` — registered by `scripts/Register-RfpSchedules.ps1`. Times are **server-local (Riyadh)**. Changing the schedule means editing these tasks on the server, not the portal.

### Session Timeout
Absolute lifetime of a user session, counted **from login and unaffected by activity** (`SESSION_TIMEOUT_SECONDS = 7200` = 2 hours). Two hours after you sign in you are signed out and must log in again, even if you were working the whole time. See also *Idle Timeout*.

### SharePoint
Microsoft's document collaboration platform. Hosts RFP files, automation error logs, and TDS files at `bahracables.sharepoint.com/sites/LiveSite/RFPAutomation`.

### System Settings
Dataverse-stored configuration that operations staff can change without a code deploy — e.g., email recipient lists, notification toggles. Distinct from `config.py`, which holds developer-managed settings.

### Workflow ID
The Dataverse GUID of a Power Automate flow (different from the flow's display name). Resolved by name lookup against the `workflow` table or hard-coded via `POWER_AUTOMATE_WORKFLOW_ID`.

---

## C. Acronyms (Quick Reference)

| Acronym | Expansion | Context |
|---|---|---|
| **API** | Application Programming Interface | Backend endpoints documented in [API Documentation](../02-architecture/08-API-Documentation.md) |
| **BOQ** | Bill of Quantities | Itemized material list inside an RFP attachment |
| **BRD** | Business Requirements Document | The "why" of the system — see [01-BRD](01-BRD-Business-Requirements.md) |
| **C4** | Context, Container, Component, Code | Architecture diagramming model used in the SAD |
| **CRUD** | Create, Read, Update, Delete | Standard data operations |
| **CSV** | Comma-Separated Values | File format used for some report exports |
| **DR** | Disaster Recovery | Covered in [Security & Compliance](../03-operations/12-Security-and-Compliance.md) |
| **ER** | Entity-Relationship | Diagram type for data model — see [Data Dictionary](../02-architecture/07-Data-Dictionary-and-ER-Diagram.md) |
| **ETL** | Extract, Transform, Load | Pattern used by the RFP ingestion pipeline |
| **FRD** | Functional Requirements Document | Subsumed into the SRS in this project |
| **GUID** | Globally Unique Identifier | Used for Dataverse record IDs, MetadataId, Workflow ID |
| **HLD** | High Level Design | Module-level architecture — see [05-HLD](../02-architecture/05-HLD-High-Level-Design.md) |
| **HTTP** | HyperText Transfer Protocol | All Dataverse and portal traffic |
| **JSON** | JavaScript Object Notation | Wire format for API and Adaptive Cards |
| **JWT** | JSON Web Token | (Future) bearer token format for API auth |
| **KPI** | Key Performance Indicator | Tracked in [BRD](01-BRD-Business-Requirements.md) success metrics |
| **LLD** | Low Level Design | Class/function-level design — see [06-LLD](../02-architecture/06-LLD-Low-Level-Design.md) |
| **LSZH** | Low Smoke Zero Halogen | Cable insulation type often appearing in BOQs |
| **MDY** | Month-Day-Year | Date format used everywhere in the system (`2/23/2026 8:10 PM`) |
| **MFA** | Multi-Factor Authentication | Not used for portal login (email + password); the Ariba service account is deliberately MFA-exempt so the automation can sign in unattended |
| **MS** | Microsoft | Azure, Graph, Dataverse, SharePoint, Power Automate |
| **OData** | Open Data Protocol | Query syntax for Dataverse Web API |
| **PDF** | Portable Document Format | Common RFP attachment type |
| **RBAC** | Role-Based Access Control | The auth model — see [11-RBAC Matrix](../03-operations/11-RBAC-Permissions-Matrix.md) |
| **REST** | Representational State Transfer | API style used for FastAPI and Dataverse |
| **RFP** | Request for Proposal | The central business object |
| **SAD** | Software Architecture Document | The big picture — see [04-SAD](../02-architecture/04-SAD-Software-Architecture-Document.md) |
| **SAP** | Systems, Applications & Products (in Data Processing) | Bahra's ERP — source of Material Master |
| **SDK** | Software Development Kit | Generic — none specific to this project |
| **SEC** | Saudi Electricity Company | Primary RFP buyer |
| **SKU** | Stock Keeping Unit | Synonym for Material Code |
| **SLA** | Service Level Agreement | Operational commitments — see [Operations Runbook](../03-operations/10-Operations-Runbook.md) |
| **SP** | SharePoint | File storage |
| **SRS** | Software Requirements Specification | Functional + non-functional requirements — see [02-SRS](02-SRS-Software-Requirements-Specification.md) |
| **TDS** | Technical Data Sheet | Product datasheet PDF |
| **TTL** | Time-To-Live | Cache freshness duration |
| **UAT** | User Acceptance Testing | Pre-prod validation phase |
| **UI** | User Interface | The React frontend |
| **URL** | Uniform Resource Locator | Web address |
| **UX** | User Experience | Interaction design quality |
| **YAML** | YAML Ain't Markup Language | Format used for doc frontmatter |

---

## D. System Roles

Two roles are seeded, both marked `is_system: true`:

| Role | Description | Permission Set | Source |
|---|---|---|---|
| **Admin** | Full system access | **All 42 permissions** (computed as every key in `PERMISSIONS`, so it stays complete as permissions are added) | `services/permission_definitions.py` → `DEFAULT_ROLES["Admin"]` |
| **RFP Bidder** | Can view and work with RFPs, restricted from admin features | **Exactly these 10:** `rfp.view`, `rfp.download`, `rfp.submit`, `rfp.decline`, `rfp.open.view`, `rfp.open.delegate`, `rfp.sharepoint.view`, `dashboard.view`, `logs.view`, `material_insights.view` | `services/permission_definitions.py` → `DEFAULT_ROLES["RFP Bidder"]` |
| **Custom roles** | Created via the portal's Role Management page | Any subset of the 42 permissions | Stored in `cr673_bahra_roles` |

Note that **RFP Bidder does not include `rfp.open.remind`** (sending reminders) or `analytics.view` — grant those through a custom role if a bidder needs them.

There is **no Approver role** — see *Approver* in section A.

The Admin role cannot be permanently deleted from the portal, and **must not be renamed**: some checks match the literal role name `Admin`, so renaming it silently breaks admin access.

---

## E. Permission Vocabulary

There are **42 permissions**. Each follows a strict naming pattern: **`module.action`** (lowercase, dot-separated, snake_case).

Two groupings of the same 42 keys exist in the code. The table below is the **backend module namespace** (`MODULE_LABELS`) — the prefix you see in a permission key. The **Role Management screen** groups the same keys differently, by where they appear in the UI (Sidebar Menus · RFP Operations · User Management · Role Management · Master Data · System Settings · SAP Password). If a label in the portal doesn't match this table, that is why.

### Modules

| Module Key | Display Label |
|---|---|
| `analytics` | Analytics |
| `audit_logs` | Audit Trail |
| `column_config` | Column Configuration |
| `dashboard` | Dashboard |
| `keyword_master` | Keyword Master |
| `logs` | Activity Logs |
| `material_insights` | Material Insights |
| `material_master` | Material Master |
| `rfp` | RFP Operations |
| `rfp_team` | RFP Team |
| `role_management` | Role Management |
| `sap_password` | SAP Password |
| `schedule_automation` | Schedule & Automation |
| `system_settings` | System Settings |
| `user_management` | User Management |

### Actions

| Action | Meaning |
|---|---|
| `view` | Read-only access — list, detail, search |
| `create` | Add a new record |
| `edit` | Modify an existing record |
| `delete` | Remove a record |
| `manage` | Combined create/edit/delete (used where granular split adds no value, e.g. `schedule_automation.manage`) |
| `download` | Pull RFP attachments to local machine |
| `submit` | Send a finalized bid |
| `decline` | Mark an RFP as declined |
| `change` | Domain-specific mutation (e.g., `sap_password.change`) |
| `remind` | Send a reminder to a non-responding recipient (`rfp.open.remind`) |
| `delegate` | Hand a product line to another recipient (`rfp.open.delegate`) |

**Permission changes take effect only after the affected user signs out and back in.** Permissions are read from the session, which is fixed at login — editing a role does not update anyone who is already signed in.

Full list of all 42 permissions: see [services/permission_definitions.py](../../backend/services/permission_definitions.py) and [11-RBAC Permissions Matrix](../03-operations/11-RBAC-Permissions-Matrix.md).

---

## F. Naming Conventions

### Dataverse

| Object | Convention | Example |
|---|---|---|
| Table logical name | `cr673_bahra_<entity_name>` (snake_case, singular or plural-as-stored) | `cr673_bahra_users` |
| Table API plural (EntitySetName) | Assigned by Dataverse — **not derivable**; look it up, never guess | `cr673_bahra_userses` |
| Column logical name | `cr673_<column_name>` | `cr673_status`, `cr673_email` |

### Code

| Item | Convention | Example |
|---|---|---|
| Python files | `snake_case.py` | `dataverse_helper.py` |
| Python classes | `PascalCase` | `DataverseClient` |
| Python functions | `snake_case` | `seed_default_roles()` |
| Python constants | `UPPER_SNAKE_CASE` | `SESSION_TIMEOUT_SECONDS` |
| TypeScript components | `PascalCase` | `ScheduleDialog` |
| TypeScript hooks | `useCamelCase` | `useHasPermission` |
| Frontend files | `kebab-case.tsx` | `schedule-dialog.tsx` |

### Documentation

| Item | Convention | Example |
|---|---|---|
| Doc filename | `NN-Title-In-Kebab-Case.md` | `04-SAD-Software-Architecture-Document.md` |
| Heading style | Sentence case | "Software architecture document" |
| Voice (user manuals) | Second person ("you click...") | "You'll see the dashboard" |
| Voice (technical docs) | Third person | "The matching engine returns…" |
| Cross-links | Relative markdown paths | `[link](../03-operations/09-Deployment-Guide.md)` |

### Dates

- **Display & storage:** MDY format with no leading zeros — `2/23/2026 8:10 PM`
- **Python format string (Windows):** `%#m/%#d/%Y %#I:%M %p`
- **YAML frontmatter `last_updated`:** ISO 8601 — `2026-07-17`

---

## Adding a New Term

When you encounter or coin a term not in this glossary:

1. Decide which section it belongs to (A–F).
2. Insert it **alphabetically** within that section.
3. Use this entry template:
   ```
   ### Term Name
   One-sentence definition. Optional second sentence with context, links, or examples.
   ```
4. Bump this file's `version` and `last_updated` in the frontmatter.
5. If the term applies to other docs, link to it from there.
