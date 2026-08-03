---
title: Deployment Guide — Bahra Electric RFP Automation
version: 1.1
last_updated: 2026-07-17
owner: Manish Soni (Manish.soni@dynatechconsultancy.com)
status: Draft
audience: IT Ops, DevOps, System Administrators
---

# Deployment Guide

> **Goal.** Take a clean Windows VM and end up with the RFP Automation portal running, reachable from a browser, talking to Dataverse, sending emails, and driven on a schedule by Windows Task Scheduler.
>
> **Time budget.** ~90 minutes for a first-time deploy; ~20 minutes for subsequent updates.

---

## 0. The existing production deployment

This guide describes a clean install. The **current production system** is already deployed with these values — use them, not the dev-machine paths, when working on the live server:

| Thing | Value |
|---|---|
| Server VM (LAN-only) | `192.168.111.192` (Windows Server 2016) |
| Repo root | `C:\Bahra-Automation-RFP-System` — **not** the dev path `C:\python\RFP-automation` |
| Virtualenv | `C:\Bahra-Automation-RFP-System\env\Scripts\python.exe` |
| Config file | `C:\Bahra-Automation-RFP-System\backend\config\config.py` |
| Windows service | **`rfp-api`** (WinSW) |
| Backend bind | **`127.0.0.1:8000`** — localhost-only |
| Portal URL (internal) | `https://be-aramco-01.bahra-cables.com/rfp` via **IIS** reverse proxy |
| TLS | **Internal-CA-issued** cert for `be-aramco-01.bahra-cables.com`, from Bahra's certificate authority — trusted on the LAN (CA root distributed to company machines), **not publicly trusted** |
| Adaptive-card callback | **Microsoft Entra Application Proxy (Passthrough)** — see §10.3 |
| Scheduling | **Windows Task Scheduler**, folder `\Bahra-RFP\` — see §11.5 |

> **This VM also hosts the COA application. Do not touch COA** — its IIS site, services, and bindings are out of scope for every procedure in this guide.

---

## 1. Pre-flight checklist

Before you touch the server, confirm you have access to all of the following. Missing any one of these will block deployment.

| # | What | Where to get it |
|---|------|-----------------|
| 1 | **Windows VM** (Win Server 2016+ or Win 11 Pro), Administrator rights, ≥4 vCPU / 8 GB RAM / 40 GB disk | IT Ops |
| 2 | **Outbound internet** to `*.dynamics.com`, `*.sharepoint.com`, `graph.microsoft.com`, `service.ariba.com`, `*.environment.api.powerplatform.com`, `login.microsoftonline.com` — and, for the App Proxy connector, `*.msappproxy.net` + `*.servicebus.windows.net` **without TLS inspection** | IT/Network |
| 3 | **Inbound 443 from the corporate LAN only.** **No inbound rule, public IP, or port-forward is needed for the Adaptive-Card callback** — the Entra App Proxy connector is outbound-only (§10.3) | IT/Network |
| 4 | **Microsoft Entra ID P1 or P2** on the tenant — App Proxy ("Add an on-premises application") does not appear without it | Entra admin |
| 5 | **Azure AD app registration** with `TENANT_ID`, `CLIENT_ID`, `CLIENT_SECRET` and Dataverse + Graph permissions granted | Azure portal admin |
| 6 | **Dataverse environment URL** (e.g., `https://operations-bahrauat-1.crm11.dynamics.com` — note this is a **UAT** org; confirm the intended target before go-live) | Power Platform admin |
| 7 | **SharePoint site** at the path in `SITE_PATH` with `RFP-logs/` folder writable | M365 admin |
| 8 | **Actionable Email Developer Dashboard** access for the originator ID, to whitelist the callback host | M365 admin |
| 9 | **Source code** access (git clone URL or zip) | Project owner |
| 10 | **Reverse-proxy plan** — IIS (production uses IIS + URL Rewrite + ARR) for TLS termination and SPA hosting | IT Ops |

> **Production checklist** — in addition to the above, complete §11 before users touch the system.

---

## 2. Architecture recap

One FastAPI process on one host (see [SAD §4](../02-architecture/04-SAD-Software-Architecture-Document.md)):

| Process | Port | Purpose |
|---------|------|---------|
| `dashboard_main.py` | **8000** | **The canonical entry point.** Mounts every router: REST API, RBAC, dashboard, automation, actionable-card callback |
| `automation_main.py` | 8100 | Standalone-automation deployment mounting only the automation router — **not used in production**; the same router is already mounted by `dashboard_main`. Do not add functionality to it |

