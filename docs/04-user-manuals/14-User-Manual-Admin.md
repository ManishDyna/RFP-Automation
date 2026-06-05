---
title: User Manual — Admin
version: 1.0
last_updated: 2026-04-22
owner: Samir Tak (samir.tak@dynatechconsultancy.com)
audience: System Admins
status: Draft
---

# User Manual — Admin

You have full access to the RFP Automation Portal. This manual walks you through every admin task in the order you'll typically do them.

**Tech-deep tasks** (deploying, troubleshooting internals, security hardening) live in:
- [Deployment Guide](../03-operations/09-Deployment-Guide.md)
- [Operations Runbook](../03-operations/10-Operations-Runbook.md)
- [RBAC Permissions Matrix](../03-operations/11-RBAC-Permissions-Matrix.md)
- [Security & Compliance](../03-operations/12-Security-and-Compliance.md)

---

## 1. First login

Log in with the Admin credentials provided during deployment. **Change the password immediately.** Click your avatar → **Profile** → **Change password**.

Verify you can see the full sidebar:

- Dashboard
- RFP Insights
- Material Insights
- Activity Logs
- Analytics
- SAP Logs
- View System Settings
- Audit Logs
- Schedule & Automation
- User Management
- Role Management
- Master Data (expanded)

Any missing item means your role isn't `Admin` — contact the system owner.

---

## 2. User management

### 2.1 Creating a user

1. Sidebar → **User Management** → **Create User**.
2. Fill: email, name, phone (optional), **role**, initial password.
3. Click **Save**.

Tell the new user to log in and change their password.

### 2.2 Editing / deactivating a user

1. User Management → click a row → **Edit**.
2. Change the role or other details.
3. Or click **Deactivate** — the user can no longer log in but their audit history is preserved.

Deactivation is reversible. Use **Delete** only when you're certain the user will never return (keeps audit clean for compliance).

### 2.3 Unlocking an account

After 5 failed logins in 15 minutes, an account locks.

1. User Management → click the user.
2. Click **Unlock**.

### 2.4 Forgot-password resets

Users can self-service via the login page's *Forgot password*. If a user never receives the email, verify:

- Email is correct
- The shared mailbox is healthy
- No spam-filter rule blocks messages from the portal sender

---

## 3. Roles & permissions

### 3.1 Understanding roles

Two roles are pre-seeded:
- **Admin** — all permissions
- **RFP Bidder** — can view and respond to RFPs

