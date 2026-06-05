---
title: Security & Compliance — Bahra Electric RFP Automation
version: 1.0
last_updated: 2026-04-22
owner: Samir Tak (samir.tak@dynatechconsultancy.com)
audience: Admins, Security Reviewers, Compliance Officers
status: Draft
---

# Security & Compliance

Security controls, data classification, secrets handling, audit, backup, and incident response for the RFP Automation platform.

Related: [Deployment Guide](09-Deployment-Guide.md) · [Operations Runbook](10-Operations-Runbook.md) · [RBAC Permissions Matrix](11-RBAC-Permissions-Matrix.md)

---

## 1. Threat model (summary)

| Asset | Threats | Primary mitigation |
|---|---|---|
| RFP pricing data | Competitor leakage, insider tampering | RBAC · audit log · encrypted transport |
| SAP master material | Unauthorised modification | `material_master.*` permissions · audit log |
| User credentials | Brute force, phishing | bcrypt hash · session tokens · HTTPS only |
| Dataverse API access | Token theft, over-privileged app | Azure AD app + tenant isolation · least-privilege Application User |
| Ariba portal credentials | Theft from config, bot abuse | Move to Key Vault · isolated automation server |
| Email integrations | Spoofed adaptive-card callbacks | Substrate token verification · Originator ID allow-list |

Out of scope (assumed handled by infrastructure): network perimeter, endpoint antivirus, physical security of the host, Azure AD conditional access.

---

## 2. Authentication

### 2.1 End-user authentication

- Users log in via the React UI (`/login`) against the `cr673_bahra_users` table.
- Passwords are stored as **bcrypt** hashes (cost factor 12). Plaintext passwords never touch disk.
- Successful login opens a server-side **session** backed by `itsdangerous` signed cookies (FastAPI `SessionMiddleware`).
- Session payload: `{id, email, name, role, permissions, is_active}`. Permissions are snapshotted at login for fast checks.
- Session cookie attributes:
  - `HttpOnly` — not readable from JavaScript
  - `SameSite=Lax`
  - `Secure` — **must be true in production** (set via reverse proxy / HTTPS termination)
  - Max age: 8 hours (configurable via `SESSION_MAX_AGE_SECONDS`)
- Session secret: `SESSION_SECRET_KEY` in `config/config.py`. **Must be a 32+ byte random string.** The shipped default `change-me-please` must be replaced before production.

### 2.2 Service-to-service authentication

The dashboard and automation services authenticate to Microsoft 365 and Dataverse as a **confidential client application** using OAuth 2.0 client credentials:

- Tenant ID: `TENANT_ID` in `config/config.py`
- Client ID: `CLIENT_ID`
- Client secret: `CLIENT_SECRET` (see §4 for rotation and storage)
- Authority: `https://login.microsoftonline.com/{TENANT_ID}`
- Scopes requested:
  - `https://<org>.crm4.dynamics.com/.default` for Dataverse
  - `https://graph.microsoft.com/.default` for email + SharePoint

Tokens are cached in-process by [helpers/dataverse_helper.py](../../helpers/dataverse_helper.py) and refreshed ~5 min before expiry.

### 2.3 Adaptive-card callbacks

When a Bidder clicks *Submit* inside an actionable email, Outlook sends a POST to `/api/actionable/respond` with a **Microsoft substrate JWT**. The route verifies:

1. Token signature against Microsoft's public JWKs
2. Issuer = `https://substrate.office.com/sts/`
3. `appid` = our registered Originator ID
4. `sub` (email) matches a known bidder row

Rejected tokens produce a 401 and log to `cr673_bahra_audit_logs` with `action = ACTIONABLE_REJECTED`.

---

## 3. Authorization

See [RBAC Permissions Matrix](11-RBAC-Permissions-Matrix.md) for the full role × permission grid.

Key points:

- Every HTTP route that mutates data **must** call `user_has_permission(user, perm)` or be wrapped by a `PermissionGuard` dependency.
- Frontend permission checks (`useHasPermission`) are for UX only — never for security.
- Sessions carry a snapshot of permissions; re-login required to refresh after a role change (or wait ≤ 300 s cache TTL).

---

## 4. Secrets management

### 4.1 Inventory of secrets

| Secret | Current storage (dev) | Recommended production storage |
|---|---|---|
| Azure AD `CLIENT_SECRET` | `config/config.py` | Azure Key Vault · env var · NSSM service env |
| `SESSION_SECRET_KEY` | `config/config.py` (default `change-me-please`) | Env var, generated via `secrets.token_urlsafe(48)` |
| SAP portal password | SAP staging DB + session | Azure Key Vault · rotated per SAP policy |
| Ariba portal password | `config/config.py` / system settings | Azure Key Vault |
| Email service account | Azure AD app itself (no password — client credentials) | n/a |
| Dataverse Application User role | Power Platform admin centre | n/a (not a secret, but a grant) |

### 4.2 Rotation policy

