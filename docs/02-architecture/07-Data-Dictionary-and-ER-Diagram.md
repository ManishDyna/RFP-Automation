---
title: Data Dictionary & ER Diagram — Bahra Electric RFP Automation
version: 1.0
last_updated: 2026-04-22
owner: Samir Tak (samir.tak@dynatechconsultancy.com)
status: Draft
audience: Developers, DBAs, Data Analysts, Integration Engineers
---

# Data Dictionary & ER Diagram

> **Purpose.** Authoritative description of every Dataverse table the RFP Automation system reads or writes.
> **Pair with:** [SAD §9](04-SAD-Software-Architecture-Document.md) for the cluster overview · [Glossary](../01-business/03-Glossary-and-Acronyms.md) for terminology · [API Documentation](08-API-Documentation.md) for endpoints.

---

## 1. Reading this document

### 1.1 Schema conventions

| Concept | Convention |
|---------|------------|
| **Publisher prefix** | All custom tables use `cr673_` (one row of `cr6db_cr673_*` is also present — see §5.10) |
| **Logical name** | Used in Dataverse metadata, e.g. `cr673_bahra_roles` |
| **EntitySetName (API name)** | OData CRUD path. Dataverse pluralizes by appending **`es`** (e.g., `cr673_bahra_roleses`). Always confirm via `EntityDefinitions(LogicalName='...')?$select=EntitySetName`. |
| **Primary key** | Dataverse auto-creates `<logicalname>id` (GUID) for every table — not listed in column tables below |
| **Primary name** | The "label" column (e.g., `cr673_name`); flagged in column tables |
| **Display name vs logical name** | Code uses `use_display_names=True` → reads/writes go through `helpers/dataverse_helper.py::get_column_mapping()` which translates display→logical |
| **All custom columns are strings** | The schema uses `String` or `Memo` types only. Booleans are stored as `"true"` / `"false"`; dates as `"M/D/YYYY h:MM AM/PM"` (no leading zeros) or ISO 8601; JSON as serialized text in Memo columns |

### 1.2 Date formats

| Format | Example | Used by |
|--------|---------|---------|
| MDY display | `4/22/2026 8:10 PM` | Most date columns; matches portal display |
| ISO 8601 | `2026-04-22T20:10:00Z` | `RFP_End_Date` after `normalize_date_format()`; `created_date` from Dataverse system fields |

### 1.3 Source-of-truth for column definitions

| Source | Tables defined |
|--------|----------------|
| [Support-Files/setup_rbac_tables.py](../../Support-Files/setup_rbac_tables.py) | `cr673_bahra_roles`, `cr673_bahra_role_permissions`, `cr673_bahra_audit_logs`, `cr673_bahra_user_status` |
| [Support-Files/setup_master_data_tables.py](../../Support-Files/setup_master_data_tables.py) | `cr673_bahra_material_master`, `cr673_bahra_keywords`, `cr673_bahra_rfp_team` |
| [Support-Files/setup_dynamic_columns_table.py](../../Support-Files/setup_dynamic_columns_table.py) | `cr673_bahra_rfp_team_columns` (+ `extra_data` on rfp_team, `response_data` on rfp_response) |
| [Support-Files/setup_rfps_v2_table.py](../../Support-Files/setup_rfps_v2_table.py) + [setup_rfp_activity_columns.py](../../Support-Files/setup_rfp_activity_columns.py) | `cr673_bahra_rfps_v2` |
| [Support-Files/seed_system_settings.py](../../Support-Files/seed_system_settings.py) | `cr673_bahra_system_settings` (rows seeded; columns inferred from seed payloads) |
| Inferred from service code | `cr673_bahra_users`, `cr673_bahra_sap_infomation`, `cr673_bahra_automation_log1`, `cr673_bahra_automation_schedules`, `cr673_bhara_rfp_status`, `cr6db_cr673_bahra_rfp_response` |

> **⚠ Inferred tables** (six of the sixteen) were created outside the setup scripts in this repo. Their columns below are reconstructed from the read/write call sites. **Validate against the live environment before relying on these definitions for migrations.**

---

## 2. ER Diagram (Logical)

