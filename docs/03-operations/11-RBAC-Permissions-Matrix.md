---
title: RBAC Permissions Matrix — Bahra Electric RFP Automation
version: 1.1
last_updated: 2026-07-17
owner: Manish Soni (Manish.soni@dynatechconsultancy.com)
audience: Admins, Security Reviewers, Auditors
status: Draft
---

# RBAC Permissions Matrix

Authoritative reference for all roles, permissions, and access rules in the RFP Automation platform.

**Source of truth:** [services/permission_definitions.py](../../backend/services/permission_definitions.py). If this document conflicts with the code, the code wins — update this document.

**There are exactly 42 permissions** (verified by importing `PERMISSIONS` from the running code, 2026-07-17). Any doc quoting a different number is stale.

---

## 1. Concepts

### 1.1 Permissions

- A **permission** is a string key in the form `module.action` (e.g., `rfp.submit`, `user_management.delete`).
- The full list lives in the `PERMISSIONS` dict in [permission_definitions.py](../../backend/services/permission_definitions.py).
- Permissions are **atomic** — no hierarchy, no inheritance. Granting `role_management.edit` does **not** imply `role_management.view`.

### 1.2 Roles

- A **role** is a named bundle of permissions, stored in `cr673_bahra_roles`.
- Role → permission mappings are stored in `cr673_bahra_role_permissions` (one row per role × permission pair).
- Each **user** has **exactly one role** (`users.role` column; one-to-one, not many-to-many).
- Two **system roles** ship pre-seeded: `Admin` and `RFP Bidder`. System roles cannot be deleted.

> ⚠️ **Role-permission rows store the role name denormalized and are queried by it. Renaming a role orphans its permission rows** — the role survives with zero effective permissions. Delete-and-recreate rather than rename, or re-save the permission set immediately after a rename.

### 1.3 Enforcement — and its four sharp edges

| Layer | Mechanism | Is it a security boundary? |
|---|---|---|
| Backend route guards | `Depends(require_permission("module.action"))` / `require_admin` / `get_current_user` in [middleware/auth.py](../../backend/middleware/auth.py) | **Yes — this is the only real gate** |
| Backend inline checks | `request.session.get("user")` → 401, used across much of `routes/dashboard.py` and parts of `routes/api.py` | Yes (auth only, not permission) |
| Frontend | `useHasPermission("rfp.submit")` in [frontend/src/hooks/use-auth.ts](../../frontend/src/hooks/use-auth.ts) · `<PermissionGuard>` route wrapper | **No — cosmetic only** |

Four behaviours you must know before reasoning about access:

1. **Permission changes require re-login.** `require_permission(key)` checks `key in user["permissions"]`, read **straight from the session**, which is **frozen at login**. Granting or revoking a permission has **no effect on a logged-in user** until they log out and back in. The RBAC cache TTL (§1.4) governs *lookups*, not live sessions — do not confuse them. **A revoke is not effective until the session expires (max 2 h) or the user re-logs.**

2. **`require_admin` bypasses the permission system entirely.** It is a hardcoded check that the user's role **name**, lowercased, equals `"admin"`. It reads no permissions. Consequences:
   - **Renaming the `Admin` role breaks every `require_admin` route**, plus the frontend's `useIsAdmin()` and the Admin delete/toggle guards.
   - A custom role granted all 42 permissions still **fails** `require_admin`, because its name isn't `Admin`.

3. **Frontend checks are cosmetic.** The Zustand auth store **persists `user` — including `permissions` — to `localStorage`** under key `auth-storage`. A user can edit that array in devtools and unlock any UI element. The backend `require_permission` is what actually stops them. Never treat a hidden button as a control.

4. **`set_role_permissions` silently drops unknown keys.** Any key not present in `PERMISSIONS` is discarded without error or warning. A typo in a permission key produces a role that saves "successfully" and is missing that grant.

### 1.4 Caching

Role → permission lookups are cached per-process. Two different knobs, which is worth knowing when they disagree:

| Cache | TTL source |
|---|---|
| Per-role permissions | `get_setting('RBAC_CACHE_TTL_SECONDS', 300)` — configurable in System Settings |
| Roles list | **hardcoded** `_ROLES_CACHE_TTL = 300` — *not* driven by the setting above |

Restart `rfp-api` to force-clear both. Neither clears a user's session snapshot — see §1.3(1).

---

## 2. Permissions catalog (42 total)

