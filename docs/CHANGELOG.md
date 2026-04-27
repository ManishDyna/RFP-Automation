# Changelog

All notable changes to the Bahra Electric RFP Automation platform are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html) — `MAJOR.MINOR.PATCH`.

Update procedure: on every release, add a new section at the top. Move entries from the running `## [Unreleased]` section into the dated release. Never rewrite historical releases.

---

## [Unreleased]

### Added
- Initial enterprise documentation set (README, BRD, SRS, Glossary, SAD, HLD, LLD, Data Dictionary, API, Deployment Guide, Operations Runbook, RBAC Matrix, Security & Compliance, end-user manuals)

### Changed
-

### Fixed
-

### Deprecated
-

### Removed
-

### Security
-

---

## [1.0.0] — 2026-01-15

Initial production release. Phase-1 MVP.

### Added
- Core RFP lifecycle (ingest → match → route → respond → track)
- Email ingestion via Microsoft Graph
- SharePoint folder sync
- Ariba portal scraper (Playwright)
- Fuzzy material-match engine with keyword expansion
- Adaptive-card bidder responses in Outlook
- Portal UI for Bidder / Admin workflows
- RBAC with 42 permissions and 2 seeded roles (Admin, RFP Bidder)
- Comprehensive audit trail in `cr673_bahra_audit_logs`
- 16 Dataverse tables under the `cr673_` publisher prefix
- Power Automate integration for schedule triggers
- NSSM-based Windows service deployment

### Known issues at release
- No app-level rate limiting on login endpoint
- Single-worker automation (no HA for the scraper)
- `CLIENT_SECRET` ships in `config/config.py` — must be moved to Key Vault before production (see Security & Compliance §4)

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