Most "relationships" are **logical, not enforced** — Dataverse foreign keys are implemented as plain string columns holding the related row's GUID or a natural key (e.g., `RFP_ID`). The diagram shows the intent.

```mermaid
%%{init: {'theme':'neutral'}}%%
erDiagram
    USERS ||--o| USER_STATUS : "1:1 lifecycle"
    USERS }o--|| ROLES : "role (logical FK)"
    ROLES ||--o{ ROLE_PERMISSIONS : "has many"
    USERS ||--o{ AUDIT_LOGS : "actor_email"
    USERS ||--o{ SAP_PASSWORD : "user_email"

    RFPS_V2 ||--o{ RFP_RESPONSE : "rfp_id"
    RFPS_V2 ||--o{ AUTOMATION_LOG1 : "RFP_ID"
    RFP_STATUS ||--o{ RFPS_V2 : "participated (lookup)"
    RFP_TEAM ||--o{ RFP_RESPONSE : "product → bidder routing"
    RFP_TEAM_COLUMNS ||--o{ RFP_TEAM : "column definitions"
    RFP_TEAM_COLUMNS ||--o{ RFP_RESPONSE : "column definitions"

    MATERIAL_MASTER ||--o{ KEYWORDS : "matching pair"
    MATERIAL_MASTER ||--o{ RFPS_V2 : "Matched_Data JSON"
    KEYWORDS ||--o{ RFPS_V2 : "Matched_Data JSON"

    AUTOMATION_SCHEDULES ||--o{ AUTOMATION_LOG1 : "triggers runs"

    SYSTEM_SETTINGS {
        string Key PK
        string Value
    }

    USERS {
        string email PK_natural
        string name
        string role
        string password "bcrypt"
    }

    USER_STATUS {
        string user_id FK
        string is_active
        string failed_attempts
        string locked_until
        string last_login
        string password_changed_at
    }

    ROLES {
        string name PK_natural
        string description
        string is_system
        string is_active
    }

    ROLE_PERMISSIONS {
        string role_id FK
        string role_name
        string permission_key
    }

    AUDIT_LOGS {
        string action
        string category
        string actor_email
        string target_type
        string target_id
        string ip_address
    }

    RFPS_V2 {
        string RunID
        string RFP_ID PK_natural
        string Company_Name
        string RFP_End_Date
        string participated FK
        string Matched_Data "JSON"
        string Email_Status
        string Downloaded_At
    }

    RFP_RESPONSE {
        string rfp_id FK
        string product FK
        string bidder_email
        string response_data "JSON"
    }

    RFP_TEAM {
        string product PK_natural
        string name
        string email
        string extra_data "JSON dynamic columns"
    }

    RFP_TEAM_COLUMNS {
        string column_key PK_natural
        string column_label
        string column_type
        string column_category
        string sort_order
    }

    MATERIAL_MASTER {
        string material_code PK_natural
        string description
        string is_active
    }

    KEYWORDS {
        string keyword PK_natural
        string is_active
    }

    AUTOMATION_LOG1 {
        string RunID
        string Timestamp
        string Category
        string Action
        string automation_status
        string Message
        string RFP_ID FK
    }

    AUTOMATION_SCHEDULES {
        string frequency
        string interval
        string start_time
        string timezone
        string enabled
    }

    SAP_PASSWORD {
        string password "encrypted"
        string user_email FK
        string username
        string created_date
    }

    RFP_STATUS {
        string status_code PK_natural
        string display_label
    }
```

---

## 3. Table catalog (overview)

