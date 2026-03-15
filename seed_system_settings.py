"""
Seed System Settings - Populates the cr673_bahra_system_settings Dataverse table
from current config.py values. Idempotent: skips existing keys.

Usage:
    python seed_system_settings.py
    python seed_system_settings.py --update   # Update sections, sub_sections, descriptions
"""

import json
import sys
from helpers.dataverse_helper import DataverseClient
from config.config import (
    TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL,
    SYSTEM_SETTINGS_TABLE_API, SYSTEM_SETTINGS_TABLE_LOGICAL,
)
import config.config as config

# ─────────────────────────────────────────────────────
# Seed Data: one dict per config key
# 2 top-level sections: Admin, Developer
# Admin  sub-tabs: General, Email, Security & Access
# Developer sub-tabs: Azure & Auth, Automation, SharePoint, File Paths, Dataverse Tables
# ─────────────────────────────────────────────────────
SEED_DATA = [
    # ═══════════════════════════════════════════════════
    # SECTION: Admin  ►  Sub-tab: General
    # ═══════════════════════════════════════════════════

    {"key": "URL", "value": "https://service.ariba.com/Sourcing.aw/109582016/aw?awh=r&awssk=u9fNiSxN&dard=1#b0",
     "label": "Ariba Portal URL", "section": "Admin", "sub_section": "General", "data_type": "string",
     "description": "The Ariba sourcing portal URL used by the automation bot. Used by: RFP download automation. Changing this will redirect the bot to a different portal page.",
     "is_editable": True, "is_sensitive": False},

    {"key": "COMPANY_NAME", "value": "Saudi Electricity Company",
     "label": "Default Company Name", "section": "Admin", "sub_section": "General", "data_type": "string",
     "description": "Default company name used when none is specified. Used by: RFP processing, file naming, email templates. Changing this updates which company appears by default in new RFP operations.",
     "is_editable": True, "is_sensitive": False},

    {"key": "COMPANY_OPTIONS", "value": json.dumps(["Saudi Electricity Company", "Aramco e-Marketplace", "SABIC - Saudi Basic Industries Corp.", "HADEED - RAJHI STEEL"]),
     "label": "Company Options", "section": "Admin", "sub_section": "General", "data_type": "json",
     "description": "JSON list of company names available in the portal. Used by: RFP processing, company selection dropdowns. Adding/removing entries changes which companies users can select. Must be a valid JSON array of strings.",
     "is_editable": True, "is_sensitive": False},

    {"key": "VALID_RFP_STATUSES", "value": json.dumps(["no", "saved_draft", "submitted", "declined"]),
     "label": "Valid RFP Statuses", "section": "Admin", "sub_section": "General", "data_type": "json",
     "description": "Allowed RFP participation status values. Used by: RFP status tracking, validation logic. Adding or removing statuses affects which values the system accepts. Must be a valid JSON array of strings.",
     "is_editable": True, "is_sensitive": False},

    {"key": "DASHBOARD_TTL_SECONDS", "value": "300",
     "label": "Dashboard Cache TTL", "section": "Admin", "sub_section": "General", "data_type": "number",
     "description": "How long dashboard stats are cached before refreshing from Dataverse (in seconds). Used by: Dashboard page. Lower = fresher data but more API calls. Default 300 = 5 minutes.",
     "is_editable": True, "is_sensitive": False},

    {"key": "LOGS_TTL_SECONDS", "value": "300",
     "label": "Logs Cache TTL", "section": "Admin", "sub_section": "General", "data_type": "number",
     "description": "How long automation logs are cached before refreshing from Dataverse (in seconds). Used by: Logs page. Lower = more up-to-date logs but more API calls. Default 300 = 5 minutes.",
     "is_editable": True, "is_sensitive": False},

    {"key": "SAP_LOGS_TTL_SECONDS", "value": "300",
     "label": "SAP Logs Cache TTL", "section": "Admin", "sub_section": "General", "data_type": "number",
     "description": "How long SAP password logs are cached before refreshing (in seconds). Used by: SAP Logs page. Lower = more up-to-date logs but more API calls. Default 300 = 5 minutes.",
     "is_editable": True, "is_sensitive": False},

    # ═══════════════════════════════════════════════════
    # SECTION: Admin  ►  Sub-tab: Email
    # ═══════════════════════════════════════════════════

    {"key": "EMAIL_MODE", "value": "dev",
     "label": "Email Mode", "section": "Admin", "sub_section": "Email", "data_type": "string",
     "description": "Controls routing for ALL outgoing emails. Used by: every email notification, RFP alerts, password resets. In 'dev' mode every email goes to DEV_EMAIL only. Switching to 'prod' immediately sends to real recipients -- verify all EMAIL_TO_* values first.",
     "is_editable": True, "is_sensitive": False},

    {"key": "DEV_EMAIL", "value": "KSAGov.tenders@bahra-cables.com",
     "label": "Dev Email", "section": "Admin", "sub_section": "Email", "data_type": "email",
     "description": "Catch-all email address used in 'dev' mode. Used by: all email notifications when EMAIL_MODE is 'dev'. All outgoing emails route here instead of real recipients. Changing this redirects all dev-mode emails to a new address.",
     "is_editable": True, "is_sensitive": False},

    {"key": "EMAIL_TO_NEW_RFP", "value": config.EMAIL_TO_NEW_RFP,
     "label": "Email: New RFP Found", "section": "Admin", "sub_section": "Email", "data_type": "email",
     "description": "Recipient when a NEW RFP is found on the portal. Used by: RFP download automation. Sent once per new RFP with the RFP file attached and matched materials. Only active when EMAIL_MODE is 'prod'.",
     "is_editable": True, "is_sensitive": False},

    {"key": "EMAIL_TO_NO_NEW_RFP", "value": config.EMAIL_TO_NO_NEW_RFP,
     "label": "Email: No New RFP", "section": "Admin", "sub_section": "Email", "data_type": "email",
     "description": "Recipient when automation runs but finds NO new RFP on the portal. Used by: RFP download automation. Sent as a status update so admins know the bot ran successfully.",
     "is_editable": True, "is_sensitive": False},

    {"key": "EMAIL_TO_RFP_DECLINED", "value": config.EMAIL_TO_RFP_DECLINED,
     "label": "Email: RFP Declined", "section": "Admin", "sub_section": "Email", "data_type": "email",
     "description": "Recipient when an RFP is declined via the portal. Used by: RFP decline automation. Confirms the decline action was completed.",
     "is_editable": True, "is_sensitive": False},

    {"key": "EMAIL_TO_RFP_ERROR_IN_SUBMISSION", "value": config.EMAIL_TO_RFP_ERROR_IN_SUBMISSION,
     "label": "Email: Submission Error", "section": "Admin", "sub_section": "Email", "data_type": "email",
     "description": "Recipient when an RFP submission fails with an error. Used by: RFP submit automation. Contains error details so the team can investigate and retry.",
     "is_editable": True, "is_sensitive": False},

    {"key": "EMAIL_TO_RFP_ERROR_IN_DECLINE", "value": config.EMAIL_TO_RFP_ERROR_IN_DECLINE,
     "label": "Email: Decline Error", "section": "Admin", "sub_section": "Email", "data_type": "email",
     "description": "Recipient when an RFP decline fails with an error. Used by: RFP decline automation. Contains error details for investigation.",
     "is_editable": True, "is_sensitive": False},

    {"key": "EMAIL_TO_AUTOMATION_FAILURE", "value": config.EMAIL_TO_AUTOMATION_FAILURE,
     "label": "Email: Automation Failure", "section": "Admin", "sub_section": "Email", "data_type": "email",
     "description": "Recipient when the automation bot crashes or encounters a critical failure. Used by: automation error handler. This is the most important alert email -- ensure it reaches someone who can respond quickly.",
     "is_editable": True, "is_sensitive": False},

    {"key": "EMAIL_TO_RFP_SUBMITTED", "value": config.EMAIL_TO_RFP_SUBMITTED,
     "label": "Email: RFP Submitted", "section": "Admin", "sub_section": "Email", "data_type": "email",
     "description": "Recipient when an RFP is successfully submitted on the portal. Used by: RFP submit automation. Confirms the submission was completed.",
     "is_editable": True, "is_sensitive": False},

    {"key": "EMAIL_TO_RFP_SAVED_DRAFT", "value": config.EMAIL_TO_RFP_SAVED_DRAFT,
     "label": "Email: RFP Saved Draft", "section": "Admin", "sub_section": "Email", "data_type": "email",
     "description": "Recipient when an RFP is saved as draft on the portal. Used by: RFP draft automation. Notifies the team that a draft is ready for review.",
     "is_editable": True, "is_sensitive": False},

    {"key": "EMAIL_TO_RFP_REMINDER", "value": config.EMAIL_TO_RFP_REMINDER,
     "label": "Email: RFP Reminder", "section": "Admin", "sub_section": "Email", "data_type": "email",
     "description": "Recipient for RFP deadline reminder notifications. Used by: RFP reminder scheduler. Sent before RFP deadlines to prompt action.",
     "is_editable": True, "is_sensitive": False},

    {"key": "EMAIL_TO_NEW_RFP_WITH_MATCH", "value": config.EMAIL_TO_NEW_RFP_WITH_MATCH,
     "label": "Email: New RFP With Match", "section": "Admin", "sub_section": "Email", "data_type": "email",
     "description": "Recipient when a new RFP is found AND has material matches in master data. Used by: RFP download automation with material matching. Contains the matched materials summary.",
     "is_editable": True, "is_sensitive": False},

    {"key": "EMAIL_TO_NO_MATCHED_DATA", "value": config.EMAIL_TO_NO_MATCHED_DATA,
     "label": "Email: No Matched Data", "section": "Admin", "sub_section": "Email", "data_type": "email",
     "description": "Recipient when material matching runs but finds no matches in master data. Used by: material matching service. Alerts the team to review material master data.",
     "is_editable": True, "is_sensitive": False},

    {"key": "EMAIL_TO_NEW_RFP_NO_MATCH", "value": config.EMAIL_TO_NEW_RFP_NO_MATCH,
     "label": "Email: New RFP No Match", "section": "Admin", "sub_section": "Email", "data_type": "email",
     "description": "Recipient when a new RFP is found but has NO material matches. Used by: RFP download automation. Alerts the team that manual material review is needed.",
     "is_editable": True, "is_sensitive": False},

    {"key": "DECLINE_BUTTON_EMAILS", "value": json.dumps(["Shubham.kumbhar@dynatechconsultancy.com"]),
     "label": "Decline Button Emails", "section": "Admin", "sub_section": "Email", "data_type": "json",
     "description": "Email addresses authorized to see the 'Decline RFP' button in consolidated response emails. Used by: actionable card email builder. Only these users will see the decline option. Must be a valid JSON array of email strings.",
     "is_editable": True, "is_sensitive": False},

    # ═══════════════════════════════════════════════════
    # SECTION: Admin  ►  Sub-tab: Security & Access
    # ═══════════════════════════════════════════════════

    {"key": "SESSION_TIMEOUT_SECONDS", "value": "7200",
     "label": "Session Timeout", "section": "Admin", "sub_section": "Security & Access", "data_type": "number",
     "description": "How long a user session stays active (in seconds). Used by: login/auth system. After this time users are automatically logged out. Reducing this forces more frequent logins for all portal users.",
     "is_editable": True, "is_sensitive": False},

    {"key": "RBAC_CACHE_TTL_SECONDS", "value": "300",
     "label": "RBAC Cache TTL", "section": "Admin", "sub_section": "Security & Access", "data_type": "number",
     "description": "How long role-permissions are cached before refreshing from Dataverse (in seconds). Used by: auth middleware on every API request. Lower = permission changes take effect faster but more Dataverse calls.",
     "is_editable": True, "is_sensitive": False},

    {"key": "ACCOUNT_LOCKOUT_THRESHOLD", "value": "5",
     "label": "Account Lockout Threshold", "section": "Admin", "sub_section": "Security & Access", "data_type": "number",
     "description": "Number of failed login attempts before an account gets locked. Used by: login page, auth middleware. Setting too low may lock out legitimate users who mistype their password.",
     "is_editable": True, "is_sensitive": False},

    {"key": "ACCOUNT_LOCKOUT_DURATION_MINUTES", "value": "30",
     "label": "Account Lockout Duration", "section": "Admin", "sub_section": "Security & Access", "data_type": "number",
     "description": "How long a locked account stays locked (in minutes). Used by: login page, auth middleware. After this period, the user can try logging in again.",
     "is_editable": True, "is_sensitive": False},

    {"key": "PASSWORD_MIN_LENGTH", "value": "8",
     "label": "Password Min Length", "section": "Admin", "sub_section": "Security & Access", "data_type": "number",
     "description": "Minimum required password length for user accounts. Used by: user registration, password change. Increasing this will require longer passwords for all new password changes.",
     "is_editable": True, "is_sensitive": False},

    {"key": "PASSWORD_REQUIRE_UPPERCASE", "value": "true",
     "label": "Require Uppercase", "section": "Admin", "sub_section": "Security & Access", "data_type": "boolean",
     "description": "Whether passwords must contain at least one uppercase letter. Used by: user registration, password change. Disabling reduces password strength requirements.",
     "is_editable": True, "is_sensitive": False},

    {"key": "PASSWORD_REQUIRE_NUMBER", "value": "true",
     "label": "Require Number", "section": "Admin", "sub_section": "Security & Access", "data_type": "boolean",
     "description": "Whether passwords must contain at least one number. Used by: user registration, password change. Disabling reduces password strength requirements.",
     "is_editable": True, "is_sensitive": False},

    {"key": "PASSWORD_MAX_AGE_DAYS", "value": "90",
     "label": "Password Max Age", "section": "Admin", "sub_section": "Security & Access", "data_type": "number",
     "description": "Maximum password age in days before users must change it. Used by: login page (forces password change). Setting to 0 disables password expiry. Reducing this forces earlier password changes for all users.",
     "is_editable": True, "is_sensitive": False},

    # ═══════════════════════════════════════════════════
    # SECTION: Developer  ►  Sub-tab: Azure & Auth
    # ═══════════════════════════════════════════════════

    {"key": "TENANT_ID", "value": "46aa82d0-1a4b-4b08-b520-514ccbe1e7ca",
     "label": "Azure Tenant ID", "section": "Developer", "sub_section": "Azure & Auth", "data_type": "string",
     "description": "Azure AD tenant ID for Graph API and Dataverse authentication. Used by: SharePoint file operations, Dataverse API calls. If wrong, ALL external API connections will fail.",
     "is_editable": True, "is_sensitive": True},

    {"key": "CLIENT_ID", "value": "97312492-991a-46be-91de-62430026f72d",
     "label": "Azure Client ID", "section": "Developer", "sub_section": "Azure & Auth", "data_type": "string",
     "description": "Azure AD app registration client ID. Used by: SharePoint file operations, Dataverse API calls. If wrong, authentication will fail for all external services.",
     "is_editable": True, "is_sensitive": True},

    {"key": "CLIENT_SECRET", "value": "pDN8Q~kLKXRoOmEB5PvLRDo-zVH2o91IjRtaJagr",
     "label": "Azure Client Secret", "section": "Developer", "sub_section": "Azure & Auth", "data_type": "string",
     "description": "Azure AD app registration client secret. Used by: SharePoint file operations, Dataverse API calls. Secrets expire periodically -- update this when Azure rotates the secret or the system will stop working.",
     "is_editable": True, "is_sensitive": True},

    {"key": "RESOURCE_URL", "value": "https://operations-bahrauat-1.crm11.dynamics.com",
     "label": "Dataverse Resource URL", "section": "Developer", "sub_section": "Azure & Auth", "data_type": "string",
     "description": "Dataverse environment base URL. Used by: ALL Dataverse operations (read, write, query). If wrong, the entire system loses database connectivity.",
     "is_editable": True, "is_sensitive": False},

    {"key": "FORGOT_PASSWORD_FLOW_URL", "value": "https://dab4cde858caeaa0b535f6dbd4b6cf.a6.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/326c08241613446da0e9cd6235d4e666/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=r3S5vKCYj3BQ0ymdc-qsBY2fPgzbsM67EDzfIiQcQFQ",
     "label": "Forgot Password Flow URL", "section": "Developer", "sub_section": "Azure & Auth", "data_type": "string",
     "description": "Power Automate HTTP trigger URL for forgot-password emails. Used by: login page password reset. If wrong, users cannot reset their passwords.",
     "is_editable": True, "is_sensitive": True},

    # ═══════════════════════════════════════════════════
    # SECTION: Developer  ►  Sub-tab: Automation
    # ═══════════════════════════════════════════════════

    {"key": "FLOW_URL", "value": "https://dab4cde858caeaa0b535f6dbd4b6cf.a6.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/8b59f8e17de8493ab5f575461aa92133/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=bG4Z-fghyYpzFZHxsyu8yzsrSlPlNEkzgMCQeKvS9VI",
     "label": "Power Automate Flow URL", "section": "Developer", "sub_section": "Automation", "data_type": "string",
     "description": "Power Automate HTTP trigger URL for sending ALL emails. Used by: email_helper (every outgoing email). If this URL is wrong or expired, NO emails will be sent from the system.",
     "is_editable": True, "is_sensitive": True},

    {"key": "ACTIONABLE_CARD_ORIGINATOR_ID", "value": "4f5d8362-8a49-420d-8506-6b1c0a616647",
     "label": "Actionable Card Originator ID", "section": "Developer", "sub_section": "Automation", "data_type": "string",
     "description": "Microsoft Actionable Email originator ID for Adaptive Cards in Outlook. Used by: RFP response emails with interactive buttons. If wrong, Outlook will not render the actionable card and users cannot respond via email.",
     "is_editable": True, "is_sensitive": False},

    {"key": "ACTIONABLE_CARD_CALLBACK_URL", "value": "https://xp7z0w4z-8000.inc1.devtunnels.ms/api/actionable-card/response",
     "label": "Actionable Card Callback URL", "section": "Developer", "sub_section": "Automation", "data_type": "string",
     "description": "Public HTTPS URL that Outlook posts to when users submit an Adaptive Card. Used by: actionable card response handler. Must be publicly accessible. If wrong, card submissions from Outlook will fail silently.",
     "is_editable": True, "is_sensitive": False},

    # ═══════════════════════════════════════════════════
    # SECTION: Developer  ►  Sub-tab: SharePoint
    # ═══════════════════════════════════════════════════

    {"key": "SHAREPOINT_HOSTNAME", "value": "bahracables.sharepoint.com",
     "label": "SharePoint Hostname", "section": "Developer", "sub_section": "SharePoint", "data_type": "string",
     "description": "SharePoint Online hostname. Used by: file upload/download, RFP log storage. Changing this redirects all SharePoint operations to a different tenant.",
     "is_editable": True, "is_sensitive": False},

    {"key": "SITE_PATH", "value": "/sites/LiveSite/RFPAutomation",
     "label": "SharePoint Site Path", "section": "Developer", "sub_section": "SharePoint", "data_type": "string",
     "description": "Path to the SharePoint site for RFP file storage. Used by: file upload/download operations. Changing this points all file operations to a different SharePoint site.",
     "is_editable": True, "is_sensitive": False},

    {"key": "DRIVE_NAME", "value": "Documents",
     "label": "SharePoint Drive Name", "section": "Developer", "sub_section": "SharePoint", "data_type": "string",
     "description": "SharePoint document library name. Used by: file upload/download. Changing this switches which document library is used for storing RFP files.",
     "is_editable": True, "is_sensitive": False},

    {"key": "SP_BASE_FOLDER", "value": "RFP-logs",
     "label": "SharePoint Base Folder", "section": "Developer", "sub_section": "SharePoint", "data_type": "string",
     "description": "Root folder in SharePoint for all RFP log files. Used by: email attachments, log uploads, master data exports. Changing this moves the base folder for all SharePoint file operations.",
     "is_editable": True, "is_sensitive": False},

    # ═══════════════════════════════════════════════════
    # SECTION: Developer  ►  Sub-tab: File Paths
    # ═══════════════════════════════════════════════════

    {"key": "OUTPUT_DIR", "value": config.OUTPUT_DIR,
     "label": "Output Directory", "section": "Developer", "sub_section": "File Paths", "data_type": "string",
     "description": "Local directory where downloaded RFP files are stored. Used by: RFP download automation, file processing. Changing this redirects all output files to a new folder. The directory will be created if it does not exist.",
     "is_editable": True, "is_sensitive": False},

    {"key": "FAILURE_LOGS_DIR", "value": config.FAILURE_LOGS_DIR,
     "label": "Failure Logs Directory", "section": "Developer", "sub_section": "File Paths", "data_type": "string",
     "description": "Local directory for automation error log files. Used by: failure logger, error analysis. Changing this redirects error logs to a new folder.",
     "is_editable": True, "is_sensitive": False},

    {"key": "SP_FAILURE_LOGS_FOLDER", "value": "RFP-logs/automation-error-logs",
     "label": "Failure Logs SharePoint Folder", "section": "Developer", "sub_section": "File Paths", "data_type": "string",
     "description": "SharePoint folder path for uploading automation error logs. Used by: failure logger (uploads error details to SharePoint). Changing this redirects log uploads to a different SharePoint folder.",
     "is_editable": True, "is_sensitive": False},

    # ═══════════════════════════════════════════════════
    # SECTION: Developer  ►  Sub-tab: Dataverse Tables
    # ═══════════════════════════════════════════════════

    # System Tables — Locked, non-editable. Descriptions explain which service uses them.
    {"key": "AUTOMATION_LOG_TABLE_LOGICAL", "value": "cr673_bahra_automation_log1",
     "label": "Automation Log Table (Logical)", "section": "Developer", "sub_section": "Dataverse Tables", "data_type": "string",
     "description": "Logical name for the automation log table. Used by: automation logging, dashboard. Non-editable -- changing would break all automation log operations.", "is_editable": False, "is_sensitive": False},

    {"key": "AUTOMATION_LOG_TABLE_API", "value": "cr673_bahra_automation_log1s",
     "label": "Automation Log Table (API)", "section": "Developer", "sub_section": "Dataverse Tables", "data_type": "string",
     "description": "API name for the automation log table. Used by: automation logging, dashboard. Non-editable.", "is_editable": False, "is_sensitive": False},

    {"key": "RFP_ACTIVITY_LOG_TABLE_LOGICAL", "value": "cr673_requestforproposal",
     "label": "RFP Activity Log Table (Logical)", "section": "Developer", "sub_section": "Dataverse Tables", "data_type": "string",
     "description": "Logical name for the RFP activity log table. Used by: RFP tracking, dashboard, logs page. Non-editable.", "is_editable": False, "is_sensitive": False},

    {"key": "RFP_ACTIVITY_LOG_TABLE_API", "value": "cr673_requestforproposals",
     "label": "RFP Activity Log Table (API)", "section": "Developer", "sub_section": "Dataverse Tables", "data_type": "string",
     "description": "API name for the RFP activity log table. Used by: RFP tracking, dashboard, logs page. Non-editable.", "is_editable": False, "is_sensitive": False},

    {"key": "USERS_TABLE_LOGICAL", "value": "cr673_bahra_users",
     "label": "Users Table (Logical)", "section": "Developer", "sub_section": "Dataverse Tables", "data_type": "string",
     "description": "Logical name for the users table. Used by: user management, authentication. Non-editable.", "is_editable": False, "is_sensitive": False},

    {"key": "USERS_TABLE_API", "value": "cr673_bahra_userses",
     "label": "Users Table (API)", "section": "Developer", "sub_section": "Dataverse Tables", "data_type": "string",
     "description": "API name for the users table. Used by: user management, authentication. Non-editable.", "is_editable": False, "is_sensitive": False},

    {"key": "SAP_PASSWORD_TABLE_LOGICAL", "value": "cr673_bahra_sap_infomation",
     "label": "SAP Password Table (Logical)", "section": "Developer", "sub_section": "Dataverse Tables", "data_type": "string",
     "description": "Logical name for the SAP password table. Used by: SAP credentials service. Non-editable.", "is_editable": False, "is_sensitive": False},

    {"key": "SAP_PASSWORD_TABLE_API", "value": "cr673_bahra_sap_infomations",
     "label": "SAP Password Table (API)", "section": "Developer", "sub_section": "Dataverse Tables", "data_type": "string",
     "description": "API name for the SAP password table. Used by: SAP credentials service. Non-editable.", "is_editable": False, "is_sensitive": False},

    {"key": "AUTOMATION_SCHEDULE_TABLE_LOGICAL", "value": "cr673_bahra_automation_schedules",
     "label": "Automation Schedule Table (Logical)", "section": "Developer", "sub_section": "Dataverse Tables", "data_type": "string",
     "description": "Logical name for the automation schedule table. Used by: scheduler service. Non-editable.", "is_editable": False, "is_sensitive": False},

    {"key": "AUTOMATION_SCHEDULE_TABLE_API", "value": "cr673_bahra_automation_scheduleses",
     "label": "Automation Schedule Table (API)", "section": "Developer", "sub_section": "Dataverse Tables", "data_type": "string",
     "description": "API name for the automation schedule table. Used by: scheduler service. Non-editable.", "is_editable": False, "is_sensitive": False},

    {"key": "RFP_STATUS_TABLE_LOGICAL", "value": "cr673_bhara_rfp_status",
     "label": "RFP Status Table (Logical)", "section": "Developer", "sub_section": "Dataverse Tables", "data_type": "string",
     "description": "Logical name for the RFP status tracking table. Used by: RFP status updates, dashboard. Non-editable.", "is_editable": False, "is_sensitive": False},

    {"key": "RFP_STATUS_TABLE_API", "value": "cr673_bhara_rfp_statuses",
     "label": "RFP Status Table (API)", "section": "Developer", "sub_section": "Dataverse Tables", "data_type": "string",
     "description": "API name for the RFP status tracking table. Used by: RFP status updates, dashboard. Non-editable.", "is_editable": False, "is_sensitive": False},

    {"key": "ROLES_TABLE_LOGICAL", "value": "cr673_bahra_roles",
     "label": "Roles Table (Logical)", "section": "Developer", "sub_section": "Dataverse Tables", "data_type": "string",
     "description": "Logical name for the roles table. Used by: RBAC system, role management page. Non-editable.", "is_editable": False, "is_sensitive": False},

    {"key": "ROLES_TABLE_API", "value": "cr673_bahra_roleses",
     "label": "Roles Table (API)", "section": "Developer", "sub_section": "Dataverse Tables", "data_type": "string",
     "description": "API name for the roles table. Used by: RBAC system, role management page. Non-editable.", "is_editable": False, "is_sensitive": False},

    {"key": "ROLE_PERMISSIONS_TABLE_LOGICAL", "value": "cr673_bahra_role_permissions",
     "label": "Role Permissions Table (Logical)", "section": "Developer", "sub_section": "Dataverse Tables", "data_type": "string",
     "description": "Logical name for the role permissions table. Used by: RBAC permission checks. Non-editable.", "is_editable": False, "is_sensitive": False},

    {"key": "ROLE_PERMISSIONS_TABLE_API", "value": "cr673_bahra_role_permissionses",
     "label": "Role Permissions Table (API)", "section": "Developer", "sub_section": "Dataverse Tables", "data_type": "string",
     "description": "API name for the role permissions table. Used by: RBAC permission checks. Non-editable.", "is_editable": False, "is_sensitive": False},

    {"key": "AUDIT_LOG_TABLE_LOGICAL", "value": "cr673_bahra_audit_logs",
     "label": "Audit Log Table (Logical)", "section": "Developer", "sub_section": "Dataverse Tables", "data_type": "string",
     "description": "Logical name for the audit log table. Used by: audit logging, audit log viewer page. Non-editable.", "is_editable": False, "is_sensitive": False},

    {"key": "AUDIT_LOG_TABLE_API", "value": "cr673_bahra_audit_logses",
     "label": "Audit Log Table (API)", "section": "Developer", "sub_section": "Dataverse Tables", "data_type": "string",
     "description": "API name for the audit log table. Used by: audit logging, audit log viewer page. Non-editable.", "is_editable": False, "is_sensitive": False},

    {"key": "USER_STATUS_TABLE_LOGICAL", "value": "cr673_bahra_user_status",
     "label": "User Status Table (Logical)", "section": "Developer", "sub_section": "Dataverse Tables", "data_type": "string",
     "description": "Logical name for the user status table. Used by: user lifecycle (lockout, activation). Non-editable.", "is_editable": False, "is_sensitive": False},

    {"key": "USER_STATUS_TABLE_API", "value": "cr673_bahra_user_statuses",
     "label": "User Status Table (API)", "section": "Developer", "sub_section": "Dataverse Tables", "data_type": "string",
     "description": "API name for the user status table. Used by: user lifecycle (lockout, activation). Non-editable.", "is_editable": False, "is_sensitive": False},

    {"key": "SYSTEM_SETTINGS_TABLE_LOGICAL", "value": "cr673_bahra_system_settings",
     "label": "System Settings Table (Logical)", "section": "Developer", "sub_section": "Dataverse Tables", "data_type": "string",
     "description": "Logical name for the system settings table (this page). Used by: settings service. Non-editable.", "is_editable": False, "is_sensitive": False},

    {"key": "SYSTEM_SETTINGS_TABLE_API", "value": "cr673_bahra_system_settingses",
     "label": "System Settings Table (API)", "section": "Developer", "sub_section": "Dataverse Tables", "data_type": "string",
     "description": "API name for the system settings table (this page). Used by: settings service. Non-editable.", "is_editable": False, "is_sensitive": False},

    {"key": "MATERIAL_MASTER_TABLE_LOGICAL", "value": "cr673_bahra_material_master",
     "label": "Material Master Table (Logical)", "section": "Developer", "sub_section": "Dataverse Tables", "data_type": "string",
     "description": "Logical name for the material master table. Used by: material matching, master data page. Non-editable.", "is_editable": False, "is_sensitive": False},

    {"key": "MATERIAL_MASTER_TABLE_API", "value": "cr673_bahra_material_masters",
     "label": "Material Master Table (API)", "section": "Developer", "sub_section": "Dataverse Tables", "data_type": "string",
     "description": "API name for the material master table. Used by: material matching, master data page. Non-editable.", "is_editable": False, "is_sensitive": False},

    {"key": "KEYWORDS_TABLE_LOGICAL", "value": "cr673_bahra_keywords",
     "label": "Keywords Table (Logical)", "section": "Developer", "sub_section": "Dataverse Tables", "data_type": "string",
     "description": "Logical name for the keywords table. Used by: keyword matching in RFP processing. Non-editable.", "is_editable": False, "is_sensitive": False},

    {"key": "KEYWORDS_TABLE_API", "value": "cr673_bahra_keywordses",
     "label": "Keywords Table (API)", "section": "Developer", "sub_section": "Dataverse Tables", "data_type": "string",
     "description": "API name for the keywords table. Used by: keyword matching in RFP processing. Non-editable.", "is_editable": False, "is_sensitive": False},

    {"key": "RFP_TEAM_DV_TABLE_LOGICAL", "value": "cr673_bahra_rfp_team",
     "label": "RFP Team Table (Logical)", "section": "Developer", "sub_section": "Dataverse Tables", "data_type": "string",
     "description": "Logical name for the RFP team table. Used by: team assignment, email routing per product. Non-editable.", "is_editable": False, "is_sensitive": False},

    {"key": "RFP_TEAM_DV_TABLE_API", "value": "cr673_bahra_rfp_teams",
     "label": "RFP Team Table (API)", "section": "Developer", "sub_section": "Dataverse Tables", "data_type": "string",
     "description": "API name for the RFP team table. Used by: team assignment, email routing per product. Non-editable.", "is_editable": False, "is_sensitive": False},

    {"key": "RFP_TEAM_COLUMNS_TABLE_LOGICAL", "value": "cr673_bahra_rfp_team_columns",
     "label": "RFP Team Columns Table (Logical)", "section": "Developer", "sub_section": "Dataverse Tables", "data_type": "string",
     "description": "Logical name for the RFP team columns table. Used by: dynamic column definitions for RFP team. Non-editable.", "is_editable": False, "is_sensitive": False},

    {"key": "RFP_TEAM_COLUMNS_TABLE_API", "value": "cr673_bahra_rfp_team_columnses",
     "label": "RFP Team Columns Table (API)", "section": "Developer", "sub_section": "Dataverse Tables", "data_type": "string",
     "description": "API name for the RFP team columns table. Used by: dynamic column definitions for RFP team. Non-editable.", "is_editable": False, "is_sensitive": False},

    {"key": "RFP_RESPONSE_TABLE_LOGICAL", "value": "cr6db_cr673_bahra_rfp_response",
     "label": "RFP Response Table (Logical)", "section": "Developer", "sub_section": "Dataverse Tables", "data_type": "string",
     "description": "Logical name for the RFP response table. Used by: actionable card responses from Outlook. Non-editable.", "is_editable": False, "is_sensitive": False},

    {"key": "RFP_RESPONSE_TABLE_API", "value": "cr6db_cr673_bahra_rfp_responses",
     "label": "RFP Response Table (API)", "section": "Developer", "sub_section": "Dataverse Tables", "data_type": "string",
     "description": "API name for the RFP response table. Used by: actionable card responses from Outlook. Non-editable.", "is_editable": False, "is_sensitive": False},
]

