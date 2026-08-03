---
title: Troubleshooting — Bahra Electric RFP Automation
version: 1.1
last_updated: 2026-07-17
owner: Manish Soni (Manish.soni@dynatechconsultancy.com)
audience: Ops, Admins, Developers
status: Living document
---

# Troubleshooting

Growing FAQ of known issues, root causes, and fixes. Add entries as new symptoms are diagnosed.

When you fix an issue that isn't already listed: add it. One entry = one symptom. Keep entries scannable — **Symptom → Cause → Fix**.

> **Every entry here must be real.** If you cannot point at the code, the config key, or the command that proves it, don't add it. An invented fix at 2am is worse than no entry.

Related:
- [Operations Runbook §6](03-operations/10-Operations-Runbook.md#6-common-errors-and-how-to-fix-them) — the on-call copy, with the production commands
- [Operations Runbook §7](03-operations/10-Operations-Runbook.md#7-scheduled-jobs) — scheduling and the two open defects
- [Deployment Guide §14](03-operations/09-Deployment-Guide.md#14-troubleshooting-common-deployment-issues) — first-deploy issues
- [Security & Compliance §9](03-operations/12-Security-and-Compliance.md#9-incident-response) — for security-classed issues

> **Production is `rfp-api` (WinSW) on VM `192.168.111.192`, repo `C:\Bahra-Automation-RFP-System`, backend on `127.0.0.1:8000`.** The dev path `C:\python\RFP-automation` is not the server. See [Operations Runbook §1](03-operations/10-Operations-Runbook.md#1-system-at-a-glance).

---

## Two known open defects — check here first

| Report | Answer |
|---|---|
| "Bidders aren't getting reminder emails" | **Known open defect — §6.4.** Not a regression |
| "I changed the schedule and nothing happened" | **Known open defect — §6.5.** Expected; the page is a no-op |

---

## Table of contents

1. [Login & session](#1-login--session)
2. [Dashboard / UI](#2-dashboard--ui)
3. [RFPs](#3-rfps)
4. [Adaptive cards & the callback](#4-adaptive-cards--the-callback)
5. [Matching engine](#5-matching-engine)
6. [Automation / scheduled jobs](#6-automation--scheduled-jobs)
7. [Playwright / Ariba scraping](#7-playwright--ariba-scraping)
8. [Dataverse](#8-dataverse)
9. [Email sending](#9-email-sending)
10. [RBAC / permissions](#10-rbac--permissions)
11. [Deployment & services](#11-deployment--services)
12. [Performance](#12-performance)

---

## 1. Login & session

### 1.1 "Invalid email or password" with known-good credentials

**Cause:** User row exists but is deactivated, or `users.role` points at a role that was renamed or deleted.

**Fix:**
1. Check the user's row in `cr673_bahra_user_status` — status should be `Active`.
2. Verify `users.role` matches an existing `cr673_bahra_roles` name. Role names are matched as **strings** — a rename breaks the link (§10.2).
3. Have the user try "Forgot password" to reset cleanly (§1.4).

### 1.2 Account locked out

**Cause:** `record_failed_login` in [`backend/services/user_lifecycle_service.py`](../backend/services/user_lifecycle_service.py) increments `failed_attempts`; at `ACCOUNT_LOCKOUT_THRESHOLD` (default **5**) it sets `locked_until` to now + `ACCOUNT_LOCKOUT_DURATION_MINUTES` (default **30**). Both are System Settings keys. A successful login clears both.

**Fix:** Admin → User Management → **Unlock** (calls `unlock_user`). Or wait out `locked_until`. If a user is locked on their *first* attempt, `locked_until` is stale from a prior incident — unlock clears it.

### 1.3 "Session expired" / user logged out unexpectedly

**Cause:** The effective session lifetime is a **flat 2-hour absolute** cookie `max_age` (`SESSION_TIMEOUT_SECONDS = 7200`, [`backend/config/config.py`](../backend/config/config.py)). It is not a sliding window — activity does not extend it.

**There is no idle timeout.** `IDLE_TIMEOUT_SECONDS`, `SESSION_WARNING_SECONDS`, and `SESSION_REFRESH_INTERVAL` exist in `config.py` but **no code reads them**. Don't chase an idle timeout that isn't implemented.

**Fix:**
1. Two hours after login is expected behaviour — the user logs back in.
2. Sooner than that: the session cookie is `rfp_session`, scoped to **`path=/rfp`**. Users must reach the site on the configured hostname and under `/rfp`; hitting the raw IP or a different path drops the cookie.
3. Verify the IIS reverse proxy forwards the `Cookie` header.
4. If the service restarted *and* the session secret changed, all cookies invalidate. Note the secret is currently **hardcoded** (`secret_key="change-me-please"` in [`backend/dashboard_main.py`](../backend/dashboard_main.py)), so a restart alone does **not** invalidate sessions — and that hardcoding is itself a finding ([Deployment Guide §11.2](03-operations/09-Deployment-Guide.md#11-production-hardening)).

### 1.4 "Forgot password" email never arrives

**Cause:** This path does **not** go through Graph `sendMail`. `routes/api.py` POSTs the reset payload to a **Power Automate flow** at `FORGOT_PASSWORD_FLOW_URL` (a System Settings key), and raises `502 "Flow error: <code>"` if the flow returns non-2xx.

**Fix:**
1. Check the dashboard log for `Flow error:` and the status code it carries.
2. Verify `FORGOT_PASSWORD_FLOW_URL` in Admin → System Settings is the current HTTP-trigger URL, and that the flow is **turned on** in Power Automate. A flow that is off, or whose trigger URL was regenerated, is the usual cause.
3. Fall back to Admin → User Management → reset the user's password manually.

---

## 2. Dashboard / UI

### 2.1 Whole UI blank after deploy

**Cause:** `frontend/dist/` missing or stale. In production IIS serves `dist/` directly — FastAPI does not host the SPA.

**Fix:** `cd frontend; npm install; npm run build`. Verify `dist/index.html` exists. **`npm run build` erases `dist/`, including the `web.config` carrying the IIS rewrite rules — re-paste it** ([Deployment Guide §8](03-operations/09-Deployment-Guide.md#8-build-the-frontend)).

### 2.2 "Network error" on every API call

**Cause:** CORS rejection, or the user hit the server by IP so the `path=/rfp` cookie doesn't attach.

**Fix:**
1. Use the configured hostname (`https://be-aramco-01.bahra-cables.com/rfp`), not an IP.
2. CORS origins are a **hardcoded list in [`backend/dashboard_main.py`](../backend/dashboard_main.py)** (`allow_origins=[...]`) — **not** a `config.py` setting. Add the origin there and `Restart-Service rfp-api`.

### 2.3 Sidebar missing items the user should see

**Cause:** Their role lacks the permission gating that item — or their session predates the grant.

**Fix:** See §10.1 first (permissions are frozen at login). Then check the role's grants against the [RBAC Permissions Matrix](03-operations/11-RBAC-Permissions-Matrix.md).

### 2.4 Tables stuck on "loading"

**Cause:** Backend exception or Dataverse throttling.

**Fix:** Browser devtools → Network → find the failing request. A **500** carries an 8-character `error_id` in the body — grep the service stdout for that id to find the traceback. A **429** is §8.3.

---

## 3. RFPs

### 3.1 BOQ table shows raw field names like `cr673_qty`

**Cause:** The `DataverseClient` column-mapping cache (`_column_mapping_cache` in [`backend/helpers/dataverse_helper.py`](../backend/helpers/dataverse_helper.py)) holds a stale logical→display map after a schema change. **This cache has no TTL and no reload endpoint** — it lives for the life of the process.

**Fix:** `Restart-Service rfp-api`. (`POST /api/system-settings/reload-cache` will **not** help — it only invalidates the *settings* cache.)

### 3.2 Fields return `null` for rows that clearly have values

**Cause:** Same stale mapping as §3.1. Also note `use_display_names=True` **rewrites the primary-key column** to its display label, so `row.get("<table>id")` returns `None` — that is by design, not a bug. Resolve the PK via the logical→display reverse map.

**Fix:** Restart the service. In code, `get_column_mapping(table, force_refresh=True)` after a schema operation.

### 3.3 RFP row stuck in "Processing"

**Cause:** The run was abandoned — usually the service restarted mid-run. `_RUN_STATE` is **in-memory and process-local**, so it does not survive a restart and the row is orphaned.

**Fix:** See [Operations Runbook §6.8](03-operations/10-Operations-Runbook.md#6-common-errors-and-how-to-fix-them). Short version: check `/api/automation/status`; check `cr673_bahra_automation_log1` for the last row touching that RFP ID; force a retry with `.\Invoke-RfpAutomation.ps1 -Job download`, or wait for the next scheduled tick.

### 3.4 Attachments won't download from SharePoint

**Cause:** The file was renamed or deleted, or the Graph app lost its permission on the site.

**Fix:** Confirm the file still exists under `RFP-logs/`. [`backend/helpers/sharepoint_helper.py`](../backend/helpers/sharepoint_helper.py) already tries **three** filename strategies (exact → normalised → partial containment) to survive portal filenames that don't round-trip — if all three miss, the file genuinely isn't there. Re-run the download job for that RFP.

---

## 4. Adaptive cards & the callback

The callback runs over **Microsoft Entra Application Proxy (Passthrough)**. The devtunnel is retired — any instruction to "keep the dev tunnel running" is stale.

### 4.1 Card renders as a plain email with no inputs

**Cause:** Recipient's client doesn't support actionable messages, or the originator ID isn't approved.

**Fix:** Direct them to Outlook Web / Desktop, or the portal. Confirm `ACTIONABLE_CARD_ORIGINATOR_ID` is registered and approved at https://outlook.office.com/connectors/oam/publish.

### 4.2 Card renders but the buttons do nothing

**Cause, in order of likelihood:**

1. **App Proxy switched to Entra-ID pre-auth.** Outlook's Actions service sends a *service* token, not an interactive sign-in — pre-auth redirects it to a login page and every button dies silently.
2. Connector down, or `rfp-api` stopped.
3. **Provider approval alone only makes the card *render*.** The token-audience app must have **Expose an API** configured with Microsoft's Actions app id `48af08dc-…` **authorized** on it, or Outlook never POSTs.

**Fix:** Probe from an **off-LAN** machine:

```powershell
curl.exe -i https://<app-proxy-host>.msappproxy.net/rfp/api/actionable-card/response
```

- **401/500 from the app** = healthy. The token check rejected an anonymous probe — that is the point.
- **A Microsoft login page** = pre-auth is on. Set **Pre Authentication = Passthrough**.
- **Timeout / 502** = the connector can't reach `:8000`, or `rfp-api` is down.

### 4.3 `500 "APP_ID_URI not configured"`

**Cause:** `ACTIONABLE_CARD_APP_ID_URI` is unset — **or, far more often, `config.py` was edited and the service was never restarted.** The token check **fails closed** when the audience is unconfigured.

**Fix:** **`Restart-Service rfp-api`.** Nothing re-reads `config.py` at runtime. This is a recurring, known cause — check it before you check anything else.

### 4.4 401 "invalid audience / issuer"

**Cause:** Token claims don't match config.

**Fix:** On failure the code re-decodes the token **unverified** purely to log the actual `aud`/`iss`/`azp` against the expected values — read that log line first. Then:
- **`iss`**: both v1.0 (`https://sts.windows.net/{tenant}/`) and v2.0 (`https://login.microsoftonline.com/{tenant}/v2.0`) are accepted, so a mismatch means a **different tenant**, not a version problem.
- **`aud`**: must be `ACTIONABLE_CARD_APP_ID_URI` (the bare client id is also accepted).
- **`azp`** (or `appid` on v1.0 tokens): must be `ACTIONABLE_CARD_ACTIONS_APP_ID` = Microsoft's fixed **`48af08dc-…`** — **not** our app id.

### 4.5 `…/response/refresh` 404s while the base URL works

**Cause:** `ACTIONABLE_CARD_CALLBACK_URL` doesn't end in the exact suffix `/api/actionable-card/response`. [`backend/helpers/email_helper.py`](../backend/helpers/email_helper.py) builds `/refresh` by appending to that value, and derives `/decline` via `rsplit("/response", 1)`. **Every button follows from that one string.** Change the host, never the suffix.

**Fix:** Correct the value in `config.py`, `Restart-Service rfp-api`. **Already-sent emails carry the old URL** — the fix only applies to freshly sent cards.

### 4.6 Card shows stale data on re-open

**Cause:** `POST /response/refresh` is Outlook's `autoInvokeAction`, fired on open. **It must respond within 2 seconds** or Outlook times out and shows the cached card.

**Fix:** If the backend is slow or cold, the refresh silently loses. Open the RFP in the portal for the authoritative view.

---

## 5. Matching engine

> **There is no fuzzy matching, no similarity score, no confidence value, and no threshold.** No similarity library (`rapidfuzz`, `fuzzywuzzy`, `difflib`, …) is imported anywhere in `backend/`. `MatchMethod` is a categorical label — `"exact"`, `"keyword"`, or `None` — not a number. Any doc or ticket referring to a match threshold or match percentage is describing something that does not exist.

The engine is a deterministic two-tier classifier in `process_folder`, [`backend/rfp/download_rfp.py`](../backend/rfp/download_rfp.py):

1. Pull a **literal 9-digit** SAP code out of the row via `re.findall(r'\d{9}', ...)`.
2. **Exact**: pure string equality against the Material Master → `MatchMethod="exact"`.
3. **Keyword** (only if exact failed): **bidirectional substring containment** — `if csv_keyword in mat_keyword or mat_keyword in csv_keyword` — then `str.contains(...)` re-search and **`.head(1)`** → `MatchMethod="keyword"`.
4. Otherwise unmatched.

**The two hazards follow directly from that:** substring containment is unranked and aggressive, and `.head(1)` takes an **arbitrary** first candidate, not a best one. There is no tie-break and nothing to tune.

### 5.1 Common items not auto-matching

**Cause:** No Material Master row with that 9-digit code, and no Keyword Master row that fires on the description. **Not a threshold** — there isn't one.

**Fix:** Add the **row**, in Admin → Master Data:
1. Prefer a **Material Master** row carrying the real 9-digit code — that hits the exact tier and is unambiguous.
2. Only add a **Keyword Master** row if there's no code to match on. Read §5.2 before you do.

Both are read by `get_all_materials_for_matching()` / `get_all_keywords_for_matching()` in [`backend/services/master_data_service.py`](../backend/services/master_data_service.py) — Dataverse-first, SharePoint CSV fallback (`RFP-logs/master-files/material.csv`, `unique_keywords.csv`), with a **5-minute TTL cache**. A new row takes up to 5 minutes to take effect.

### 5.2 Wrong material matched

**Cause:** Almost always a **too-broad Keyword Master row**. Matching is bidirectional substring containment, so a short keyword like `CU` matches *any* description containing those two characters anywhere. The engine then takes `.head(1)` of the candidate set — an arbitrary row. A short keyword doesn't produce a weak match; it produces a **confident wrong** one.

**Fix:**
1. **There is no match-override control in the UI.** A bidder cannot correct a match, and neither can an admin, per-row. The only lever is the master data.
2. Find the offending keyword: look for the shortest / most generic Keyword Master rows that appear in the wrongly-matched description. **Delete or lengthen them.**
3. Add a Material Master row with the correct 9-digit code so the item resolves on the **exact** tier and never reaches the keyword path.
4. Re-run the download job for that RFP after the 5-minute cache TTL.

> **Rule of thumb:** treat every new keyword as a global regex-ish wildcard against the whole master. Short keywords are the single biggest source of wrong matches.

---

## 6. Automation / scheduled jobs

Full detail — cadence, exit codes, both open defects — in [Operations Runbook §7](03-operations/10-Operations-Runbook.md#7-scheduled-jobs). This section is the symptom index.

### 6.1 No runs in `automation_log1` for the last day

**Cause:** `rfp-api` is down, or the scheduled tasks aren't firing.

**Fix:**
```powershell
Get-Service rfp-api
Invoke-WebRequest http://127.0.0.1:8000/health -UseBasicParsing

Get-ScheduledTask -TaskPath '\Bahra-RFP\' | Get-ScheduledTaskInfo |
  Format-Table TaskName, LastRunTime, LastTaskResult, NextRunTime
```

Download and sync run on **Windows Task Scheduler** (folder `\Bahra-RFP\`: `RFP-Download-OpenRFPs`, `RFP-Sync-Portal`), **not** Power Automate and **not** the portal's Schedule page. **Do not check the schedule toggle in the UI — it tells you nothing (§6.5).**

Also tail `backend\LOGS\scheduler\scheduler-<yyyy-MM>.log`.

### 6.2 Scheduled task exits `0` but nothing was downloaded

**Cause:** **Exit 0 means the job *finished*, not that it *succeeded*.** The run flag clears in a `finally`, so a crashed run also reports 0.

**Fix:** If the automation log shows **0 of 4 companies processed** while manual runs work, it's the Playwright browser-install failure — **§7.1**. Otherwise check `backend\LOGS\` for the failure bundle and the alert sent to `EMAIL_TO_AUTOMATION_FAILURE`.

Other exit codes: `1` API unreachable · `2` already running (409) · `3` timeout — **the job was not killed, it is still running server-side**; check `/api/automation/status` before re-triggering.

### 6.3 Download and sync collided

**Cause:** They use **separate `_RUN_STATE` flags**, so the in-app 409 guard does **not** stop them running at once against the same Ariba account. Only the **3-hour schedule offset** keeps them apart (download 00/06/12/18, sync 03/09/15/21 — Riyadh server-local).

**Fix:** Don't re-align the schedules. If someone triggered a job manually into the other's window, wait it out.

### 6.4 ⚠️ OPEN DEFECT — reminder emails are not sending

**Cause:** The `Bahra-RFP-Reminder-Emails-Cron-job` Power Automate flow fires at a **dead devtunnel**. No scheduled task replaces it — `Register-RfpSchedules.ps1` registers `download` and `sync` only. App Proxy publishes only `/api/actionable-card/`, so it doesn't help either. **Bidders are not being chased.**

**Fix (manual workaround — this is the current state, not a regression):**
```powershell
cd C:\Bahra-Automation-RFP-System\scripts
.\Invoke-RfpAutomation.ps1 -Job reminder
```
Sends **real bidder email**. Safe to re-run: the reminder logic uses `Reminder_3Day_Sent` / `Reminder_1Day_Sent` idempotency flags, so it won't double-send a stage. See [Operations Runbook §7.3](03-operations/10-Operations-Runbook.md#7-scheduled-jobs).

### 6.5 ⚠️ OPEN DEFECT — the Schedule Automation page is a silent no-op

**Cause:** The page targets `POWER_AUTOMATE_FLOW_NAME = "Bahra-E-binding-cron-job"` — the exact flow the Task Scheduler migration turns off. Post-migration the row saves, the flow's Recurrence trigger is patched, a **success toast appears** — and the real download cadence (Task Scheduler) does not change.

**Fix:** There isn't one; know the behaviour.
- **Never tell a user the schedule changed because the page said so.** The authority is `Get-ScheduledTask -TaskPath '\Bahra-RFP\'`.
- **Do not "fix" it by re-enabling `Bahra-E-binding-cron-job`** — if it ever reaches a live URL, download fires from **both** sources.
- To really change the cadence: edit the triggers in [`scripts/Register-RfpSchedules.ps1`](../scripts/Register-RfpSchedules.ps1) and re-run it elevated. See [Operations Runbook §7.4](03-operations/10-Operations-Runbook.md#7-scheduled-jobs).

### 6.6 `NotImplementedError` on subprocess when an automation starts

**Cause:** Playwright was driven **directly from a FastAPI request handler**. Uvicorn runs a **SelectorEventLoop**, which on Windows cannot spawn subprocesses — and Playwright must launch Chromium.

**Fix (code-level):** every Playwright path must go through `_run_async_in_thread(...)` in [`backend/routes/automation.py`](../backend/routes/automation.py), which runs the coroutine on a **new daemon thread with its own `ProactorEventLoop`** and returns 202 immediately. `await`ing a Playwright function straight from a handler will always fail this way. If you see this after adding a route, that's the bug.

---

## 7. Playwright / Ariba scraping

> **Chromium runs HEADED** — `headless_mode = False` is hardcoded in `common_flow` ([`backend/automation_logic.py:484`](../backend/automation_logic.py)). Browser windows on the server console are **expected**, not a fault. Each run gets an isolated `pw-profile-{label}-{uuid8}` user-data-dir under temp, so parallel runs don't share a profile.

### 7.1 Scheduled runs process 0 companies; manual runs work

**This is the highest-frequency automation failure. Check it first.**

```
Executable doesn't exist at C:\Windows\system32\config\systemprofile\AppData\Local\ms-playwright\...
```

**Cause:** **Playwright installs browsers per-user**, into the profile of whoever ran `playwright install`. `rfp-api` launches Chromium, and it runs as **LocalSystem**, whose profile is `C:\Windows\system32\config\systemprofile`. Browsers installed under a human account are invisible to it. Classic signature: **manual runs work, every scheduled run processes 0 of 4 companies, and the task still exits 0.**

**Fix:** Install Chromium **under the service identity** (e.g. `psexec -s`), or set `PLAYWRIGHT_BROWSERS_PATH` to a shared path and install there. Then `Restart-Service rfp-api`.

> The **service** identity needs the browsers — not yours, and not the scheduled task's. The task only makes a localhost HTTP call; it never runs Playwright.

### 7.2 "Browser launch failed"

**Cause:** Chromium not installed for the running identity (§7.1), or EDR/antivirus blocking the executable.

**Fix:** Confirm §7.1 first. Then whitelist the Playwright browsers folder in EDR.

### 7.3 Scraper logs in then times out

**Cause:** Ariba changed its DOM.

**Fix:** Open the latest failure folder under `backend\LOGS\` — it holds `error.png` and the page HTML at the moment of failure. Update the selector. Selectors live in `COMPANY_RFP_SELECTORS` in [`backend/config/config.py`](../backend/config/config.py); note all four companies currently map to the **same** default selector list, so a "one company broke" report usually means the shared list broke.

### 7.4 Chromium processes pile up

**Cause:** Contexts leaked when a run died hard.

**Fix:**
```powershell
Get-Process chrome, chromium -ErrorAction SilentlyContinue | Stop-Process -Force
Restart-Service rfp-api
```
Per-run `pw-profile-*` dirs under temp are disposable — delete them if temp is filling up.

---

## 8. Dataverse

### 8.1 `401 Unauthorized` on every call

**Cause:** `CLIENT_SECRET` expired (24-month max life), or the Application User lost its security role.

**Fix:**
1. Regenerate the secret in Azure Portal → App Registrations → Certificates & Secrets.
2. Update `CLIENT_SECRET` in `backend/config/config.py` and **`Restart-Service rfp-api`**.
3. Confirm the Application User still holds its role in Power Platform Admin Center.

> **`backend/config/config.py` is gitignored and has never been committed.** Secrets are **not** in the repository — they live in an untracked, per-host file. That means: `git pull` won't overwrite it, a rollback won't revert it, a fresh clone won't contain it, and **rotation is manual on every host**. Keep a copy in secure storage.

### 8.2 `404 NotFound` on a table you know exists

**Cause:** `EntitySetName` mismatch. **Dataverse pluralization is not predictable — never guess it.**

| Logical | Actual API name | Rule applied |
|---|---|---|
| `cr673_bahra_roles` | `cr673_bahra_roleses` | `+es` |
| `cr673_bahra_rfp_reminder_for_info` | `cr673_bahra_rfp_reminder_for_infos` | `+s` |
| `cr673_bahra_user_status` | `cr673_bahra_user_statuses` | `status` → `statuses` |

**Fix:** Ask the API, don't infer:

```
GET {RESOURCE_URL}/api/data/v9.2/EntityDefinitions(LogicalName='<logical>')?$select=EntitySetName
```

Paste the returned value into the matching `*_API` constant in [`backend/config/config.py`](../backend/config/config.py) (each table is a `_LOGICAL` + `_API` pair) and restart. The `setup_*_table.py` scripts in `backend/Support-Files/` print the resolved name after `PublishXml` for exactly this reason.

> Two table names contain **real, load-bearing typos**: `cr673_bahra_sap_infomation` (missing `r`) and `cr673_bhara_rfp_status` (prefix transposed). They are the actual names — **do not "correct" them.**

### 8.3 `429 TooManyRequests`

**Cause:** Bulk operation exceeded the tenant throttle.

**Fix:** The `DataverseClient` retries with backoff. If it still fails, reduce batch size in the calling code. Check a download and a sync aren't overlapping (§6.3).

---

## 9. Email sending

### 9.1 No emails reaching bidders

**Cause:** `EMAIL_MODE` is still `"dev"`, which routes **all** outgoing mail to `DEV_EMAIL`. (There is no `EMAIL_DEV_RECIPIENT` — that key does not exist.)

**Fix:**
1. **If it's a reminder email, stop — that's §6.4, a known defect, not a config problem.**
2. Set `EMAIL_MODE = "prod"` in [`backend/config/config.py`](../backend/config/config.py) and **`Restart-Service rfp-api`**. `EMAIL_MODE` and `DEV_EMAIL` are **config-file values**, not System Settings — editing them in the portal will not help.
3. Production recipient lists (`EMAIL_TO_NEW_RFP`, `EMAIL_TO_RFP_REMINDER`, `EMAIL_TO_AUTOMATION_FAILURE`, …) **are** in the `cr673_bahra_system_settings` table (Admin → System Settings), looked up **at send time**. The `config.py` constants for those are only fallbacks for when Dataverse is unreachable.
4. Check the log for Graph `/sendMail` errors — 403 = permission (`Mail.Send` not consented), 401 = token, 400 = bad payload. Check the sender mailbox quota.

### 9.2 A card email arrived but renders as plain HTML

**Cause:** Something rewrote the message body. The card payload lives in a `<script type="application/adaptivecard+json">` block, and **both Power Automate and Graph's JSON `sendMail` strip `<script>` tags**.

**Fix:** [`backend/helpers/email_helper.py`](../backend/helpers/email_helper.py) deliberately builds a **raw MIME message** to survive this. If someone "simplified" it back to JSON `sendMail`, that's the regression. Don't do it.

---

## 10. RBAC / permissions

### 10.1 "Permission denied" right after granting the permission

**Cause:** **`require_permission` reads permissions straight from the session, which is frozen at login.** A grant made five minutes ago has no effect on an existing session. The RBAC cache TTL is a **red herring** for this symptom.

**Fix:** Have the user **log out and log back in**. This is the single most common cause. (A service restart does *not* refresh a live user's session.)

> **Permission denials are not audited** — there is no 403 event to correlate against. You are working from the user's report and the request log only.

### 10.2 A role change broke access for a whole role

**Cause:** **Role-permission rows store the role name denormalized and query by it — renaming a role orphans its permission rows.** Separately, `require_admin` is a **hardcoded check for the literal name `"Admin"`**, bypassing the permission system entirely: renaming the Admin role breaks every admin-only route and `useIsAdmin()` in the frontend.

**Fix:** Rename it back, or re-apply the permission grants under the new name. **Never rename the `Admin` role.**

### 10.3 Menu item is visible but clicking it 403s

**Cause:** Frontend permission checks are **cosmetic**. `useHasPermission` reads a Zustand store that **persists `user.permissions` to localStorage** under `auth-storage` — a user can edit their own permission list and unlock UI. The backend `require_permission` is the real gate, and it is what returned the 403.

**Fix:** The 403 is correct behaviour. Grant the permission properly (then §10.1 — they must re-login), or accept the item is hidden for that role. See the [RBAC Permissions Matrix](03-operations/11-RBAC-Permissions-Matrix.md).

### 10.4 Can't delete or deactivate a role

**Cause:** Expected. `Admin` and `RFP Bidder` are seeded with `is_system: true`; system roles cannot be deleted or toggled (`400` with the reason in `detail`).

**Fix:** Create a new custom role instead. Note `set_role_permissions` **silently drops** any key not defined in [`backend/services/permission_definitions.py`](../backend/services/permission_definitions.py) — if a grant seems to vanish, the key was misspelled.

---

## 11. Deployment & services

### 11.1 `ModuleNotFoundError: No module named 'config'` / `routes` at startup

**Cause:** The backend was launched from the repo root instead of `backend\`. **The working directory MUST be `backend\`** — that's what puts `backend/` on `sys.path` so the top-level imports (`from config.config import ...`) resolve.

**Fix:**
```powershell
cd C:\Bahra-Automation-RFP-System\backend
..\env\Scripts\python.exe dashboard_main.py
```
For the service, fix its working directory in the WinSW XML. The same rule applies to every one-off script.

### 11.2 Downloads / logs appear in the wrong folder

**Cause:** Same root cause as §11.1. `ALLRFPs/`, `LOGS/`, and `logs/` are anchored to **`os.getcwd()`** — launched from the repo root, the app silently writes RFP bundles and failure logs outside `backend\`. **No error is raised; the data just isn't where anyone looks for it.**

**Fix:** Relaunch with the working directory set to `backend\` (§11.1), and move any stray folders back.

### 11.3 Service won't start

**Cause:** Port in use, bad Python path, or a `config.py` syntax error.

**Fix:**
```powershell
netstat -ano | findstr :8000
cd C:\Bahra-Automation-RFP-System\backend
..\env\Scripts\python.exe dashboard_main.py   # run manually to see the traceback
```
Then check the Windows Event Log (Applications → `rfp-api`) and the stdout/stderr paths configured in the WinSW service XML. **Production uses WinSW, not NSSM** — `nssm` commands will not work on this server.

### 11.4 A config change had no effect

**Cause:** **Nothing re-reads `backend/config/config.py` at runtime.**

**Fix:** `Restart-Service rfp-api` (or `net stop rfp-api ; net start rfp-api`). This is a recurring source of confusing failures — see §4.3 for the classic symptom.

### 11.5 `/health` returns 503

**Cause:** The process is up but **Dataverse is unreachable** — `/health` reads one row from the users table, so it's not a bare liveness probe.

**Fix:** Check network/DNS/firewall to `*.dynamics.com`. Then §8.1 — the secret may have expired.

---

## 12. Performance

### 12.1 Dashboard loads slowly on first hit

**Cause:** Cold caches after a restart (settings, RBAC, and master-data caches are all ~300 s / 5 min TTL).

**Fix:** Expected; it warms after the first request. If it persists, profile the query and narrow the date range.

### 12.2 Matching a large BOQ is slow

**Cause:** The keyword path is genuinely O(n·m): for each row's keywords it runs `str.contains` across the master column **and every other object-dtype column** in the master, concatenating and de-duplicating as it goes ([`backend/rfp/download_rfp.py`](../backend/rfp/download_rfp.py), `_find_master_rows_by_keyword`). Master size drives it directly.

**Fix:** There is **no algorithm setting to change** — no `MATCH_ALGORITHM`, no threshold, no alternative matcher exists. The practical levers:
1. **Reduce keyword-path traffic** — every row that matches a 9-digit code on the **exact** tier skips this code entirely. Better Material Master coverage is the real fix, and it fixes §5.2 at the same time.
2. **Prune over-broad Keyword Master rows** (§5.2) — they enlarge the candidate set on every row.

Long-term this needs pre-indexing the master at process start; that work does not exist yet. Don't promise it as a setting.

---

## Adding a new entry

Copy this template and fill in:

```markdown
### N.N <short symptom>

**Cause:** <1-2 lines — point at the file, config key, or command that proves it>

**Fix:** <numbered steps or short paragraph>
```

Keep it terse. If the fix is long, link out to a dedicated page.

**Before you add an entry, verify it against the code.** No thresholds, scores, or settings that don't exist; no service names from a different host; no fixes you haven't run. If you can't verify it, leave it out.

---

## Change history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-04-22 | Manish Soni | Initial troubleshooting FAQ |
| 1.1 | 2026-07-17 | Manish Soni | Verified every entry against code. Removed invented match thresholds, match override, email-ingestion pipeline, and Power Automate shared-secret entries. Corrected prod service to `rfp-api`/WinSW and scheduling to Task Scheduler. Added Playwright service-account browsers, App Proxy callback triage, working-directory and ProactorEventLoop failures, and the two open defects |