| # | Logical name | API name (`EntitySetName`) | Cluster | Purpose | Source |
|---|--------------|----------------------------|---------|---------|--------|
| 1 | `cr673_bahra_rfps_v2` | `cr673_bahra_rfps_v2s` | RFP lifecycle | One row per discovered RFP — full lifecycle state (download → match → email → response) | setup_rfps_v2_table.py |
| 2 | `cr6db_cr673_bahra_rfp_response` | `cr6db_cr673_bahra_rfp_responses` | RFP lifecycle | Bidder responses captured from Adaptive Card emails | inferred + setup_dynamic_columns_table.py |
| 3 | `cr673_bhara_rfp_status` | `cr673_bhara_rfp_statuses` | RFP lifecycle | Lookup table for valid RFP participation statuses | inferred |
| 4 | `cr673_bahra_users` | `cr673_bahra_userses` | Identity | Portal user accounts | inferred |
| 5 | `cr673_bahra_roles` | `cr673_bahra_roleses` | Identity | Dynamic RBAC role definitions | setup_rbac_tables.py |
| 6 | `cr673_bahra_role_permissions` | `cr673_bahra_role_permissionses` | Identity | Maps roles → permission keys (many-to-one logical FK) | setup_rbac_tables.py |
| 7 | `cr673_bahra_user_status` | `cr673_bahra_user_statuses` | Identity | Per-user lifecycle: active flag, lockout state, last login, password expiry | setup_rbac_tables.py |
| 8 | `cr673_bahra_audit_logs` | `cr673_bahra_audit_logses` | Identity | Append-only audit trail for privileged actions | setup_rbac_tables.py |
| 9 | `cr673_bahra_material_master` | `cr673_bahra_material_masters` | Master data | Source-of-truth material codes for matching | setup_master_data_tables.py |
| 10 | `cr673_bahra_keywords` | `cr673_bahra_keywordses` | Master data | Match-keywords for fuzzy/keyword matching | setup_master_data_tables.py |
| 11 | `cr673_bahra_rfp_team` | `cr673_bahra_rfp_teams` | Master data | Maps product → team member email for routing | setup_master_data_tables.py |
| 12 | `cr673_bahra_rfp_team_columns` | `cr673_bahra_rfp_team_columnses` | Master data | Dynamic column definitions for the rfp_team table + Adaptive Card | setup_dynamic_columns_table.py |
| 13 | `cr673_bahra_automation_log1` | `cr673_bahra_automation_log1s` | Operations | Per-step automation event log (every category × action) | inferred from log_events.py |
| 14 | `cr673_bahra_automation_schedules` | `cr673_bahra_automation_scheduleses` | Operations | Mirror of the active Power Automate Recurrence schedule | inferred |
| 15 | `cr673_bahra_sap_infomation` | `cr673_bahra_sap_infomations` | Integration | Audit / rotation log of SAP password changes | inferred |
| 16 | `cr673_bahra_system_settings` | `cr673_bahra_system_settingses` | Integration | Runtime-mutable settings (email recipients, etc.) | seed_system_settings.py |

---

## 4. Cluster — RFP lifecycle

### 4.1 `cr673_bahra_rfps_v2` — RFP activity log

> Definitive source of truth for one RFP. The `Matched_Data` column holds a JSON document with all material match results so analytics can be reconstructed from this single row.

| # | Logical name | Display | Type | Length | Key | Notes |
|---|--------------|---------|------|--------|-----|-------|
| 1 | `cr673_RunID` | RunID | String | 200 | **Primary Name** | Automation run UUID (`uuid.uuid4()`) |
| 2 | `cr673_RFP_ID` | RFP_ID | String | 500 | Natural key | Vendor-portal RFP identifier (e.g., `Doc12345`) |
| 3 | `cr673_Company_Name` | Company_Name | String | 200 | | "Saudi Electricity Company", "Aramco e-Marketplace", etc. |
| 4 | `cr673_RFP_End_Date` | RFP_End_Date | String | 200 | | ISO 8601 after `normalize_date_format()` |
| 5 | `cr673_owner_name` | owner_name | String | 200 | | RFP owner / buyer from portal |
| 6 | `cr673_publish_time` | publish_time | String | 200 | | When RFP was published on portal |
| 7 | `cr673_participated` | participated | String | 50 | FK → rfp_status | One of `no` · `saved_draft` · `submitted` · `declined` |
| 8 | `cr673_Link` | Link | String | 2000 | | Direct URL into Ariba |
| 9 | `cr673_Matched_Data` | Matched_Data | Memo | 1,048,576 | | Categorized JSON: `{exact_matches, keyword_matches, not_matched, summary}` |
| 10 | `cr673_Email_Status` | Email_Status | String | 200 | | "sent" / "failed" / specific error tag |
| 11 | `cr673_Email_To` | Email_To | String | 500 | | Semicolon-separated recipients |
| 12 | `cr673_Email_Sent_At` | Email_Sent_At | String | 200 | | MDY datetime |
| 13 | `cr673_Downloaded_At` | Downloaded_At | String | 200 | | MDY datetime; presence here triggers dedup logic |
| 14 | `cr673_Reminder_1Day_Sent` | Reminder_1Day_Sent | String | 10 | | "true" / "false" |
| 15 | `cr673_Reminder_3Day_Sent` | Reminder_3Day_Sent | String | 10 | | "true" / "false" |
| 16 | `cr673_response_count` | response_count | String | 50 | | Number of team members who have responded |
| 17 | `cr673_first_response_at` | first_response_at | String | 200 | | MDY datetime of first bidder response |
| 18 | `cr673_all_responses_at` | all_responses_at | String | 200 | | MDY datetime when last expected response landed |
| 19 | `cr673_rfp_type` | rfp_type | String | 200 | | Portal event type: RFQ, RFP, Tender, etc. |