| Secret | Rotation cadence | Owner |
|---|---|---|
| `CLIENT_SECRET` | Every 12 months (Azure max is 24 — set a shorter reminder) | Azure AD admin |
| `SESSION_SECRET_KEY` | On compromise or whenever a former admin leaves | System owner |
| SAP password | Per SAP Basis policy (typically 90 days) | SAP Basis team |
| Ariba password | When Ariba prompts, or every 180 days | Procurement |
| bcrypt password hash (per-user) | Self-service; force-reset on suspected compromise | User · Admin |

### 4.3 Replacing `config/config.py` secrets with env vars (recommended)

```python
# config/config.py
import os

CLIENT_SECRET = os.environ.get("BAHRA_CLIENT_SECRET") or _raise("BAHRA_CLIENT_SECRET not set")
SESSION_SECRET_KEY = os.environ.get("BAHRA_SESSION_SECRET") or _raise("BAHRA_SESSION_SECRET not set")
```

Set them in NSSM: `nssm set BahraRFP-Dashboard AppEnvironmentExtra BAHRA_CLIENT_SECRET=...`.

### 4.4 What must **not** be committed

- `config/config.py` with real secrets (add to `.gitignore`; ship `config/config.example.py` instead)
- `.env` files
- `logs/` or `LOGS/` contents (may contain tokens from tracebacks)
- Any `.docx` or `.xlsx` containing real customer pricing

---

## 5. Transport security (TLS)

