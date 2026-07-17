---
title: Operations Runbook — Bahra Electric RFP Automation
version: 1.1
last_updated: 2026-07-17
owner: Manish Soni (Manish.soni@dynatechconsultancy.com)
audience: IT Operations, Admins, On-call Engineers
status: Draft
---

# Operations Runbook

This runbook is the **day-to-day operating manual** for the RFP Automation platform in production. It answers: *how do I start and stop the system, where are the logs, what do common errors look like, and how do I recover?*

Related docs:
- [Deployment Guide](09-Deployment-Guide.md) — one-time install & configuration
- [RBAC Permissions Matrix](11-RBAC-Permissions-Matrix.md) — access control
- [Security & Compliance](12-Security-and-Compliance.md) — secrets, audit, DR

> ## ⚠️ Read this first — two known open defects
>
> 1. **Reminder emails are NOT sending.** The `Bahra-RFP-Reminder-Emails-Cron-job` Power Automate flow fires at a **dead devtunnel**, and no scheduled task replaces it. Bidders are not being chased. See **§7.3**.
> 2. **The Schedule Automation page is a silent no-op.** It writes to the very Power Automate flow the Task Scheduler migration turned off. Operators get a success toast and **nothing changes**. See **§7.4**.
>
> Neither is fixed. Do not tell a user "the reminder went out" or "the schedule is updated" on the strength of the UI.

---

## 1. System at a glance

| Item | Value |
|---|---|
| Server VM | `192.168.111.192` (Windows Server 2016), LAN-only |
| Repo root | `C:\Bahra-Automation-RFP-System` — **not** the dev path `C:\python\RFP-automation` |
| Portal URL | `https://be-aramco-01.bahra-cables.com/rfp` (IIS reverse proxy) |
| Backend | FastAPI + Uvicorn on **`127.0.0.1:8000`** — localhost-only |
| Windows service | **`rfp-api`** (WinSW) |
| Frontend | React + Vite, built to `frontend/dist/`, served by IIS |
| Data store | Microsoft Dataverse (OData v9.2) |
| TLS | **Internal-CA-issued** cert for `be-aramco-01.bahra-cables.com` — LAN-trusted (CA root distributed to company machines), not publicly trusted |
| Adaptive-card callback | Microsoft Entra **Application Proxy (Passthrough)**, `…msappproxy.net/rfp/api/actionable-card/` |
| Scheduling | **Windows Task Scheduler**, folder `\Bahra-RFP\` (§7) |
| Runtimes | Python 3.10 · Node 20 LTS |

> **This VM also hosts the COA application. Do not touch COA** — not its IIS site, not its services.

There is **one long-running service**:

| Service | Entry point | Purpose |
|---|---|---|
| `rfp-api` | `backend/dashboard_main.py` | Everything — HTTP API, RBAC, actionable-card callbacks, **and** the automation jobs (each runs on its own background thread inside this process) |

There is **no separate automation service**. `automation_main.py` exists in the tree as a standalone-automation deployment but is **not run in production**; its routes are already mounted by `dashboard_main`.

---

## 2. Start / stop / restart

### 2.1 Production

```powershell
Get-Service rfp-api
Restart-Service rfp-api
# or
net stop rfp-api ; net start rfp-api
```

`services.msc` → **rfp-api** → right-click → Start / Stop / Restart works too.

### 2.2 Manual (smoke test / debugging)

**The working directory MUST be `backend\`.** It puts `backend/` on `sys.path` so the top-level imports resolve, and it anchors the `os.getcwd()`-based data folders (`ALLRFPs/`, `LOGS/`) inside `backend/`. Launching from the repo root fails at import, or silently writes data to the wrong place.

```powershell
cd C:\Bahra-Automation-RFP-System\backend
..\env\Scripts\python.exe dashboard_main.py
```

The virtualenv lives at `env/` in the **repo root**, one level above `backend/`. Any one-off script runs the same way — `cd backend` first.

> **Rule:** restart `rfp-api` whenever `backend/config/config.py` changes. **Nothing re-reads it at runtime** — an unrestarted backend serving a stale config is a recurring source of confusing failures (e.g. `500 "APP_ID_URI not configured"` on card callbacks).

> **Restart safety:** `_RUN_STATE` (the in-memory job lock) is **process-local and not durable**. Restarting mid-run abandons any in-flight automation — the Dataverse row is left as-is and the next scheduled tick picks it up. Restart is safe; just don't do it while a submit is in flight if you can avoid it.

---

## 3. Health checks

### 3.1 `/health`

```powershell
Invoke-WebRequest http://127.0.0.1:8000/health -UseBasicParsing
# → {"status":"healthy","dataverse":"connected"}
```

This is **not** a bare liveness probe — it reads one row from the users table in Dataverse. A **503** means Dataverse is unreachable, not that the process is down.

### 3.2 Automation liveness

Automations run inside `rfp-api`, so there is no second process to check. Check instead:

1. Current job state: `Invoke-RestMethod http://127.0.0.1:8000/api/automation/status` — returns the `download_running` / `sync_running` / `sync_sp_dv_running` flags and a progress percentage
2. Recent activity in `cr673_bahra_automation_log1` (Dataverse) — every run writes rows
3. Scheduler results: `Get-ScheduledTaskInfo -TaskPath '\Bahra-RFP\' -TaskName 'RFP-Download-OpenRFPs'` and `backend\LOGS\scheduler\scheduler-<yyyy-MM>.log`
4. No stuck Playwright browsers: `Get-Process chrome, chromium -ErrorAction SilentlyContinue`