**Analytics columns** added by [setup_rfp_activity_columns.py](../../Support-Files/setup_rfp_activity_columns.py): `rfp_type`, `total_line_items`, `match_rate_pct`, `exact_match_count`, `keyword_match_count`, `file_size_bytes`, `first_response_at`, `all_responses_at`, `response_count`. (Some duplicate the columns above — confirm against live schema.)

**Upsert key.** Code in [core/log_events.py](../../core/log_events.py) `log_rfp_activity()` uses `RFP_ID eq '<id>'` for dedup. If a row with `Downloaded_At` set is found, only "meaningful" updates (participation change, email status change, missing owner_name, etc.) are applied.

**Indexes.** Recommend a Dataverse alternate key on `cr673_RFP_ID` to enforce uniqueness; today the code does this in software.

---

### 4.2 `cr6db_cr673_bahra_rfp_response` — Bidder responses

> One row per (RFP × bidder) capturing everything the bidder submitted via the Adaptive Card. The cross-publisher `cr6db_` prefix indicates this table was created in a different solution/publisher and later joined into the RFP solution.

| # | Logical name | Display | Type | Length | Notes |
|---|--------------|---------|------|--------|-------|
| 1 | *(primary name)* | name / id | String | 200 | Synthetic identifier — typically `<rfp_id>_<email>` |
| 2 | `cr673_rfp_id` | rfp_id | String | 500 | Logical FK → `rfps_v2.RFP_ID` |
| 3 | `cr673_bidder_email` | bidder_email | String | 300 | Email of the responding bidder (matched against rfp_team) |
| 4 | `cr673_submitted_at` | submitted_at | String | 200 | MDY datetime |
| 5 | `cr673_response_data` | response_data | Memo | 4000 | JSON: `{products: [{product, results, remarks}]}` for grouped multi-product submissions; legacy single-product responses live at the top level |

**Inferred from** [routes/actionable_cards.py](../../routes/actionable_cards.py) `_get_all_responses_for_rfp()`. Confirm exact column names against live env.

**Why JSON in response_data?** RFP team columns are dynamic (see §6.2). A schema migration would be needed every time the team adds a new input field. Storing `{key: value}` JSON keeps the table stable.

---

### 4.3 `cr673_bhara_rfp_status` — Status lookup

> Tiny lookup table (4 rows) that mirrors `VALID_RFP_STATUSES` in `config/config.py`. Exists primarily so that Power Apps / Power BI can show friendly labels.

| # | Logical name | Display | Type | Length | Notes |
|---|--------------|---------|------|--------|-------|
| 1 | `cr673_status_code` | status_code | String | 50 | One of `no` · `saved_draft` · `submitted` · `declined` |
| 2 | `cr673_display_label` | display_label | String | 100 | "Not yet participated", "Draft saved", etc. |

> **Note the typo** in the schema name: `bhara` (no `a`), not `bahra`. This is preserved in code and config.

---

## 5. Cluster — Identity

### 5.1 `cr673_bahra_users` — Portal users

