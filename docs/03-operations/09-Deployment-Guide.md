---
title: Deployment Guide — Bahra Electric RFP Automation
version: 1.0
last_updated: 2026-04-22
owner: Samir Tak (samir.tak@dynatechconsultancy.com)
status: Draft
audience: IT Ops, DevOps, System Administrators
---

# Deployment Guide

> **Goal.** Take a clean Windows VM and end up with the RFP Automation portal running, reachable from a browser, talking to Dataverse, sending emails, and ready to be triggered by Power Automate.
>
> **Time budget.** ~90 minutes for a first-time deploy; ~20 minutes for subsequent updates.

---

## 1. Pre-flight checklist

Before you touch the server, confirm you have access to all of the following. Missing any one of these will block deployment.

| # | What | Where to get it |
|---|------|-----------------|
| 1 | **Windows VM** (Win Server 2019/2022 or Win 11 Pro), Administrator rights, ≥4 vCPU / 8 GB RAM / 40 GB disk | IT Ops |
| 2 | **Outbound internet** to `*.dynamics.com`, `*.sharepoint.com`, `graph.microsoft.com`, `service.ariba.com`, `*.environment.api.powerplatform.com`, `substrate.office.com`, `login.microsoftonline.com` | IT/Network |
| 3 | **Inbound 443** from corporate users; from Power Automate (public IP or dev tunnel for the actionable-card callback) | IT/Network |
| 4 | **Azure AD app registration** with `TENANT_ID`, `CLIENT_ID`, `CLIENT_SECRET` and Dataverse + Graph permissions granted | Azure portal admin |
| 5 | **Dataverse environment URL** (e.g., `https://operations-bahrauat-1.crm11.dynamics.com`) | Power Platform admin |
| 6 | **SharePoint site** at the path in `SITE_PATH` with `RFP-logs/` folder writable | M365 admin |
| 7 | **Power Automate Cloud Flow** named `Bahra-E-binding-cron-job` inside a Solution (not "My Flows") with a Recurrence trigger | Power Automate maker |
| 8 | **Source code** access (git clone URL or zip) | Project owner |
| 9 | **Reverse-proxy plan** — IIS / nginx / Cloudflare Tunnel for TLS termination (recommended, not strictly required for internal-only use) | IT Ops |

> **Production checklist** — in addition to the above, complete §11 before users touch the system.

---

## 2. Architecture recap

Two FastAPI processes on one host (see [SAD §4](../02-architecture/04-SAD-Software-Architecture-Document.md)):

| Process | Port | Purpose |
|---------|------|---------|
| `dashboard_main.py` | **8000** | All user-facing HTTP (React SPA, REST API, RBAC, actionable-card callback) |
| `automation_main.py` | **8100** | Long-running browser automation (Playwright + Ariba) |

The React frontend is built into static files and served by the Dashboard API in production (or by Vite at `:5173` in development).

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
# Pick a deployment root. Project owner uses C:\python\RFP-automation
mkdir C:\python
cd C:\python
git clone <your-repo-url> RFP-automation
cd RFP-automation
```

Or unzip a release archive into the same path. End state: `C:\python\RFP-automation\` contains `dashboard_main.py`, `automation_main.py`, `config/`, `routes/`, `services/`, `helpers/`, `frontend/`, etc.

---

## 5. Python virtualenv + dependencies

```powershell
cd C:\python\RFP-automation

# Create virtualenv (the project uses 'env' as the directory name)
python -m venv env

# Activate
.\env\Scripts\Activate.ps1
# If PowerShell blocks the script:
#   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Upgrade pip
python -m pip install --upgrade pip