Grouped by **backend module namespace** (`MODULE_LABELS`), which is the grouping this document uses throughout.

> **Two groupings exist in the code.** `MODULE_LABELS` (used here) groups by the `module` half of the permission key. `PERMISSION_CATEGORIES` groups by **sidebar layout** for the Roles UI, with different, shorter labels — e.g. it puts `rfp.view` under *Sidebar Menus* and `rfp.submit` under *RFP Operations*, splitting one module across two categories, and it exposes only `system_settings.edit` / `sap_password.change` under their own headings. Both cover all 42 keys. **The check-box layout an admin sees in the Roles page follows `PERMISSION_CATEGORIES`, not the tables below** — the keys are identical, only the visual grouping differs.

### 2.1 User Management (`user_management`)

| Permission | Description |
|---|---|
| `user_management.view` | View user list |
| `user_management.create` | Create new users |
| `user_management.edit` | Edit existing users |
| `user_management.delete` | Delete users |

### 2.2 Role Management (`role_management`)

| Permission | Description |
|---|---|
| `role_management.view` | View roles and permissions |
| `role_management.create` | Create new roles |
| `role_management.edit` | Edit roles and assign permissions |
| `role_management.delete` | Delete roles |

### 2.3 SAP Password (`sap_password`)

| Permission | Description |
|---|---|
| `sap_password.view` | View SAP password logs |
| `sap_password.change` | Change SAP password |

### 2.4 Schedule & Automation (`schedule_automation`)

| Permission | Description |
|---|---|
| `schedule_automation.manage` | Manage automation schedules |

### 2.5 Analytics (`analytics`)

| Permission | Description |
|---|---|
| `analytics.view` | View analytics dashboard |

### 2.6 RFP Operations (`rfp`) — 8 permissions

| Permission | Description |
|---|---|
| `rfp.view` | View RFP insights and details |
| `rfp.download` | Download RFPs from portal |
| `rfp.submit` | Submit RFPs |
| `rfp.decline` | Decline RFPs |
| `rfp.open.view` | View Open RFP reminder tracker page |
| `rfp.open.remind` | Send reminder emails to RFP team members who haven't responded |
| `rfp.open.delegate` | Delegate an RFP product line to a different recipient |
| `rfp.sharepoint.view` | Open the SharePoint folder for an RFP |

> **`rfp` is the only module whose keys are three segments deep** (`rfp.open.view`). The module is still `rfp` — the split is on the first dot only.

### 2.7 Dashboard (`dashboard`)

| Permission | Description |
|---|---|
| `dashboard.view` | View main dashboard |

### 2.8 Logs (`logs`, `audit_logs`)

| Permission | Description |
|---|---|
| `logs.view` | View automation activity logs |
| `audit_logs.view` | View audit trail logs |

### 2.9 Material Insights (`material_insights`)

| Permission | Description |
|---|---|
| `material_insights.view` | View material insights |

### 2.10 Material Master (`material_master`)

| Permission | Description |
|---|---|
| `material_master.view` | View material codes |
| `material_master.create` | Add new material codes |
| `material_master.edit` | Edit material codes |
| `material_master.delete` | Delete material codes |

### 2.11 Keyword Master (`keyword_master`)

| Permission | Description |
|---|---|
| `keyword_master.view` | View keywords |
| `keyword_master.create` | Add new keywords |
| `keyword_master.edit` | Edit keywords |
| `keyword_master.delete` | Delete keywords |

### 2.12 RFP Team (`rfp_team`)

| Permission | Description |
|---|---|
| `rfp_team.view` | View RFP team assignments |
| `rfp_team.create` | Add RFP team members |
| `rfp_team.edit` | Edit RFP team members |
| `rfp_team.delete` | Delete RFP team members |

### 2.13 Column Configuration (`column_config`)

| Permission | Description |
|---|---|
| `column_config.view` | View column configuration |
| `column_config.create` | Add column definitions |
| `column_config.edit` | Edit column definitions |
| `column_config.delete` | Delete column definitions |

### 2.14 System Settings (`system_settings`)

| Permission | Description |
|---|---|
| `system_settings.view` | View system settings and configuration |
| `system_settings.edit` | Edit system settings and configuration |

---

## 3. Default roles

Two roles are seeded by `services.dynamic_role_service.seed_default_roles()`, from the `DEFAULT_ROLES` template in [permission_definitions.py](../../backend/services/permission_definitions.py). Both are `is_system: True`.

