---
title: Software Requirements Specification (SRS) — Bahra Electric RFP Automation
version: 1.1
last_updated: 2026-04-23
owner: Samir Tak (samir.tak@dynatechconsultancy.com)
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

- Ariba portal RFP ingestion (scheduled Playwright scrape)
- BOQ (Bill of Quantities) parsing and material matching
- Role-based user portal
- Outlook-integrated response capture via adaptive cards
- Reporting and audit

### 2.3 Operating environment

| Component | Requirement |
|---|---|
| Server OS | Windows Server 2019/2022 or Windows 11 Enterprise |
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
| Admin | Yes | All permissions |
| RFP Bidder | Yes | View & respond to assigned RFPs |

Additional roles may be created by Admins at runtime via the Role Management UI using the permission catalogue in [services/permission_definitions.py](../../services/permission_definitions.py).

---

## 4. Functional requirements

### 4.1 Authentication & session

| ID | Requirement |
|---|---|
| FR-01 | The system SHALL authenticate users via email + password against `cr673_bahra_users`. |
| FR-02 | Passwords SHALL be stored as bcrypt hashes (cost factor ≥ 12). **⚠️ Security gap:** the current implementation compares passwords in plaintext ([services/user_service.py:197-213](../../services/user_service.py#L197-L213)) — remediation is tracked in [Security & Compliance](../03-operations/12-Security-and-Compliance.md). |
| FR-03 | Successful login SHALL create a server-side session with an idle timeout of 30 minutes and an absolute timeout of 2 hours. |
| FR-04 | The system SHALL support a *forgot password* flow that emails a one-time, time-limited token (expiry ≤ 24 h) via Power Automate. |
| FR-05 | The system SHALL lock the login for an email / IP after 5 consecutive failed logins within a 5-minute window. |
| FR-06 | An admin SHALL be able to unlock a locked account. |
| FR-07 | The system SHALL allow users to change their own password, re-requiring the current password. |

### 4.2 Authorization (RBAC)

| ID | Requirement |
|---|---|
| FR-10 | The system SHALL maintain a catalogue of permissions as defined in [permission_definitions.py](../../services/permission_definitions.py). |
| FR-11 | The system SHALL allow admins to create, edit, and delete non-system roles. |
| FR-12 | The system SHALL NOT allow deleting or renaming the `Admin` role. |
| FR-13 | Each user SHALL be assigned exactly one role. |
| FR-14 | Every HTTP endpoint that mutates data SHALL check the relevant permission server-side. |
| FR-15 | The frontend SHALL hide UI controls for which the user lacks permission (UX-only). |

### 4.3 RFP ingestion

| ID | Requirement |
|---|---|
| FR-20 | The system SHALL scrape the Ariba supplier portal on a scheduled cron (Power Automate trigger → `GET /download-rfps-automation`) and download new RFPs for the configured buyer entities. |
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
| FR-40 | The matching engine SHALL attempt an exact match on the 9-digit SAP material code first, and fall back to a substring keyword match on the material name / description when the exact match misses. |
| FR-41 | The matching engine SHALL use the `cr673_bahra_keywords` table to expand tokens before matching. |
| FR-42 | The matching result SHALL persist on `cr673_bahra_rfps_v2.Matched_Data` as JSON with per-line match details. |
| FR-43 | An authorised user SHALL be able to override a match manually via the UI. |

### 4.6 Bidder assignment & notification

| ID | Requirement |
|---|---|
| FR-50 | The system SHALL assign bidders to RFPs based on `cr673_bahra_rfp_team` rules (by customer, material category, or manual). |
| FR-51 | On assignment, the system SHALL send one adaptive-card email per bidder with the relevant line items. |
| FR-52 | The adaptive-card email SHALL support a *Submit* and a *Decline* action that posts back to the system. |
| FR-53 | The system SHALL send deadline-based reminder emails 3 days before the RFP due date and again 1 day before, using the `Reminder_3Day_Sent` / `Reminder_1Day_Sent` flags to prevent duplicate sends. |
| FR-54 | Reminders SHALL respect the per-RFP deadline field; none SHALL be sent after the deadline. |

### 4.7 Response capture

| ID | Requirement |
|---|---|
| FR-60 | A bidder SHALL be able to submit prices via the adaptive card in Outlook. |
| FR-61 | A bidder SHALL be able to submit prices via the dashboard UI. |
| FR-62 | The dynamic response form SHALL be driven by active rows in `cr673_bahra_rfp_team_columns`. |
| FR-63 | The system SHALL validate server-side: required fields, numeric ranges, dropdown values, date formats. |
| FR-64 | On successful submission, the system SHALL persist to `cr6db_cr673_bahra_rfp_response` and update the RFP status on `cr673_bahra_rfps_v2`. |
| FR-65 | The system SHALL record the submission method (`adaptive_card` / `dashboard`) and source email / IP. |

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

| ID | Requirement |
|---|---|
| FR-110 | An authorised user SHALL be able to configure automation schedules (cron-like) via the UI. |
| FR-111 | The UI SHALL persist the schedule to Dataverse and push it to Power Automate (Recurrence trigger patch). |
| FR-112 | A schedule change SHALL be audited with before/after values. |

---

## 5. Use cases (narrative)

### UC-01 — Bidder responds to an adaptive-card RFP

**Actor:** Bidder (Basim)
**Pre:** An adaptive-card email has arrived in Outlook.
**Main flow:**
1. Basim opens the email.
2. The card shows RFP metadata and line items with blank price/lead-time fields.
3. Basim fills the fields and clicks *Submit*.
4. Outlook validates client-side (required + numeric).
5. Outlook POSTs to `/api/actionable-card/response` with a substrate JWT.
6. The system verifies the JWT and writes to the RFP response table.
7. The card updates in place to show "Submitted — thank you".
**Post:** RFP row status = `Submitted`; audit row `RFP_SUBMITTED` written.
**Alt:** invalid numeric → inline error, no server call. JWT invalid → card shows "Action failed"; audit row `ACTIONABLE_REJECTED`.

### UC-02 — Admin creates a custom role

**Actor:** Admin (Khalid)
**Pre:** Logged in with Admin role.
**Main flow:**
1. Khalid navigates to *Role Management* → *Create Role*.
2. Enters a role name and selects permissions.
3. Submits; system calls `POST /api/roles/create` then `PUT /api/roles/{id}/permissions`.
4. Dataverse rows created; cache invalidated.
**Post:** Role appears in the list; any user assigned this role gets the new permission set on next session refresh.
**Alt:** Duplicate name → 409; rename required.

### UC-03 — Bidder submits via dashboard (no Outlook)

**Actor:** Bidder
**Pre:** Logged into the portal; has `rfp.submit`.
**Main flow:**
1. Opens RFP detail page.
2. Fills dynamic response form.
3. Clicks *Submit*; system calls `POST /dashboard/submit-rfp-final`.
4. Validation passes; row updated.
**Post:** Status = `Submitted`; confirmation toast.
**Alt:** validation fails → field-level errors shown.

### UC-04 — Automated Ariba scrape

**Actor:** System (Power Automate scheduler)
**Pre:** Ariba credentials configured; automation service healthy.
**Main flow:**
1. Scheduler triggers `GET /download-rfps-automation`.
2. Orchestrator launches headless Chromium, logs in (or reuses session), lists open RFPs.
3. For each new RFP, downloads attachments and creates a `cr673_bahra_rfps_v2` row.
4. Match engine runs; bidders notified via adaptive-card emails.
**Post:** `cr673_bahra_automation_log1` row with counts; RFPs visible in dashboard.
**Alt:** Ariba down or DOM changed → failure artifacts saved to the `LOGS/` folder on the Windows host and surfaced on the dashboard's error panel for operator review.

### UC-05 — Admin pauses the automation schedule

**Actor:** Admin
**Pre:** Has `schedule_automation.manage`.
**Main flow:**
1. Opens *Schedule & Automation*.
2. Edits the schedule (e.g. disables the cron or widens the interval).
3. System calls `POST /dashboard/schedule-automation` with the new config.
4. Backend persists to Dataverse and patches the Power Automate Recurrence trigger.
**Post:** The Ariba scrape runs on the new schedule (or not at all). Audit row `SCHEDULE_UPDATED`.

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
| EI-04 | Power Automate Cloud Flow (HTTP trigger + Recurrence trigger) for scheduler push. |
| EI-05 | Ariba portal web UI via Playwright / Chromium. |
| EI-06 | SAP integration limited to password push via `services/sap_service.py`. |
| EI-07 | Actionable-messages substrate via Outlook (inbound JWT-signed POST). |

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
| NFR-20 | All secrets SHALL be rotatable without code changes (env var / Key Vault). |
| NFR-21 | Session cookies SHALL be `HttpOnly`, `SameSite=Lax`, and `Secure` in production. |
| NFR-22 | The system SHALL enforce TLS 1.2+ for all inbound and outbound traffic. |
| NFR-23 | Adaptive-card callbacks SHALL verify the substrate JWT (signature, issuer, originator). |
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
| NFR-40 | Every state transition of an RFP SHALL be reconstructible from `cr673_bahra_audit_logs`. |
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
- **Ariba service account exempt from MFA.** The scraper logs into Ariba automatically on a schedule, so the Ariba user it uses cannot have multi-factor authentication (phone prompt / OTP). IT must grant an MFA exemption for this specific service account.
- **Power Automate Premium licence.** Scheduling the Ariba scrape uses a Premium Power Automate connector (Dataverse + HTTP). Bahra must keep a Premium licence active — without it, the schedule does not fire.
- **TLS certificate from Bahra's certificate authority.** The dashboard must be served over HTTPS. IT must issue the production certificate from Bahra's internal CA and renew it before expiry — the project does not manage its own certificates.
- **Pandoc installed on the ops workstation.** The Word-format user and admin manuals are generated from Markdown using Pandoc. Whoever runs the generator script needs Pandoc installed locally; runtime users do not.

## 10. Out-of-scope (reiterated)

Pulled forward from the BRD: automated pricing, negotiation, full SAP write-back, mobile-native app, external customer login.

## 11. Revision history

Tracked in [CHANGELOG.md](../CHANGELOG.md). Each SRS change SHOULD increment the top-matter `version` and add a line describing the change.