# Keys that were removed (unused in runtime). Listed here for reference only.
REMOVED_KEYS = [
    "LOGS_FETCH_TOP_MAX", "LOGS_FETCH_AHEAD_FACTOR",
    "DEFAULT_PAGE_SIZE", "MIN_PAGE_SIZE", "MAX_PAGE_SIZE",
    "DASHBOARD_HTTP_MAX_AGE",
    "SESSION_WARNING_SECONDS", "SESSION_REFRESH_INTERVAL", "IDLE_TIMEOUT_SECONDS",
    "TDS_FILE_PATH", "SP_BASE_FOLDER_RFP_UPLOAD_FILES", "RFP_TEAM_TABLE",
]


def seed_settings():
    """Seed system settings from SEED_DATA into Dataverse. Idempotent."""
    print("=" * 60)
    print("Seeding System Settings to Dataverse")
    print("=" * 60)

    client = DataverseClient(TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL)

    existing_rows = client.get_all_rows(
        SYSTEM_SETTINGS_TABLE_API,
        table_logical_name=SYSTEM_SETTINGS_TABLE_LOGICAL,
        use_display_names=True,
    )
    existing_keys = {row.get("Key", row.get("cr673_key", "")) for row in existing_rows}
    print(f"Found {len(existing_keys)} existing settings in Dataverse\n")

    created = 0
    skipped = 0

    for item in SEED_DATA:
        key = item["key"]
        if key in existing_keys:
            print(f"  [SKIP] {key} (already exists)")
            skipped += 1
            continue

        row_data = {
            "Key": key,
            "Value": str(item["value"]),
            "Label": item["label"],
            "Section": item["section"],
            "Sub Section": item.get("sub_section", ""),
            "Data Type": item["data_type"],
            "Description": item.get("description", ""),
            "Is Editable": True if item.get("is_editable", True) else False,
            "Is Sensitive": True if item.get("is_sensitive", False) else False,
        }

        try:
            client.insert_row(
                SYSTEM_SETTINGS_TABLE_API,
                row_data,
                table_logical_name=SYSTEM_SETTINGS_TABLE_LOGICAL,
                use_display_names=True,
            )
            print(f"  [CREATE] {key}")
            created += 1
        except Exception as e:
            print(f"  [ERROR] {key}: {e}")

    print(f"\nDone! Created: {created}, Skipped: {skipped}, Total: {len(SEED_DATA)}")