```powershell
cd C:\Bahra-Automation-RFP-System\backend
..\env\Scripts\python.exe -c "from services.dynamic_role_service import seed_default_roles; seed_default_roles()"
```

> There is **no `setup_rbac_tables.py`** — that script has been deleted from the tree. The four RBAC tables must already exist; seeding is the command above (or the Roles admin page).

### 3.1 Admin

- **Description:** Full system access — all permissions granted
- **System role:** Yes (cannot be deleted, cannot be toggled inactive)
- **Permissions:** **all 42**, defined as `list(PERMISSIONS.keys())` — **computed dynamically**. Any permission added to the code is automatically in Admin's template on the next seed. Existing Admin rows in Dataverse are **not** retro-granted; re-seed to pick up new keys.
- ⚠️ **Do not rename this role.** `require_admin` is a hardcoded name check (§1.3) — renaming it breaks every admin-only route.

### 3.2 RFP Bidder

- **Description:** Can view and work with RFPs, restricted from admin features
- **System role:** Yes
- **Permissions — exactly 10:**
  - `rfp.view`
  - `rfp.download`
  - `rfp.submit`
  - `rfp.decline`
  - `rfp.open.view`
  - `rfp.open.delegate`
  - `rfp.sharepoint.view`
  - `dashboard.view`
  - `logs.view`
  - `material_insights.view`

**Deliberately absent — do not assume otherwise:**

| Not granted | Consequence |
|---|---|
| `rfp.open.remind` | A Bidder can **see** the Open RFP tracker (`rfp.open.view`) and **delegate** a line, but **cannot send reminder emails**. Chasing is an Admin action |
| `analytics.view` | The Analytics page is inaccessible to Bidders |
| All admin / master-data keys | No user management, roles, master data, settings, audit logs, SAP logs, or schedule access |

---

## 4. Role × Permission grid

`A` = Admin · `B` = RFP Bidder · ✓ = granted · · = not granted

Add columns for custom roles as you create them.

| Permission | A | B |
|---|---|---|
| **User Management** | | |
| `user_management.view` | ✓ | · |
| `user_management.create` | ✓ | · |
| `user_management.edit` | ✓ | · |
| `user_management.delete` | ✓ | · |
| **Role Management** | | |
| `role_management.view` | ✓ | · |
| `role_management.create` | ✓ | · |
| `role_management.edit` | ✓ | · |
| `role_management.delete` | ✓ | · |
| **SAP Password** | | |
| `sap_password.view` | ✓ | · |
| `sap_password.change` | ✓ | · |
| **Schedule & Automation** | | |
| `schedule_automation.manage` | ✓ | · |
| **Analytics** | | |
| `analytics.view` | ✓ | · |
| **RFP Operations** | | |
| `rfp.view` | ✓ | ✓ |
| `rfp.download` | ✓ | ✓ |
| `rfp.submit` | ✓ | ✓ |
| `rfp.decline` | ✓ | ✓ |
| `rfp.open.view` | ✓ | ✓ |
| `rfp.open.remind` | ✓ | **·** |
| `rfp.open.delegate` | ✓ | ✓ |
| `rfp.sharepoint.view` | ✓ | ✓ |
| **Dashboard** | | |
| `dashboard.view` | ✓ | ✓ |
| **Logs** | | |
| `logs.view` | ✓ | ✓ |
| `audit_logs.view` | ✓ | · |
| **Material Insights** | | |
| `material_insights.view` | ✓ | ✓ |
| **Material Master** | | |
| `material_master.view` | ✓ | · |
| `material_master.create` | ✓ | · |
| `material_master.edit` | ✓ | · |
| `material_master.delete` | ✓ | · |
| **Keyword Master** | | |
| `keyword_master.view` | ✓ | · |
| `keyword_master.create` | ✓ | · |
| `keyword_master.edit` | ✓ | · |
| `keyword_master.delete` | ✓ | · |
| **RFP Team** | | |
| `rfp_team.view` | ✓ | · |
| `rfp_team.create` | ✓ | · |
| `rfp_team.edit` | ✓ | · |
| `rfp_team.delete` | ✓ | · |
| **Column Configuration** | | |
| `column_config.view` | ✓ | · |
| `column_config.create` | ✓ | · |
| `column_config.edit` | ✓ | · |
| `column_config.delete` | ✓ | · |
| **System Settings** | | |
| `system_settings.view` | ✓ | · |
| `system_settings.edit` | ✓ | · |

