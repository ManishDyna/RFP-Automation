/**
 * Static context metadata for system settings.
 * Provides impact level, feature-area tags, and related settings
 * so admins/developers can understand what each setting affects.
 *
 * Settings not in this map render normally (no dot/tags).
 * Locked Dataverse table-name settings are intentionally excluded.
 */

export type ImpactLevel = 'info' | 'warning' | 'critical'

export interface SettingContext {
  impact: ImpactLevel
  tags: string[]
  relatedKeys?: string[]
}

export const SETTING_CONTEXT: Record<string, SettingContext> = {
  // ── Critical: system-breaking if wrong ──────────────────────

  EMAIL_MODE: {
    impact: 'critical',
    tags: ['Email', 'Automation'],
    relatedKeys: ['DEV_EMAIL', 'EMAIL_TO_NEW_RFP', 'EMAIL_TO_NO_NEW_RFP'],
  },
  TENANT_ID: {
    impact: 'critical',
    tags: ['SharePoint', 'Dataverse'],
    relatedKeys: ['CLIENT_ID', 'CLIENT_SECRET'],
  },
  CLIENT_ID: {
    impact: 'critical',
    tags: ['SharePoint', 'Dataverse'],
    relatedKeys: ['TENANT_ID', 'CLIENT_SECRET'],
  },
  CLIENT_SECRET: {
    impact: 'critical',
    tags: ['SharePoint', 'Dataverse'],
    relatedKeys: ['TENANT_ID', 'CLIENT_ID'],
  },
  RESOURCE_URL: {
    impact: 'critical',
    tags: ['Dataverse'],
    relatedKeys: ['TENANT_ID', 'CLIENT_ID', 'CLIENT_SECRET'],
  },
  FLOW_URL: {
    impact: 'critical',
    tags: ['Email', 'Automation'],
  },
  FORGOT_PASSWORD_FLOW_URL: {
    impact: 'critical',
    tags: ['Login & Security'],
  },

  // ── Warning: changes user-facing behavior ───────────────────

  DEV_EMAIL: {
    impact: 'warning',
    tags: ['Email'],
    relatedKeys: ['EMAIL_MODE'],
  },
  EMAIL_TO_NEW_RFP: {
    impact: 'warning',
    tags: ['Email', 'RFP Processing'],
  },
  EMAIL_TO_NO_NEW_RFP: {
    impact: 'warning',
    tags: ['Email', 'Automation'],
  },
  EMAIL_TO_RFP_DECLINED: {
    impact: 'warning',
    tags: ['Email', 'RFP Processing'],
  },
  EMAIL_TO_RFP_ERROR_IN_SUBMISSION: {
    impact: 'warning',
    tags: ['Email', 'RFP Processing'],
  },
  EMAIL_TO_RFP_ERROR_IN_DECLINE: {
    impact: 'warning',
    tags: ['Email', 'RFP Processing'],
  },
  EMAIL_TO_AUTOMATION_FAILURE: {
    impact: 'warning',
    tags: ['Email', 'Automation'],
  },
  EMAIL_TO_RFP_SUBMITTED: {
    impact: 'warning',
    tags: ['Email', 'RFP Processing'],
  },
  EMAIL_TO_RFP_SAVED_DRAFT: {
    impact: 'warning',
    tags: ['Email', 'RFP Processing'],
  },
  EMAIL_TO_RFP_REMINDER: {
    impact: 'warning',
    tags: ['Email', 'RFP Processing'],
  },
  EMAIL_TO_NEW_RFP_WITH_MATCH: {
    impact: 'warning',
    tags: ['Email', 'RFP Processing'],
  },
  EMAIL_TO_NO_MATCHED_DATA: {
    impact: 'warning',
    tags: ['Email', 'RFP Processing'],
  },
  EMAIL_TO_NEW_RFP_NO_MATCH: {
    impact: 'warning',
    tags: ['Email', 'RFP Processing'],
  },
  DECLINE_BUTTON_EMAILS: {
    impact: 'warning',
    tags: ['Email', 'RFP Processing'],
  },
  ACTIONABLE_CARD_ORIGINATOR_ID: {
    impact: 'warning',
    tags: ['Email', 'Automation'],
    relatedKeys: ['ACTIONABLE_CARD_CALLBACK_URL'],
  },
  ACTIONABLE_CARD_CALLBACK_URL: {
    impact: 'warning',
    tags: ['Email', 'Automation'],
    relatedKeys: ['ACTIONABLE_CARD_ORIGINATOR_ID'],
  },
  SESSION_TIMEOUT_SECONDS: {
    impact: 'warning',
    tags: ['Login & Security'],
  },
  ACCOUNT_LOCKOUT_THRESHOLD: {
    impact: 'warning',
    tags: ['Login & Security'],
    relatedKeys: ['ACCOUNT_LOCKOUT_DURATION_MINUTES'],
  },
  ACCOUNT_LOCKOUT_DURATION_MINUTES: {
    impact: 'warning',
    tags: ['Login & Security'],
    relatedKeys: ['ACCOUNT_LOCKOUT_THRESHOLD'],
  },
  PASSWORD_MIN_LENGTH: {
    impact: 'warning',
    tags: ['Login & Security'],
    relatedKeys: ['PASSWORD_REQUIRE_UPPERCASE', 'PASSWORD_REQUIRE_NUMBER'],
  },
  PASSWORD_REQUIRE_UPPERCASE: {
    impact: 'warning',
    tags: ['Login & Security'],
    relatedKeys: ['PASSWORD_MIN_LENGTH', 'PASSWORD_REQUIRE_NUMBER'],
  },
  PASSWORD_REQUIRE_NUMBER: {
    impact: 'warning',
    tags: ['Login & Security'],
    relatedKeys: ['PASSWORD_MIN_LENGTH', 'PASSWORD_REQUIRE_UPPERCASE'],
  },
  PASSWORD_MAX_AGE_DAYS: {
    impact: 'warning',
    tags: ['Login & Security'],
  },
  RBAC_CACHE_TTL_SECONDS: {
    impact: 'warning',
    tags: ['Login & Security'],
  },
  SHAREPOINT_HOSTNAME: {
    impact: 'warning',
    tags: ['SharePoint'],
    relatedKeys: ['SITE_PATH', 'DRIVE_NAME', 'SP_BASE_FOLDER'],
  },
  SITE_PATH: {
    impact: 'warning',
    tags: ['SharePoint'],
    relatedKeys: ['SHAREPOINT_HOSTNAME', 'DRIVE_NAME'],
  },
  DRIVE_NAME: {
    impact: 'warning',
    tags: ['SharePoint'],
    relatedKeys: ['SHAREPOINT_HOSTNAME', 'SITE_PATH'],
  },
  SP_BASE_FOLDER: {
    impact: 'warning',
    tags: ['SharePoint'],
    relatedKeys: ['SP_FAILURE_LOGS_FOLDER'],
  },

  // ── Info: safe, localized impact ────────────────────────────

  URL: {
    impact: 'info',
    tags: ['RFP Processing', 'Automation'],
  },
  COMPANY_NAME: {
    impact: 'info',
    tags: ['RFP Processing'],
    relatedKeys: ['COMPANY_OPTIONS'],
  },
  COMPANY_OPTIONS: {
    impact: 'info',
    tags: ['RFP Processing'],
    relatedKeys: ['COMPANY_NAME'],
  },
  VALID_RFP_STATUSES: {
    impact: 'info',
    tags: ['RFP Processing'],
  },
  OUTPUT_DIR: {
    impact: 'info',
    tags: ['Automation'],
    relatedKeys: ['FAILURE_LOGS_DIR'],
  },
  FAILURE_LOGS_DIR: {
    impact: 'info',
    tags: ['Automation'],
    relatedKeys: ['OUTPUT_DIR', 'SP_FAILURE_LOGS_FOLDER'],
  },
  SP_FAILURE_LOGS_FOLDER: {
    impact: 'info',
    tags: ['SharePoint', 'Automation'],
    relatedKeys: ['FAILURE_LOGS_DIR'],
  },
  DASHBOARD_TTL_SECONDS: {
    impact: 'info',
    tags: ['Dashboard'],
    relatedKeys: ['LOGS_TTL_SECONDS', 'SAP_LOGS_TTL_SECONDS'],
  },
  LOGS_TTL_SECONDS: {
    impact: 'info',
    tags: ['Dashboard'],
    relatedKeys: ['DASHBOARD_TTL_SECONDS', 'SAP_LOGS_TTL_SECONDS'],
  },
  SAP_LOGS_TTL_SECONDS: {
    impact: 'info',
    tags: ['Dashboard'],
    relatedKeys: ['DASHBOARD_TTL_SECONDS', 'LOGS_TTL_SECONDS'],
  },
}

/** Get context for a setting key, or undefined if not mapped */
export function getSettingContext(key: string): SettingContext | undefined {
  return SETTING_CONTEXT[key]
}

/** Impact level display config */
export const IMPACT_CONFIG: Record<ImpactLevel, { color: string; bgColor: string; label: string }> = {
  critical: { color: 'text-red-600', bgColor: 'bg-red-500', label: 'Critical' },
  warning: { color: 'text-amber-600', bgColor: 'bg-amber-400', label: 'Warning' },
  info: { color: 'text-blue-500', bgColor: 'bg-blue-400', label: 'Safe' },
}