You will often need custom roles. See [RBAC Matrix §6](../03-operations/11-RBAC-Permissions-Matrix.md#6-creating-a-custom-role) for suggested roles like Approver, Master Data Steward, Auditor.

### 3.2 Creating a role

1. Sidebar → **Role Management** → **Create Role**.
2. Enter **Name** (unique) and **Description**.
3. Check the permission boxes — they are grouped into Sidebar Menus, RFP Operations, User Management, Role Management, Master Data, System Settings, and SAP Password.
4. Click **Save**.

Any user assigned this role gets the permissions on their next login (or after ≤ 5 minutes).

### 3.3 Editing a role

1. Role Management → click the role → **Edit**.
2. Change name or check/uncheck permissions.
3. Save.

Users with this role get the new permissions on next session refresh.

### 3.4 Deleting a role

**Soft delete** (recommended): click **Deactivate**. The role is hidden and no new users can be assigned. Users already on it keep it until you move them.

**Hard delete**: click **Permanent delete**. This removes the role and all its permission mappings. Users assigned to it become permissionless until reassigned.

Neither works for `Admin` — it is protected.

### 3.5 Assigning a role

Done at user level: User Management → Edit user → change the **Role** dropdown → Save.

---

## 4. Master data

Open the **Master Data** section in the sidebar — it has four tabs.

### 4.1 Material Master

The SAP material catalogue used for auto-matching.

- **Add:** click **Add material** → enter code, description, keywords, active flag.
- **Edit:** click a row → modify → Save.
- **Delete:** click a row → **Delete**.
- **Bulk import:** click **Import** → upload a CSV or XLSX with columns `code, description, keywords, is_active`.

Keep this list as close to SAP as possible. A weekly sync from SAP is recommended.

### 4.2 Keyword Master

Aliases that help the matching engine understand non-standard terms.

Example row: `term = XLPE`, `expands_to = cross linked polyethylene, XLPE, X-LPE`.

Add a keyword whenever bidders complain that a common item isn't auto-matching.

### 4.3 RFP Team

The list of internal bidders and the customers/materials they handle. Used by the assignment engine.

Fields: name, email, assignment-type (by customer, by material category, or manual).

### 4.4 Column Configuration

Controls the **response form** fields that bidders fill in.

- Add / remove / reorder fields
- Set field type (text, number, date, dropdown, boolean)
- Mark required
- Provide dropdown options (comma-separated)

Changing the column config updates the form for **future** RFPs; existing RFPs retain the columns they were created with (schema captured per RFP — check with dev team if you need to retrofit).

---

## 5. System settings

Sidebar → **View System Settings**.

| Common setting | Typical value | Why you'd change it |
|---|---|---|
| `MATCH_THRESHOLD_PCT` | 75 | Raise for stricter matching; lower if too many rows go unmatched |
| `REMINDER_DAILY_TIME` | 09:00 | Shift the reminder send hour |
| `EMAIL_MODE` | `prod` | Switch to `dev` when testing — all mail routes to `EMAIL_DEV_RECIPIENT` |
| `RBAC_CACHE_TTL_SECONDS` | 300 | Shorten for faster permission propagation (at cost of DB load) |
| `FAILURE_LOGS_DIR` | `C:\python\RFP-automation\LOGS` | Change only with dev guidance |

**Editing:** click the row → change value → Save.

**Sensitive values** (passwords, secrets) show as `***`. Click **Reveal** to view; the reveal is audited.

After any change, click **Reload cache** to apply immediately (otherwise it takes up to 5 minutes).

---

## 6. Schedule & Automation

Sidebar → **Schedule & Automation**.

You see the current schedule for each automation job (email scan, SharePoint, Ariba, match-notify, reminder, cleanup).

To change:
1. Click **Edit** next to a job.
2. Adjust the cron-like fields (interval, time, days of week).
3. Save. The change is pushed to Power Automate.

To pause a job, set its **Active** toggle off.

**Warning:** disabling all schedules means *nothing* happens automatically. Bidders won't get reminders; new emails won't be pulled.

---

## 7. SAP password

Sidebar → **SAP Logs** (visible because you have `sap_password.view` + `sap_password.change`).

- **View logs** — each past password change with user, timestamp, and outcome.
- **Change password** — click **Change password**, enter new password twice, confirm.

The system pushes the new password to SAP via the configured connector. A failure shows an error; if so, the old password is retained.

Rotate per your organisation's SAP Basis policy (typically every 90 days).

---

## 8. Audit logs

Sidebar → **Audit Logs**.

Every state-changing action is here. Filter by:

- **User** — see what one person did
- **Module** — user_management, role_management, rfp, system_settings, etc.
- **Action** — LOGIN_FAILURE, ROLE_UPDATED, RFP_SUBMITTED, etc.
- **Date range**

Click a row to see the JSON **details** — typically includes the before/after values of the change.

**Export** as XLSX for quarterly reviews.

**Do not delete audit rows.** The portal does not expose a delete; if anyone requests it, escalate to the system owner + Legal.

---

## 9. Dashboards for monitoring

Keep these bookmarked:

- **Dashboard** — RFP volume and status KPIs
- **Material Insights** — which materials come up most
- **Activity Logs** — recent system actions (not security events; that's audit)
- **SAP Logs** — password-change history

Watch for:

- Sudden drops in RFP ingestion (scraper broken?)
- Spike in `LOGIN_FAILURE` in audit logs (brute force?)
- Spike in `ACTIONABLE_REJECTED` (spoofed cards?)

If anything looks odd, see the [Operations Runbook](../03-operations/10-Operations-Runbook.md).

---

## 10. End-user support

Common questions you'll get:

| Question | Answer / Fix |
|---|---|
| "I can't log in" | Unlock account (§2.3) · verify role is active |
| "I don't see the RFP" | Check date filter · check RBAC role has `rfp.view` · check the RFP's bidder assignment row in `rfp_team` |
| "The match is wrong" | Add / edit a keyword (§4.2) · ask the bidder to override manually |
| "Reminder emails keep coming" | User didn't submit or decline; they need to respond |
| "Card in Outlook doesn't work" | Ask them to submit via the portal; note it for dev |
| "I want a new response field" | Add it in Column Configuration (§4.4) |

For anything you can't resolve in 5 minutes, escalate to the system owner (see [Operations Runbook §13](../03-operations/10-Operations-Runbook.md#13-contacts)).

---

## 11. Onboarding a new bidder — end-to-end checklist

- [ ] Create user in User Management with role `RFP Bidder` (or a custom role)
- [ ] Add a row in Master Data → RFP Team with their email and assignment rules
- [ ] Share the portal URL and the [Quick Start Guide](16-Quick-Start-Guide.md)
- [ ] Send the [Bidder User Manual](13-User-Manual-Bidder.md) (or `.docx`)
- [ ] Verify they can log in and see at least one sample RFP
- [ ] Verify they receive adaptive-card emails (or test with a dev RFP first)

---

## 12. Offboarding a user

- [ ] Deactivate in User Management (don't delete — preserves audit)
- [ ] Remove/replace their entry in Master Data → RFP Team (reassign open RFPs to a teammate)
- [ ] Check Audit Logs for recent sensitive actions
- [ ] Rotate any shared credentials the user knew (if applicable)

---

## 13. Quarterly admin checklist

Once a quarter:

- [ ] Run an access review — export User list, verify roles still make sense
- [ ] Export 90-day Audit Logs to archive
- [ ] Verify SAP password was rotated in the last 90 days
- [ ] Check that `EMAIL_MODE` is still `prod` in System Settings
- [ ] Check that `LOGS/` folder isn't bloated (see Operations Runbook §10)
- [ ] Confirm the `CLIENT_SECRET` isn't expiring in the next 60 days (Azure Portal)

---

## 14. When something is wrong

1. **Don't panic.** Almost nothing is irreversible.
2. Check the [Operations Runbook §6 common errors](../03-operations/10-Operations-Runbook.md#6-common-errors-and-how-to-fix-them).
3. If a service is down → restart it via NSSM or Services.
4. If data looks wrong → check audit logs first — usually it was a user action, not a bug.
5. If a security incident is suspected → follow the [Security & Compliance §9 playbook](../03-operations/12-Security-and-Compliance.md#9-incident-response).
6. If stuck, contact the system owner.