# Install dependencies
pip install -r Support-Files\requirements.txt
```

> Installation takes 5-15 minutes. Heavy packages: `playwright`, `pandas`, `numpy`, `pyarrow`, `selenium`.

### 5.1 Install Playwright browsers

The Ariba scraper uses Chromium via Playwright. Browser binaries are downloaded separately:

```powershell
playwright install chromium
# Optional: install OS-level dependencies (rarely needed on Windows Server)
# playwright install-deps
```

### 5.2 Verify the install

```powershell
python -c "import fastapi, playwright, msal, pandas; print('ok')"
# ok
```

---

## 6. Configure the application

All configuration lives in [`config/config.py`](../../config/config.py). Open it and update:

### 6.1 Azure AD / Dataverse — §1 and §2

```python
TENANT_ID     = "<your-tenant-guid>"
CLIENT_ID     = "<your-app-client-id>"
CLIENT_SECRET = "<your-app-client-secret>"   # see §11.1 — move out of source control before production
RESOURCE_URL  = "https://<your-env>.crm11.dynamics.com"
```

### 6.2 SharePoint — §3

```python
SHAREPOINT_HOSTNAME = "<your-tenant>.sharepoint.com"
SITE_PATH           = "/sites/<your-site-path>"
DRIVE_NAME          = "Documents"
SP_BASE_FOLDER      = "RFP-logs"
```

### 6.3 Power Automate — §4

```python
FLOW_URL                              = "<full HTTP-trigger URL of your run-now flow>"
POWER_AUTOMATE_FLOW_NAME              = "Bahra-E-binding-cron-job"
POWER_AUTOMATE_RECURRENCE_TRIGGER_NAME = "Recurrence"
ACTIONABLE_CARD_ORIGINATOR_ID         = "<your registered originator ID>"
ACTIONABLE_CARD_CALLBACK_URL          = "https://<your-public-host>/api/actionable-card/response"
```

> **Originator ID** is registered via https://outlook.office.com/connectors/oam/publish — required for Adaptive Cards in Outlook to work.

### 6.4 Email mode — §6

```python
EMAIL_MODE = "dev"     # change to "prod" only after verifying recipient lists
DEV_EMAIL  = "<inbox you want all dev emails routed to>"
```

> **Stay in `"dev"` mode** for the first run end-to-end. Switch to `"prod"` after §11.4.

### 6.5 Session secret — §7

The default `SessionMiddleware secret_key="change-me-please"` in `dashboard_main.py:53` is **not safe for production**. See §11.2.

---

## 7. Provision Dataverse tables

> **Idempotent.** All setup scripts skip existing tables/columns and can be re-run safely.

Run from the project root with the venv activated:

```powershell
# 1. RBAC tables (roles, role_permissions, audit_logs, user_status)
python Support-Files\setup_rbac_tables.py

# 2. Master data (material_master, keywords, rfp_team)
python Support-Files\setup_master_data_tables.py

# 3. RFPs v2 main table
python Support-Files\setup_rfps_v2_table.py

# 4. Analytics columns on rfps_v2
python Support-Files\setup_rfp_activity_columns.py

# 5. Dynamic team-column definitions
python Support-Files\setup_dynamic_columns_table.py