---

## 5. Route → permission map

Every frontend route is wrapped in `<PermissionGuard>` with `fallback={<AccessDenied />}`. From [frontend/src/App.tsx](../../frontend/src/App.tsx):

| Route | Required permission |
|---|---|
| `/dashboard` | `dashboard.view` |
| `/dashboard/rfp-insights` | `rfp.view` |
| `/dashboard/material-insights` | `material_insights.view` |
| `/dashboard/logs` | `logs.view` |
| `/dashboard/open-rfps` | `rfp.open.view` |
| `/dashboard/analytics` | `analytics.view` |
| `/dashboard/profile` | **none** — any authenticated user |
| `/admin/users` | `user_management.view` |
| `/admin/roles` | `role_management.view` |
| `/admin/audit-logs` | `audit_logs.view` |
| `/admin/sap-logs` | `sap_password.view` |
| `/admin/system-settings` | `system_settings.view` |
| `/admin/master-data` | **any of** `material_master.view`, `keyword_master.view`, `rfp_team.view`, `column_config.view` |
| `/login` | unguarded |
| `/` | redirects to `/dashboard` |

> **`PermissionGuard` array semantics are ANY-of, not ALL-of** — it uses `.some()`. `/admin/master-data` opens for a user holding just one of those four.
>
> These guards are **cosmetic** (§1.3(3)). The corresponding backend routes are what actually enforce access.

**Sidebar visibility** follows `PERMISSION_CATEGORIES["sidebar_menus"]` in [permission_definitions.py](../../backend/services/permission_definitions.py), which maps the same permissions to menu items (Dashboard, RFP Insights, Material Insights, Activity Logs, Open RFP, Analytics, SAP Logs, View System Settings, Audit Logs, Schedule & Automation). User Management, Role Management, and Master Data sections appear when the user holds *any* permission in that module.

---

## 6. Creating a custom role

**UI path:** *Role Management → Create Role*

**Required permission:** `role_management.create`

**Fields:**
- **Name** (required, unique, case-insensitive). Cannot be `Admin`.
- **Description** (optional)
- **Permissions** (check-list grouped by category; mirrors §2)
- **Is Active** (default: true)

**Process:**
1. Admin clicks *Create Role*, fills in name + description, checks boxes
2. Frontend posts to `POST /api/roles` → creates row in `cr673_bahra_roles`
3. Then posts to `POST /api/roles/{id}/permissions` → inserts one row per permission in `cr673_bahra_role_permissions`
4. Cache is invalidated for the new role name

**Recommended custom roles** (not pre-seeded, create as needed):

| Role | Permissions (suggested) | Typical user |
|---|---|---|
| **RFP Approver** | `dashboard.view`, `rfp.view`, `rfp.download`, `analytics.view`, `logs.view`, `audit_logs.view`, `material_insights.view` | Procurement manager approving bids |
| **Master Data Steward** | All `material_master.*`, all `keyword_master.*`, `rfp_team.view`, `column_config.view`, `dashboard.view` | Data owner maintaining SAP catalogue |
| **Auditor (read-only)** | `dashboard.view`, `rfp.view`, `logs.view`, `audit_logs.view`, `analytics.view`, `user_management.view`, `role_management.view`, `system_settings.view` | External audit or compliance |
| **Automation Operator** | `dashboard.view`, `rfp.view`, `logs.view`, `schedule_automation.manage`, `sap_password.view` | IT Ops managing schedules |

---

## 7. Assigning a role to a user

**UI path:** *User Management → Edit User → Role dropdown*

**Required permission:** `user_management.edit`

- Exactly one role per user. Changing a role revokes all prior permissions and grants the new set.
- ⚠️ **Role changes take effect only on the user's next login.** The session snapshot is frozen at login (§1.3(1)). Waiting out the RBAC cache does **not** help — that cache governs server-side lookups, not the session. **To make a revoke effective immediately, the user's session must end** (they log out, or the 2-hour cookie expires).
- Setting a user to **inactive** in `cr673_bahra_user_status` blocks **login** — it does **not** terminate an existing session.

---

## 8. Audit policy

Role and permission changes write a row to `cr673_bahra_audit_logs` via [services/audit_service.py](../../backend/services/audit_service.py):