def update_existing_rows():
    """Update section, sub_section, and description for existing rows. Delete removed keys."""
    print("=" * 60)
    print("Updating existing settings (sections + sub_sections + descriptions)")
    print("=" * 60)

    client = DataverseClient(TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL)

    seed_lookup = {item["key"]: item for item in SEED_DATA}

    existing_rows = client.get_all_rows(
        SYSTEM_SETTINGS_TABLE_API,
        table_logical_name=SYSTEM_SETTINGS_TABLE_LOGICAL,
        use_display_names=True,
    )

    updated = 0
    deleted = 0

    for row in existing_rows:
        key = row.get("Key", row.get("cr673_key", ""))
        record_id = row.get("Bahra System Settings", row.get("cr673_bahra_system_settingsid", ""))
        if not key or not record_id:
            continue

        # Delete removed keys
        if key in REMOVED_KEYS:
            try:
                client.delete_row(SYSTEM_SETTINGS_TABLE_API, record_id)
                print(f"  [DELETE] {key}")
                deleted += 1
            except Exception as e:
                print(f"  [ERROR deleting] {key}: {e}")
            continue

        # Update section/sub_section/description if changed
        if key in seed_lookup:
            seed = seed_lookup[key]
            current_section = row.get("Section", row.get("cr673_section", ""))
            current_sub = row.get("Sub Section", row.get("cr6db_sub_section", ""))
            current_desc = row.get("Description", row.get("cr673_description", ""))

            new_section = seed["section"]
            new_sub = seed.get("sub_section", "")
            new_desc = seed.get("description", "")

            # Build update payload only for changed fields
            updates = {}
            if current_section != new_section:
                updates["Section"] = new_section
            if current_sub != new_sub:
                updates["Sub Section"] = new_sub
            if current_desc != new_desc:
                updates["Description"] = new_desc

            if updates:
                try:
                    client.update_row(
                        SYSTEM_SETTINGS_TABLE_API,
                        record_id,
                        updates,
                        table_logical_name=SYSTEM_SETTINGS_TABLE_LOGICAL,
                        use_display_names=True,
                    )
                    changed = ", ".join(updates.keys())
                    print(f"  [UPDATE] {key}: {changed}")
                    updated += 1
                except Exception as e:
                    print(f"  [ERROR updating] {key}: {e}")

    print(f"\nDone! Updated: {updated}, Deleted: {deleted}")


if __name__ == "__main__":
    if "--update" in sys.argv:
        update_existing_rows()
    else:
        seed_settings()
        print("\nRun with --update to update sections/sub_sections/descriptions of existing rows")
