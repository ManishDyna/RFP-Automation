---
title: RBAC Permissions Matrix — Bahra Electric RFP Automation
version: 1.0
last_updated: 2026-04-22
owner: Samir Tak (samir.tak@dynatechconsultancy.com)
audience: Admins, Security Reviewers, Auditors
status: Draft
---

# RBAC Permissions Matrix

Authoritative reference for all roles, permissions, and access rules in the RFP Automation platform.

**Source of truth:** [services/permission_definitions.py](../../services/permission_definitions.py). If this document conflicts with the code, the code wins — update this document.

---

## 1. Concepts

### 1.1 Permissions

- A **permission** is a string key in the form `module.action` (e.g., `rfp.submit`, `user_management.delete`).
- The full list lives in the `PERMISSIONS` dict in [permission_definitions.py](../../services/permission_definitions.py).
- Permissions are **atomic** — no hierarchy, no inheritance. Granting `role_management.edit` does **not** imply `role_management.view`.

### 1.2 Roles

- A **role** is a named bundle of permissions, stored in `cr673_bahra_roles`.
- Role → permission mappings are stored in `cr673_bahra_role_permissions` (one row per role × permission pair).
- Each **user** has **exactly one role** (`users.role` column; one-to-one, not many-to-many).
- Two **system roles** ship pre-seeded: `Admin` and `RFP Bidder`. System roles cannot be deleted.

### 1.3 Enforcement

Permissions are enforced at three layers:

| Layer | Mechanism |
|---|---|
| Backend (FastAPI) | `services.dynamic_role_service.user_has_permission(user, perm)` — called from route guards or inline checks |
| Frontend (React) | `useHasPermission("rfp.submit")` hook in [frontend/src/hooks/use-auth.ts](../../frontend/src/hooks/use-auth.ts) — hides/disables UI elements |
| Sidebar visibility | Each menu item declares a permission via `PERMISSION_CATEGORIES["sidebar_menus"]`; items the user lacks are hidden |

> The backend is the security boundary. The frontend uses permissions for UX only — never for security.

### 1.4 Caching

Role → permission lookups are cached per-process for `RBAC_CACHE_TTL_SECONDS` (default **300 s**, configurable via the system settings table). Role changes take up to 5 minutes to fully propagate, or restart the dashboard to force a refresh.

---

## 2. Permissions catalog (42 total)

Grouped by module.

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

### 2.6 RFP Operations (`rfp`)

| Permission | Description |
|---|---|
| `rfp.view` | View RFP insights and details |
| `rfp.download` | Download RFPs from portal |
| `rfp.submit` | Submit RFPs |
| `rfp.decline` | Decline RFPs |

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

Two roles are seeded automatically by `services.dynamic_role_service.seed_default_roles()` (run via `setup_rbac_tables.py` or on first startup).

### 3.1 Admin

- **Description:** Full system access — all permissions granted
- **System role:** Yes (cannot be deleted, cannot be toggled inactive)
- **Permissions:** **all 42** permissions listed above

### 3.2 RFP Bidder

- **Description:** Can view and work with RFPs, restricted from admin features
- **System role:** Yes
- **Permissions (7):**
  - `rfp.view`
  - `rfp.download`
  - `rfp.submit`
  - `rfp.decline`
  - `dashboard.view`
  - `logs.view`
  - `material_insights.view`

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

## 5. Sidebar visibility rules

Each menu item is shown only when the user holds the matching permission. From [permission_definitions.py `PERMISSION_CATEGORIES["sidebar_menus"]`](../../services/permission_definitions.py):

| Menu item | Required permission |
|---|---|
| Dashboard | `dashboard.view` |
| RFP Insights | `rfp.view` |
| Material Insights | `material_insights.view` |
| Activity Logs | `logs.view` |
| Analytics | `analytics.view` |
| SAP Logs | `sap_password.view` |
| View System Settings | `system_settings.view` |
| Audit Logs | `audit_logs.view` |
| Schedule & Automation | `schedule_automation.manage` |

User Management, Role Management, and Master Data sections are shown when the user holds *any* permission in that module.

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
- Role changes are effective after the RBAC cache expires (≤ 300 s) or on the user's next session refresh (logout/login).
- Setting a user to **inactive** in `cr673_bahra_user_status` blocks login regardless of role.

---

## 8. Audit policy

Every role or permission change writes a row to `cr673_bahra_audit_logs` with:

| Column | Value |
|---|---|
| `user_name` | The admin performing the change |
| `action` | `ROLE_CREATED` / `ROLE_UPDATED` / `ROLE_DELETED` / `ROLE_PERMISSIONS_CHANGED` / `USER_ROLE_ASSIGNED` |
| `module` | `role_management` or `user_management` |
| `details` | JSON payload — `{"role_name":"Auditor","before":[...],"after":[...]}` |
| `ip_address` | Source IP of the request |
| `created_date` | UTC timestamp |

Audit rows are **append-only** — never update or delete them. Retention: indefinite (compliance). See [Security & Compliance](12-Security-and-Compliance.md) §Audit.

**Who can read audit logs:** only roles with `audit_logs.view` (Admin by default).

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
| "Admin" user sees "Permission denied" | Admin role was renamed, or user's row has a blank role | Ensure role name is exactly `Admin` and user row has `role = Admin` |
| New permission granted but UI still blocks | RBAC cache not yet expired | Wait 5 min or restart dashboard |
| User can't log in after role delete | Orphaned `users.role` pointing at deleted role | Re-assign the user to a valid role |
| Created role but users can't see new menu | Menu is gated by `sidebar_menus` mapping; permission not in their set | Re-check the permission list against §5 |
| Duplicate `role_permissions` rows | Two parallel `set_role_permissions` calls | The code deletes-then-inserts; race is rare but possible. Re-run `set_role_permissions` to de-dupe |

---

## 11. Future work (non-breaking)

- **Multi-role per user** — requires a join table (`cr673_bahra_user_roles`) and union semantics in `get_user_permissions`
- **Hierarchical permissions** — e.g., `*.view` implies all view permissions; currently not supported
- **Deny rules** — currently only allow-rules are supported; deny would need a priority field
- **Per-RFP access (ABAC)** — restrict bidders to *their* RFPs; not in scope for v1