| Column | Value |
|---|---|
| `actor_email` / `actor_name` | The admin performing the change |
| `action` | `ROLE_CREATED` / `ROLE_UPDATED` / `ROLE_DELETED` / `ROLE_PERMISSIONS_UPDATED` / `SEED_ROLES` |
| `category` | `ROLE` (or `USER` for user changes) |
| `target_type` / `target_id` | What was changed |
| `details` | JSON payload — **truncated to 4000 characters** |
| `ip_address` | Source IP of the request |
| `created_date` | Timestamp |

Audit rows are **append-only** — never update or delete them. Retention: indefinite (compliance). See [Security & Compliance §7](12-Security-and-Compliance.md#7-audit-trail).

**Who can read audit logs:** only roles with `audit_logs.view` (Admin by default).

> ⚠️ **Two limits an auditor must know:**
> - **Audit writes are fire-and-forget on a daemon thread**; a failed write only prints, and in-flight writes can be dropped at interpreter exit. **The absence of a row is not proof the action didn't happen.**
> - **Permission denials (403) are not audited.** There is no record of failed authorization attempts.

---

## 9. Access-review workflow

Perform every 6 months, or on change of ownership:

1. Export user list (`/api/users` or Dataverse) → spreadsheet with `name`, `email`, `role`, `is_active`, `last_login`
2. Export role list (`/api/roles`) → spreadsheet with role name and permission count
3. For each active user: business owner confirms the assigned role is still appropriate
4. Deactivate (set `is_active = false`) users who left the organisation
5. Archive the review spreadsheet with the audit logs for the period

---

## 10. Common pitfalls

| Pitfall | Why it happens | Fix |
|---|---|---|
| **New permission granted but the user is still blocked** | **The session is frozen at login** (§1.3(1)) — the most common report by far | **User logs out and back in.** Waiting for the cache does nothing |
| **A revoked user still has access** | Same cause, and it is a **security** issue, not cosmetic | End their session — they log out, or wait out the 2-hour cookie. Deactivating them blocks the *next* login only |
| "Admin" user sees "Permission denied" everywhere | The Admin role was **renamed**. `require_admin` is a hardcoded name check (§1.3(2)), and the rename also **orphaned the role's permission rows** (§1.2) | Rename it back to exactly `Admin`, then re-save its permission set |
| Custom role with all 42 permissions still fails admin routes | `require_admin` checks the role **name**, not permissions | Only a role literally named `Admin` passes. Use `require_permission` routes instead |
| A permission ticked in the UI didn't save | `set_role_permissions` **silently drops keys not in `PERMISSIONS`** (§1.3(4)) — usually a typo introduced in code, not the UI | Compare the key against §2 exactly |
| Hidden button, but the user did the action anyway | Frontend permissions live in **localStorage** and are editable (§1.3(3)) | Confirm the backend route has a `require_permission` dependency. **Note: all 10 automation endpoints have none** |
| Created role but users can't see new menu | Menu is gated by `sidebar_menus`; permission not in their set | Re-check against §5 — **and have them re-login** |
| User can't log in after role delete | Orphaned `users.role` pointing at a deleted role | Re-assign the user to a valid role |
| Duplicate `role_permissions` rows | Two parallel `set_role_permissions` calls | The code deletes-then-inserts; race is rare but possible. Re-run `set_role_permissions` to de-dupe |

---

## 11. Future work (non-breaking)

- **Refresh permissions without re-login** — re-read permissions per request (or version the session) instead of snapshotting at login; today every grant/revoke needs a re-login (§1.3(1))
- **Replace `require_admin` with a permission** — remove the hardcoded role-name check so the Admin role can be renamed safely (§1.3(2))
- **Reject unknown permission keys** — make `set_role_permissions` error instead of silently dropping (§1.3(4))
- **Reference roles by id, not name** — so renaming a role stops orphaning its permission rows (§1.2)
- **Audit permission denials** — no 403 events are recorded today (§8)
- **Multi-role per user** — requires a join table and union semantics in `get_user_permissions`
- **Hierarchical permissions** — e.g., `*.view` implies all view permissions; currently not supported
- **Deny rules** — currently only allow-rules are supported; deny would need a priority field
- **Per-RFP access (ABAC)** — restrict bidders to *their* RFPs; not in scope for v1

---

## 12. Change history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-04-22 | Manish Soni | Initial permissions matrix |
| 1.1 | 2026-07-17 | Manish Soni | Verified against code; App Proxy callback, Task Scheduler migration, prod topology, 42 permissions, corrected security posture |
