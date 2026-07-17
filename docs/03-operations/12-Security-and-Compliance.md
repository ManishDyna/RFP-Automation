---
title: Security & Compliance — Bahra Electric RFP Automation
version: 1.1
last_updated: 2026-07-17
owner: Manish Soni (Manish.soni@dynatechconsultancy.com)
audience: Admins, Security Reviewers, Compliance Officers
status: Draft
---

# Security & Compliance

Security controls, data classification, secrets handling, audit, backup, and incident response for the RFP Automation platform.

Related: [Deployment Guide](09-Deployment-Guide.md) · [Operations Runbook](10-Operations-Runbook.md) · [RBAC Permissions Matrix](11-RBAC-Permissions-Matrix.md)

> **Posture in one paragraph.** The system is **LAN-only**: the backend binds `127.0.0.1:8000`, IIS serves the portal on the corporate network with an internal-CA-issued cert, and the **only** public surface is the Adaptive-Card callback path published through Entra Application Proxy (outbound-only connector, Passthrough). Much of the security today rests on that network position rather than on in-app controls — several endpoints are unauthenticated, the session secret is hardcoded, and there is no idle timeout. §11 lists the residual risks honestly; do not read this document as a claim that the app would be safe if exposed.

---

## 1. Threat model (summary)

| Asset | Threats | Primary mitigation |
|---|---|---|
| RFP pricing data | Competitor leakage, insider tampering | RBAC · LAN-only exposure · encrypted transport. **Note: RFP operations are not audited** (§7) |
| SAP master material | Unauthorised modification | `material_master.*` permissions · audit log |
| User credentials | Brute force, phishing | bcrypt hash · signed session cookie. **No rate limiting, no MFA** (§11) |
| Dataverse API access | Token theft, over-privileged app | Azure AD app + tenant isolation · least-privilege Application User |
| Ariba portal credentials | Theft from the local config file, bot abuse | Untracked config file on the host · isolated server. **No secret store** (§4) |
| Adaptive-card callback | Spoofed callbacks from the public internet | Entra token validation in-app (§2.3) · Originator ID allow-list. **Note:** the proxy publish is NOT scoped to this one path — see §5.1 and RR-21 |
| Automation endpoints | Unauthenticated triggering | **Network position only** — they have no auth at all (§3). Must never be internet-reachable |

Out of scope (assumed handled by infrastructure): network perimeter, endpoint antivirus, physical security of the host, Azure AD conditional access.

---

## 2. Authentication

### 2.1 End-user authentication