### 3.3 Dataverse reachability

If `/health` returns 503, Dataverse is the suspect. Confirm the app registration's secret hasn't expired and the Application User still holds its security role, then escalate to the Dataverse/Azure AD admin.

### 3.4 Adaptive-card callback reachability

From an **off-LAN** machine:

```powershell
curl.exe -i https://bahrarfpadaptivecardcallback-bahracables.msappproxy.net/rfp/api/actionable-card/response
```

- **401/500 from the app** = healthy (the token check rejected an unauthenticated probe — that's the point).
- **A Microsoft login page** = the App Proxy app was switched to Entra-ID pre-auth. The card buttons are broken. Set Pre Authentication back to **Passthrough**.
- **Timeout/502** = the connector can't reach `:8000`, or `rfp-api` is down.

Also check what else is exposed: `…msappproxy.net/rfp/health` and `…/rfp/api/login` **should** be unreachable — but the publish is currently rooted at the IIS site (that is what preserves the `/rfp` prefix the callback needs), so they may well respond. If they do, treat it as a live security issue and see [Security & Compliance RR-21](12-Security-and-Compliance.md#11-residual-risks) — the priority is `/rfp/api/automation/*`, which has **no authentication at all**.

---

## 4. Where the logs live

All paths are relative to the **`backend\`** working directory, i.e. `C:\Bahra-Automation-RFP-System\backend\`.

| Source | Location | What you will find |
|---|---|---|
| Service stdout/stderr | Path configured in the WinSW service XML | Uvicorn request log, Python tracebacks, automation `print()` output |
| Automation logs + Playwright artifacts | `backend\LOGS\` | `error.png` screenshots, page HTML, per-run folders |
| Failure bundles (uploaded to SharePoint) | `backend\automation-error-logs\` → SharePoint `SP_FAILURE_LOGS_FOLDER` | Bundled evidence for a failed run |
| **Scheduled-task runner log** | `backend\LOGS\scheduler\scheduler-<yyyy-MM>.log` | One line per trigger/poll from `Invoke-RfpAutomation.ps1`; monthly file |
| Downloaded RFP bundles | `backend\ALLRFPs\` | BOQ Excel/PDF per RFP |
| Audit log (business events) | Dataverse `cr673_bahra_audit_logs` | Auth, user, role, settings events — **not** RFP operations (§6.9) |
| Automation log (job runs) | Dataverse `cr673_bahra_automation_log1` | Per-run status, RFP counts, error summaries |
| RFP activity log | Dataverse `cr673_bahra_rfps_v2` | Per-RFP timeline (the v1 table is deprecated) |
| Windows Event Log | Applications → `rfp-api` | Service start/stop, crash exit codes |
| Task Scheduler history | Task Scheduler → `\Bahra-RFP\` → History tab | Trigger fired / last run result |

Tail the scheduler log:

```powershell
Get-Content C:\Bahra-Automation-RFP-System\backend\LOGS\scheduler\scheduler-2026-07.log -Tail 100 -Wait
```

> **Unhandled 500s** carry an 8-character `error_id` in the response body. Grep the service stdout for that id to find the matching traceback.

> **Activity Logs page has a browse cap.** The Logs page loads only the newest ~5,000 rows, so client-side search cannot see older runs. Use the page's **search box** — `/dashboard/view-logs?search=` queries the whole table server-side.

---

## 5. Routine daily checks (10-minute morning routine)

1. **Service up?** `Get-Service rfp-api` → `Running`
2. **`/health` returns 200** — `Invoke-WebRequest http://127.0.0.1:8000/health -UseBasicParsing`
3. **Yesterday's scheduled runs fired and finished?**
   ```powershell
   Get-ScheduledTask -TaskPath '\Bahra-RFP\' | Get-ScheduledTaskInfo |
     Format-Table TaskName, LastRunTime, LastTaskResult, NextRunTime
   ```
   Expect `LastTaskResult = 0`. See §7.2 for what the other exit codes mean — **and note `0` means the job *finished*, not that it *succeeded*.**
4. **Cross-check the scheduler log** — `backend\LOGS\scheduler\` — against `cr673_bahra_automation_log1`. A task that exits 0 while the automation log shows zero companies processed is the Playwright-browser failure in §6.3
5. **No ballooning log folders** — `backend\LOGS\` under 1 GB. If it grew overnight, find which run is looping on failure
6. **No stuck Chromium processes** — `Get-Process chrome, chromium -ErrorAction SilentlyContinue | Measure-Object`
7. **App Proxy connector Active** — Entra ID → Application proxy → connector shows **Active**

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
2. Generate a new secret, update `CLIENT_SECRET` in `backend/config/config.py` (or env var), **`Restart-Service rfp-api`**
3. Confirm the Dataverse Application User still has its security role in Power Platform Admin Center

### 6.2 `429 Too Many Requests` from Dataverse

**Symptom:** Bursts of errors during bulk imports; some RFP rows fail to write.

**Fix:** The `DataverseClient` retries with backoff. If it still fails:
- Reduce batch size in the calling code
- Check that a scheduled download and sync aren't overlapping (§7.1) — they use **separate** `_RUN_STATE` flags and do **not** block each other
- Contact Microsoft if throttling happens during normal single-user activity

### 6.3 Scheduled runs "succeed" but process 0 companies (Playwright browsers)

**Symptom:** The scheduled task exits `0`, but the automation log shows 0 of 4 companies processed. Manual runs from an interactive session work fine. Logs contain:

```
Executable doesn't exist at C:\Windows\system32\config\systemprofile\AppData\Local\ms-playwright\...
```

**Root cause:** Playwright installs browsers **per-user**. `rfp-api` runs as **LocalSystem**, whose profile is `C:\Windows\system32\config\systemprofile` — the browsers were installed into a human's profile instead. Chromium is launched by `rfp-api`, so it's the *service* identity that needs them, not yours and not the task's.

**Fix:** install Chromium under the service identity (e.g. `psexec -s`), or set `PLAYWRIGHT_BROWSERS_PATH` to a shared path and install there. Then `Restart-Service rfp-api`.

> This is why §5's morning check cross-references the scheduler log against the automation log: **exit 0 does not mean the work happened.**

### 6.4 Playwright/Chromium hangs while scraping Ariba

**Symptom:** Automation run never completes; `chrome.exe` consuming CPU; the run flag never clears and the scheduled task eventually exits `3`.

**Fix:**
```powershell
Get-Process chrome, chromium -ErrorAction SilentlyContinue | Stop-Process -Force
Restart-Service rfp-api
```

Each run uses an isolated `pw-profile-{label}-{uuid8}` user-data-dir under temp, so killing browsers doesn't corrupt a shared profile. **Chromium runs headed** (not headless) by design — seeing browser windows on the server console is expected, not a fault.

If it keeps happening, Ariba probably changed its DOM. Open the latest `backend\LOGS\` failure folder's `error.png` to see the page state at failure, and update the selector.

### 6.5 Adaptive-card responses don't appear in the dashboard

**Symptom:** Bidder submits via Outlook; nothing updates in the RFP row.

**Fix checklist:**
1. **Is the callback publicly reachable?** Run the off-LAN probe in §3.4. A **login page** = App Proxy pre-auth is on (must be Passthrough). A **timeout/502** = the connector is down or `rfp-api` is stopped.
2. **Was the card built with the right URL?** `ACTIONABLE_CARD_CALLBACK_URL` must end exactly `/api/actionable-card/response` — `/refresh` and `/decline` are derived from it. A `404` on `…/response/refresh` while the base works is this exact bug. **Already-sent emails carry the old URL** — the fix only affects freshly sent cards.
3. **`500 "APP_ID_URI not configured"`** = `config.py` was edited but `rfp-api` was never restarted, **or** `ACTIONABLE_CARD_APP_ID_URI` is genuinely unset. The token check **fails closed** when the audience is unconfigured.
4. **401 invalid audience/issuer** — inspect the log line: on failure the code re-decodes the token unverified purely to log the actual `aud`/`iss`/`azp` against the expected values. Both v1.0 (`sts.windows.net/{tenant}/`) and v2.0 issuers are accepted, so an issuer mismatch means a different tenant. `azp`/`appid` must be Microsoft's fixed Actions app id `48af08dc-…` — **not** our app id.
5. **Card renders but buttons do nothing** — provider approval alone only makes it render. The token-audience app needs **Expose an API** configured with `48af08dc-…` **authorized** on it.
6. **Refresh action specifically fails** — `POST /response/refresh` is Outlook's `autoInvokeAction` on open and **must respond within 2 s** or Outlook times out.

### 6.6 Email not sending (or sending to the wrong mailbox)

**Symptom:** Emails don't arrive.

**Fix:**
1. **If it's a reminder email — see §7.3. Reminders are a known open defect, not a misconfiguration.**
2. Check `EMAIL_MODE` in `backend/config/config.py`: `dev` routes **everything** to `DEV_EMAIL`; `prod` uses real recipients
3. Production recipient lists live in the `cr673_bahra_system_settings` table (Admin → System Settings), looked up **at send time**. The `config.py` constants are only fallbacks for when Dataverse is unreachable
4. Verify the Graph app has `Mail.Send` (admin consented). Inspect the log for `Graph /sendMail` errors — 403 = permission, 401 = token, 400 = bad payload
5. Check the sender mailbox quota

> **Why email is sent as raw MIME:** the card payload lives in a `<script type="application/adaptivecard+json">` block, and **both Power Automate and Graph's JSON `sendMail` strip `<script>` tags** — which would destroy the card. `email_helper.py` builds a raw MIME message to survive this. Don't "simplify" it back to JSON sendMail.

### 6.7 Frontend shows "Network error" on every page

**Fix:**
1. Session cookie missing — the cookie is scoped to `path=/rfp`. Users must hit the configured hostname, not an IP
2. CORS blocked — check `allow_origins` in `dashboard_main.py` matches the frontend origin
3. Session secret changed — all existing cookies invalidated; users must log out and back in

### 6.8 RFP row stuck in "Processing"

**Fix:**
1. Check `cr673_bahra_automation_log1` for the most recent row touching that RFP ID
2. Check `/api/automation/status` — if the flag is still set, the run is genuinely in flight
3. If the process was restarted mid-run, `_RUN_STATE` is gone (it is in-memory only) and the row is orphaned. The next scheduled tick retries
4. To force a retry now: trigger the job from the dashboard, or `.\Invoke-RfpAutomation.ps1 -Job download`

### 6.9 "Permission denied" in UI for someone who should have access

**Fix, in order:**
1. **Have they logged out and back in?** `require_permission` reads permissions **straight from the session**, which is **frozen at login**. A permission granted five minutes ago has no effect until re-login. This is the single most common cause — the RBAC cache TTL is a red herring for this symptom
2. Is the user's row in `cr673_bahra_user_status` set to `Active`?
3. Does their role have the specific permission? See [RBAC Permissions Matrix](11-RBAC-Permissions-Matrix.md)
4. **Was the role recently renamed?** Role-permission rows store the role name **denormalized**; renaming a role **orphans its permission rows**. And `require_admin` is a hardcoded check for the literal name `"Admin"` — renaming the Admin role breaks every admin-only route
5. RBAC per-role cache is 300 s; restart `rfp-api` to force-clear

> Permission **denials are not audited** — there is no 403 event in the audit log to correlate against. You are working from the user's report and the request log only.

---

## 7. Scheduled jobs

> **This area is mid-migration.** Scheduling has moved from Power Automate onto **Windows Task Scheduler** on the server. Read §7.3 and §7.4 before touching anything here.

### 7.1 Current schedule (Windows Task Scheduler)

Registered by [`scripts/Register-RfpSchedules.ps1`](../../scripts/Register-RfpSchedules.ps1) into the **`\Bahra-RFP\`** task folder. Each task runs [`scripts/Invoke-RfpAutomation.ps1`](../../scripts/Invoke-RfpAutomation.ps1), which calls the local API.

| Task | Job | Daily triggers | Runner timeout | What it does |
|---|---|---|---|---|
| `RFP-Download-OpenRFPs` | `download` | **00:00, 06:00, 12:00, 18:00** | 90 min | Discovers and downloads new RFPs from the supplier portals |
| `RFP-Sync-Portal` | `sync` | **03:00, 09:00, 15:00, 21:00** | 60 min | Syncs RFP status/deadlines from the portals back into Dataverse |

**Times are server-local — Riyadh (Arab Standard Time).**

> ⚠️ **Timezone correction.** The old Power Automate flows ran on **India Standard Time** (UTC+5:30 vs Riyadh's UTC+3), so a flow set to "12:00" actually fired at **09:30 Riyadh**. The task times above are Riyadh times and are **not** a literal carry-over of the old flow's clock. If you're comparing old and new run times, that 2.5-hour shift is expected.

**Why sync is offset 3 hours from download:** `download` and `sync` use **separate `_RUN_STATE` flags**, so the in-app 409 guard would **not** stop them running at once against the same Ariba account. The offset — not the lock — is what prevents two Playwright sessions colliding. **Do not re-align these schedules.**

**Task account:** SYSTEM (`-UseSystem` → ServiceAccount / RunLevel Highest). This is justified because the task only makes a **localhost HTTP call and writes a log file** — it does **not** run Playwright. `rfp-api` runs Playwright, under its own identity. (Which is also why §6.3's browser-install problem belongs to the *service* identity, not the task's.)

Re-registering is idempotent and safe:
```powershell
# ELEVATED PowerShell on 192.168.111.192
cd C:\Bahra-Automation-RFP-System\scripts
.\Register-RfpSchedules.ps1 -UseSystem -WhatIf    # preview
.\Register-RfpSchedules.ps1 -UseSystem

# Verify
Get-ScheduledTask -TaskPath '\Bahra-RFP\' | Format-Table TaskName, State
Get-ScheduledTaskInfo -TaskPath '\Bahra-RFP\' -TaskName 'RFP-Sync-Portal'
```

### 7.2 The runner: `Invoke-RfpAutomation.ps1`

It fires the endpoint, then **polls `/api/automation/status` until the job's run flag clears** — so Task Scheduler's "Last Run Result" reflects the job *finishing*, not just the request being accepted (the API returns 202 immediately and works on a background thread).

| `-Job` | Endpoint | Status flag | Async |
|---|---|---|---|
| `download` | `/api/download-rfps-automation` | `download_running` | yes |
| `sync` | `/api/sync_portal_data` | `sync_running` | yes |
| `sync-sp-dv` | `/api/sync-sharepoint-dataverse` | `sync_sp_dv_running` | yes |
| `reminder` | `/api/rfp-reminder` | none | no — blocks and returns its result |

Key parameters: `-BaseUrl http://127.0.0.1:8000` · `-StartupWaitSeconds 120` (covers a reboot where the task fires before `rfp-api` has started) · `-TimeoutMinutes` · `-PollSeconds 15` · `-SkipIfRunning` · `-LogDir ...\backend\LOGS\scheduler`.

**Exit codes — read these carefully:**

| Code | Meaning | What to do |
|---|---|---|
| `0` | The job **finished** | ⚠️ **Finished ≠ succeeded.** The run flag clears in a `finally`, so a *crashed* run also exits 0. Confirm real work happened via `cr673_bahra_automation_log1`; failures surface as bundles in `backend\LOGS\` and an alert to `EMAIL_TO_AUTOMATION_FAILURE` |
| `1` | API unreachable | Is `rfp-api` running? Check `/health` |
| `2` | Already running (HTTP 409) and `-SkipIfRunning` was not set | A previous run overran its window, or someone triggered it from the UI. The registered tasks **do** pass `-SkipIfRunning`, so they log a warning and exit 0 instead |
| `3` | Did not finish within `-TimeoutMinutes` | **The job was not killed — it is still running server-side.** Check `/api/automation/status` before re-triggering |

Manual run:
```powershell
cd C:\Bahra-Automation-RFP-System\scripts
.\Invoke-RfpAutomation.ps1 -Job sync -TimeoutMinutes 45
```

### 7.3 ⚠️ OPEN ISSUE — reminder emails are not sending

**Status: broken in production. Not fixed.**

The reminder job is the one flow the migration deliberately left on Power Automate (`Bahra-RFP-Reminder-Emails-Cron-job` → `/api/rfp-reminder`). But that flow — like the two it replaced — fires at a **dead devtunnel** (`https://0vv8220f-8000.inc1.devtunnels.ms`). The request never reaches the backend, so **bidders are not being chased for overdue responses.**

Why nothing is covering it:
- **No scheduled task replaces it.** `Register-RfpSchedules.ps1` registers `download` and `sync` only — the reminder was explicitly out of scope.
- **App Proxy does not help.** It publishes **only** `/api/actionable-card/`, by design. `/api/rfp-reminder` is not, and must not be, internet-reachable.
- `Invoke-RfpAutomation.ps1 -Job reminder` **exists and works**, but nothing schedules it.

**Manual workaround** — run on the server when reminders are needed:
```powershell
cd C:\Bahra-Automation-RFP-System\scripts
.\Invoke-RfpAutomation.ps1 -Job reminder
```
This sends **real bidder email**. The reminder logic itself is sound (pure Dataverse read + email, no browser; 3-day/1-day cadence with `Reminder_3Day_Sent` / `Reminder_1Day_Sent` idempotency flags, so a re-run will not double-send the same stage).

**Permanent fixes, either of which closes this:** register a third scheduled task for `-Job reminder` (the runner already supports it), or repoint the Power Automate flow at a URL the cloud can actually reach. Until one is done, **treat reminders as manual**.

### 7.4 ⚠️ OPEN ISSUE — the Schedule Automation page is a silent no-op

**Status: misleading UI in production. Not fixed.**

The portal's **Schedule Automation** page (`schedule_automation.manage`) still targets **`Bahra-E-binding-cron-job`** — the exact Power Automate flow that `Register-RfpSchedules.ps1` instructs you to turn off.

What happens when an operator edits the schedule post-migration:
1. The row saves to `cr673_bahra_automation_scheduleses`. ✅
2. The backend patches the flow's Recurrence trigger. ✅ (via the `workflow` table in the same Dataverse environment — failure here is non-fatal and swallowed)
3. A **success toast** appears. ✅
4. **The actual download cadence does not change.** ❌ It is driven by the `RFP-Download-OpenRFPs` scheduled task, which knows nothing about this page.

**Consequences for on-call:**
- **Never tell a user the schedule changed because the page said so.** The authority is `Get-ScheduledTask -TaskPath '\Bahra-RFP\'`.
- **Do not "fix" this by re-enabling `Bahra-E-binding-cron-job`.** If that flow is turned back on *and* it ever reaches a live URL, **download fires from both sources**.
- To actually change the cadence, edit the triggers in `Register-RfpSchedules.ps1` and re-run it elevated (§7.1).

### 7.5 Power Automate flow disposition

| Flow | Endpoint | Disposition |
|---|---|---|
| `Bahra-E-binding-cron-job` | `/download-rfps-automation` | **Turn off** — replaced by `RFP-Download-OpenRFPs`. Leaving it on risks double-firing |
| `Bahra-sync-open-rfp-status-cron-job` | `/api/sync_portal_data` | **Turn off** — replaced by `RFP-Sync-Portal` |
| `Bahra-RFP-Reminder-Emails-Cron-job` | `/api/rfp-reminder` | **Leave on** by decision — but it is pointed at a dead URL and is **not working** (§7.3) |

Only the download flow is editable from the portal's Schedule page; the other two are invisible to it.

---

## 8. Manual operations

All backend commands run **from inside `backend\`** (§2.2).

### 8.1 Trigger an automation job

From the dashboard UI (the sidebar buttons), or on the server:

```powershell
cd C:\Bahra-Automation-RFP-System\scripts
.\Invoke-RfpAutomation.ps1 -Job download          # discover + download open RFPs
.\Invoke-RfpAutomation.ps1 -Job sync              # sync portal status back to Dataverse
.\Invoke-RfpAutomation.ps1 -Job sync-sp-dv        # reconcile SharePoint ↔ Dataverse
.\Invoke-RfpAutomation.ps1 -Job reminder          # ⚠️ sends real bidder email — see §7.3
```

Or call the API directly — `Invoke-RestMethod http://127.0.0.1:8000/api/download-rfps-automation`. Note the automation endpoints are **unauthenticated**, which is exactly why they must never be internet-reachable.

### 8.2 Reset a stuck Playwright session

```powershell
Get-Process chrome, chromium -ErrorAction SilentlyContinue | Stop-Process -Force
Restart-Service rfp-api
```

Per-run profile dirs (`pw-profile-*`) live under temp and are disposable; clear them if temp is filling up.

### 8.3 Re-seed RBAC default roles

Safe to re-run.

```powershell
cd C:\Bahra-Automation-RFP-System\backend
..\env\Scripts\python.exe -c "from services.dynamic_role_service import seed_default_roles; seed_default_roles()"
```

Recreates `Admin` (all 42 permissions, computed dynamically from the code) and `RFP Bidder` (10).

> There is no `setup_rbac_tables.py` — it has been deleted. The RBAC tables must already exist.

### 8.4 Inspect current system settings

```powershell
cd C:\Bahra-Automation-RFP-System\backend
..\env\Scripts\python.exe check_settings.py
```

### 8.5 Clear caches without restarting

Caches are 300 s TTL, so usually just wait. To force-clear immediately:

```powershell
Restart-Service rfp-api
```

> A restart does **not** refresh a logged-in user's permissions — those are frozen in their session cookie until they log out and back in (§6.9).

---

## 9. Monitoring & alerting (recommended)

The system ships with **no built-in alerting**. Operations should wire up:

- **Uptime monitor** → `GET http://127.0.0.1:8000/health` every 60 s (from inside the LAN — the backend is localhost-only and the portal is not internet-facing)
- **Windows Event Log forwarder** → SIEM for `rfp-api` service crash events
- **Scheduled-task result alert** → alarm when `Get-ScheduledTaskInfo` reports `LastTaskResult ≠ 0` for a `\Bahra-RFP\` task. **Also alarm on a task that exits 0 while writing no rows to `cr673_bahra_automation_log1`** — exit 0 does not mean the work happened (§7.2)
- **Dataverse flow** → email ops when `cr673_bahra_automation_log1.status = 'Failed'`
- **Disk-space alert** on the volume hosting `backend\LOGS\` — warn at 80 %
- **Azure AD** → email the admin 30 days before `CLIENT_SECRET` expires (set a calendar reminder if AAD notifications are off)
- **App Proxy connector** → alert if the connector leaves **Active**; a dead connector silently breaks every card button

> **Audit writes are fire-and-forget on a daemon thread and failures only print** — do not build an alert that assumes the audit log is complete (see [Security & Compliance §7](12-Security-and-Compliance.md#7-audit-trail)).

---

## 10. Capacity & housekeeping

| Area | Rule of thumb | How to clean up |
|---|---|---|
| `backend\LOGS\` | Keep last 90 days | **Manual** — there is no cleanup job. `Remove-Item` folders older than 90 days |
| `backend\LOGS\scheduler\` | Monthly files; keep 12 | Manual |
| `backend\ALLRFPs\` | Keep last 180 days of downloaded BOQ attachments | Manual pruning; large files can be moved to cold storage |
| `pw-profile-*` dirs under temp | Disposable | Delete when temp fills up; each run creates a fresh one |
| `cr673_bahra_automation_log1` | Keep last 1 year | Bulk-delete in Dataverse (requires System Administrator) |
| `cr673_bahra_audit_logs` | Keep **indefinitely** (compliance) | Do not prune without Legal approval |
| Dataverse storage (overall) | Under your licensed capacity | Power Platform Admin Center → Storage tab |

---

## 11. Change management

Any change that affects production flows through:

1. **Pull request** against the trunk branch
2. **Peer review** by the owner (Manish Soni) or delegate
3. **Release notes** added to [CHANGELOG.md](../CHANGELOG.md)
4. **Deploy window** — avoid the scheduled task windows in §7.1 (00:00/06:00/12:00/18:00 and 03:00/09:00/15:00/21:00 Riyadh) and month-end close
5. **Post-deploy verification** — §3 health checks + one end-to-end smoke test

> **There is no automated test suite of any kind** — verified 2026-07-17. No `tests/` directory, no `pytest` suite, no load-test tooling. Verification is manual; §3 and §5 are the gate.

Rollback: redeploy the previous Git tag, `Restart-Service rfp-api`. Remember that `backend/config/config.py` is **untracked** — a rollback does not revert it, and a config change needs its own restart. If a Dataverse schema migration went wrong, restore via Dataverse point-in-time restore.

---

## 12. On-call playbook

**Severity guide:**

| Severity | Example | SLA |
|---|---|---|
| SEV-1 | Portal down, no RFPs accepted; or card callbacks failing for all bidders | 15 min ack, 1 h fix |
| SEV-2 | Automation not running but portal up | 30 min ack, 4 h fix |
| SEV-3 | Single feature broken (e.g., one portal's selectors) | Next business day |
| SEV-4 | Cosmetic / UX bug | Backlog |

**First 5 minutes of any page:**

1. `Invoke-WebRequest http://127.0.0.1:8000/health -UseBasicParsing`
2. `Get-Service rfp-api`
3. `Invoke-RestMethod http://127.0.0.1:8000/api/automation/status` — is something stuck in flight?
4. Tail the last 200 lines of the service stdout log and `backend\LOGS\scheduler\`
5. Identify whether the issue is: code, config (**was the service restarted after the last `config.py` edit?**), Dataverse, external dep (Ariba/SharePoint/Email), App Proxy, or network
6. If the cause is not obvious in 5 min: **`Restart-Service rfp-api`** — safe; the only in-memory state is `_RUN_STATE`, which abandons in-flight runs that the next tick retries
7. If restart doesn't fix it within 5 min: open the relevant troubleshooting section above, escalate to the owner

**Known-issue triage — check these before investigating:**

| Report | Answer |
|---|---|
| "Bidders aren't getting reminder emails" | **Known open defect — §7.3.** Not a regression. Run the manual workaround |
| "I changed the schedule and nothing happened" | **Known open defect — §7.4.** Expected. The real cadence is Task Scheduler |
| "The automation ran but nothing downloaded" | Likely the Playwright/LocalSystem browser issue — §6.3 |
| "The card buttons stopped working" | §3.4, then §6.5. Check the App Proxy connector is Active and pre-auth is still Passthrough |
| "I gave them the permission and they still can't get in" | They need to **log out and back in** — §6.9 |

---

## 13. Contacts

| Role | Who | How to reach |
|---|---|---|
| System owner | **Manish Soni** | **Manish.soni@dynatechconsultancy.com** — escalation point for all SEV-1/SEV-2 |
| Dataverse / Power Platform admin | *(fill in)* | |
| Azure AD / Entra app registration & App Proxy admin | *(fill in)* | |
| Ariba administrator (business side) | *(fill in)* | |
| SAP integration contact | *(fill in)* | |
| On-call rotation | *(fill in)* | |

---

## 14. Document maintenance

Update this runbook whenever you:
- Add a new service, script, or scheduled task
- Encounter a novel incident — add a row to §6
- Close either of the open defects in §7.3 / §7.4 — **remove the banner at the top of this doc**
- Change monitoring / alerting infrastructure
- Rotate credentials or change the service-account pattern

Bump `version` and `last_updated` in the frontmatter on every edit.

---

## 15. Change history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-04-22 | Manish Soni | Initial runbook |
| 1.1 | 2026-07-17 | Manish Soni | Verified against code; App Proxy callback, Task Scheduler migration, prod topology, 42 permissions, corrected security posture |
