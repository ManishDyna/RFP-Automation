---
title: Troubleshooting — Bahra Electric RFP Automation
version: 1.0
last_updated: 2026-04-22
owner: Samir Tak (samir.tak@dynatechconsultancy.com)
audience: Ops, Admins, Developers
status: Living document
---

# Troubleshooting

Growing FAQ of known issues, root causes, and fixes. Add entries as new symptoms are diagnosed.

When you fix an issue that isn't already listed: add it. One entry = one symptom. Keep entries scannable — **Symptom → Likely cause → Fix**.

Related:
- [Operations Runbook §6](03-operations/10-Operations-Runbook.md#6-common-errors-and-how-to-fix-them) — the on-call copy
- [Security & Compliance §9](03-operations/12-Security-and-Compliance.md#9-incident-response) — for security-classed issues
- [Deployment Guide §Troubleshooting](03-operations/09-Deployment-Guide.md) — first-deploy issues

---

## Table of contents

1. [Login & session](#1-login--session)
2. [Dashboard / UI](#2-dashboard--ui)
3. [RFPs](#3-rfps)
4. [Adaptive cards (Outlook)](#4-adaptive-cards-outlook)
5. [Matching engine](#5-matching-engine)
6. [Automation / scheduled jobs](#6-automation--scheduled-jobs)
7. [Playwright / Ariba scraping](#7-playwright--ariba-scraping)
8. [Dataverse](#8-dataverse)
9. [Email sending](#9-email-sending)
10. [Power Automate integration](#10-power-automate-integration)
11. [RBAC / permissions](#11-rbac--permissions)
12. [Deployment & services](#12-deployment--services)
13. [Performance](#13-performance)

---

## 1. Login & session

### 1.1 "Invalid email or password" with known-good credentials

**Cause:** User row exists but is deactivated, or the role was renamed/deleted leaving the user pointing at a non-existent role.

**Fix:**
1. Check `cr673_bahra_user_status.status` for the user — should be `Active`.
2. Verify `users.role` matches an existing `cr673_bahra_roles.name`.
3. Have the user try "Forgot password" to reset cleanly.

### 1.2 Account locks immediately on first attempt

**Cause:** Previous lockout counter wasn't reset after a prior incident.

**Fix:** Admin → User Management → Unlock. Or manually set the lockout fields to null in `user_status`.

### 1.3 "Session expired" every few minutes

**Cause:** `SESSION_SECRET_KEY` rotated recently without redeploying the frontend, or a reverse-proxy drops cookies.

**Fix:** Have all users log out, restart the dashboard, log back in. Verify the reverse proxy forwards the `Cookie` header.

### 1.4 "Forgot password" email never arrives

**Cause:** Shared mailbox unreachable, `Mail.Send` permission not consented, or recipient mailbox full.

**Fix:** Check dashboard logs for `/sendMail` errors. Re-consent the Graph permission if needed. Fall back to Admin → Reset the user's password manually.

---

## 2. Dashboard / UI

### 2.1 Whole UI blank after deploy

**Cause:** Frontend build not copied to `frontend/dist/`, or FastAPI static-mount path wrong.

**Fix:** Inside `frontend/`, run `npm ci && npm run build`. Verify `dist/index.html` exists. Restart dashboard service.

### 2.2 "Network error" in every API call

**Cause:** CORS rejection, or the user hit the server via IP while cookies are bound to hostname.

**Fix:** Use the configured hostname. Check `cors_allowed_origins` in `config/config.py` includes that hostname.

### 2.3 Sidebar missing items that the user should see

**Cause:** Role lacks the permissions that gate those items. Or RBAC cache is stale.

**Fix:** See [RBAC Matrix §5](03-operations/11-RBAC-Permissions-Matrix.md#5-sidebar-visibility-rules). If permissions are correct, restart dashboard to clear cache.

### 2.4 Dashboard KPIs show 0 everywhere

**Cause:** Date filter too narrow, or caching bug, or the user's role has no RFPs in scope.

**Fix:** Clear the date filter. Restart the dashboard (force cache clear). Confirm the user has `dashboard.view` and at least `rfp.view`.

### 2.5 Tables paginate forever / "loading" spinner stuck

**Cause:** OData throttling or backend exception.

**Fix:** Inspect browser devtools → Network → failing request. Usually shows 429 or 500. Fix upstream and retry.

---

## 3. RFPs

### 3.1 RFP appears twice in the list

**Cause:** Duplicate ingestion — same email processed twice, or SP + email both had the attachment.

**Fix:** The newer row wins logically. Admin: delete the older row or mark it `Declined` with reason "duplicate".

### 3.2 RFP stuck in "Processing" for hours

**Cause:** Automation crashed mid-run; orchestrator hasn't retried yet.

**Fix:** Wait for the next scheduled tick, or manually trigger via *Automation → Re-run*. If persistent, check `cr673_bahra_automation_log1` for error details.

### 3.3 Attachments won't download

**Cause:** SharePoint permission drift, expired Graph token, or the original file was deleted.

**Fix:** Re-auth by restarting the dashboard. Check the file still exists in SharePoint. If all else fails, re-ingest the RFP.

### 3.4 BOQ table shows raw field names like `cr673_qty`

**Cause:** Column metadata cache stale after a Dataverse schema change.

**Fix:** Restart the dashboard (reloads metadata cache) or call `/api/system-settings/reload-cache`.

---

## 4. Adaptive cards (Outlook)

### 4.1 Card renders as a plain email with no inputs

**Cause:** Recipient is on a mobile client or webmail that doesn't support actionable messages.

**Fix:** Direct them to use Outlook Web / Desktop, or submit via the portal instead.

### 4.2 Submit button does nothing

**Cause:** Outlook substrate can't reach the callback endpoint.

**Fix:** Verify the public URL is reachable from the internet (not just internal). If hosted behind a firewall, Outlook's substrate IP ranges must be allowed.

### 4.3 Card action fails with "Action not allowed"

**Cause:** Originator ID mismatch — not registered at amdesigner.azurewebsites.net for the sender.

**Fix:** Register the sender email + originator at the actionable-messages portal. See [Deployment Guide §11](03-operations/09-Deployment-Guide.md#11-production-hardening).

### 4.4 Card stale — shows old prices on re-open

**Cause:** Refresh action not firing (expected behaviour in some Outlook versions).

**Fix:** Click refresh manually, or open the RFP in the portal.

---

## 5. Matching engine

### 5.1 Common items not auto-matching

**Cause:** Keyword alias missing or threshold too strict.

**Fix:** Master Data → Keywords → add alias. Or lower `MATCH_THRESHOLD_PCT` in System Settings (default 75).

### 5.2 Wrong material matched

**Cause:** Description tokens coincidentally overlap with a different material's tokens.

**Fix:** Bidder can override in the UI. Admin should add a disambiguating keyword to improve future matches.

### 5.3 Match percentage = 0 on an RFP with clear material codes

**Cause:** BOQ was parsed as images (scanned PDF) and description wasn't extracted.

**Fix:** Re-ingest with a clean Excel / text PDF if possible. Manual override will be needed otherwise.

---

## 6. Automation / scheduled jobs

### 6.1 No runs in `automation_log1` for the last day

**Cause:** Automation service is down, or Power Automate schedule is paused.

**Fix:** `nssm status BahraRFP-Automation`. Check the schedule toggle in the UI. Restart if needed.

### 6.2 Email scan runs but finds nothing

**Cause:** Graph `Mail.Read` permission revoked, or the shared mailbox's inbox rules moved emails elsewhere.

**Fix:** Re-consent the Graph permission. Check Outlook inbox rules for the shared mailbox.

### 6.3 Same RFPs re-ingested every cycle

**Cause:** Deduplication logic isn't marking emails as read.

**Fix:** Inspect the email helper in `helpers/email_helper.py` — the "mark as read" call after successful ingest is the key. Re-test with one email.

---

## 7. Playwright / Ariba scraping

### 7.1 "Browser launch failed"

**Cause:** Chromium not installed or antivirus blocking.

**Fix:** `python -m playwright install chromium`. Whitelist the Playwright folder in EDR.

### 7.2 Scraper logs in then times out

**Cause:** Ariba DOM changed, or cloudflare challenge.

**Fix:** Open `LOGS/<run>/error.png` for the failure state. Update the selector. Consider adding explicit wait + stealth plugin.

### 7.3 Scraper is blocked / captcha

**Cause:** Too many concurrent logins, or IP reputation hit.

**Fix:** Throttle cadence. If persistent, move the automation host to a different IP.

### 7.4 Chromium processes pile up

**Cause:** Playwright context leak — exceptions bypass the `browser.close()` call.

**Fix:** `Get-Process chromium | Stop-Process -Force` then restart the service. Long-term: wrap in `try/finally` (already in code as of v1.0.0; any regressions should be treated as a bug).

---

## 8. Dataverse

### 8.1 `401 Unauthorized` on every call

**Cause:** `CLIENT_SECRET` expired, or Application User removed from environment.

**Fix:** Rotate the secret via Azure Portal; update config; restart services. Verify the Application User still has the correct security role in Power Platform Admin Center.

### 8.2 `404 NotFound` on a table we know exists

**Cause:** EntitySetName mismatch. Dataverse auto-pluralizes with `es` (e.g., `cr673_bahra_roles` → `cr673_bahra_roleses`).

**Fix:** Query `EntityDefinitions(LogicalName='...')?$select=EntitySetName` and update `config/config.py` with the correct API name.

### 8.3 `429 TooManyRequests`

**Cause:** Bulk operation exceeded tenant throttle.

**Fix:** The client retries with backoff. If still failing, reduce batch size. Stagger schedules so runs don't overlap.

### 8.4 Fields return as `null` for rows that clearly have values

**Cause:** Metadata cache has stale display-name → logical-name mapping after a schema change.

**Fix:** Restart the dashboard to rebuild the mapping. Long-term: call `get_column_mapping` with `force_refresh=True` after schema ops.

---

## 9. Email sending

### 9.1 No emails reaching bidders

**Cause:** `EMAIL_MODE` still set to `dev`, all mail going to `EMAIL_DEV_RECIPIENT`.

**Fix:** System Settings → `EMAIL_MODE` → `prod`. Reload cache.

### 9.2 Outbound rejected by tenant policy

**Cause:** Message flagged as phishing / external sender spoofing.

**Fix:** Exchange admin: whitelist the sender or add an SPF/DKIM/DMARC-friendly alias. Avoid suspicious Subject patterns.

### 9.3 429 / throttled by Graph sendMail

**Cause:** Burst of > 10k emails in a short window.

**Fix:** Spread sending; use `batch` endpoint if needed. Graph default limit is ~30 mail/min per user.

---

## 10. Power Automate integration

### 10.1 Schedule change in UI didn't fire Power Automate

**Cause:** HTTP trigger URL wrong, shared HMAC secret mismatch, or PA flow turned off.

**Fix:** Check `POWER_AUTOMATE_SCHEDULE_URL` in system settings. Verify the flow is enabled. Inspect dashboard logs for the sync call's response.

### 10.2 Power Automate calls our endpoint but it returns 401

**Cause:** Shared-secret header missing or rotated.

**Fix:** Update both sides (PA flow and app setting) with the same secret.

---

## 11. RBAC / permissions

### 11.1 User sees "Permission denied" after role change

**Cause:** In-memory cache holds old permissions (300 s TTL) or the session snapshot is stale.

**Fix:** Have the user log out / log back in, or restart the dashboard.

### 11.2 Admin can't edit their own role

**Cause:** Expected behaviour — `Admin` role is protected.

**Fix:** You can't change Admin. If you need a less-powerful admin, create a new role.

### 11.3 Custom role's users can see menu items but get 403 on click

**Cause:** Sidebar-visibility and backend-permission lists diverged.

**Fix:** Each menu item maps to exactly one permission ([RBAC §5](03-operations/11-RBAC-Permissions-Matrix.md#5-sidebar-visibility-rules)). Grant the missing permission or hide the menu item.

---

## 12. Deployment & services

### 12.1 Service won't start

**Cause:** Port already in use, bad Python path, or bad `config.py` syntax.

**Fix:** `netstat -ano | findstr :8000` for port. Run `python dashboard_main.py` manually to see the traceback. Fix and restart.

### 12.2 NSSM shows `SERVICE_STOPPED` after every start

**Cause:** App throws at startup and NSSM thinks it's crashing.

**Fix:** Tail `nssm get BahraRFP-Dashboard AppStderr` path. Most common: missing Python dependency or `config/config.py` error.

### 12.3 `/health` 503 after redeploy

**Cause:** Service is up but Dataverse unreachable (it tests connectivity).

**Fix:** Confirm network → Dataverse. Check firewall / DNS. Rotate the secret if recently invalidated.

---

## 13. Performance

### 13.1 Dashboard loads > 5 s

**Cause:** Cold cache on startup, or a heavy aggregation query.

**Fix:** Cache warms after first request. If persistent, profile the query; consider reducing date range.

### 13.2 Matching a single BOQ takes > 30 s

**Cause:** Material master has 100k+ rows and algorithm is O(n·m).

**Fix:** Switch `MATCH_ALGORITHM` to `rapidfuzz_token_set_ratio` (optimised). Long-term: pre-index the master at process start.

### 13.3 Spinner on every page nav

**Cause:** Session lookup slow — Dataverse RTT too high, or auth token renewal on every request.

**Fix:** Measure with a browser devtools Network timeline. Ensure MSAL token cache is hitting (should renew hourly, not per-request).

---

## Adding a new entry

Copy this template and fill in:

```markdown
### N.N <short symptom in imperative>

**Cause:** <1-2 lines>

**Fix:** <numbered steps or short paragraph>
```

Keep it terse. If the fix is long, link out to a dedicated page.