- Users log in via the React UI (`/login`) against the `cr673_bahra_users` table.
- Passwords are stored as **bcrypt** hashes. Plaintext passwords never touch disk.
- Successful login opens a **session** backed by a signed cookie (Starlette `SessionMiddleware`), cookie name `rfp_session`, `path=/rfp`.
- Session payload includes `permissions` — **snapshotted at login** and never refreshed. See [RBAC §1.3](11-RBAC-Permissions-Matrix.md#13-enforcement--and-its-four-sharp-edges).
- **Session lifetime: a flat 2-hour absolute `max_age`** (`SESSION_TIMEOUT_SECONDS = 7200`).

> ⚠️ **There is no idle timeout, despite config that implies one.** `IDLE_TIMEOUT_SECONDS` (1800), `SESSION_WARNING_SECONDS` (300), and `SESSION_REFRESH_INTERVAL` (300) exist in `backend/config/config.py` but are **never read by any code**. `last_activity` is written into the session and echoed back, but **never compared against a threshold**. An unattended, logged-in browser stays authenticated for the full 2 hours regardless of inactivity. Do not claim a 30-minute idle timeout in any control questionnaire.

> ⚠️ **The session secret is hardcoded.** `SessionMiddleware(secret_key="change-me-please")` in `dashboard_main.py` — anyone with source access can **forge a session cookie for any user, including Admin**. This is the highest-severity in-app finding. Tracked in `backend/Support-Files/OPTIMIZATION_PLAN.md`. Fix: [Deployment §11.2](09-Deployment-Guide.md#112-replace-the-session-secret).

### 2.2 Service-to-service authentication

The backend authenticates to Microsoft 365 and Dataverse as a **confidential client application** using OAuth 2.0 **client credentials** (app-only) via MSAL:

- Tenant ID: `TENANT_ID` · Client ID: `CLIENT_ID` · Client secret: `CLIENT_SECRET` (see §4)
- Authority: `https://login.microsoftonline.com/{TENANT_ID}`
- Scopes: `{RESOURCE_URL}/.default` for Dataverse · `https://graph.microsoft.com/.default` for email + SharePoint

Email is sent app-only via `POST /v1.0/users/{sender}/sendMail` (send-as). Tokens are cached in-process by [helpers/dataverse_helper.py](../../backend/helpers/dataverse_helper.py).

### 2.3 Adaptive-card callbacks

When a Bidder clicks *Submit* inside an actionable email, **Microsoft's Actions service** — not the user's browser — POSTs to the callback with an **Entra bearer token**. The request arrives via Entra Application Proxy in **Passthrough** mode, which forwards it (and its `Authorization` header) unmodified; **App Proxy performs no authentication of its own**. The security boundary is `_verify_actionable_message_token` in [routes/actionable_cards.py](../../backend/routes/actionable_cards.py), which verifies:

1. **Signature** — RS256 against the tenant's **v2.0 JWKS**, discovered from `{tenant}/v2.0/.well-known/openid-configuration`.
2. **`aud`** — must match `ACTIONABLE_CARD_APP_ID_URI` (either the AppIdUri or the bare client id). **Fails closed if that value is unconfigured** — no audience, no access.
3. **`iss`** — checked **manually after decode** (`verify_iss=False` is passed deliberately) because **both issuer forms are accepted**: `https://login.microsoftonline.com/{tenant}/v2.0` **and** `https://sts.windows.net/{tenant}/`. Microsoft sends a **v1.0** or v2.0 token depending on the resource app's token-version setting; accepting only one would break the buttons.
4. **`azp`** (falling back to **`appid`** on v1.0 tokens) — must equal `ACTIONABLE_CARD_ACTIONS_APP_ID`, **Microsoft's fixed Actions app id `48af08dc-…`, not our app id**. This is what stops any other caller who happens to hold a token for our audience.
5. **`exp`** — verified.

Identity is taken from `preferred_username` / `upn` / `unique_name` / `email` — **not `sub`**, which is an opaque pairwise id, not an email.

> On failure the code re-decodes the token **unverified** solely to log the actual `aud`/`iss`/`azp` against the expected values. That log line is the fastest triage for a 401.

> ⚠️ **`GET /api/actionable-card/responses/{rfp_id}` performs no token verification and no session check — it is unauthenticated** (§3). It is not published through App Proxy, so it is reachable only from the LAN.

> ⚠️ Legacy EAT authentication was retired by Microsoft on 2026-06-08; this Entra-token path is the current and only supported mechanism. The token-audience app must have **Expose an API** configured with `48af08dc-…` authorized on it — provider approval alone only makes the card *render*.

---

## 3. Authorization

See [RBAC Permissions Matrix](11-RBAC-Permissions-Matrix.md) for the full role × permission grid and its enforcement caveats.

Key points:

- The intended guard is `Depends(require_permission("module.action"))` from [middleware/auth.py](../../backend/middleware/auth.py).
- **Four different auth mechanisms coexist** in the codebase — a reviewer must check which one a given route uses, not assume:
  1. `require_permission` / `require_admin` / `get_current_user` dependencies;
  2. inline `request.session.get("user")` → 401 (much of `routes/dashboard.py`, parts of `routes/api.py`) — authenticates but checks **no permission**;
  3. inline `has_access_to_feature(...)` via `services/role_service` (`user_management.py` only);
  4. token-based — Entra bearer (`actionable_cards.py`), query/form JWT (`rfp_upload.py`).
- **`require_admin` is a hardcoded role-**name** check** that bypasses the permission system entirely. Renaming the `Admin` role breaks every route using it.
- **Permissions are read from the session and frozen at login** — a revoke is not effective until the session ends (≤ 2 h).
- **Frontend permission checks are cosmetic.** The Zustand store persists `user.permissions` to **`localStorage`** (key `auth-storage`); a user can edit the array in devtools to unlock UI. The backend is the only real gate.

### 3.1 Unauthenticated endpoints (by design or by omission)

| Endpoint(s) | Auth | Note |
|---|---|---|
| **All 10 `automation` endpoints** (`/api/download-rfps-automation`, `/api/sync_portal_data`, `/api/rfp-reminder`, …) | **None** — no session, no permission dependency | Anyone who can reach port 8000 can trigger a full Playwright run or send bidder email. **Mitigated only by network position.** They must never be published through App Proxy or IIS to the internet |
| `GET /api/actionable-card/responses/{rfp_id}` | **None** | Discloses bidder responses for an RFP id to any LAN caller |
| `GET /api/company-options` | **None** | Low sensitivity |
| `/health` | None | Discloses Dataverse connectivity |
| login / logout / forgot / reset | None (by design) | **No rate limiting** — see §11 RR-04 |

> The automation router is **double-mounted** (with and without the `/api` prefix), so each of those 10 endpoints is live at **two** paths. Any network ACL must cover both.

---

## 4. Secrets management

### 4.1 Where secrets actually live — read this before making claims

**`backend/config/config.py` is NOT in git.** It is listed in `.gitignore`, and `git log --all` confirms it has **never been committed** (verified 2026-07-17). **Do not state or repeat that secrets are committed to source control — that is false**, and it has appeared in earlier drafts of this document.

The accurate finding is narrower but still real:

> **Secrets live in plaintext in an untracked local file on each host** (`backend/config/config.py`). There is **no secret store** — no Key Vault, no environment-variable indirection, no encryption at rest beyond the filesystem. **Rotation is entirely manual**: edit the file on each host and restart `rfp-api`.

Consequences to plan around:
- **Anyone with filesystem or RDP access to the server can read every secret**, and the file is protected only by NTFS permissions.
- **There is no inventory or expiry tracking.** Nothing warns you that `CLIENT_SECRET` is about to expire.
- **The file is not restored by a `git clone`.** It is also not overwritten by `git pull` — which is convenient for deploys, but means a host's config can silently drift from every other host. Keep a copy in secure storage; it is a **single point of failure for disaster recovery** (§8).

### 4.2 Inventory of secrets

| Secret | Current storage | Recommended production storage |
|---|---|---|
| Azure AD `CLIENT_SECRET` | `backend/config/config.py` (untracked, plaintext) | Azure Key Vault · env var via the WinSW service `<env>` block |
| Session secret | **hardcoded** `"change-me-please"` in `dashboard_main.py` — **this one IS in git** | Env var, 32+ random bytes |
| `UPLOAD_TOKEN_SECRET` | `config.py`, still at its placeholder default `"change-me-upload-secret-set-via-system-settings"` | Env var, random |
| SAP portal password | Dataverse (`credentials_provider.py` resolves `USERNAME`/`PASSWORD` at import) | Key Vault · rotated per SAP policy |
| Ariba portal password | Dataverse / `config.py` | Azure Key Vault |
| Email service account | Azure AD app itself (no password — client credentials) | n/a |
| Dataverse Application User role | Power Platform admin centre | n/a (a grant, not a secret) |

> **The session secret is the exception to §4.1** — it is not in `config.py`; it is hardcoded in `dashboard_main.py`, which **is** tracked. It is therefore readable by anyone with repo access and must be treated as **already compromised** until replaced.

### 4.3 Rotation policy

| Secret | Rotation cadence | Owner |
|---|---|---|
| `CLIENT_SECRET` | Every 12 months (Azure max is 24 — set a shorter reminder) | Azure AD admin |
| Session secret | On compromise, whenever a former admin leaves, and **immediately** as part of replacing the hardcoded default | System owner |
| `UPLOAD_TOKEN_SECRET` | On compromise; **immediately** to replace the placeholder | System owner |
| SAP password | Per SAP Basis policy (typically 90 days) | SAP Basis team |
| Ariba password | When Ariba prompts, or every 180 days | Procurement |
| bcrypt password hash (per-user) | Self-service; force-reset on suspected compromise | User · Admin |

**Every rotation requires `Restart-Service rfp-api`** — nothing re-reads `config.py` at runtime, and a rotation that "didn't take" is almost always a missed restart.

### 4.4 Moving secrets to env vars (recommended)

```python
# backend/config/config.py
import os

CLIENT_SECRET = os.environ["BAHRA_CLIENT_SECRET"]
```

Set them in the WinSW service definition's `<env>` entries, or as machine environment variables. Long-term: Azure Key Vault.

### 4.5 What must **not** be committed

- `backend/config/config.py` — already gitignored; **keep it that way**
- `.env` files
- `backend/LOGS/` contents (may contain tokens from tracebacks)
- Any `.docx` or `.xlsx` containing real customer pricing

### 4.6 Revealing masked secrets in the portal

The System Settings admin page can **reveal** masked secret values, and that read is audited (`SETTING_REVEALED`).

> ⚠️ **There is no separate "reveal" permission.** `system_settings.edit` alone is sufficient to unmask a stored secret. Any role granted `system_settings.edit` for routine configuration work can also read every secret held in System Settings. Treat `system_settings.edit` as a secret-reading grant when performing access reviews.

---

## 5. Transport security (TLS) and network exposure

- **The FastAPI server speaks plain HTTP and binds `127.0.0.1:8000`** — it is not reachable from the network at all. **IIS** terminates TLS on 443 and reverse-proxies to it. Keep the backend on localhost; do not rebind uvicorn to `0.0.0.0`.
- **Portal certificate:** issued by **Bahra's internal certificate authority** for `be-aramco-01.bahra-cables.com`. It is trusted on the LAN because the CA root is distributed to company machines, so the portal shows the lock without warnings. It is **not publicly trusted** — which is precisely why the callback cannot use this hostname and instead uses the Microsoft-managed `msappproxy.net` domain (§5.1). This is the recommended internal arrangement; no action needed beyond tracking the renewal date.
- Minimum TLS version: 1.2. Disallow TLS 1.0/1.1 and weak ciphers.
- HSTS header: `Strict-Transport-Security: max-age=31536000; includeSubDomains`.

### 5.1 The only public surface: the Adaptive-Card callback

The callback runs over **Microsoft Entra Application Proxy**, which **supersedes the devtunnel** described in earlier plans. Security-relevant properties:

| Property | Value | Why it matters |
|---|---|---|
| Connector direction | **Outbound-only** (443 to `*.msappproxy.net`, `*.servicebus.windows.net`) | **No inbound firewall port, no public IP, no port-forward.** The VM stays LAN-only. This is strictly better than the devtunnel it replaced |
| Pre-authentication | **Passthrough** (required) | Outlook sends a **service** token; Entra-ID pre-auth would redirect to a login page and break the buttons. **The proxy therefore authenticates nothing — the app's own token check (§2.3) is the entire boundary** |
| Published path | **Intended:** only the callback. **Actual:** the Internal URL points at IIS so the `/rfp` prefix survives — which roots the publish at the site, not the callback path | ⚠️ **The dashboard, `/upload`, and the unauthenticated `/api/automation/*` may therefore be publicly reachable.** Verify and restrict — see RR-21 |
| Users and groups | empty | Passthrough forwards anonymously by design |

**Verify the negative** — this is a standing control check, not a one-off. From off-LAN:

```powershell
# SHOULD be unreachable — with a site-rooted publish they probably are not. If they respond, see RR-21.
curl.exe -i https://bahrarfpadaptivecardcallback-bahracables.msappproxy.net/rfp/health
curl.exe -i https://bahrarfpadaptivecardcallback-bahracables.msappproxy.net/rfp/api/login
```

If either responds, the publish scope has been widened and the whole LAN-only posture is void. Escalate immediately.

Runbook: [`Azure-App-Proxy-Adaptive-Card-Setup.md`](../../Azure-App-Proxy-Adaptive-Card-Setup.md).

---

## 6. Data classification

| Data | Classification | Location | Notes |
|---|---|---|---|
| Bidder pricing | **Confidential** | `rfps_v2.Matched_Data`, `rfp_team.response_data` | Visible only to Admin and the responding Bidder |
| SAP material master | Internal | `cr673_bahra_material_master` | Sanitised — no costs |
| User PII (name, email) | Internal | `cr673_bahra_users` | Email is also primary identifier |
| Password hashes | **Confidential** | `cr673_bahra_users.password_hash` | bcrypt, salted per row |
| Audit logs | **Confidential** (regulatory) | `cr673_bahra_audit_logs` | Retain indefinitely. Incomplete — see §7.1 |
| Ariba session screenshots / page HTML | Internal | `backend\LOGS\` failure folders | **May capture a logged-in portal session.** Purge after 90 days (manual — no cleanup job) |
| Downloaded BOQ files | **Confidential** | `backend\ALLRFPs\` | Bidder-facing pricing source documents |
| Secrets | **Confidential** | `backend\config\config.py` (plaintext, untracked) | §4.1 |

**Do not** log raw passwords, session cookies, or Dataverse bearer tokens. Note that unhandled exceptions are caught by the global handler in `dashboard_main.py`, which returns only an 8-character `error_id` to the client and writes the traceback server-side — keep it that way; do not surface tracebacks in responses.

---

## 7. Audit trail

Rows are written to `cr673_bahra_audit_logs` by [services/audit_service.py](../../backend/services/audit_service.py).

**Row fields:** `action`, `category`, `actor_email`, `actor_name`, `target_type`, `target_id`, `details` (JSON, **truncated to 4000 characters**), `ip_address`, `created_date`.

**Categories:** `AUTH`, `USER`, `ROLE`, `RFP`, `SYSTEM`.

**Actions actually emitted** — this is the complete list, not an illustrative sample:

| Category | `action` values |
|---|---|
| `AUTH` | `LOGIN`, `LOGIN_FAILED`, `LOGOUT`, `PASSWORD_CHANGED`, `PASSWORD_RESET` |
| `USER` | `USER_CREATED`, `USER_UPDATED`, `USER_DELETED`, `USER_ACTIVATED`, `USER_DEACTIVATED`, `USER_UNLOCKED` |
| `ROLE` | `ROLE_CREATED`, `ROLE_UPDATED`, `ROLE_DELETED`, `ROLE_PERMISSIONS_UPDATED`, `SEED_ROLES` |
| `SYSTEM` | `SETTING_UPDATED`, `SETTING_REVEALED` (audits reads of masked secrets) |
| `RFP` | **none — see below** |

### 7.1 ⚠️ Coverage gaps — what the audit log does NOT tell you

Three limits that materially change how much weight this log can carry:

1. **No RFP operation is audited.** The `RFP` category is **defined in the code but never used**. Downloads, submits, declines, reminders, and delegations — the system's core business actions, the ones that move pricing data — write **nothing** to the audit log. Reconstructing "who submitted this bid" means correlating `cr673_bahra_rfps_v2` (the RFP activity log) and `cr673_bahra_automation_log1` instead. **Do not represent this system as having an end-to-end audit trail of RFP activity.**
2. **No permission denials are recorded.** There is no 403 / authorization-failure event. Probing and privilege-escalation attempts leave no audit evidence.
3. **Writes are fire-and-forget and can be silently lost.** Each write is dispatched to a **daemon thread**; a failure only `print()`s to stdout, and in-flight writes may be **dropped at interpreter exit** (i.e. on every service restart). **The absence of a row is not evidence that an action did not occur.** For any investigation, corroborate against the service stdout log.

**Retention:** indefinite. Purging requires Legal + System Owner approval.

**Access:** `audit_logs.view` permission. By default only Admin. Note that `system_settings.edit` — a *different* permission — is sufficient to reveal masked secrets (§4.6).

**Integrity:** audit rows are append-only; no UI or API updates them. Dataverse retains platform-level change-history on the table itself as a backstop. The log lives in the **same Dataverse tenant as the data it audits** (§11 RR-07).

**Sampling for review:** every quarter, export the past 90 days' audit logs and review failed logins (`LOGIN_FAILED`), role and permission changes, and `SETTING_REVEALED` events. RFP activity must be reviewed from `cr673_bahra_rfps_v2` instead (see gap 1).

---

## 8. Backup & disaster recovery

### 8.1 Data backup

| Asset | Backup mechanism | Frequency | RPO |
|---|---|---|---|
| Dataverse tables | Microsoft platform backup (point-in-time restore) | Continuous | < 5 min |
| `backend\LOGS\`, `backend\ALLRFPs\` | File-level backup (to network share / Azure Files) | Nightly | 24 h |
| **`backend\config\config.py`** | ⚠️ **Nothing automatic — it is untracked and NOT in git.** Must be copied to secure storage manually | On every change | **n/a — this is a gap** |
| SAP / Ariba credentials | Offline secure record | On rotation | n/a |

> ⚠️ **`config.py` is the single biggest DR gap.** It is not in git, not in a secret store, and not backed up by anything the repo provides. **If the VM's disk is lost, the configuration is lost** and must be rebuilt from scratch (tenant/client/secret, Dataverse URL, SharePoint paths, callback URL, email recipients). Take a copy into secure storage now and after every edit, and treat that copy as a secret.

### 8.2 Application recovery (RTO)

| Failure | Recovery action | Target RTO |
|---|---|---|
| `rfp-api` service crash | WinSW restart | < 1 min |
| Host failure | Redeploy from Git **+ restore `config.py` from secure storage** (§8.1) | 4 h |
| Dataverse data corruption | PITR to last known good state | 2 h (support ticket) |
| Azure AD app secret leaked | Rotate via Azure Portal + update `config.py` + `Restart-Service rfp-api` | 30 min |
| **Session secret compromised** | Replace it, restart — **invalidates every session immediately** | 15 min |
| App Proxy connector lost | Re-install the connector **on the VM** and re-register | 1 h — card buttons are down meanwhile |
| Full tenant loss | Re-provision from Git + restore latest Dataverse export | 24 h |

### 8.3 Redeploy procedure (summary)

See [Deployment Guide](09-Deployment-Guide.md) for the full steps. TL;DR:

1. Provision the Windows Server host
2. Clone the repo to `C:\Bahra-Automation-RFP-System` · install Python/Node
3. **Restore `backend\config\config.py` from secure storage** — a clone will not bring it
4. `npm install && npm run build` inside `frontend/` · re-paste `web.config` into `dist\`
5. Register the `rfp-api` service **with working directory = `backend\`** · start
6. Re-register the scheduled tasks: `Register-RfpSchedules.ps1 -UseSystem` (elevated)
7. Install the App Proxy connector on the VM; confirm the callback probe (§5.1)
8. Run the `/health` smoke test

Dataverse data recovers independently via Microsoft.

---

## 9. Incident response

### 9.1 Severity levels

See [Operations Runbook §12](10-Operations-Runbook.md#12-on-call-playbook).

### 9.2 Security-specific playbook

**Suspected credential compromise:**
1. Rotate the affected secret in `backend\config\config.py` (or Azure Portal for `CLIENT_SECRET`) and **`Restart-Service rfp-api`** — the rotation does nothing until the restart
2. **Invalidate all user sessions** by changing the session secret + restart. (Until the hardcoded `"change-me-please"` is replaced, assume **every** session is forgeable — §2.1)
3. Pull audit log rows for the affected principal in the last 30 days — **and corroborate against the service stdout log**, since audit writes can be silently lost (§7.1)
4. Force-reset affected user passwords. Note that deactivating a user **does not end their current session** (up to 2 h)
5. Post-mortem within 5 business days

**Suspected data exfiltration:**
1. Preserve logs (snapshot `backend\LOGS\` and audit rows) before anything else
2. Identify scope: which rows, which user, what time window. ⚠️ **RFP operations are not audited** (§7.1) — reconstruct from `cr673_bahra_rfps_v2` and `cr673_bahra_automation_log1`, and expect gaps
3. Notify System Owner + Legal
4. If customer pricing leaked → notify affected bidders per contract obligation
5. Root-cause: insider · compromised credential · forged session cookie (§2.1) · unauthenticated endpoint (§3.1) · software bug · missing permission check
6. File a CVE-style disclosure only if an external dependency was the root cause

**Actionable-card spoofing attempt:**
1. 401s from `_verify_actionable_message_token` → check the failure log line, which records the actual `aud`/`iss`/`azp` against expected. **Rejected tokens are not written to the audit log** — the service stdout log is the only record
2. Verify `azp`/`appid` is still being checked against Microsoft's Actions app id `48af08dc-…`, and that `ACTIONABLE_CARD_APP_ID_URI` is set (it fails closed if not)
3. Review the Originator ID Target URLs · remove any host that shouldn't be there (e.g. a retired devtunnel)
4. No user action required — rejected tokens did not mutate state

**Unexpected automation run / suspicious trigger:**
1. The automation endpoints are **unauthenticated** (§3.1) — a run has **no actor attached** and nothing identifies who triggered it
2. Distinguish scheduled from ad-hoc: check `backend\LOGS\scheduler\` and Task Scheduler history for `\Bahra-RFP\`. A run with no corresponding scheduler entry was triggered by something else
3. Confirm the automation paths were never published through App Proxy or IIS (§5.1)

### 9.3 Contact tree

| When | Who |
|---|---|
| First discovery | On-call engineer ([Operations Runbook §13](10-Operations-Runbook.md#13-contacts)) |
| SEV-1 / SEV-2 within 15 min | **System Owner — Manish Soni (Manish.soni@dynatechconsultancy.com)** |
| Security-classified within 1 h | Organisation CISO / InfoSec team |
| PII breach within 24 h | Legal + DPO (if applicable under local law) |

---

## 10. Compliance checklist

Use before go-live and on every major release. **Items marked ❌ are known-unmet today** — see §11.

- [ ] ❌ Session secret replaced — the hardcoded `"change-me-please"` is still in `dashboard_main.py` (§2.1)
- [ ] ❌ `UPLOAD_TOKEN_SECRET` replaced — still at its placeholder default (§4.2)
- [ ] ❌ Automation endpoints authenticated — all 10 are open; today they rely on network position alone (§3.1)
- [ ] ❌ `GET /api/actionable-card/responses/{rfp_id}` authenticated (§3.1)
- [ ] ❌ Idle timeout enforced — the config keys exist but no code reads them (§2.1)
- [ ] ❌ RFP operations audited — the `RFP` category is never emitted (§7.1)
- [ ] `CLIENT_SECRET` moved out of the plaintext config file into env var / Key Vault (§4.4)
- [ ] **`backend\config\config.py` copied to secure storage** — it is untracked, unbacked-up, and unrecoverable if the disk is lost (§8.1)
- [ ] `config.py` confirmed still gitignored and never committed
- [ ] HTTPS enforced via IIS (backend stays on `127.0.0.1:8000`, never `0.0.0.0`)
- [ ] Session cookie `Secure=true`
- [ ] **App Proxy scope verified from off-LAN** — confirm what `…msappproxy.net/rfp/health` and `/rfp/api/login` actually return. They *should* be unreachable; the current site-rooted publish likely serves them (§5.1, RR-21)
- [ ] **App Proxy pre-authentication is still `Passthrough`** (Entra-ID pre-auth breaks the buttons)
- [ ] `/api/automation/*` confirmed **not** reachable from the internet, on **both** mount paths (§3.1)
- [ ] Default `Admin` account password changed; shared admin account disabled
- [ ] `EMAIL_MODE` set to `prod`; recipient lists verified in System Settings
- [ ] CORS `allow_origins` locked to the production hostname(s) — no `*`
- [ ] Adaptive-card Originator ID registered; Target URLs contain the App Proxy host and **no retired devtunnel**
- [ ] Azure AD app granted **only** required Graph scopes
- [ ] Dataverse Application User granted least-privilege security role (custom role preferred over System Administrator)
- [ ] Dataverse target org confirmed — the shipped default is a **UAT** org (§Deployment §1)
- [ ] Access review completed within last 6 months — **including who holds `system_settings.edit`, which can reveal secrets** (§4.6)
- [ ] Backup verified — restore test completed within last 90 days
- [ ] Audit log export scheduled quarterly
- [ ] Secret rotation calendar populated for the next 12 months
- [ ] Dependency vulnerability scan (pip-audit, npm audit) run in the last 30 days with no HIGH/CRITICAL unresolved

---

## 11. Known residual risks

Ordered roughly by severity. These are **current, verified findings**, not hypotheticals.

| ID | Risk | Mitigation / accepted trade-off |
|---|---|---|
| RR-01 | **Session secret is hardcoded** (`"change-me-please"`, in git) — session cookies are **forgeable by anyone with source access**, including as Admin | **Unmitigated.** Fix: [Deployment §11.2](09-Deployment-Guide.md#112-replace-the-session-secret). Tracked in `backend/Support-Files/OPTIMIZATION_PLAN.md` |
| RR-02 | **All 10 automation endpoints are unauthenticated** (and double-mounted, so two paths each). Anyone reaching port 8000 can trigger Playwright runs or send bidder email | Mitigated **only** by network position: backend on localhost, LAN-only IIS, App Proxy publishing just the callback path. Never publish these |
| RR-03 | **Secrets sit in plaintext in an untracked local config file**, with no secret store and manual rotation. Readable by anyone with RDP/filesystem access. Also **not backed up** (§8.1) | Correct framing: **not** committed to git (verified) — the risk is host-local exposure + DR loss. Fix: env vars / Key Vault (§4.4) |
| RR-04 | **No idle timeout** despite `IDLE_TIMEOUT_SECONDS` etc. existing in config — nothing reads them. Effective lifetime is a flat 2-hour absolute cookie | **Unmitigated.** Do not claim an idle timeout in control questionnaires |
| RR-05 | **RFP operations are not audited** — the `RFP` category exists but is never emitted. No record of who submitted/declined a bid | Reconstruct from `cr673_bahra_rfps_v2` + `cr673_bahra_automation_log1`. Fix: emit `RFP` audit events |
| RR-06 | **Audit writes are fire-and-forget on a daemon thread** and can be silently lost (including at every service restart) | Absence of a row proves nothing. Corroborate with stdout logs. Fix: synchronous or queued writes with failure handling |
| RR-07 | **Permission changes require re-login** — a revoke stays ineffective for up to 2 hours | Terminate the session on high-severity revokes. Fix: per-request permission read |
| RR-08 | **`require_admin` is a hardcoded role-name check** that bypasses permissions; renaming the `Admin` role breaks admin routes | Don't rename the role. Fix: replace with a permission check |
| RR-09 | **`system_settings.edit` alone reveals masked secrets** — no separate reveal permission | Treat that grant as secret-read access in reviews (§4.6). Reveals are audited (`SETTING_REVEALED`) |
| RR-10 | **Frontend permissions persist to `localStorage`** and are user-editable | By design — client gating is cosmetic; the backend enforces. Risk is only where a backend route lacks a guard (RR-02) |
| RR-11 | **No permission-denial (403) auditing** | Probing leaves no audit evidence |
| RR-12 | `UPLOAD_TOKEN_SECRET` at its placeholder default | Replace (§4.2) |
| RR-13 | No rate-limiting on the login endpoint | Mitigate with an IIS rate-limit rule; future: slowapi middleware |
| RR-14 | No MFA for portal login | Accepted v1; relies on the LAN perimeter + strong passwords. Future: delegate auth to Entra ID |
| RR-15 | **Passthrough App Proxy authenticates nothing** — the app's own token check is the entire boundary for the one public path | Accepted and necessary (pre-auth breaks Outlook's service token). The token check is strict: fixed Actions app id, fails closed on unconfigured audience (§2.3) |
| RR-16 | Portal cert is internal-CA-issued — LAN-trusted, not publicly trusted | **Accepted — this is the intended internal arrangement.** It is why the callback uses the Microsoft-managed `msappproxy.net` domain rather than this hostname. Only ongoing action: track the renewal date |
| RR-17 | Single FastAPI process = single point of failure; `_RUN_STATE` is in-memory, process-local, and assumes one worker | WinSW auto-restart. HA would need a shared lock, not just a second process |
| RR-18 | Ariba scraper uses shared credentials | Mitigate by isolating the server and vaulting the password |
| RR-19 | Audit log lives in the same Dataverse tenant as the data it audits | Mitigate by exporting quarterly to immutable storage (Azure Blob with legal hold) |
| RR-20 | **Reminder emails are not sending** (dead devtunnel; no scheduled task) — an availability/compliance gap in bidder communication, not a breach | Manual workaround + fix in [Operations Runbook §7.3](10-Operations-Runbook.md#7-scheduled-jobs) |
| RR-21 | **App Proxy publish is likely broader than the callback path.** The live callback is `…/rfp/api/actionable-card/response`; for that prefix to survive, the Internal URL must point at IIS at the site root rather than being path-scoped. Sibling paths under the same origin — including `/rfp/api/login`, `/rfp/health`, the upload page, and the **entirely unauthenticated** `/rfp/api/automation/*` — may therefore be reachable from the public internet. This would remove the network position that most of §1's mitigations rely on | **Verify first** (§5.1 curl checks from off-LAN). If confirmed: scope the publish to the callback path and update `ACTIONABLE_CARD_CALLBACK_URL` to the resulting shorter public URL (then restart `rfp-api`), or block sibling paths at IIS for proxy-sourced traffic. **Highest-priority open item** — `/api/automation/*` has no auth at all |

---

## 12. References

- [services/permission_definitions.py](../../backend/services/permission_definitions.py) — permission catalogue (42 keys)
- [services/dynamic_role_service.py](../../backend/services/dynamic_role_service.py) — RBAC enforcement
- [middleware/auth.py](../../backend/middleware/auth.py) — `get_current_user`, `require_permission`, `require_admin`
- [services/audit_service.py](../../backend/services/audit_service.py) — audit writes
- [helpers/dataverse_helper.py](../../backend/helpers/dataverse_helper.py) — token handling
- [routes/actionable_cards.py](../../backend/routes/actionable_cards.py) — adaptive-card token verification
- [`Azure-App-Proxy-Adaptive-Card-Setup.md`](../../Azure-App-Proxy-Adaptive-Card-Setup.md) — callback exposure runbook (current target state)
- [`HTTPS-NotSecure-Fix-Plan.md`](../../HTTPS-NotSecure-Fix-Plan.md) — earlier IIS/TLS plan; its Phase-2 devtunnel is retired by App Proxy
- Microsoft — [Actionable messages security and authentication](https://learn.microsoft.com/outlook/actionable-messages/security-requirements)
- Microsoft — [Dataverse security model](https://learn.microsoft.com/power-platform/admin/wp-security-cds)
- OWASP Application Security Verification Standard (ASVS) 4.0 — used as reference for control scope

---

## 13. Change history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-04-22 | Manish Soni | Initial security & compliance baseline |
| 1.1 | 2026-07-17 | Manish Soni | Verified against code; App Proxy callback, Task Scheduler migration, prod topology, 42 permissions, corrected security posture |