| # | Logical name | Display | Type | Length | Notes |
|---|--------------|---------|------|--------|-------|
| 1 | `cr673_email` | email | String | 300 | Natural login key |
| 2 | `cr673_name` | name | String | 200 | Display name |
| 3 | `cr673_role` | role | String | 200 | Role name (FK to `roles.name`) — string lookup, not GUID |
| 4 | `cr673_password` | password | String | 200 | bcrypt hash |
| 5 | `cr673_created_date` | created_date | String | 100 | MDY datetime |
| 6 | `cr673_update_date` | update_date | String | 100 | MDY datetime |

**DISPLAY_COLUMNS** in [services/user_service.py](../../services/user_service.py): `created_date, email, name, role, password, update_date`.

---

### 5.2 `cr673_bahra_roles` — Dynamic roles

| # | Logical name | Display | Type | Length | Key | Notes |
|---|--------------|---------|------|--------|-----|-------|
| 1 | `cr673_name` | name | String | 200 | **Primary Name** | Role name (e.g., "Admin", "RFP Bidder") — used as natural key |
| 2 | `cr673_description` | description | String | 500 | | Human-readable role description |
| 3 | `cr673_is_system` | is_system | String | 10 | | `"true"` for built-in (Admin, RFP Bidder) — cannot be deleted |
| 4 | `cr673_is_active` | is_active | String | 10 | | `"true"` / `"false"` |
| 5 | `cr673_created_date` | created_date | String | 100 | | MDY datetime |
| 6 | `cr673_update_date` | update_date | String | 100 | | MDY datetime |

**Default rows** (seeded by [services/dynamic_role_service.py](../../services/dynamic_role_service.py) `seed_default_roles()`): `Admin` (41 perms), `RFP Bidder` (7 perms).

---

### 5.3 `cr673_bahra_role_permissions` — Role × permission mapping

> Many-to-one. One row per (role, permission_key) pair. `permission_key` matches one of the 41 keys in [services/permission_definitions.py](../../services/permission_definitions.py).

| # | Logical name | Display | Type | Length | Notes |
|---|--------------|---------|------|--------|-------|
| 1 | `cr673_name` | name | String | 200 | **Primary Name** — typically `<role_name>::<permission_key>` |
| 2 | `cr673_role_id` | role_id | String | 100 | GUID → `roles` |
| 3 | `cr673_role_name` | role_name | String | 200 | Denormalized for display |
| 4 | `cr673_permission_key` | permission_key | String | 200 | e.g., `rfp.submit` |
| 5 | `cr673_created_date` | created_date | String | 100 | MDY datetime |

---

### 5.4 `cr673_bahra_user_status` — User lifecycle

> 1:1 with `users` (logical, not enforced).

| # | Logical name | Display | Type | Length | Notes |
|---|--------------|---------|------|--------|-------|
| 1 | `cr673_name` | name | String | 200 | **Primary Name** — usually the user email |
| 2 | `cr673_user_id` | user_id | String | 100 | GUID → `users` |
| 3 | `cr673_is_active` | is_active | String | 10 | `"true"` blocks login when `"false"` |
| 4 | `cr673_failed_attempts` | failed_attempts | String | 10 | Resets on successful login |
| 5 | `cr673_locked_until` | locked_until | String | 100 | MDY datetime; if in the future, login blocked |
| 6 | `cr673_last_login` | last_login | String | 100 | MDY datetime |
| 7 | `cr673_password_changed_at` | password_changed_at | String | 100 | MDY datetime; drives PASSWORD_MAX_AGE_DAYS rotation |
| 8 | `cr673_deactivated_by` | deactivated_by | String | 200 | Admin email who disabled the account |
| 9 | `cr673_deactivated_at` | deactivated_at | String | 100 | MDY datetime |
| 10 | `cr673_created_date` | created_date | String | 100 | MDY datetime |
| 11 | `cr673_update_date` | update_date | String | 100 | MDY datetime |

---

### 5.5 `cr673_bahra_audit_logs` — Audit trail

> Append-only. **Never deleted**. Queryable via Audit Logs admin page.