- **All production traffic must be HTTPS.** The FastAPI server speaks plain HTTP; a reverse proxy (IIS with ARR, nginx, or Azure Application Gateway) must terminate TLS.
- Minimum TLS version: 1.2
- HSTS header: `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- Certificate: organisation-issued, auto-renewed via ACME or AD CA
- Disallow TLS 1.0/1.1 and weak ciphers (SSL Labs grade A minimum)

---

## 6. Data classification

| Data | Classification | Location | Notes |
|---|---|---|---|
| Bidder pricing | **Confidential** | `rfps_v2.Matched_Data`, `rfp_team.response_data` | Visible only to Admin and the responding Bidder |
| SAP material master | Internal | `cr673_bahra_material_master` | Sanitised — no costs |
| User PII (name, email) | Internal | `cr673_bahra_users` | Email is also primary identifier |
| Password hashes | **Confidential** | `cr673_bahra_users.password_hash` | bcrypt, salted per row |
| Audit logs | **Confidential** (regulatory) | `cr673_bahra_audit_logs` | Retain indefinitely |
| Ariba session cookies / screenshots | Internal | `LOGS/*.png` | Purge after 90 days |

**Do not** log raw passwords, session cookies, or Dataverse bearer tokens. The logger's default format does not, but custom traces in `error_handler.py` should scrub the `Authorization` header before writing.

---

## 7. Audit trail

Every state-changing action writes a row to `cr673_bahra_audit_logs`:

| Category | Example `action` values |
|---|---|
| RFP lifecycle | `RFP_CREATED`, `RFP_SUBMITTED`, `RFP_DECLINED`, `RFP_APPROVED`, `RFP_REASSIGNED` |
| RBAC | `ROLE_CREATED`, `ROLE_UPDATED`, `ROLE_DELETED`, `ROLE_PERMISSIONS_CHANGED`, `USER_CREATED`, `USER_UPDATED`, `USER_DEACTIVATED`, `USER_ROLE_ASSIGNED` |
| Settings | `SYSTEM_SETTINGS_UPDATED`, `SCHEDULE_UPDATED` |
| Security | `LOGIN_SUCCESS`, `LOGIN_FAILURE`, `LOGOUT`, `ACTIONABLE_REJECTED` |
| Master data | `MATERIAL_MASTER_CREATED/UPDATED/DELETED`, `KEYWORD_CREATED/UPDATED/DELETED` |

**Retention:** indefinite. Purging requires Legal + System Owner approval.

**Access:** `audit_logs.view` permission. By default only Admin.

**Integrity:** audit rows are append-only; no UI or API updates them. Dataverse retains platform-level change-history on the table itself as a backstop.

**Sampling for review:** every quarter, export the past 90 days' audit logs and review failed logins, privilege escalations, and unusual RFP activity.

---

## 8. Backup & disaster recovery

### 8.1 Data backup

| Asset | Backup mechanism | Frequency | RPO |
|---|---|---|---|
| Dataverse tables | Microsoft platform backup (point-in-time restore up to 28 days) | Continuous | < 5 min |
| `LOGS/`, `ALLRFPs/` | File-level backup (to network share / Azure Files) | Nightly | 24 h |
| `config/config.py` (without secrets) | Git commit | On every change | n/a |
| Secrets (Key Vault) | Azure Key Vault soft-delete + purge protection | Continuous | < 1 min |
| SAP / Ariba credentials | Key Vault + offline secure record | On rotation | n/a |

### 8.2 Application recovery (RTO)

| Failure | Recovery action | Target RTO |
|---|---|---|
| Dashboard service crash | NSSM auto-restart (configured) | < 1 min |
| Host failure | Failover to standby VM (if provisioned) or redeploy from Git | 4 h |
| Dataverse data corruption | PITR to last known good state | 2 h (support ticket) |
| Azure AD app secret leaked | Rotate via Azure Portal + redeploy | 30 min |
| Full tenant loss | Re-provision from Git + restore latest Dataverse export | 24 h |

### 8.3 Redeploy procedure (summary)

See [Deployment Guide](09-Deployment-Guide.md) for the full steps. TL;DR:

1. Provision Windows Server host
2. Clone the repo · install Python/Node
3. Restore `config/config.py` (or env vars) from secure storage
4. `npm install && npm run build` inside `frontend/`
5. Re-register NSSM services · start
6. Run `/health` smoke test

Dataverse data recovers independently via Microsoft.

---

## 9. Incident response

### 9.1 Severity levels

See [Operations Runbook §12](10-Operations-Runbook.md#12-on-call-playbook).

### 9.2 Security-specific playbook

**Suspected credential compromise:**
1. Rotate the affected secret immediately (Key Vault or Azure Portal)
2. Invalidate all user sessions by rotating `SESSION_SECRET_KEY` + restart
3. Pull audit log rows for the affected principal in the last 30 days
4. Force-reset affected user passwords
5. Post-mortem within 5 business days

**Suspected data exfiltration:**
1. Preserve logs (snapshot `LOGS/` and audit rows) before anything else
2. Identify scope: which rows, which user, what time window
3. Notify System Owner + Legal
4. If customer pricing leaked → notify affected bidders per contract obligation
5. Root-cause: insider · compromised credential · software bug · missing permission check
6. File a CVE-style disclosure only if an external dependency was the root cause

**Actionable-card spoofing attempt:**
1. `ACTIONABLE_REJECTED` spike in audit logs → verify substrate token validation is functioning
2. Review Originator ID allow-list · revoke any that shouldn't be there
3. No user action required — rejected tokens did not mutate state

### 9.3 Contact tree

| When | Who |
|---|---|
| First discovery | On-call engineer (§Operations Runbook §13) |
| SEV-1 / SEV-2 within 15 min | System Owner — Samir Tak |
| Security-classified within 1 h | Organisation CISO / InfoSec team |
| PII breach within 24 h | Legal + DPO (if applicable under local law) |

---

## 10. Compliance checklist

Use before go-live and on every major release:

- [ ] `CLIENT_SECRET` stored outside Git (Key Vault or env var)
- [ ] `SESSION_SECRET_KEY` replaced with 32+ random bytes
- [ ] HTTPS enforced via reverse proxy (no plain HTTP listener)
- [ ] Session cookie `Secure=true`
- [ ] Default `Admin` account password changed; shared admin account disabled
- [ ] `EMAIL_MODE` set to `prod`
- [ ] CORS `allowed_origins` locked to the production hostname(s) — no `*`
- [ ] Adaptive-card Originator ID registered and restricted to expected sender mailbox
- [ ] Azure AD app granted **only** required Graph scopes (`Mail.Send`, `Sites.Read.All`, `User.Read.All`)
- [ ] Dataverse Application User granted least-privilege security role (custom role preferred over System Administrator)
- [ ] Backup verified — restore test completed within last 90 days
- [ ] Audit log export scheduled quarterly
- [ ] Secret rotation calendar populated for the next 12 months
- [ ] Access review completed within last 6 months
- [ ] Dependency vulnerability scan (pip-audit, npm audit) run in the last 30 days with no HIGH/CRITICAL unresolved

---

## 11. Known residual risks

| ID | Risk | Mitigation / accepted trade-off |
|---|---|---|
| RR-01 | Single FastAPI process per service = single point of failure | Mitigate with NSSM auto-restart; high-availability would need a load-balanced pair |
| RR-02 | In-memory RBAC cache means permission revokes take up to 5 min | Accepted; force restart on high-severity revokes |
| RR-03 | `config/config.py` still contains some secrets in repo checkouts | Mitigate by moving to env vars / Key Vault (§4.3) |
| RR-04 | No rate-limiting on login endpoint | Mitigate with reverse-proxy rate-limit rule; future: add slowapi middleware |
| RR-05 | Ariba scraper uses shared credentials | Mitigate by isolating the automation server and vaulting the password |
| RR-06 | No MFA for portal login | Accepted v1; relies on network perimeter + strong passwords. Future: delegate auth to Entra ID |
| RR-07 | Audit log lives in the same Dataverse tenant as the data it audits | Mitigate by exporting quarterly to immutable storage (Azure Blob with legal hold) |

---

## 12. References

- [services/permission_definitions.py](../../services/permission_definitions.py) — permission catalogue
- [services/dynamic_role_service.py](../../services/dynamic_role_service.py) — RBAC enforcement
- [helpers/dataverse_helper.py](../../helpers/dataverse_helper.py) — token handling
- [routes/actionable_cards.py](../../routes/actionable_cards.py) — adaptive-card verification
- Microsoft — [Actionable messages security and authentication](https://learn.microsoft.com/outlook/actionable-messages/security-requirements)
- Microsoft — [Dataverse security model](https://learn.microsoft.com/power-platform/admin/wp-security-cds)
- OWASP Application Security Verification Standard (ASVS) 4.0 — used as reference for control scope
