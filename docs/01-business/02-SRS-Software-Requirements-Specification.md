---
title: Software Requirements Specification (SRS) — Bahra Electric RFP Automation
version: 1.2
last_updated: 2026-07-17
owner: Manish Soni (Manish.soni@dynatechconsultancy.com)
audience: Developers, QA, Product owners, Auditors
status: Draft
---

# Software Requirements Specification (SRS)

Detailed functional and non-functional requirements. Where the [BRD](01-BRD-Business-Requirements.md) asks *why*, this document answers *what*. Implementation (*how*) lives in the [HLD](../02-architecture/05-HLD-High-Level-Design.md) / [LLD](../02-architecture/06-LLD-Low-Level-Design.md).

Related: [API](../02-architecture/08-API-Documentation.md) · [Data Dictionary](../02-architecture/07-Data-Dictionary-and-ER-Diagram.md) · [RBAC Matrix](../03-operations/11-RBAC-Permissions-Matrix.md) · [Glossary](03-Glossary-and-Acronyms.md)

---

## 1. Introduction

### 1.1 Purpose

This SRS defines the software requirements for the Bahra Electric RFP Automation Portal. It is the contract between business stakeholders (what the system must do) and the engineering team (what must be built and tested).

### 1.2 Conventions

- **MUST / SHALL** — mandatory requirement
- **SHOULD** — strongly recommended
- **MAY** — optional / future
- Requirement IDs: `FR-nn` (functional), `NFR-nn` (non-functional), `UC-nn` (use case), `DR-nn` (data)
- Cross-references: every requirement links to the artifact that implements or tests it

### 1.3 Document structure

- §2 Overall description
- §3 Users & roles
- §4 Functional requirements
- §5 Use cases (narrative)
- §6 Data requirements
- §7 External interfaces
- §8 Non-functional requirements
- §9 Assumptions & dependencies

---

## 2. Overall description

### 2.1 Product perspective

A new system, integrated with existing Bahra infrastructure: Azure AD, Microsoft 365 (Exchange, SharePoint, Power Automate), and Dataverse. It replaces ad-hoc Excel / Outlook workflows for RFP handling.

### 2.2 Product features (high-level)

- RFP ingestion from Bahra's **single** Ariba supplier account (scheduled Playwright scrape). The four buyer organisations — Saudi Energy, Aramco e-Marketplace, HADEED - RAJHI STEEL, Saudi Aramco Mobil Refinery — are selected within that one account via Ariba's company selector, not through separate portals or integrations.
- BOQ (Bill of Quantities) parsing and deterministic two-tier material matching
- Role-based user portal (42 permissions)
- Outlook-integrated response capture via adaptive cards
- Reporting and audit

### 2.3 Operating environment

| Component | Requirement |
|---|---|
| Server OS | Windows Server (production runs Windows Server 2016) or Windows 11 Enterprise for development |
| Runtime | Python 3.10, Node 20 LTS |
| Data store | Microsoft Dataverse (cloud) |
| Browser | Chrome latest version |
| Email client for adaptive cards | Outlook Web / Desktop with actionable-messages enabled |

### 2.4 Design & implementation constraints

This section lists non-negotiable limits that bound any design. Actual design decisions live in the [HLD](../02-architecture/05-HLD-High-Level-Design.md) / [LLD](../02-architecture/06-LLD-Low-Level-Design.md).

- All business data at rest in Microsoft Dataverse (no separate SQL / NoSQL store)
- Integration via HTTPS only (TLS 1.2 minimum)
- Deployment target is a single Windows host (both FastAPI processes + Playwright)
- Runtime versions fixed at Python 3.10 and Node 20 LTS
- Frontend must be compatible with Outlook actionable-messages (Office 365)
- Dataverse API rate limits govern bulk-write strategy (retry + pagination required)
- No client installation required for end users
- UI strings in English only

---

## 3. Users & roles

Full role × permission grid is in [RBAC Matrix](../03-operations/11-RBAC-Permissions-Matrix.md). Summary:

| Role | Seeded | Main capabilities |
|---|---|---|
| Admin | Yes | All **42** permissions |
| RFP Bidder | Yes | View & respond to assigned RFPs — exactly **10** permissions: `rfp.view`, `rfp.download`, `rfp.submit`, `rfp.decline`, `rfp.open.view`, `rfp.open.delegate`, `rfp.sharepoint.view`, `dashboard.view`, `logs.view`, `material_insights.view` |

Both are system roles (`is_system: true`). There is no Approver role and no approval workflow — an RFP moves from open to `submitted` or `declined` with no sign-off step.

Additional roles may be created by Admins at runtime via the Role Management UI using the permission catalogue in [services/permission_definitions.py](../../backend/services/permission_definitions.py).

---

## 4. Functional requirements

### 4.1 Authentication & session

| ID | Requirement |
|---|---|
| FR-01 | The system SHALL authenticate users via email + password against `cr673_bahra_users`. |
| FR-02 | Passwords SHALL be stored as bcrypt hashes (cost factor ≥ 12). **⚠️ Security gap:** the current implementation compares passwords in plaintext ([services/user_service.py:197-213](../../backend/services/user_service.py#L197-L213)) — remediation is tracked in [Security & Compliance](../03-operations/12-Security-and-Compliance.md). |
| FR-03 | Successful login SHALL create a session that expires **2 hours after login regardless of activity**. **⚠️ Gap:** `IDLE_TIMEOUT_SECONDS`, `SESSION_WARNING_SECONDS`, and `SESSION_REFRESH_INTERVAL` exist in `config.py` but are read by no code — there is **no idle timeout**, only the flat 2-hour absolute expiry. Either implement the idle timeout or remove the misleading settings. |
| FR-04 | The system SHALL support a *forgot password* flow that emails a one-time token via Power Automate. **The token currently expires after 30 minutes**, not 24 hours. |
| FR-05 | The system SHALL rate-limit login for an email / IP after 5 consecutive failed attempts within a 5-minute window, responding `429` until the window clears. This lock is held in the API process's memory: it releases itself after the window and is lost on service restart. |
| FR-06 | An admin SHALL be able to unlock a locked account. **⚠️ Gap:** the Dataverse-backed account lock (`record_failed_login`, 5 attempts → 30-minute lock) is implemented but **never called from the login path**, so failed logins never set it. The Unlock control only clears a lock set some other way; the rate limit in FR-05 is what users actually hit, and it needs no admin action. |
| FR-07 | The system SHALL allow users to change their own password, re-requiring the current password. |

### 4.2 Authorization (RBAC)

| ID | Requirement |
|---|---|
| FR-10 | The system SHALL maintain a catalogue of permissions as defined in [permission_definitions.py](../../backend/services/permission_definitions.py). It currently holds **42** keys. |
| FR-11 | The system SHALL allow admins to create, edit, and delete non-system roles. |
| FR-12 | The system SHALL NOT allow deleting or renaming the `Admin` role. Renaming would break access: `require_admin` matches the literal role name `Admin`. |
| FR-13 | Each user SHALL be assigned exactly one role. |
| FR-14 | Every HTTP endpoint that mutates data SHALL check the relevant permission server-side. **⚠️ Gap:** the 10 automation endpoints (`/api/download-rfps-automation`, `/api/sync_portal_data`, and siblings) currently have **no authentication or permission check** at all. |
| FR-15 | The frontend SHALL hide UI controls for which the user lacks permission (UX-only). Frontend checks are cosmetic — permissions are persisted to `localStorage`, so a user can unhide UI locally; the server-side check in FR-14 is the real gate. |
| FR-16 | A permission or role change SHALL take effect for the affected user on their next login. Permissions are copied into the session at login and are **not** re-read afterwards, so a signed-in user keeps their old permissions until they sign out and back in. |

### 4.3 RFP ingestion

| ID | Requirement |
|---|---|
| FR-20 | The system SHALL scrape Bahra's Ariba supplier account on a schedule and download new RFPs for each of the four configured buyer organisations, switching between them via Ariba's company selector within the same session. The live schedule is a **Windows Scheduled Task** (`RFP-Download-OpenRFPs`, daily at 00:00 / 06:00 / 12:00 / 18:00 Riyadh) that calls `GET /api/download-rfps-automation` on localhost; the Power Automate trigger that previously did this is retired. |
| FR-21 | On ingest, the system SHALL create or upsert a row in `cr673_bahra_rfps_v2` with `source`, `customer`, `received_date`, and a reference to the BOQ artifact. |
| FR-22 | The system SHALL deduplicate by RFP ID + customer — re-ingesting the same file SHALL update, not duplicate. |
| FR-23 | The system SHALL log each ingest run to `cr673_bahra_automation_log1` with status and counts. |

### 4.4 BOQ parsing

| ID | Requirement |
|---|---|
| FR-30 | The system SHALL parse BOQ line items from the downloaded XLSX documents. |
| FR-31 | The parser SHALL produce a list of `{code, description, qty, uom}` tuples preserving original order. |
| FR-32 | The parser SHALL tolerate merged cells, header rows, and footer notes. |

### 4.5 Material matching

| ID | Requirement |
|---|---|
| FR-40 | The matching engine SHALL attempt an exact match on the 9-digit SAP material code first (string equality), and fall back to bidirectional substring keyword containment on the material name / description when the exact match misses. Implementation: `process_folder` in [rfp/download_rfp.py](../../backend/rfp/download_rfp.py). |
| FR-41 | The matching engine SHALL be **deterministic**: no similarity score, no confidence value, and no configurable threshold. Match quality is tuned through Material Master and Keyword Master **data**, not through settings. |
| FR-42 | Each matched line SHALL be labelled with the tier that matched it — `exact` or `keyword` — or left unmatched. This label is a category, not a score, and SHALL be surfaced to users as such. |
| FR-43 | Where keyword matching yields multiple candidate materials, the engine currently selects the **first candidate encountered** with no ranking or tie-break. **⚠️ Known limitation:** a broad keyword can therefore attach a loosely-related material. Any future ranking work belongs here. |
| FR-44 | Reference data SHALL be loaded from Dataverse with a SharePoint CSV fallback (`material.csv`, `unique_keywords.csv`) and cached for 5 minutes ([services/master_data_service.py](../../backend/services/master_data_service.py)). |
| FR-45 | The matching result SHALL persist on `cr673_bahra_rfps_v2.Matched_Data` as JSON with per-line match details. |

### 4.6 Bidder assignment & notification

| ID | Requirement |
|---|---|
| FR-50 | The system SHALL assign bidders to RFPs based on `cr673_bahra_rfp_team` rules (by customer, material category, or manual). |
| FR-51 | On assignment, the system SHALL send one adaptive-card email per bidder with the relevant line items. |
| FR-52 | The adaptive-card email SHALL support a *Submit* and a *Decline* action that posts back to the system. |
| FR-53 | The system SHALL send deadline-based reminder emails 3 days before the RFP due date and again 1 day before, using the `Reminder_3Day_Sent` / `Reminder_1Day_Sent` flags to prevent duplicate sends. **⚠️ Not currently firing:** the logic exists (`rfp/rfp_reminder.py`, reachable at `/api/rfp-reminder`) but nothing schedules it — the Power Automate flow that used to call it points at a retired endpoint and no scheduled task has replaced it. See [Operations Runbook](../03-operations/10-Operations-Runbook.md). |
| FR-54 | Reminders SHALL respect the per-RFP deadline field; none SHALL be sent after the deadline. |
| FR-55 | An authorised user (`rfp.open.remind`) SHALL be able to send an on-demand reminder to a specific non-responding recipient, or to all pending recipients, from the Open RFP page. This path works today and is the interim substitute for FR-53. |
| FR-56 | An authorised user (`rfp.open.delegate`) SHALL be able to reassign a single product line of an RFP to a different recipient, recording who delegated it, to whom, and when. |

### 4.7 Response capture

| ID | Requirement |
|---|---|
| FR-60 | A bidder SHALL be able to enter their response (price, lead time, and any configured fields) on the adaptive card in Outlook and send it with *Submit All Responses*, or reject the RFP with *Decline RFP*. |
| FR-61 | The card SHALL apply **first-response-wins per team row**: once a product line has a response, a later response on that same line is not applied. |
| FR-62 | The fields shown on the card SHALL be driven by active rows in `cr673_bahra_rfp_team_columns`, so the response shape is configurable without a code change. |
| FR-63 | The system SHALL verify every card callback before acting on it: token signature against the tenant's JWKS, expected audience, an accepted issuer (v1.0 or v2.0), and Microsoft's Actions app as the authorised party. |
| FR-64 | An authorised user (`rfp.submit`) SHALL be able to push a completed response back to Ariba from the portal by supplying the RFP ID, the buyer organisation, the filled Excel workbook, and optional technical PDFs; the system SHALL drive the Ariba submission wizard on their behalf. |
| FR-65 | An authorised user (`rfp.decline`) SHALL be able to decline an RFP on Ariba from the portal by selecting the RFP and its buyer organisation. |
| FR-66 | On successful submission, the system SHALL persist the response and update the RFP status on `cr673_bahra_rfps_v2` to one of `no`, `saved_draft`, `submitted`, `declined`. |

### 4.8 Dashboard & reporting

| ID | Requirement |
|---|---|
| FR-70 | The dashboard home SHALL show KPI tiles: total RFPs, open, submitted, declined, by customer. |
| FR-71 | The dashboard SHALL support filtering by date range, customer, status, bidder. |
| FR-72 | The dashboard SHALL provide a material-insights view grouped by company. |
| FR-73 | The user SHALL be able to export any filtered RFP list as XLSX. |

### 4.9 Master data management

| ID | Requirement |
|---|---|
| FR-80 | An authorised user SHALL be able to CRUD material-master rows. |
| FR-81 | An authorised user SHALL be able to CRUD keyword rows. |
| FR-82 | An authorised user SHALL be able to CRUD RFP-team (bidder) rows. |
| FR-83 | An authorised user SHALL be able to CRUD dynamic form columns. |
| FR-84 | The material, keyword, and RFP-team master-data tables SHALL support bulk import from CSV or XLSX with row-level error reports. |

### 4.10 System settings

| ID | Requirement |
|---|---|
| FR-90 | An authorised user SHALL be able to view and edit system settings via `/api/system-settings`. |
| FR-91 | Sensitive settings SHALL be masked in the list view and revealed only via an audited endpoint. |
| FR-92 | Setting changes SHALL invalidate the in-process cache (dashboard, SAP logs, materials) on write. |

### 4.11 Audit logging

| ID | Requirement |
|---|---|
| FR-100 | Every mutating action SHALL produce one row in `cr673_bahra_audit_logs`. |
| FR-101 | Audit rows SHALL be append-only; no user SHALL be able to edit or delete them via any endpoint. |
| FR-102 | Each audit row SHALL capture: user, action, module, details (JSON), IP, timestamp. |
| FR-103 | An authorised user SHALL be able to search, filter, and export audit rows. |

### 4.12 Scheduling

The automation schedule has moved to Windows Scheduled Tasks on the application server (`RFP-Download-OpenRFPs` at 00:00/06:00/12:00/18:00 and `RFP-Sync-Portal` at 03:00/09:00/15:00/21:00, Riyadh time, registered by `scripts/Register-RfpSchedules.ps1`). The requirements below describe the portal screen, which has **not** caught up.

| ID | Requirement |
|---|---|
| FR-110 | An authorised user (`schedule_automation.manage`) SHALL be able to configure the automation schedule via the UI. |
| FR-111 | The UI SHALL persist the schedule to Dataverse and push it to Power Automate (Recurrence trigger patch). **⚠️ Obsolete as implemented:** it patches `Bahra-E-binding-cron-job`, the very flow the migration turns off. The screen saves, reports success, and changes nothing that runs. If that flow is ever re-enabled, downloads fire from both it and the scheduled task. |
| FR-112 | A schedule change SHALL be audited with before/after values. |
| FR-113 | The schedule screen SHALL drive whatever mechanism actually runs the automation. **Not met** — resolving FR-111 means either repointing this screen at Task Scheduler or removing it in favour of the server-side runbook. |

---

## 5. Use cases (narrative)

### UC-01 — Bidder responds to an adaptive-card RFP

**Actor:** Bidder (Basim)
**Pre:** An adaptive-card email has arrived in Outlook.
**Main flow:**
1. Basim opens the email. The card auto-refreshes to show the current state of each product line (this call must complete within ~2 s or Outlook abandons it).
2. The card shows RFP metadata and his product lines with blank response fields.
3. Basim fills the fields and clicks *Submit All Responses*.
4. Outlook POSTs to `/api/actionable-card/response` with an Entra-issued token, reaching the system through Entra Application Proxy.
5. The system verifies the token (signature, audience, issuer, authorised party) and records the response.
6. The card updates in place to confirm.
**Post:** The responded lines are settled; the RFP's status reflects the response.
**Alt:** A line already answered by a colleague is not overwritten (first-response-wins). Token invalid → the action fails and the reason is logged server-side.
**Note:** RFP operations are **not** written to the audit log today — use the Activity Logs page to trace them.

### UC-02 — Admin creates a custom role

**Actor:** Admin (Khalid)
**Pre:** Logged in with Admin role.
**Main flow:**
1. Khalid navigates to *Role Management* → *Create Role*.
2. Enters a role name and selects permissions.
3. Submits; system calls `POST /api/roles/create` then `PUT /api/roles/{id}/permissions`.
4. Dataverse rows created; cache invalidated.
**Post:** Role appears in the list. **Users already signed in keep their old permissions until they log out and back in** — permissions are captured in the session at login.
**Alt:** Duplicate name → 409; rename required.

### UC-03 — Bidder pushes a completed response back to Ariba

**Actor:** Bidder
**Pre:** Logged into the portal; has `rfp.submit`; has the buyer's workbook filled in.
**Main flow:**
1. Clicks *Submit RFP* in the sidebar.
2. Picks the RFP ID and the buyer organisation, and uploads the filled Excel workbook (plus optional technical PDFs).
3. Clicks Submit; the request is accepted immediately (`202`) and the work continues in the background.
4. The automation drives the Ariba submission wizard and reports progress.
**Post:** Status = `submitted`; the run appears in Activity Logs.
**Alt:** The RFP ID belongs to a different buyer → the dialog rejects it before starting. Another submit is already running for that RFP → rejected with `409`.

### UC-04 — Automated Ariba scrape

**Actor:** System (Windows Scheduled Task `RFP-Download-OpenRFPs`)
**Pre:** Ariba credentials configured; the `rfp-api` service is running.
**Main flow:**
1. At 00:00 / 06:00 / 12:00 / 18:00 Riyadh time, Task Scheduler runs `scripts/Invoke-RfpAutomation.ps1 -Job download`, which calls `GET /api/download-rfps-automation` on localhost and then polls until the run finishes.
2. The orchestrator launches Chromium (**headed**, not headless), signs in, and works through each buyer organisation via Ariba's company selector.
3. For each new RFP, downloads attachments and creates a `cr673_bahra_rfps_v2` row.
4. Match engine runs; bidders notified via adaptive-card emails.
**Post:** `cr673_bahra_automation_log1` row with counts; RFPs visible in dashboard.
**Alt:** Ariba down or DOM changed → failure artifacts saved to `backend/LOGS/` on the host, uploaded to SharePoint, and mailed to `EMAIL_TO_AUTOMATION_FAILURE`.
**Caution:** The task's exit code says the run **finished**, not that it **succeeded** — a crashed run also exits 0. Judge success from the logs and failure emails, not the Last Run Result.

### UC-05 — Admin changes the automation schedule

**Actor:** Admin
**Pre:** Has `schedule_automation.manage`.
**Current reality:** The *Schedule & Automation* dialog persists to Dataverse and patches the Recurrence trigger of the **retired** `Bahra-E-binding-cron-job` flow, then reports success. **The live schedule does not change.** Changing it today means editing the `\Bahra-RFP\` scheduled tasks on the application server — see [Operations Runbook](../03-operations/10-Operations-Runbook.md). This use case is retained to describe intended behaviour; see FR-113 for the gap.

---

## 6. Data requirements

See [Data Dictionary](../02-architecture/07-Data-Dictionary-and-ER-Diagram.md) for the authoritative schema.

| ID | Requirement |
|---|---|
| DR-01 | All business data SHALL persist in Microsoft Dataverse — no secondary DB. |
| DR-02 | Tables SHALL use the `cr673_bahra_` prefix (publisher customisation), except `cr6db_cr673_bahra_rfp_response` which uses the response-entity prefix. |
| DR-03 | Date columns SHALL store timestamps in `M/D/YYYY h:mm AM/PM` format (project-wide convention; see memory/date-format). |
| DR-04 | JSON payload columns (`Matched_Data`, `response_data`, `extra_data`) SHALL be valid JSON or empty. |
| DR-05 | The audit log table SHALL be append-only in practice (no delete API). |
| DR-06 | The system SHALL NOT store cleartext user passwords anywhere. **⚠️ Security gap:** the current `cr673_bahra_userses` table stores passwords in plaintext; remediation is tracked in [Security & Compliance](../03-operations/12-Security-and-Compliance.md). |
| DR-07 | The system SHALL NOT log Dataverse bearer tokens. |

---

## 7. External interfaces

| ID | Requirement |
|---|---|
| EI-01 | Microsoft Graph `/sendMail` for outbound email (adaptive cards, reminders, notifications). |
| EI-02 | Microsoft Graph `/sites/.../drive` for SharePoint read/write of RFP artifacts and logs. |
| EI-03 | Microsoft Dataverse OData v9.2 for all data I/O. |
| EI-04 | Power Automate Cloud Flow for the forgot-password email. The scheduler flows are retired; automation is triggered by Windows Task Scheduler calling the local API. |
| EI-05 | Ariba supplier account web UI via Playwright / Chromium (one account, four buyer organisations). |
| EI-06 | SAP integration limited to password push via `services/sap_service.py`. |
| EI-07 | Actionable-messages substrate via Outlook (inbound token-signed POST), reaching the system through **Entra Application Proxy** in Passthrough mode. Only `/api/actionable-card/` is published externally; the portal itself stays LAN-only behind IIS. |

All interfaces SHALL use HTTPS with TLS 1.2 minimum.

---

## 8. Non-functional requirements

### 8.1 Performance (targets)

| ID | Requirement |
|---|---|
| NFR-01 | Dashboard API p95 response time SHOULD be ≤ 500 ms for KPI tiles at normal load. |
| NFR-02 | RFP list API p95 SHOULD be ≤ 1 s for 500-row pages. |
| NFR-03 | Login SHOULD complete within 1 s under normal load. |
| NFR-04 | Matching a single BOQ with 50 line items against the material-master SHOULD complete within 3 s. |

### 8.2 Availability

| ID | Requirement |
|---|---|
| NFR-10 | Uptime target: 99.0 % during business hours (Sun–Thu 08:00–18:00 AST). |
| NFR-11 | Planned maintenance windows outside business hours; announce 48 h in advance. |

### 8.3 Security

| ID | Requirement |
|---|---|
| NFR-20 | All secrets SHALL be rotatable without code changes (env var / Key Vault). **Not met:** secrets live in `backend/config/config.py`, an untracked local file on each host (it is git-ignored and has never been committed). There is no secret store and rotation is manual — editing it requires restarting the `rfp-api` service. |
| NFR-21 | Session cookies SHALL be `HttpOnly`, `SameSite=Lax`, and `Secure` in production. |
| NFR-22 | The system SHALL enforce TLS 1.2+ for all inbound and outbound traffic. |
| NFR-23 | Adaptive-card callbacks SHALL verify the inbound token (signature against tenant JWKS, audience, issuer, authorised party). Met — and it fails closed if the expected audience is unconfigured. |
| NFR-25 | The session signing key SHALL be a per-deployment secret. **Not met:** `SessionMiddleware` uses a hardcoded default key, so session cookies are forgeable by anyone with source access. Tracked in `backend/Support-Files/OPTIMIZATION_PLAN.md`. |
| NFR-26 | Endpoints that trigger automation SHALL require authentication. **Not met** — see FR-14. |
| NFR-24 | The system SHALL follow the [Security & Compliance](../03-operations/12-Security-and-Compliance.md) checklist before each production release. |

### 8.4 Usability

| ID | Requirement |
|---|---|
| NFR-30 | New Bidders SHALL be able to complete their first RFP submission unaided within 30 minutes of onboarding. |
| NFR-31 | The UI SHALL be fully keyboard-navigable for primary workflows. |
| NFR-32 | The UI SHALL meet WCAG 2.1 AA for color contrast and focus indicators. |

### 8.5 Auditability

| ID | Requirement |
|---|---|
| NFR-40 | Every state transition of an RFP SHALL be reconstructible from `cr673_bahra_audit_logs`. **Not met:** the audit log covers authentication, user, role, master-data, and system-setting events — **RFP operations are not written to it**. RFP history is currently reconstructible only from the Activity Logs table (`cr673_bahra_rfps_v2`). |
| NFR-41 | Audit data SHALL be retained indefinitely unless Legal approves purge. |
| NFR-42 | An authorised user SHALL be able to export any audit slice as XLSX. |

### 8.6 Compliance

| ID | Requirement |
|---|---|
| NFR-50 | Data SHALL remain within Bahra's M365 tenant region. |
| NFR-51 | User PII SHALL be limited to name, email, phone; no national ID or payroll data. |

---

## 9. Assumptions & dependencies

The items in this section are things the system *needs from outside* to work — they're provided by IT, Microsoft, or the business, not built by the project team. If any of these change or disappear, the system will stop working (or never start). Treat this list as IT Operations' go-live checklist.

- **Microsoft 365 tenant with Dataverse and Power Platform licences.** Every RFP, user, role, audit entry, and setting is stored in Dataverse, and the Ariba cron is driven by Power Automate. If the licences lapse, the system stops working the same day.
- **Shared Outlook mailbox with permission to send email.** IT must provision a shared mailbox and grant the system's Azure AD app `Mail.Send` permission on it. Every adaptive-card email, reminder, and status notification leaves from this mailbox.
- **SharePoint site already set up by IT.** The system writes downloaded RFPs, error logs, and technical data sheets to a SharePoint document library. IT must create the site, the library, and the folder structure before go-live — the system does not create its own storage.
- **A single Ariba supplier account, exempt from MFA.** All four buyer organisations are reached through one account. The scraper signs in automatically on a schedule, so that account cannot have multi-factor authentication (phone prompt / OTP). IT must grant an MFA exemption for this specific service account.
- **Entra ID P1 or P2 licence.** The Outlook Submit/Decline buttons reach the system through Entra Application Proxy, which requires P1/P2. Without it the cards stop working — and the alternative (exposing the system to the internet) is not acceptable.
- **An Application Proxy connector running on the application server.** The backend listens on localhost only, so the connector has to be on the same machine. It is outbound-only — no inbound firewall port and no public IP are needed.
- **TLS certificate from Bahra's certificate authority.** The dashboard must be served over HTTPS at `https://be-aramco-01.bahra-cables.com/rfp`. IT must issue and renew the certificate — the project does not manage its own certificates.
- **Power Automate licence for the forgot-password flow.** The password-reset email is sent by a Power Automate flow. If it is disabled, self-service password reset stops working (the rest of the system is unaffected).

## 10. Out-of-scope (reiterated)

Pulled forward from the BRD: automated pricing, negotiation, full SAP write-back, mobile-native app, external customer login.

## 11. Revision history

Also tracked in [CHANGELOG.md](../CHANGELOG.md). Each SRS change SHOULD increment the top-matter `version` and add a row here.

| Version | Date | Author | Change |
|---|---|---|---|
| 1.2 | 2026-07-17 | Manish Soni | Verified against code; corrected matching description, single Ariba tenant, 42 permissions, known issues |