| # | Logical name | Display | Type | Length | Notes |
|---|--------------|---------|------|--------|-------|
| 1 | `cr673_name` | name | String | 200 | **Primary Name** — short summary for list view |
| 2 | `cr673_action` | action | String | 100 | e.g., `LOGIN_SUCCESS`, `ROLE_CREATE`, `RFP_SUBMIT` |
| 3 | `cr673_category` | category | String | 50 | `auth` · `rbac` · `rfp` · `user_management` · `system` |
| 4 | `cr673_actor_email` | actor_email | String | 200 | Who performed the action |
| 5 | `cr673_actor_name` | actor_name | String | 200 | Display name at time of action |
| 6 | `cr673_target_type` | target_type | String | 100 | e.g., `user`, `role`, `rfp` |
| 7 | `cr673_target_id` | target_id | String | 200 | GUID or natural key of the affected record |
| 8 | `cr673_details` | details | Memo | 4000 | JSON or freeform diff |
| 9 | `cr673_ip_address` | ip_address | String | 100 | Client IP (taken from request headers) |
| 10 | `cr673_created_date` | created_date | String | 100 | MDY datetime |

---

## 6. Cluster — Master data

### 6.1 `cr673_bahra_material_master` — Material codes

| # | Logical name | Display | Type | Length | Key | Notes |
|---|--------------|---------|------|--------|-----|-------|
| 1 | `cr673_material_code` | material_code | String | 100 | **Primary Name / natural** | SAP material code |
| 2 | `cr673_description` | description | Memo | 2000 | | Free-text description used for fuzzy matching |
| 3 | `cr673_is_active` | is_active | String | 10 | | `"true"` / `"false"` — only active rows participate in matching |
| 4 | `cr673_created_date` | created_date | String | 100 | | MDY datetime |
| 5 | `cr673_updated_date` | updated_date | String | 100 | | MDY datetime |

---

### 6.2 `cr673_bahra_keywords` — Match keywords

| # | Logical name | Display | Type | Length | Key | Notes |
|---|--------------|---------|------|--------|-----|-------|
| 1 | `cr673_keyword` | keyword | String | 500 | **Primary Name** | Keyword phrase (e.g., "XLPE 11kV") |
| 2 | `cr673_is_active` | is_active | String | 10 | | `"true"` / `"false"` |
| 3 | `cr673_created_date` | created_date | String | 100 | | MDY datetime |
| 4 | `cr673_updated_date` | updated_date | String | 100 | | MDY datetime |

---

### 6.3 `cr673_bahra_rfp_team` — Team member routing

> Drives "which bidder gets which RFP email" by `product`. Dynamic columns are stored in `extra_data` JSON (see §6.4).

| # | Logical name | Display | Type | Length | Key | Notes |
|---|--------------|---------|------|--------|-----|-------|
| 1 | `cr673_product` | product | String | 200 | **Primary Name** | Product family (Cables, etc.) — `"All"` is a wildcard |
| 2 | `cr673_name` | name | String | 200 | | Bidder display name |
| 3 | `cr673_email` | email | String | 300 | | Bidder email (matched against incoming card responses) |
| 4 | `cr673_is_active` | is_active | String | 10 | | `"true"` / `"false"` |
| 5 | `cr673_created_date` | created_date | String | 100 | | MDY datetime |
| 6 | `cr673_updated_date` | updated_date | String | 100 | | MDY datetime |
| 7 | `cr673_extra_data` | extra_data | Memo | 4000 | | JSON: `{column_key: value}` for any dynamic column defined in `rfp_team_columns` |

---

### 6.4 `cr673_bahra_rfp_team_columns` — Dynamic column definitions

> Drives the dynamic table shown on Adaptive Cards and the Master Data → RFP Team page. **Default seeded columns:** `product · name · email · results · remarks`.