Production runs **only `dashboard_main.py`**, as the `rfp-api` service. The React frontend is built to static files and served by IIS; IIS reverse-proxies `/api`, `/dashboard`, `/upload`, `/health` to `127.0.0.1:8000`.

---

## 3. Install system prerequisites

### 3.1 Python 3.10

Download Python 3.10.x (64-bit) from python.org. During install:

- ✅ Check **Add Python to PATH**
- ✅ Check **Install for all users**
- ✅ Disable PATH length limit (final step)

Verify:
```powershell
python --version
# Python 3.10.x
```

> The codebase relies on Windows-specific `WindowsProactorEventLoopPolicy` and `%#m/%#d/%Y` strftime tokens. **Do not deploy on Linux without changes.**

### 3.2 Node.js 20 LTS

Required only if you need to rebuild the React frontend on the server. If you're shipping a pre-built `frontend/dist/`, you can skip this.

Download Node.js 20 LTS from nodejs.org. Verify:
```powershell
node --version    # v20.x
npm --version
```

### 3.3 Git (optional but recommended)

For pulling updates without re-uploading the whole tree.

### 3.4 IIS / nginx (recommended for production)

Used as a reverse proxy in front of `:8000` for TLS termination, response compression, and static-file caching. Configuration is shown in §10.

---

## 4. Get the source code

```powershell
# Production uses C:\Bahra-Automation-RFP-System. The dev machine uses C:\python\RFP-automation.
git clone <your-repo-url> C:\Bahra-Automation-RFP-System
cd C:\Bahra-Automation-RFP-System
```

Or unzip a release archive into the same path. End state: the deployment root contains `backend/` (which holds `dashboard_main.py`, `automation_main.py`, `config/`, `routes/`, `services/`, `helpers/`, `rfp/`), plus `frontend/`, `scripts/`, and `env/`.

> **Layout note:** all Python code lives under `backend/`. The virtualenv (`env/`) and the `frontend/` and `scripts/` folders sit at the **repo root**, one level above `backend/`.

---

## 5. Python virtualenv + dependencies

```powershell
cd C:\Bahra-Automation-RFP-System

# Create virtualenv at the repo root (the project uses 'env' as the directory name)
python -m venv env

# Activate
.\env\Scripts\Activate.ps1
# If PowerShell blocks the script:
#   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Upgrade pip
python -m pip install --upgrade pip

# Install dependencies
pip install -r backend\Support-Files\requirements.txt
```

> Installation takes 5-15 minutes. Heavy packages: `playwright`, `pandas`, `numpy`, `pyarrow`, `selenium`.

### 5.1 Install Playwright browsers

The Ariba scraper uses Chromium via Playwright. Browser binaries are downloaded separately:

```powershell
playwright install chromium
```

> ⚠️ **Playwright installs browsers per-user, into the profile of whoever runs `playwright install`.** The `rfp-api` service launches Chromium, so the browsers must be installed **for the identity the service runs as**. If `rfp-api` runs as LocalSystem and you installed the browsers as yourself, every service-driven run fails with `Executable doesn't exist at C:\Windows\system32\config\systemprofile\AppData\Local\ms-playwright\...` while manual runs from your own session work fine. Either run `playwright install chromium` under the service identity (e.g. via `psexec -s`) or set `PLAYWRIGHT_BROWSERS_PATH` to a shared location and install there.

### 5.2 Verify the install

```powershell
python -c "import fastapi, playwright, msal, pandas; print('ok')"
# ok
```

> **There is no automated test suite of any kind** — verified 2026-07-17. No `tests/` directory, no `pytest` suite, no load-test tooling. Do not look for an automated gate before deploy: post-deploy verification (§3) is manual.

---

## 6. Configure the application

All configuration lives in [`backend/config/config.py`](../../backend/config/config.py). Open it and update:

> **`backend/config/config.py` is not tracked in git** — it is gitignored and has never been committed. Each host carries its own untracked copy, which `git pull` will not overwrite. That also means it is not restored by a clone: keep a copy in secure storage (see [Security & Compliance §4](12-Security-and-Compliance.md#4-secrets-management)).
>
> **Every change to `config.py` requires a service restart** (`Restart-Service rfp-api`). Nothing re-reads the file at runtime.

### 6.1 Azure AD / Dataverse — §1 and §2

```python
TENANT_ID     = "<your-tenant-guid>"
CLIENT_ID     = "<your-app-client-id>"
CLIENT_SECRET = "<your-app-client-secret>"
RESOURCE_URL  = "https://<your-env>.crm11.dynamics.com"
```

> The value shipped today is `https://operations-bahrauat-1.crm11.dynamics.com` — a **UAT** organisation configured as the default. Confirm this is intended before go-live.

### 6.2 SharePoint — §3

```python
SHAREPOINT_HOSTNAME = "<your-tenant>.sharepoint.com"
SITE_PATH           = "/sites/<your-site-path>"
DRIVE_NAME          = "Documents"
SP_BASE_FOLDER      = "RFP-logs"
```

### 6.3 Actionable cards & Power Automate — §4

```python
ACTIONABLE_CARD_ORIGINATOR_ID  = "<your registered originator ID>"
ACTIONABLE_CARD_CALLBACK_URL   = "https://bahrarfpadaptivecardcallback-bahracables.msappproxy.net/rfp/api/actionable-card/response"
ACTIONABLE_CARD_APP_ID_URI     = "<AppIdUri of the token-audience app>"
ACTIONABLE_CARD_ACTIONS_APP_ID = "48af08dc-..."   # Microsoft's fixed Actions app id — NOT your app id
UPLOAD_BASE_URL                = "https://be-aramco-01.bahra-cables.com/rfp/"
FLOW_URL                       = "<full HTTP-trigger URL of your run-now flow>"
POWER_AUTOMATE_FLOW_NAME       = "Bahra-E-binding-cron-job"
POWER_AUTOMATE_RECURRENCE_TRIGGER_NAME = "Recurrence"
```

> ⚠️ **`ACTIONABLE_CARD_CALLBACK_URL` must keep the exact suffix `/api/actionable-card/response`.** The card builder in [`backend/helpers/email_helper.py`](../../backend/helpers/email_helper.py) appends `/refresh` and derives `/decline` from this one value, so every button follows from it. Change the host, never the suffix.
>
> This value is **config-file only** — it is in `REMOVED_KEYS` in `backend/Support-Files/seed_system_settings.py`, so it is deliberately **not** read from the Dataverse System Settings table. `config.py` is the single source of truth for it.

> **Originator ID** is registered via https://outlook.office.com/connectors/oam/publish — required for Adaptive Cards in Outlook to render, and the callback host must be listed there as a Target URL before the buttons will POST.

> ⚠️ **`POWER_AUTOMATE_FLOW_NAME` points at `Bahra-E-binding-cron-job` — the flow the Task Scheduler migration turns off.** This makes the portal's *Schedule Automation* page a silent no-op. See [Operations Runbook §7.4](10-Operations-Runbook.md#7-scheduled-jobs).

### 6.4 Email mode — §6

```python
EMAIL_MODE = "dev"     # change to "prod" only after verifying recipient lists
DEV_EMAIL  = "<inbox you want all dev emails routed to>"
```

> **Stay in `"dev"` mode** for the first run end-to-end. Switch to `"prod"` after §11.4.

### 6.5 Session secret — §7

The hardcoded `SessionMiddleware(secret_key="change-me-please")` in `dashboard_main.py` is **not safe for production** — anyone with source access can forge a session cookie. See §11.2.

`UPLOAD_TOKEN_SECRET` likewise still carries its placeholder default (`"change-me-upload-secret-set-via-system-settings"`). Replace it.

---

## 7. Provision Dataverse tables

> **Idempotent.** All setup scripts skip existing tables/columns and can be re-run safely.

**Run from inside `backend/`** — the scripts use the same top-level imports as the server:

```powershell
cd C:\Bahra-Automation-RFP-System\backend

# 1. Master data (material_master, keywords, rfp_team)
..\env\Scripts\python.exe Support-Files\setup_master_data_tables.py

# 2. RFPs v2 main table
..\env\Scripts\python.exe Support-Files\setup_rfps_v2_table.py

# 3. Analytics columns on rfps_v2
..\env\Scripts\python.exe Support-Files\setup_rfp_activity_columns.py

# 4. Dynamic team-column definitions
..\env\Scripts\python.exe Support-Files\setup_dynamic_columns_table.py

# 5. Open-RFP reminder tracker + delegation
..\env\Scripts\python.exe Support-Files\setup_open_rfp_reminder_table.py
..\env\Scripts\python.exe Support-Files\setup_delegation_table.py

# 6. RFP status category options
..\env\Scripts\python.exe Support-Files\setup_rfp_status_category_options.py

# 7. Seed runtime settings (email recipients)
..\env\Scripts\python.exe Support-Files\seed_system_settings.py
```

> **There is no `setup_rbac_tables.py`** — that script has been deleted from the tree. The RBAC tables (`cr673_bahra_roles`, `cr673_bahra_role_permissions`, `cr673_bahra_audit_logs`, `cr673_bahra_user_status`) must already exist; roles are seeded separately via §7.1.

Each script prints its resolved **`EntitySetName`** after `PublishXml`. **Compare it against `config/config.py` and paste it into the matching `*_API` constant — never guess the pluralization.** Dataverse is inconsistent about it (`cr673_bahra_roles` → `cr673_bahra_roleses`, but `cr673_bahra_rfp_reminder_for_info` → `cr673_bahra_rfp_reminder_for_infos`).

> **The following tables must already exist** (not created by the scripts in this repo): `cr673_bahra_users`, `cr673_bahra_sap_infomation`, `cr673_bahra_automation_log1`, `cr673_bahra_automation_schedules`, `cr673_bhara_rfp_status`, `cr673_bahra_system_settings`, `cr6db_cr673_bahra_rfp_response`. If any are missing, create them in the Power Platform maker portal using the column lists in [Data Dictionary §5/§7/§8](../02-architecture/07-Data-Dictionary-and-ER-Diagram.md).

### 7.1 Seed default roles

Either via API after the server is running:
```bash
curl -X POST http://localhost:8000/api/roles/seed -H "Cookie: session=..."
```

Or directly via the Roles admin page. Creates **`Admin` (all 42 permissions)** and **`RFP Bidder` (10 permissions)** — see [RBAC Permissions Matrix §3](11-RBAC-Permissions-Matrix.md#3-default-roles).

### 7.2 Create the first Admin user

Until the first user is created, no one can log in. Either:

- **Direct insert** into `cr673_bahra_users` via Power Apps with `email`, `name`, `role=Admin`, and a bcrypt-hashed `password`, or
- **Run the bootstrap script** if your project provides one (check `Support-Files/` for `create_admin.py` — not in standard tree)

---

## 8. Build the frontend

```powershell
cd C:\Bahra-Automation-RFP-System\frontend
npm install
npm run build
# Output: frontend/dist/
```

Serve `dist/` from **IIS**, and reverse-proxy the API paths to `127.0.0.1:8000` (§10). Do not mount the SPA inside FastAPI in production — the backend is bound to localhost and IIS is the only thing listening on 443.

> `npm run build` **erases `dist/`**, including the `web.config` that carries the IIS rewrite rules. Keep a backup copy of `web.config` and re-paste it after every rebuild.

---

## 9. Start the backend

### 9.1 The working-directory rule (read this first)

**The backend MUST be launched with its working directory set to `backend/`.** This is not a style preference — two things break otherwise:

1. It puts `backend/` on `sys.path`, so the top-level imports (`from config.config import ...`, `from routes.api import ...`) resolve.
2. The runtime data folders are anchored to `os.getcwd()` — `ALLRFPs/`, `LOGS/`, `logs/` must resolve **inside `backend/`**. Launch from the repo root and the app writes downloads and failure bundles to the wrong place.

The same applies to any one-off script (§7, §13).

### 9.2 Manual start (smoke test)

```powershell
# The working directory MUST be backend\
cd C:\Bahra-Automation-RFP-System\backend
..\env\Scripts\python.exe dashboard_main.py
```

Sanity check:
```powershell
curl http://localhost:8000/health
# {"status":"healthy","dataverse":"connected"}
```

> The `/health` check probes Dataverse (reads one row from the users table) — a 503 means Dataverse is unreachable, not that the process is down.

Open the portal in a browser. The login screen should load. Log in as the Admin user from §7.2.

`automation_main.py` (port 8100) is **not** started in production — its routes are already mounted by `dashboard_main`.

### 9.3 Run as a Windows service (production)

Production runs a single service, **`rfp-api`**, under **WinSW**. Its working directory must be `C:\Bahra-Automation-RFP-System\backend` (§9.1).

```powershell
Restart-Service rfp-api
# or
net stop rfp-api ; net start rfp-api

Get-Service rfp-api
Invoke-WebRequest http://127.0.0.1:8000/health -UseBasicParsing
```

Verify in `services.msc` — `rfp-api` should be **Running** and set to **Automatic** start.

> **Service identity matters for Playwright** — see the warning in §5.1. If `rfp-api` runs as LocalSystem, Chromium must be installed for LocalSystem.

---

## 10. Reverse proxy and public exposure

### 10.1 IIS (the RFP portal — LAN only)

1. Install IIS + URL Rewrite + Application Request Routing; enable **proxy** in ARR Server Proxy Settings
2. Create a site bound to hostname `be-aramco-01.bahra-cables.com` on port **443** with the TLS cert. The RFP app is served under the **`/rfp` path** on this site (the COA app shares the same host), so the binding is host + port only — the `/rfp` prefix is a path, not part of the binding
3. Add `web.config` rewriting:
   - `/api/*`, `/upload/*`, `/health` → `http://127.0.0.1:8000`
   - `/dashboard/*` → `http://127.0.0.1:8000` **only when `Accept` is not `text/html`** (so page loads are served by the SPA, not proxied)
   - everything else → `frontend/dist/index.html` (SPA fallback)
4. Point the site's physical path at `frontend\dist`

The TLS cert is **issued by Bahra's internal certificate authority** for `be-aramco-01.bahra-cables.com`. It is trusted on the LAN because the CA root is distributed to company machines (typically via AD/GPO auto-enrolment), so browsers show the lock with no warning. It is **not** publicly trusted — which is why the Adaptive-Card callback cannot use this hostname and instead goes through App Proxy on a Microsoft-managed domain (§10.3).

> This VM also serves COA from IIS. Edit only the RFP site's bindings and `web.config`.

### 10.2 What stays LAN-only

Everything except the Adaptive-Card callback:

- The RBAC dashboard and all session-authenticated `/api/*`, `/dashboard/*`, `/upload` routes.
- **`/api/automation/*` — these endpoints have no authentication at all.** They must never be internet-reachable.

### 10.3 Adaptive-Card callback — Microsoft Entra Application Proxy

> **This supersedes the dev-tunnel.** Earlier versions of this guide told you to *"keep the existing dev-tunnel running"* for Outlook callbacks. **That is no longer correct** — the callback now runs over Entra Application Proxy and the devtunnel is retired. The full step-by-step runbook is [`Azure-App-Proxy-Adaptive-Card-Setup.md`](../../Azure-App-Proxy-Adaptive-Card-Setup.md) at the repo root; the earlier plan in [`HTTPS-NotSecure-Fix-Plan.md`](../../HTTPS-NotSecure-Fix-Plan.md) is superseded from its Phase 2 onward.

**Why:** Outlook's Actions service calls the card buttons from the **public internet**, but the VM is LAN-only with the backend on `127.0.0.1:8000`. App Proxy's connector is **outbound-only** — it dials out on 443 to `*.msappproxy.net` and `*.servicebus.windows.net`. **No inbound firewall port, no public IP, no port-forward.**

| Setting | Value | Why |
|---|---|---|
| Licensing | **Entra ID P1 or P2** | Without it, "Add an on-premises application" does not appear |
| Connector host | **the RFP VM itself** (`192.168.111.192`) | The backend listens on `127.0.0.1:8000`; a connector on any other host cannot reach it |
| Internal URL | **Points at IIS**, so the `/rfp` prefix survives to the backend (IIS strips it and forwards to `127.0.0.1:8000`) | Required for the live callback path `…/rfp/api/actionable-card/response` to resolve. **This makes the publish broader than the callback path — see the scope warning below** |
| External URL | default `https://bahrarfpadaptivecardcallback-bahracables.msappproxy.net/rfp/api/actionable-card/` | A custom domain would need a **publicly trusted** cert; the internal-CA cert is not publicly trusted and would be rejected |
| **Pre Authentication** | **Passthrough** ← critical | Outlook sends a **service** token, not an interactive sign-in. With Entra-ID pre-auth the proxy redirects the call to a login page and **the buttons break** |
| Users and groups | **empty** | Passthrough forwards anonymously; the app validates the token itself (§10.4) |
| Validate Backend TLS Certificate | Off | Fine for the internal leg |
| Translate URLs in Application Body | Off | |
| Backend Application Timeout | Default (85 s) | The callback is fast |

**Scope — intended vs. actual.** The *intent* is to publish only `/api/actionable-card/`, keeping the dashboard, the upload page, and `/api/automation/*` LAN-only. **The current configuration does not achieve that.** Because the live callback is `…/rfp/api/actionable-card/response`, the `/rfp` prefix must survive the proxy — which means the publish is rooted at the IIS site rather than scoped to the callback path, so sibling paths under the same origin are likely reachable publicly too.

Verify from an **off-LAN** machine:

```powershell
curl.exe -i https://bahrarfpadaptivecardcallback-bahracables.msappproxy.net/rfp/api/actionable-card/response
#   → expect a 401/500 FROM THE APP (token-validation error). A Microsoft login page means
#     pre-auth was left on. A timeout means the connector can't reach :8000.

# These SHOULD be unreachable — but with a site-rooted publish they probably are not.
curl.exe -i https://bahrarfpadaptivecardcallback-bahracables.msappproxy.net/rfp/health
curl.exe -i https://bahrarfpadaptivecardcallback-bahracables.msappproxy.net/rfp/api/login
```

> ⚠️ **If those last two return a response, the publish is too broad — treat it as a live security issue.** The priority is `/rfp/api/automation/*`: those endpoints have **no authentication whatsoever** (§10.5) and were only ever safe because they were LAN-only. Either scope the publish down to the callback path (then update `ACTIONABLE_CARD_CALLBACK_URL` to the resulting shorter public URL and restart `rfp-api`), or block the sibling paths at IIS for proxy-sourced traffic.

Then:
1. Add the `msappproxy.net` URL to the provider's **Target URLs** in the Actionable Email Developer Dashboard (the originator ID is unchanged — you are only allowing a new host).
2. Set `ACTIONABLE_CARD_CALLBACK_URL` in `config.py` to `https://…msappproxy.net/rfp/api/actionable-card/response` — **exact suffix, see §6.3**.
3. **`Restart-Service rfp-api`.** Config edits do nothing until the service restarts — an unrestarted backend is the known cause of the `500 "APP_ID_URI not configured"` symptom.
4. Point `UPLOAD_BASE_URL` at `https://be-aramco-01.bahra-cables.com/rfp/` (the Upload button is opened by staff from inside the LAN, so it does not need App Proxy), and restart again.

### 10.4 Callback token validation (unchanged by App Proxy)

App Proxy only forwards the request; `_verify_actionable_message_token` in [`backend/routes/actionable_cards.py`](../../backend/routes/actionable_cards.py) is still the security boundary. It:

- Verifies the **RS256 signature** against the tenant's v2.0 JWKS.
- Accepts **both** issuer forms — `https://login.microsoftonline.com/{tenant}/v2.0` **and** `https://sts.windows.net/{tenant}/`. Microsoft sends a **v1.0** token or a v2.0 one depending on the resource app's token-version setting, so `iss` is checked manually after decode.
- Validates `aud` against `ACTIONABLE_CARD_APP_ID_URI` (accepting either the AppIdUri or the bare client id) and **fails closed if that value is unconfigured**.
- Validates `azp` (falling back to `appid` on v1.0 tokens) against `ACTIONABLE_CARD_ACTIONS_APP_ID` — **Microsoft's fixed Actions app id `48af08dc-…`, not our app id**. This stops any other caller holding a token for our audience.

The token-audience app must have **Expose an API** configured and `48af08dc-…` **authorized** on it. Provider approval alone only makes the card *render* — without that authorization it never POSTs.

---

## 11. Production hardening

> **Do not skip.** The defaults in `config/config.py` and `dashboard_main.py` are dev-grade.

### 11.1 Move secrets into a managed store

`backend/config/config.py` is **gitignored and has never been committed** — secrets are not in the repository. But they do live in **plaintext in an untracked file on every host**, with no secret store and **manual rotation**. Move them to environment variables read at startup:

```python
import os
TENANT_ID     = os.environ["TENANT_ID"]
CLIENT_ID     = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]
```

Set values via the WinSW service definition's `<env>` entries or Windows system environment variables. Long-term: Azure Key Vault.

### 11.2 Replace the session secret

`dashboard_main.py` hardcodes:

```python
app.add_middleware(SessionMiddleware, secret_key="change-me-please", max_age=SESSION_TIMEOUT_SECONDS)
```

Anyone with source access can forge a session cookie. Replace with:

```python
SESSION_SECRET = os.environ["SESSION_SECRET"]   # 32+ random bytes, base64-encoded
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, max_age=SESSION_TIMEOUT_SECONDS, https_only=True, same_site="lax")
```

Generate a secret once: `python -c "import secrets; print(secrets.token_urlsafe(32))"`. Do the same for `UPLOAD_TOKEN_SECRET`, which still holds its placeholder default.

> **Note on session lifetime:** the effective timeout is a **flat 2-hour absolute cookie `max_age`**. `IDLE_TIMEOUT_SECONDS`, `SESSION_WARNING_SECONDS`, and `SESSION_REFRESH_INTERVAL` exist in `config.py` but **no code reads them** — there is no idle timeout. Do not assume one is in force.

### 11.3 Lock down CORS

In `dashboard_main.py`, restrict `allow_origins` to your production domain only (remove the localhost / 192.168.* entries).

### 11.4 Switch email mode

After verifying the dev recipient receives a test email and the layout is correct:

1. Set `EMAIL_MODE = "prod"` in `backend/config/config.py` (in `"dev"`, **all** outgoing email routes to `DEV_EMAIL`)
2. Verify recipient lists in the **System Settings** admin page (`EMAIL_TO_NEW_RFP`, `EMAIL_TO_RFP_REMINDER`, `EMAIL_TO_AUTOMATION_FAILURE`, …). These are read from Dataverse **at send time**; the `config.py` constants are only fallbacks for when Dataverse is unreachable
3. `Restart-Service rfp-api`

### 11.5 Register the scheduled tasks

Scheduling has moved **off Power Automate onto Windows Task Scheduler**. Deploy the `scripts\` folder to the server, then from an **elevated** PowerShell session on `192.168.111.192`:

```powershell
cd C:\Bahra-Automation-RFP-System\scripts
.\Register-RfpSchedules.ps1 -UseSystem -WhatIf    # preview
.\Register-RfpSchedules.ps1 -UseSystem            # register
```

**Turn off the two replaced Power Automate flows first**, or both sources fire:

| Flow | Disposition |
|---|---|
| `Bahra-E-binding-cron-job` → `/download-rfps-automation` | **Turn off** — replaced by `RFP-Download-OpenRFPs` |
| `Bahra-sync-open-rfp-status-cron-job` → `/api/sync_portal_data` | **Turn off** — replaced by `RFP-Sync-Portal` |
| `Bahra-RFP-Reminder-Emails-Cron-job` → `/api/rfp-reminder` | **Leave on** — out of scope by decision. ⚠️ It points at the same dead devtunnel, so **reminder emails are not sending today**. See [Operations Runbook §7.3](10-Operations-Runbook.md#7-scheduled-jobs) |

Full cadence, exit codes, and the known issues: [Operations Runbook §7](10-Operations-Runbook.md#7-scheduled-jobs).

### 11.6 Register the Adaptive Card originator ID

At https://outlook.office.com/connectors/oam/publish, register the originator ID matching `ACTIONABLE_CARD_ORIGINATOR_ID`, and add the App Proxy `msappproxy.net` host to the provider's **Target URLs**. Until the originator is approved, Adaptive Cards will not render in Outlook; until the host is a Target URL, the buttons will not POST.

---

## 12. Verify end-to-end

After deployment, run through this acceptance test:

1. **Login** — Admin user can log in via the browser
2. **Dashboard** — `/dashboard` loads, shows last automation time, no console errors
3. **Trigger automation manually** — sidebar → "Download RFPs (open)" → confirm `cr673_bahra_automation_log1` rows appear
4. **Scheduled task** — `Start-ScheduledTask -TaskPath '\Bahra-RFP\' -TaskName 'RFP-Sync-Portal'` → check `Get-ScheduledTaskInfo` for `LastTaskResult = 0` and a new entry in `backend\LOGS\scheduler\`
5. **Email** — verify the dev inbox received the "New RFP" or "No New RFP" email
6. **Adaptive Card** — open the email in Outlook, fill in Results/Remarks, click Submit → verify the response saves; then Refresh and Decline
7. **Callback scope** — from off-LAN, `…msappproxy.net/rfp/health` and `/api/login` are **not** served (§10.3)
8. **Audit log** — `/admin/audit-logs` shows the login events. (RFP operations are **not** audited — see [Security & Compliance §7](12-Security-and-Compliance.md#7-audit-trail))
9. **Health** — `http://127.0.0.1:8000/health` returns `{"status":"healthy","dataverse":"connected"}`

---

## 13. Updating an existing deployment

```powershell
# Stop the service
Stop-Service rfp-api

# Pull new code (config\config.py is untracked — git pull will not overwrite it)
cd C:\Bahra-Automation-RFP-System
git pull

# Update Python deps if requirements changed
.\env\Scripts\Activate.ps1
pip install -r backend\Support-Files\requirements.txt

# Re-run any setup script with new columns (idempotent) — from inside backend\
cd backend
..\env\Scripts\python.exe Support-Files\setup_rfps_v2_table.py
cd ..

# Rebuild frontend if changed — then RE-PASTE web.config into dist\ (npm run build erases it)
cd frontend
npm install
npm run build
cd ..

# Start the service
Start-Service rfp-api

# Smoke test
Invoke-WebRequest http://127.0.0.1:8000/health -UseBasicParsing
```

Neither the App Proxy application nor the connector is affected by a code deploy. If you changed `config.py`, the restart above is what makes it take effect.

---

## 14. Troubleshooting common deployment issues

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `ModuleNotFoundError: No module named 'config'` / `routes` at startup | Backend launched from the repo root instead of `backend\` | Launch with working directory = `backend\` (§9.1). Use `cd backend
..\env\Scripts\python.exe dashboard_main.py`, or fix the service's working directory |
| Downloads/logs appear in the repo root, not `backend\` | Same cause — `os.getcwd()`-anchored folders | Same fix (§9.1) |
| `MSAL: Failed to get access token` | Wrong or expired `CLIENT_SECRET` | Regenerate in Azure portal; update config/env; `Restart-Service rfp-api` |
| `/health` returns 503 | Dataverse read failed | Confirm the app user has data permissions; the check reads one row from `cr673_bahra_userses` |
| `Playwright: Executable doesn't exist at C:\Windows\system32\config\systemprofile\...ms-playwright` | Browsers installed for your user, but `rfp-api` runs as **LocalSystem** | Install Chromium under the service identity, or set a shared `PLAYWRIGHT_BROWSERS_PATH` (§5.1). Classic signature: manual runs work, every scheduled run processes 0 companies |
| `NotImplementedError` on subprocess during automation | Playwright driven directly from a request handler on uvicorn's SelectorEventLoop | Automations must go through `_run_async_in_thread` in `routes/automation.py`, which spins up a `ProactorEventLoop` on its own thread |
| Adaptive Card doesn't render in Outlook | Originator ID not registered | Submit at https://outlook.office.com/connectors/oam/publish |
| Card action returns an Entra **login page** / 302 | App Proxy published with **Entra ID** pre-auth | Set **Pre Authentication = Passthrough** (§10.3) |
| Card action **times out / 502** | Connector can't reach `:8000`, or `rfp-api` is down | Check `/health`; confirm the connector is **Active** and installed **on this VM**; Internal URL = `http://localhost:8000/api/actionable-card/` |
| Card action `500 "APP_ID_URI not configured"` | `config.py` edited but the service was never restarted | `Restart-Service rfp-api` |
| Card action 401 "invalid audience/issuer" | Token-audience app misconfigured | Confirm `ACTIONABLE_CARD_APP_ID_URI`, and that `48af08dc-…` is authorized on the app's Expose-an-API (§10.4) |
| `…/response/refresh` 404 but the base URL works | Callback URL suffix wrong | `ACTIONABLE_CARD_CALLBACK_URL` must end exactly `/api/actionable-card/response` (§6.3) |
| Connector won't register / "Unauthorized" | TLS inspection on outbound 443 | Exempt `*.msappproxy.net` + `*.servicebus.windows.net` from inline TLS inspection |
| Upload button opens a dead page | `UPLOAD_BASE_URL` still on the old devtunnel | Set to `https://be-aramco-01.bahra-cables.com/rfp/`, `Restart-Service rfp-api` |
| 401 from Dataverse on a specific table | Permissions not granted on that table | Power Platform admin → Security roles → grant Read/Write to your app user |
| Schedule edits in the portal don't change the cadence | **Expected post-migration.** The page targets `Bahra-E-binding-cron-job`, which is now off; the real cadence is Task Scheduler | See [Operations Runbook §7.4](10-Operations-Runbook.md#7-scheduled-jobs) |

---

## 15. Reference

- [SAD §8 — Deployment View](../02-architecture/04-SAD-Software-Architecture-Document.md#8-deployment-view)
- [Operations Runbook](10-Operations-Runbook.md)
- [Security & Compliance](12-Security-and-Compliance.md)
- [Data Dictionary](../02-architecture/07-Data-Dictionary-and-ER-Diagram.md)
- [`Azure-App-Proxy-Adaptive-Card-Setup.md`](../../Azure-App-Proxy-Adaptive-Card-Setup.md) — the callback migration runbook (current target state)
- [`HTTPS-NotSecure-Fix-Plan.md`](../../HTTPS-NotSecure-Fix-Plan.md) — the earlier IIS/TLS plan; its Phase-2 devtunnel is retired by App Proxy
- [`scripts/Register-RfpSchedules.ps1`](../../scripts/Register-RfpSchedules.ps1) · [`scripts/Invoke-RfpAutomation.ps1`](../../scripts/Invoke-RfpAutomation.ps1)
- [config/config.py](../../backend/config/config.py) — single source of truth for tunables (untracked; restart after every edit)

## 16. Change history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-04-22 | Manish Soni | Initial deployment guide — pre-flight, install, configure, services, hardening |
| 1.1 | 2026-07-17 | Manish Soni | Verified against code; App Proxy callback, Task Scheduler migration, prod topology, 42 permissions, corrected security posture |