# 6. Seed runtime settings (email recipients)
python Support-Files\seed_system_settings.py
```

Each script prints **`EntitySetName`** values you should compare against `config/config.py`. If Dataverse pluralized differently than the config expects (it shouldn't, but it can), update the corresponding `*_API` constant.

> **The following tables must already exist** (not created by the scripts in this repo): `cr673_bahra_users`, `cr673_bahra_sap_infomation`, `cr673_bahra_automation_log1`, `cr673_bahra_automation_schedules`, `cr673_bhara_rfp_status`, `cr673_bahra_system_settings`, `cr6db_cr673_bahra_rfp_response`. If any are missing, create them in the Power Platform maker portal using the column lists in [Data Dictionary §5/§7/§8](../02-architecture/07-Data-Dictionary-and-ER-Diagram.md).

### 7.1 Seed default roles

Either via API after the server is running:
```bash
curl -X POST http://localhost:8000/api/roles/seed -H "Cookie: session=..."
```

Or directly via the Roles admin page. Creates `Admin` (41 perms) and `RFP Bidder` (7 perms).

### 7.2 Create the first Admin user

Until the first user is created, no one can log in. Either:

- **Direct insert** into `cr673_bahra_users` via Power Apps with `email`, `name`, `role=Admin`, and a bcrypt-hashed `password`, or
- **Run the bootstrap script** if your project provides one (check `Support-Files/` for `create_admin.py` — not in standard tree)

---

## 8. Build the frontend

```powershell
cd C:\python\RFP-automation\frontend
npm install
npm run build
# Output: frontend/dist/
```

Wire `dist/` into the Dashboard API by either:

1. **Mounting via FastAPI** — add to `dashboard_main.py`:
   ```python
   from fastapi.staticfiles import StaticFiles
   FRONTEND_DIST = os.path.join(BASE_DIR, "frontend", "dist")
   if os.path.exists(FRONTEND_DIST):
       app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
   ```
   *(Caveat: this must come **after** all router includes, or it will swallow `/api/*` routes.)*

2. **Serving via reverse proxy** — point IIS / nginx at `frontend/dist/` for `/` and at `127.0.0.1:8000` for `/api/`, `/dashboard/`, `/health`. **Recommended.**

---

## 9. Start the services

### 9.1 Manual start (smoke test)

Open two PowerShell windows, both with the venv activated:

```powershell
# Window 1 — Dashboard API
cd C:\python\RFP-automation
.\env\Scripts\Activate.ps1
python dashboard_main.py
# Uvicorn running on http://0.0.0.0:8000
```

```powershell
# Window 2 — Automation API
cd C:\python\RFP-automation
.\env\Scripts\Activate.ps1
python automation_main.py
# Uvicorn running on http://0.0.0.0:8100
```

Sanity check:
```powershell
curl http://localhost:8000/health
# {"status":"healthy","dataverse":"connected"}

curl http://localhost:8100/docs
# Swagger UI for the automation router
```

Open `http://localhost:8000/` in a browser. The login screen should load. Log in as the Admin user from §7.2.

### 9.2 Run as Windows services (production)

The simplest reliable option is **NSSM** (the Non-Sucking Service Manager):

```powershell
# Download nssm.exe from https://nssm.cc and put it on PATH

# Dashboard service
nssm install "RFP-Dashboard" "C:\python\RFP-automation\env\Scripts\python.exe" "C:\python\RFP-automation\dashboard_main.py"
nssm set "RFP-Dashboard" AppDirectory "C:\python\RFP-automation"
nssm set "RFP-Dashboard" AppStdout "C:\python\RFP-automation\LOGS\dashboard.out.log"
nssm set "RFP-Dashboard" AppStderr "C:\python\RFP-automation\LOGS\dashboard.err.log"
nssm start "RFP-Dashboard"

# Automation service
nssm install "RFP-Automation" "C:\python\RFP-automation\env\Scripts\python.exe" "C:\python\RFP-automation\automation_main.py"
nssm set "RFP-Automation" AppDirectory "C:\python\RFP-automation"
nssm set "RFP-Automation" AppStdout "C:\python\RFP-automation\LOGS\automation.out.log"
nssm set "RFP-Automation" AppStderr "C:\python\RFP-automation\LOGS\automation.err.log"
nssm start "RFP-Automation"
```

Verify in `services.msc` — both should be in **Running** state and set to **Automatic** start.

---

## 10. Reverse proxy (recommended)

### 10.1 IIS

1. Install IIS + URL Rewrite + Application Request Routing
2. Create a site bound to `https://rfp.bahra-cables.com:443` with your TLS cert
3. Add `web.config` rewriting:
   - `/api/*`, `/dashboard/*`, `/health` → `http://127.0.0.1:8000`
   - everything else → `frontend/dist/index.html` (SPA fallback)
4. Enable **Forward proxy** in ARR Server Proxy Settings

### 10.2 nginx (alternative)

```nginx
server {
    listen 443 ssl http2;
    server_name rfp.bahra-cables.com;

    ssl_certificate     /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    root C:/python/RFP-automation/frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location ~ ^/(api|dashboard|health) {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300;
    }
}
```

---

## 11. Production hardening

> **Do not skip.** The defaults in `config/config.py` and `dashboard_main.py` are dev-grade.

### 11.1 Move secrets out of `config/config.py`

Today, `CLIENT_SECRET` and Power Automate flow signatures are committed to source. Move them to environment variables and read them at startup. Suggested pattern:

```python
import os
TENANT_ID     = os.environ["TENANT_ID"]
CLIENT_ID     = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]
```

Set values via NSSM service config (`AppEnvironmentExtra`) or Windows system environment variables. Long-term: use Azure Key Vault.

### 11.2 Replace the session secret

In `dashboard_main.py:53`, replace:

```python
app.add_middleware(SessionMiddleware, secret_key="change-me-please", max_age=SESSION_TIMEOUT_SECONDS)
```

with:

```python
SESSION_SECRET = os.environ["SESSION_SECRET"]   # 32+ random bytes, base64-encoded
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, max_age=SESSION_TIMEOUT_SECONDS, https_only=True, same_site="lax")
```

Generate a secret once: `python -c "import secrets; print(secrets.token_urlsafe(32))"`.

### 11.3 Lock down CORS

In `dashboard_main.py`, restrict `allow_origins` to your production domain only (remove the localhost / 192.168.* entries).

### 11.4 Switch email mode

After verifying the dev recipient receives a test email and the layout is correct:

1. Set `EMAIL_MODE = "prod"` in `config/config.py`
2. Verify recipient lists in the **System Settings** admin page (`EMAIL_TO_NEW_RFP`, etc.)
3. Restart the Dashboard service

### 11.5 Configure the Power Automate flow

Ensure the cron flow is **inside a Solution** (not "My Flows"). Power Automate flows under "My Flows" cannot be patched programmatically.

```
Solution → Cloud flows → Bahra-E-binding-cron-job
  Trigger: Recurrence (daily / hourly / whatever cadence)
  Action: HTTP → POST {ACTIONABLE_CARD_CALLBACK_URL or https://<host>/api/automation/run}
```

### 11.6 Register the Adaptive Card originator ID

At https://outlook.office.com/connectors/oam/publish, register the originator ID matching `ACTIONABLE_CARD_ORIGINATOR_ID`. Until approved, Adaptive Cards will not render in Outlook.

---

## 12. Verify end-to-end

After deployment, run through this acceptance test:

1. **Login** — Admin user can log in via the browser
2. **Dashboard** — `/dashboard` loads, shows last automation time, no console errors
3. **Trigger automation manually** — sidebar → "Download RFPs (open)" → confirm a Power Automate run is initiated and `cr673_bahra_automation_log1` rows appear
4. **Email** — verify the dev inbox received the "New RFP" or "No New RFP" email
5. **Adaptive Card** — open the email in Outlook, fill in Results/Remarks, click Submit → verify the response lands in `cr6db_cr673_bahra_rfp_response`
6. **Audit log** — `/admin/audit-logs` shows the login + automation events
7. **Health** — `https://<host>/health` returns `{"status":"healthy","dataverse":"connected"}`

---

## 13. Updating an existing deployment

```powershell
# Stop services
Stop-Service "RFP-Dashboard"
Stop-Service "RFP-Automation"

# Pull new code
cd C:\python\RFP-automation
git pull

# Update Python deps if requirements changed
.\env\Scripts\Activate.ps1
pip install -r Support-Files\requirements.txt

# Re-run setup scripts (idempotent — only adds new tables/columns)
python Support-Files\setup_rbac_tables.py
# ...repeat for any setup script with new columns

# Rebuild frontend if changed
cd frontend
npm install
npm run build
cd ..

# Start services
Start-Service "RFP-Automation"
Start-Service "RFP-Dashboard"

# Smoke test
curl http://localhost:8000/health
```

---

## 14. Troubleshooting common deployment issues

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `MSAL: Failed to get access token` | Wrong `CLIENT_SECRET` or expired | Regenerate in Azure portal; update env var |
| `/health` returns 503 | Dataverse table read failed | Confirm app has data permissions on the env; check `cr673_bahra_logins` exists (referenced in `dashboard_main.py:127`) |
| `Playwright: Executable doesn't exist at .../chromium-1234/chrome.exe` | Forgot `playwright install chromium` | Run it; verify in `~\AppData\Local\ms-playwright\` |
| `RuntimeError: Event loop is closed` (during automation) | Wrong asyncio policy on Windows | Confirm `WindowsProactorEventLoopPolicy` is set in both entry points (`dashboard_main.py:22`, `automation_main.py`) |
| Adaptive Card doesn't render in Outlook | Originator ID not registered | Submit at https://outlook.office.com/connectors/oam/publish |
| Card submits but response not saved | Substrate token verification failed | Check `routes/actionable_cards.py` logs; verify outbound to `substrate.office.com` |
| 401 from Dataverse on a specific table | Permissions not granted on that table | In Power Platform admin → Security roles → grant Read/Write to your app user |
| Schedule edits in portal don't change the cron | Flow is in "My Flows" not in a Solution | Move the flow into a Solution and re-resolve `workflowid` |

More live issues → see [Troubleshooting](../TROUBLESHOOTING.md) (planned).

---

## 15. Reference

- [SAD §8 — Deployment View](../02-architecture/04-SAD-Software-Architecture-Document.md#8-deployment-view)
- [Operations Runbook](10-Operations-Runbook.md)
- [Security & Compliance](12-Security-and-Compliance.md)
- [Data Dictionary](../02-architecture/07-Data-Dictionary-and-ER-Diagram.md)
- [config/config.py](../../config/config.py) — single source of truth for tunables

## 16. Change history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-04-22 | Samir Tak | Initial deployment guide — pre-flight, install, configure, services, hardening |