| # | Logical name | Display | Type | Length | Key | Notes |
|---|--------------|---------|------|--------|-----|-------|
| 1 | `cr673_column_key` | column_key | String | 100 | **Primary Name** | Stable identifier (snake_case) |
| 2 | `cr673_column_label` | column_label | String | 200 | | Human-readable header |
| 3 | `cr673_column_type` | column_type | String | 20 | | `text` · `dropdown` · `yes_no` |
| 4 | `cr673_column_category` | column_category | String | 20 | | `display` (read-only) · `input` (bidder fills) |
| 5 | `cr673_sort_order` | sort_order | String | 10 | | Numeric string |
| 6 | `cr673_dropdown_options` | dropdown_options | Memo | 2000 | | JSON array of strings (only for `type=dropdown`) |
| 7 | `cr673_is_required` | is_required | String | 10 | | `"true"` / `"false"` |
| 8 | `cr673_is_team_field` | is_team_field | String | 10 | | `"true"` if column belongs to rfp_team row; `"false"` if response-only |
| 9 | `cr673_is_protected` | is_protected | String | 10 | | `"true"` for system columns (email) — Admin cannot delete |
| 10 | `cr673_is_active` | is_active | String | 10 | | `"true"` / `"false"` |
| 11 | `cr673_created_date` | created_date | String | 100 | | MDY datetime |
| 12 | `cr673_updated_date` | updated_date | String | 100 | | MDY datetime |

---

## 7. Cluster — Operations

### 7.1 `cr673_bahra_automation_log1` — Automation event log

> Every automation step writes one row here. Use this for forensic timelines: "what did the bot do at 3:14 PM?"

| # | Logical name | Display | Type | Notes |
|---|--------------|---------|------|-------|
| 1 | `cr673_RunID` | RunID | String | UUID per automation run; matches `rfps_v2.RunID` |
| 2 | `cr673_Timestamp` | Timestamp | String | `YYYY-MM-DD HH:MM:SS` |
| 3 | `cr673_Category` | Category | String | `RFP` · `EMAIL` · `DB` · `AUTH` · `SYS` |
| 4 | `cr673_Action` | Action | String | e.g., `Download`, `Match`, `Submit`, `Email`, `Decline` |
| 5 | `cr673_automation_status` | automation_status | String | `Success` · `Fail` · `Skip` · `Warn` |
| 6 | `cr673_Message` | Message | Memo | Freeform — error trace, count summary, etc. |
| 7 | `cr673_RFP_ID` | RFP_ID | String | Optional — links back to `rfps_v2.RFP_ID` |

**Inferred from** [core/log_events.py](../../core/log_events.py) `write_log_row()` (header list literally constructs these column names). Skipped writes when an RFP was already downloaded — see code for the dedup rule.

---

### 7.2 `cr673_bahra_automation_schedules` — Schedule mirror

> Mirror of the active Power Automate Cloud Flow recurrence. Edited via the portal Schedule dialog → portal calls `helpers/power_automate_helper.py::sync_schedule_to_power_automate()` which patches the flow's recurrence trigger.

| # | Logical name | Display | Type | Notes |
|---|--------------|---------|------|-------|
| 1 | `cr673_name` | name | String | Friendly label (e.g., "Daily 8AM") |
| 2 | `cr673_frequency` | frequency | String | `Minute` · `Hour` · `Day` · `Week` · `Month` |
| 3 | `cr673_interval` | interval | String | Numeric string |
| 4 | `cr673_start_time` | start_time | String | ISO 8601 |
| 5 | `cr673_timezone` | timezone | String | IANA name → mapped to Windows TZ at sync |
| 6 | `cr673_enabled` | enabled | String | `"true"` / `"false"` |
| 7 | `cr673_updated_by` | updated_by | String | Admin email who last edited |
| 8 | `cr673_updated_date` | updated_date | String | MDY datetime |

**Inferred** — confirm columns against live env. The actual cron lives in Power Automate; this table is a UI/audit mirror.

---

## 8. Cluster — Integration

### 8.1 `cr673_bahra_sap_infomation` — SAP password rotation log

> Note the misspelling **`infomation`** (single `r`) — preserved in code and config.

| # | Logical name | Display | Type | Notes |
|---|--------------|---------|------|-------|
| 1 | `cr673_password` | password | String | Encrypted SAP password (or hashed reference) |
| 2 | `cr673_user_email` | user_email | String | Portal user who rotated it |
| 3 | `cr673_username` | username | String | SAP username |
| 4 | `cr673_created_date` | created_date | String | MDY datetime |

**Inferred from** [services/sap_service.py](../../services/sap_service.py) `create_sap_password_record(password, user_email, username)`.

---

### 8.2 `cr673_bahra_system_settings` — Runtime settings

