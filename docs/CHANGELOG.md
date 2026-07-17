# Changelog

All notable changes to the Bahra Electric RFP Automation platform are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html) — `MAJOR.MINOR.PATCH`.

Update procedure: on every release, add a new section at the top. Move entries from the running `## [Unreleased]` section into the dated release. Never rewrite historical releases — **except** to correct a statement that was factually untrue when written; mark any such correction inline.

---

## [Unreleased]

### Added
- **Windows Task Scheduler as the scheduling engine** for the download and portal-sync jobs, replacing the Power Automate cron flows ([scripts/Register-RfpSchedules.ps1](../scripts/Register-RfpSchedules.ps1), [scripts/Invoke-RfpAutomation.ps1](../scripts/Invoke-RfpAutomation.ps1)). Registers `RFP-Download-OpenRFPs` (00:00 / 06:00 / 12:00 / 18:00) and `RFP-Sync-Portal` (03:00 / 09:00 / 15:00 / 21:00) under the `\Bahra-RFP\` task folder. Times are **Riyadh** server-local — the retired flows ran on India Standard Time, so their "12:00" fired at 09:30 Riyadh.
- `Invoke-RfpAutomation.ps1` polls the run flag to completion, so Task Scheduler's "Last Run Result" reflects the job finishing rather than merely being accepted. Exit codes: `0` finished · `1` API unreachable · `2` already running · `3` timeout.
- Full documentation set re-verified against the codebase and corrected (see **Fixed** below).

### Changed
- **Adaptive-Card callback moved from a VS Code dev tunnel to Microsoft Entra Application Proxy** (Passthrough mode). The connector is outbound-only — no inbound port, no public IP, no port-forward — and publishes **only** `/api/actionable-card/`. The dashboard, upload page, and automation endpoints remain LAN-only behind IIS. Runbook: [Azure-App-Proxy-Adaptive-Card-Setup.md](../Azure-App-Proxy-Adaptive-Card-Setup.md).
- Adaptive-Card token verification migrated from legacy Actionable Message tokens to **Microsoft Entra ID**, accepting both v1.0 (`sts.windows.net/{tenant}/`) and v2.0 issuers and validating `azp`/`appid` against Microsoft's fixed Actions app id.
- Repository restructured — backend code moved under `backend/`, frontend under `frontend/`. The backend must now be launched with its working directory set to `backend/`.
- Application served under a `/rfp` path prefix (`root_path="/rfp"`), stripped by the IIS reverse proxy.

### Fixed
- Documentation corrected against the source after roughly three months of drift. The most significant corrections:
  - The LLD documented a `fuzzy_score()` function returning a confidence percentage. **No such function exists**, and no fuzzy-matching library is present anywhere in the codebase. Removed and replaced with the real two-tier exact/substring classifier.
  - The Approver manual documented an Approve / Reject / Request-Clarification workflow that **does not exist**. Rewritten as an oversight manual.
  - The HLD and TROUBLESHOOTING documented an **email-ingestion pipeline** that does not exist — RFPs are discovered by scraping SAP Ariba with Playwright.
  - `MATCH_THRESHOLD_PCT` was documented as a tunable System Setting. There is no such setting and no threshold.
  - `error_analysis_routes.py` was documented as live API. The router is **not mounted** — its endpoints are unreachable.
  - Permission count corrected to **42**; the RFP Bidder role to its real **10** permissions.
  - The four buyer organisations were described as four separate portals. They are **one SAP Ariba tenant**.
  - Every backend code link was broken by the `backend/` restructure; all were repointed.
  - **Portal URL corrected to `https://be-aramco-01.bahra-cables.com/rfp`.** The docs used an `rfp.` subdomain that does not exist — the app is served under a `/rfp` **path** on the shared host (matching `root_path="/rfp"` and `base: '/rfp/'`). The callback URL and `UPLOAD_BASE_URL` were corrected to carry the `/rfp` prefix; `UPLOAD_BASE_URL` must end in `/rfp/` or upload links break.
  - Portal TLS corrected: the cert is **issued by Bahra's internal CA** for `be-aramco-01.bahra-cables.com`, not a self-signed wildcard (a `*.` wildcard would not even match the real host).
  - Document ownership corrected to Manish Soni throughout.

