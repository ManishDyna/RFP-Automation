---
title: Operations Runbook — Bahra Electric RFP Automation
version: 1.0
last_updated: 2026-04-22
owner: Samir Tak (samir.tak@dynatechconsultancy.com)
audience: IT Operations, Admins, On-call Engineers
status: Draft
---

# Operations Runbook

This runbook is the **day-to-day operating manual** for the RFP Automation platform in production. It answers: *how do I start and stop the system, where are the logs, what do common errors look like, and how do I recover?*

Related docs:
- [Deployment Guide](09-Deployment-Guide.md) — one-time install & configuration
- [RBAC Permissions Matrix](11-RBAC-Permissions-Matrix.md) — access control
- [Security & Compliance](12-Security-and-Compliance.md) — secrets, audit, DR

---

## 1. System at a glance

| Item | Value |
|---|---|
| Dashboard API host | `http://<server>:8000` |
| Automation API host | `http://<server>:8100` |
| Frontend (served by dashboard) | `http://<server>:8000/app` |
| Backend framework | FastAPI + Uvicorn |
| Frontend framework | React + Vite (built to `frontend/dist/`) |
| Data store | Microsoft Dataverse (OData v9.2) |
| Service manager | NSSM on Windows |
| OS | Windows Server 2019/2022, or Windows 11 Enterprise |
| Python | 3.10 |
| Node | 20 LTS |

There are **two long-running services**:

| Service | Entry point | Purpose |
|---|---|---|
| `BahraRFP-Dashboard` | `dashboard_main.py` | HTTP API, frontend, actionable-card callbacks |
| `BahraRFP-Automation` | `automation_main.py` | Scheduled jobs: email scan, SharePoint pull, Ariba scrape, match/notify |

---

## 2. Start / stop / restart

### 2.1 Via NSSM (production)

```powershell
# Status
nssm status BahraRFP-Dashboard
nssm status BahraRFP-Automation

# Start / stop / restart
nssm start   BahraRFP-Dashboard
nssm stop    BahraRFP-Dashboard
nssm restart BahraRFP-Dashboard

nssm start   BahraRFP-Automation
nssm stop    BahraRFP-Automation
nssm restart BahraRFP-Automation
```

### 2.2 Via Windows Services MMC

`services.msc` → locate **BahraRFP-Dashboard** and **BahraRFP-Automation** → right-click → Start / Stop / Restart.

### 2.3 Manual (smoke test / debugging)

```powershell
cd C:\python\RFP-automation
.\env\Scripts\activate
python dashboard_main.py     # terminal 1
python automation_main.py    # terminal 2
```

> **Rule:** restart the dashboard service whenever `config/config.py` changes. The automation service only needs a restart when automation code or the automation schedule changes.

---

## 3. Health checks

### 3.1 Dashboard `/health`

```bash
curl http://localhost:8000/health
# → {"status":"ok","message":"Service is running"}
```

Any non-200 response, or the absence of the `status` key, indicates the dashboard is unhealthy.

### 3.2 Automation liveness

The automation service does not expose `/health` (it is a worker, not a public API). Check:

1. Process is running: `nssm status BahraRFP-Automation`
2. Recent activity in `cr673_bahra_automation_log1` (Dataverse) — every scheduled run writes a row
3. No stuck Playwright browsers: `Get-Process chromium, chrome -ErrorAction SilentlyContinue`

### 3.3 Dataverse reachability

```powershell
# From the app server, confirm OData endpoint is reachable
curl "https://<org>.crm4.dynamics.com/api/data/v9.2/WhoAmI" -H "Authorization: Bearer <token>"
```

If this fails, the dashboard and automation will both fail. Escalate to the Dataverse/Azure AD admin.

---

## 4. Where the logs live