> Editable via the System Settings admin page. Cached in-process for `SETTINGS_CACHE_TTL = 300` s.

| # | Logical name | Display | Type | Notes |
|---|--------------|---------|------|-------|
| 1 | `cr673_key` | Key | String | Setting key (e.g., `EMAIL_TO_NEW_RFP`) — natural key |
| 2 | `cr673_value` | Value | Memo | Setting value (string or JSON) |
| 3 | `cr673_label` | Label | String | UI-friendly label |
| 4 | `cr673_section` | Section | String | Top-level grouping (e.g., `Admin`) |
| 5 | `cr6db_sub_section` | Sub Section | String | Sub-grouping (e.g., `Email`) — note **`cr6db_`** prefix for this column only |
| 6 | `cr673_data_type` | Data Type | String | `string` · `email` · `json` · `int` · `bool` |
| 7 | `cr673_description` | Description | Memo | Long-form description shown on the settings page |
| 8 | `cr673_is_editable` | Is Editable | String | `"true"` / `"false"` |
| 9 | `cr673_is_sensitive` | Is Sensitive | String | `"true"` masks the value in the UI |

**Active seeded keys** (from [seed_system_settings.py](../../Support-Files/seed_system_settings.py) `SEED_DATA`):
- 12 `EMAIL_TO_*` recipient lists
- `DECLINE_BUTTON_EMAILS` (JSON array — emails authorized to see the Decline button)

All other settings have been moved to `config/config.py` (developer-managed) — see `REMOVED_KEYS` in the seed script.

---

## 9. Common operations

### 9.1 Look up the API name

```bash
# All Dataverse tables auto-pluralize EntitySetName by appending "es"
# Confirm with:
GET https://operations-bahrauat-1.crm11.dynamics.com/api/data/v9.2/EntityDefinitions(LogicalName='cr673_bahra_roles')?$select=EntitySetName
# → "cr673_bahra_roleses"
```

### 9.2 Upsert pattern (already implemented in `log_rfp_activity`)

```python
result = DATAVERSE.query_rows(
    table_api_name=RFP_ACTIVITY_LOG_TABLE_API,
    filter_expr=f"RFP_ID eq '{rfp_id}'",
    top=1,
    table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL,
    use_display_names=True,
)
if result["value"]:
    DATAVERSE.update_row(...)
else:
    DATAVERSE.insert_row(...)
```

### 9.3 Bulk-load `Matched_Data` JSON shape

```json
{
  "rfp_id": "Doc12345",
  "source_file": "BOQ-2026-04.xlsx",
  "rfp_end_date": "2026-05-15T18:00:00Z",
  "total_items": 42,
  "summary": {
    "exact_match_count": 18,
    "keyword_match_count": 11,
    "not_matched_count": 13,
    "match_percentage": 69.0
  },
  "exact_matches":   [{"material_code": "...", "excel_name": "...", "row_number": 5, "column_name": "Material"}, ...],
  "keyword_matches": [{"material_code": "...", "matched_keyword": "XLPE 11kV", ...}, ...],
  "not_matched":     [{"excel_name": "...", "excel_description": "...", ...}, ...]
}
```

---

## 10. Validation backlog

Items to verify against the live environment before treating this dictionary as canonical:

- [ ] `cr673_bahra_users` — confirm exact column names and types
- [ ] `cr673_bahra_sap_infomation` — confirm columns; resolve typo (rename or accept)
- [ ] `cr673_bahra_automation_log1` — confirm column names match those used in `write_log_row()` exactly
- [ ] `cr673_bahra_automation_schedules` — full column list
- [ ] `cr673_bhara_rfp_status` — confirm rows + column names; consider renaming to `cr673_bahra_rfp_status` (typo)
- [ ] `cr6db_cr673_bahra_rfp_response` — confirm full column list and primary name
- [ ] Add Dataverse alternate keys (uniqueness) on `rfps_v2.RFP_ID`, `users.email`, `roles.name`, `material_master.material_code`, `keywords.keyword`, `rfp_team_columns.column_key`, `system_settings.Key`

---

## 11. Change history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-04-22 | Samir Tak | Initial dictionary — 16 tables, ER diagram, validation backlog |