### Known issues
- **RFP reminder emails are not sending.** The reminder Power Automate flow still calls the retired dev tunnel, and no Scheduled Task replaces it. App Proxy publishes only the actionable-card path, so the flow has no reachable URL. Manual runs work via `Invoke-RfpAutomation.ps1 -Job reminder`.
- **The Schedule Automation page is a silent no-op.** It writes to `Bahra-E-binding-cron-job` — the flow the Task Scheduler migration disables — so saving succeeds while the real cadence is unchanged. Re-enabling that flow would make the download job fire from both sources.
- `download` and `sync` use separate `_RUN_STATE` flags and therefore do **not** block each other; collision avoidance relies on the 3-hour schedule offset.
- Automation endpoints are unauthenticated, as are `GET /api/actionable-card/responses/{rfp_id}` and `GET /api/company-options`.

### Security
- **Unverified, high priority:** the Entra App Proxy publish may be broader than the callback path. The live callback is `…msappproxy.net/rfp/api/actionable-card/response`; for that `/rfp` prefix to survive the proxy, the publish must be rooted at the IIS site rather than scoped to `/api/actionable-card/`. That would expose `/rfp/api/login`, `/rfp/health`, the upload page, and the **entirely unauthenticated** `/rfp/api/automation/*` to the public internet — removing the network position most other controls depend on. Verify from off-LAN and restrict. Tracked as RR-21.
- Session cookies are signed with a **hardcoded** `secret_key="change-me-please"` in the tracked `dashboard_main.py` — treat as compromised and rotate to a per-host secret.
- `UPLOAD_TOKEN_SECRET` still carries its placeholder default.
- No idle timeout is enforced. `IDLE_TIMEOUT_SECONDS`, `SESSION_WARNING_SECONDS`, and `SESSION_REFRESH_INTERVAL` exist in config but are **never read by any code**; the effective timeout is a flat 2-hour absolute cookie lifetime.
- `system_settings.edit` alone permits revealing masked secrets — there is no separate reveal permission.
- RFP operations are **not** audited, despite an `RFP` audit category existing.

---

## [1.0.0] — 2026-01-15

Initial production release. Phase-1 MVP.

> **Corrected 2026-07-17.** Several entries below described features that were never implemented (email ingestion, a fuzzy match engine) or misstated the deployment. They are corrected in place rather than left to mislead; the original wording is preserved only where it was accurate.

### Added
- Core RFP lifecycle (discover → match → route → respond → track)
- SAP Ariba portal scraper (Playwright), covering four buyer organisations within a single supplier account
- BOQ download and parsing from Excel/PDF attachments
- Material matching against the SAP Material Master — a deterministic two-tier classifier (exact 9-digit material-code equality, then substring keyword containment). *Corrected: previously described here as a "fuzzy material-match engine with keyword expansion"; no fuzzy matching, scoring, or threshold has ever existed.*
- SharePoint document sync via Microsoft Graph. *Corrected: previously listed "Email ingestion via Microsoft Graph" — Graph is used to **send** mail and to sync SharePoint, never to ingest RFPs.*
- Adaptive-card bidder responses in Outlook, with first-response-wins per team row
- Portal UI for Bidder / Admin workflows
- RBAC with 42 permissions and 2 seeded roles (Admin, RFP Bidder)
- Audit trail in `cr673_bahra_audit_logs` covering auth, user, role, and settings events
- Dataverse tables under the `cr673_` publisher prefix. *Corrected: "16 tables" — the current catalog is 18.*
- Power Automate integration for schedule triggers *(since superseded — see Unreleased)*
- Windows service deployment. *Corrected: previously "NSSM-based"; production runs `rfp-api` under **WinSW**.*

### Known issues at release
- Single-worker automation (no HA for the scraper); `_RUN_STATE` is in-memory and process-local
- `CLIENT_SECRET` and other secrets live in `backend/config/config.py`. *Corrected: the original entry said this file "ships" in the repo and implied it was committed. It is **gitignored and has never been committed** — the real exposure is untracked plaintext on each host, with no secret store and manual rotation. See [Security & Compliance](03-operations/12-Security-and-Compliance.md) §4.*
- *Removed: "No app-level rate limiting on login endpoint" — this was untrue. Login has enforced an in-memory 5-failures / 5-minute lockout since this release.*

---

## Template for future entries

```markdown
## [x.y.z] — YYYY-MM-DD

### Added
- New feature or endpoint

### Changed
- Behaviour change (note if breaking)

### Fixed
- Bug fix (reference ticket number)

### Deprecated
- Feature marked for removal (state removal date)

### Removed
- Feature removed (should have been deprecated first)

### Security
- CVE, secret rotation, or control hardening
```

Reminder: entries here should be **user-facing** or **operationally relevant**. Purely internal refactors don't belong in the changelog — use commit history for those.