| Source | Location | What you will find |
|---|---|---|
| Dashboard stdout/stderr (via NSSM) | Path configured in NSSM *I/O* tab, typically `C:\python\RFP-automation\LOGS\dashboard-stdout.log` | Uvicorn request log, Python tracebacks, `logger.error` calls |
| Automation stdout/stderr (via NSSM) | `C:\python\RFP-automation\LOGS\automation-stdout.log` | Scheduled job output, scraping progress, Power Automate callbacks |
| Playwright failure artifacts | `C:\python\RFP-automation\LOGS\<run_id>_<error>_<timestamp>/` | `error.png` screenshot, `page.html`, `trace.zip` |
| Submit-RFP failures | `C:\python\RFP-automation\LOGS\submit_rfp_error_<ts>_<shortid>/` | Screenshot + HTML of the failed Ariba submit attempt |
| Dashboard error screenshots | `C:\python\RFP-automation\LOGS\*.png` | User-facing screenshot uploads linked from RFP rows |
| Audit log (business events) | Dataverse table `cr673_bahra_audit_logs` | Who did what, when, with which payload |
| Automation log (job runs) | Dataverse table `cr673_bahra_automation_log1` | Per-run status, RFP counts, error summaries |
| Windows Event Log | Applications → `BahraRFP-*` | Service start/stop, crash exit codes |

Tail the most recent stdout lines:

```powershell
Get-Content C:\python\RFP-automation\LOGS\dashboard-stdout.log -Tail 100 -Wait
Get-Content C:\python\RFP-automation\LOGS\automation-stdout.log -Tail 100 -Wait
```

---

## 5. Routine daily checks (10-minute morning routine)

1. **Services up?** `nssm status BahraRFP-Dashboard` and `BahraRFP-Automation` both return `SERVICE_RUNNING`
2. **`/health` returns 200** — `curl http://localhost:8000/health`
3. **Yesterday's scheduled runs logged?** Query `cr673_bahra_automation_log1` — expect one row per configured schedule
4. **No ballooning log folders** — `LOGS/` under 1 GB. If it grew overnight, investigate which scraper is looping on failure
5. **No stuck Chromium processes** — `Get-Process chromium -ErrorAction SilentlyContinue | Measure-Object`
6. **Dataverse API quota OK** — check the Power Platform Admin Center if you received throttling alerts

---

## 6. Common errors and how to fix them

### 6.1 `401 Unauthorized` when calling Dataverse

**Symptom:** Dashboard logs show `DataverseClient: 401 Unauthorized`. API requests return 500.

**Root causes (most → least likely):**
1. `CLIENT_SECRET` expired — Azure AD app registration secret has a max 24-month life
2. App principal lost the Dataverse Application User role
3. Tenant ID / client ID mismatch after a rotation

**Fix:**
1. Verify secret in Azure Portal → App Registrations → *Bahra RFP Automation* → Certificates & Secrets
2. Generate a new secret, update `CLIENT_SECRET` in `config/config.py` (or env var), restart both services
3. Confirm the Dataverse Application User still has **System Administrator** (or the reduced custom role) in Power Platform Admin Center

### 6.2 `429 Too Many Requests` from Dataverse

**Symptom:** Bursts of errors during bulk imports; some RFP rows fail to write.

**Fix:** The `DataverseClient` already retries with exponential backoff. If it still fails:
- Reduce batch size in the calling code
- Stagger schedules in Power Automate (avoid 08:00 overlap)
- Contact Microsoft if throttling happens during normal single-user activity

### 6.3 Playwright/Chromium hangs while scraping Ariba

**Symptom:** Automation run never completes; `chromium.exe` consuming CPU; stdout stuck after "Navigating to Ariba".

**Fix:**
```powershell
Get-Process chromium, chrome -ErrorAction SilentlyContinue | Stop-Process -Force
nssm restart BahraRFP-Automation
```

If it keeps happening, Ariba probably changed its DOM. Open the latest `LOGS/run_<id>_rfp_error_*/error.png` to see the page state at failure, and update the scraper selector.

### 6.4 Adaptive-card responses don't appear in the dashboard

**Symptom:** Bidder submits via Outlook; nothing updates in the RFP row.

