/**
 * Static context metadata for system settings.
 * Provides impact level, feature-area tags, and related settings
 * so admins can understand what each setting affects.
 *
 * Only includes settings visible in the portal (Admin section).
 * Developer settings are managed via config/config.py only.
 */

export type ImpactLevel = 'info' | 'warning' | 'critical'

export interface SettingContext {
  impact: ImpactLevel
  tags: string[]
  relatedKeys?: string[]
}

export const SETTING_CONTEXT: Record<string, SettingContext> = {
  // ── Warning: changes user-facing behavior ───────────────────

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
  EMAIL_TO_NO_MATCHED_DATA: {
    impact: 'warning',
    tags: ['Email', 'RFP Processing'],
  },
  DECLINE_BUTTON_EMAILS: {
    impact: 'warning',
    tags: ['Email', 'RFP Processing'],
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