**Fix checklist:**
1. Adaptive-card Originator ID registered at [amdesigner.azurewebsites.net](https://amdesigner.azurewebsites.net/) for the email sender address? See [Deployment §11](09-Deployment-Guide.md#11-production-hardening)
2. Dashboard `/api/actionable/respond` reachable from the public internet (or from Microsoft's substrate service)?
3. Inspect dashboard logs for the rejection reason — invalid token, expired card, missing bidder
4. Verify `response_data` column on the RFP row was updated (if yes, the callback succeeded and the issue is downstream UI)

### 6.5 Email not sending (or sending to the wrong mailbox)

**Symptom:** Scheduled emails don't arrive; bidders complain about missing reminders.

**Fix:**
1. Check `EMAIL_MODE` in `config/config.py`:
   - `dev` → everything routes to `EMAIL_DEV_RECIPIENT`
   - `prod` → real recipients
2. Verify the Microsoft Graph app has `Mail.Send` permission (admin consented)
3. Inspect the Dashboard log for `Graph /sendMail` errors — 403 = permission, 401 = token, 400 = bad payload
4. Check sender mailbox quota

### 6.6 Frontend shows "Network error" on every page

**Symptom:** UI loads but every API call fails.

**Fix:**
1. Session cookie missing — user likely hit the site via an IP while cookies are bound to hostname. Use the configured hostname
2. CORS blocked — check `cors_allowed_origins` in `config/config.py` matches the frontend origin
3. Session secret changed — all existing cookies invalidated; users must log out and back in

### 6.7 RFP row stuck in "Processing"

**Symptom:** One or more RFPs show status `Processing` for hours with no progress.

**Fix:**
1. Check `cr673_bahra_automation_log1` for the most recent row touching that RFP ID
2. If the automation crashed mid-run, the orchestrator's next scheduled tick will retry
3. To force a retry now: admin UI → *Automation* → *Re-run for RFP*, OR set the RFP's status back to `New` and wait for the next cycle

### 6.8 "Permission denied" in UI for someone who should have access

**Fix:**
1. Is the user's row in `cr673_bahra_user_status` set to `Active`?
2. Is a role assigned? Check `cr673_bahra_user_roles` (or role reference on user row)
3. Does the role have the specific permission? See [RBAC Permissions Matrix](11-RBAC-Permissions-Matrix.md)
4. RBAC cache is 300s — wait 5 min after a role change or restart the dashboard

---

## 7. Scheduled jobs

Schedules live in the `cr673_bahra_automation_schedules` Dataverse table and are pushed to Power Automate via [helpers/power_automate_helper.py](../../helpers/power_automate_helper.py).

Typical schedules (confirm in your environment):

| Job | Default cadence | What it does |
|---|---|---|
| Email scan | Every 30 min | Pulls unread RFP emails from the shared mailbox, extracts BOQ attachments |
| SharePoint pull | Every 1 hour | Checks configured SharePoint folders for new RFPs |
| Ariba portal scan | Every 2 hours | Logs in to Ariba via Playwright, downloads new RFPs |
| Match & notify | Every 30 min | Runs fuzzy match on new RFPs, assigns to bidders, sends adaptive-card emails |
| Reminder emails | Daily 09:00 | Chases bidders who haven't responded |
| Cleanup | Daily 03:00 | Archives old LOGS folders, prunes failure screenshots > 90 days |

To pause/resume a schedule without editing Dataverse: use the admin UI *System Settings → Schedules* page, which edits the row and calls Power Automate.

---

## 8. Manual operations

### 8.1 Trigger automation for a single RFP

From the admin UI: *Automation → Re-run* (requires `automation.execute` permission).

CLI equivalent (for debugging):

```powershell
cd C:\python\RFP-automation
.\env\Scripts\activate
python -c "from automation_logic import run_for_rfp; run_for_rfp('RFP-12345')"
```

### 8.2 Force-refresh material master from SAP

```powershell
python Support-Files\sync_sap_material_master.py
```

### 8.3 Reset a stuck Playwright session

```powershell
Get-Process chromium, chrome -ErrorAction SilentlyContinue | Stop-Process -Force
Remove-Item -Recurse -Force "$env:USERPROFILE\AppData\Local\ms-playwright\ariba-session"
nssm restart BahraRFP-Automation
```

### 8.4 Re-seed RBAC default roles

Safe to re-run; it only inserts if absent.

```powershell
python Support-Files\setup_rbac_tables.py
python -c "from services.dynamic_role_service import seed_default_roles; seed_default_roles()"
```

### 8.5 Clear caches without restarting

Caches are 300 s TTL, so usually just wait. To force-clear immediately, restart the dashboard:

```powershell
nssm restart BahraRFP-Dashboard
```

---

## 9. Monitoring & alerting (recommended)

The system ships with **no built-in alerting**. Operations should wire up:

- **Uptime Robot / Pingdom** → `GET http://<server>:8000/health` every 60 s
- **Windows Event Log forwarder** → SIEM for `BahraRFP-*` service crash events
- **Dataverse flow** → send email to ops mailbox when `cr673_bahra_automation_log1.status = 'Failed'` for any run
- **Disk-space alert** on the volume hosting `LOGS/` — warn at 80 %
- **Azure AD** → email the admin 30 days before `CLIENT_SECRET` expires (set a calendar reminder if AAD notifications are off)

---

## 10. Capacity & housekeeping

| Area | Rule of thumb | How to clean up |
|---|---|---|
| `LOGS/` folder | Keep last 90 days | Daily 03:00 cleanup job; manual: `Remove-Item` folders older than 90 days |
| `ALLRFPs/` folder | Keep last 180 days of downloaded BOQ attachments | Manual pruning; large files can be moved to cold storage |
| `cr673_bahra_automation_log1` | Keep last 1 year | Bulk-delete in Dataverse (requires System Administrator) |
| `cr673_bahra_audit_logs` | Keep **indefinitely** (compliance) | Do not prune without Legal approval |
| Dataverse storage (overall) | Under your licensed capacity | Power Platform Admin Center → Storage tab |

---

## 11. Change management

Any change that affects production flows through:

1. **Pull request** against `master` (or configured trunk branch)
2. **Peer review** by the owner (Samir) or delegate
3. **Release notes** added to [CHANGELOG.md](../CHANGELOG.md)
4. **Deploy window** — avoid Sunday 08:00–12:00 (reminder email run) and month-end close
5. **Post-deploy verification** — §3 health checks + one end-to-end smoke test (submit a test RFP via the dashboard UI)

Rollback: redeploy the previous Git tag, restart both services. If a Dataverse schema migration went wrong, restore the affected table's backup via Dataverse's point-in-time restore (only available on paid tiers).

---

## 12. On-call playbook

**Severity guide:**

| Severity | Example | SLA |
|---|---|---|
| SEV-1 | Dashboard down, no RFPs accepted | 15 min ack, 1 h fix |
| SEV-2 | Automation down but dashboard up | 30 min ack, 4 h fix |
| SEV-3 | Single feature broken (e.g., one scraper) | Next business day |
| SEV-4 | Cosmetic / UX bug | Backlog |

**First 5 minutes of any page:**

1. Check `/health` on the dashboard
2. `nssm status` both services
3. Tail the last 200 lines of each stdout log
4. Identify whether the issue is: code, config, Dataverse, external dep (Ariba/SharePoint/SAP/Email), or network
5. If the cause is not obvious in 5 min: **restart both services** (safe — no in-memory state that matters)
6. If restart doesn't fix it within 5 min: open the relevant troubleshooting section above, escalate to the owner

---

## 13. Contacts

| Role | Who | How to reach |
|---|---|---|
| System owner | Samir Tak | samir.tak@dynatechconsultancy.com |
| Dataverse / Power Platform admin | *(fill in)* | |
| Azure AD / app registration admin | *(fill in)* | |
| Ariba administrator (business side) | *(fill in)* | |
| SAP integration contact | *(fill in)* | |
| On-call rotation | *(fill in)* | |

---

## 14. Document maintenance

Update this runbook whenever you:
- Add a new service, script, or scheduled job
- Encounter a novel incident — add a row to §6
- Change monitoring / alerting infrastructure
- Rotate credentials or change the service-account pattern

Bump `version` and `last_updated` in the frontmatter on every edit.
