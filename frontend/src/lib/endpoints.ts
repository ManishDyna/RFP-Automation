// =============================================================================
// Centralized API Endpoints Configuration
// =============================================================================
//
// All API endpoints should be defined here to maintain consistency
// and prevent path mismatches between frontend and backend.
//
// Backend Router Structure (from dashboard_main.py):
// ==================================================
//
// 1. routes/api.py - Router prefix: "/api"
//    - Auth: /api/login, /api/logout, /api/session/..., /api/forgot, /api/reset-password
//    - User management: /api/users/...
//    - Profile: /api/profile, /api/profile/update, /api/profile/change-password
//    - SAP: /api/sap/change-password
//    - Dashboard data (JSON): /api/dashboard/data, /api/dashboard/rfp-details, /api/dashboard/view-logs
//    - SAP logs: /api/dashboard/sap-password-logs
//    - Legacy schedule: /api/schedule/save
//
// 2. routes/automation.py - Router prefix: "/api" (added in dashboard_main.py)
//    - Automation: /api/automation/status
//    - RFP operations: /api/download-rfp, /api/decline-rfp, /api/sync_portal_data
//    - Submit RFP: /api/dashboard/submit-rfp, /api/submit-rfp
//
// 3. routes/dashboard.py - Router prefix: "/dashboard"
//    - HTML pages: /dashboard/, /dashboard/rfp-details, /dashboard/view-logs, etc.
//    - RFP status: /dashboard/rfp/status
//    - Schedule: /dashboard/schedule-automation/latest, /dashboard/schedule-automation
//    - Excel operations: /dashboard/view-excel/:id, /dashboard/save-excel/:id
//    - Materials: /dashboard/rfp/:id/materials
// =============================================================================

const API_PREFIX = '/api'
const DASHBOARD_PREFIX = '/dashboard'

export const ENDPOINTS = {
  // ==================== AUTH (routes/api.py) ====================
  AUTH: {
    LOGIN: `${API_PREFIX}/login`,
    LOGOUT: `${API_PREFIX}/logout`,
    FORGOT_PASSWORD: `${API_PREFIX}/forgot`,
    RESET_PASSWORD: `${API_PREFIX}/reset-password`,
    SESSION_REFRESH: `${API_PREFIX}/session/refresh`,
    SESSION_STATUS: `${API_PREFIX}/session/status`,
  },

  // ==================== USERS (routes/api.py) ====================
  USERS: {
    LIST: `${API_PREFIX}/users/user-list`,
    CREATE: `${API_PREFIX}/users/create`,
    UPDATE: (userId: string) => `${API_PREFIX}/users/update/${userId}`,
    DELETE: (userId: string) => `${API_PREFIX}/users/delete/${userId}`,
    ACTIVATE: (userId: string) => `${API_PREFIX}/users/${userId}/activate`,
    DEACTIVATE: (userId: string) => `${API_PREFIX}/users/${userId}/deactivate`,
    UNLOCK: (userId: string) => `${API_PREFIX}/users/${userId}/unlock`,
    STATUS: (userId: string) => `${API_PREFIX}/users/${userId}/status`,
  },

  // ==================== PROFILE (routes/api.py) ====================
  PROFILE: {
    GET: `${API_PREFIX}/profile`,
    UPDATE: `${API_PREFIX}/profile/update`,
    CHANGE_PASSWORD: `${API_PREFIX}/profile/change-password`,
  },

  // ==================== DASHBOARD DATA (routes/api.py - JSON responses) ====================
  DASHBOARD: {
    DATA: `${API_PREFIX}/dashboard/data`,
    RFP_DETAILS: `${API_PREFIX}/dashboard/rfp-details`,
    RFP_EXPORT: `${API_PREFIX}/dashboard/rfp-details/export`,
    SUBMIT_RFP: `${API_PREFIX}/dashboard/submit-rfp`,
    VALIDATE_RFP: `${API_PREFIX}/validate-rfp`,
    VIEW_LOGS: `${API_PREFIX}/dashboard/view-logs`,
    MATERIAL_INSIGHTS: `${API_PREFIX}/dashboard/material-insights`,
    MATERIAL_INSIGHTS_GROUPED: `${API_PREFIX}/dashboard/material-insights-grouped`,
    SAP_PASSWORD_LOGS: `${API_PREFIX}/dashboard/sap-password-logs`,
    VIEW_EXCEL: (rfpId: string) => `${DASHBOARD_PREFIX}/view-excel/${rfpId}`,
    SAVE_EXCEL: (rfpId: string) => `${DASHBOARD_PREFIX}/save-excel/${rfpId}`,
  },

  // ==================== SCHEDULE (routes/dashboard.py) ====================
  SCHEDULE: {
    GET_LATEST: `${DASHBOARD_PREFIX}/schedule-automation/latest`,
    SAVE: `${DASHBOARD_PREFIX}/schedule-automation`,
  },

  // ==================== RFP OPERATIONS ====================
  RFP: {
    // routes/automation.py (with /api prefix)
    DOWNLOAD: `${API_PREFIX}/download-rfp`,
    DECLINE: `${API_PREFIX}/decline-rfp`,
    SYNC_PORTAL: `${API_PREFIX}/sync_portal_data`,
    // routes/dashboard.py
    UPDATE_STATUS: `${DASHBOARD_PREFIX}/rfp/status`,
    GET_STATUS: (rfpId: string) => `${DASHBOARD_PREFIX}/rfp-status/${rfpId}`,
    GET_MATERIALS: (rfpId: string) => `${DASHBOARD_PREFIX}/rfp/${rfpId}/materials`,
    BATCH_MATCH_PERCENTAGES: `${DASHBOARD_PREFIX}/rfp/batch-match-percentages`,
    SUBMIT_FINAL: `${DASHBOARD_PREFIX}/submit-rfp-final`,
    GET_DYNAMIC_FORM: (rfpId: string) => `${DASHBOARD_PREFIX}/rfp/${rfpId}/dynamic-form-structure`,
  },

  // ==================== ERROR FILES (routes/api.py) ====================
  ERROR_FILES: {
    LIST: `${API_PREFIX}/error-files/list`,
    CONTENT: (filename: string) => `${API_PREFIX}/error-files/content/${encodeURIComponent(filename)}`,
    SCREENSHOT: (filename: string) => `${API_PREFIX}/error-files/screenshot/${encodeURIComponent(filename)}`,
  },

  // ==================== SAP (routes/api.py) ====================
  SAP: {
    CHANGE_PASSWORD: `${API_PREFIX}/sap/change-password`,
  },

  // ==================== AUTOMATION (routes/automation.py with /api prefix) ====================
  AUTOMATION: {
    STATUS: `${API_PREFIX}/automation/status`,
    DOWNLOAD_ALL_RFPS: `${DASHBOARD_PREFIX}/download-all-rfps`,
    RFP_REMINDER: `${API_PREFIX}/rfp-reminder`,
  },

  // ==================== ROLES (routes/role_routes.py) ====================
  ROLES: {
    LIST: `${API_PREFIX}/roles/list`,
    CREATE: `${API_PREFIX}/roles/create`,
    UPDATE: (id: string) => `${API_PREFIX}/roles/update/${id}`,
    DELETE: (id: string) => `${API_PREFIX}/roles/delete/${id}`,
    GET: (id: string) => `${API_PREFIX}/roles/${id}`,
    GET_PERMISSIONS: (id: string) => `${API_PREFIX}/roles/${id}/permissions`,
    SET_PERMISSIONS: (id: string) => `${API_PREFIX}/roles/${id}/permissions`,
    SEED: `${API_PREFIX}/roles/seed`,
  },

  // ==================== PERMISSIONS (routes/role_routes.py) ====================
  PERMISSIONS: {
    LIST: `${API_PREFIX}/permissions/list`,
  },

  // ==================== AUDIT LOGS (routes/api.py) ====================
  AUDIT_LOGS: {
    LIST: `${API_PREFIX}/audit-logs`,
  },

  // ==================== MASTER DATA (routes/master_data_routes.py) ====================
  MASTER_DATA: {
    MATERIALS: {
      LIST:   `${API_PREFIX}/master-data/materials/list`,
      CREATE: `${API_PREFIX}/master-data/materials/create`,
      UPDATE: (id: string) => `${API_PREFIX}/master-data/materials/update/${id}`,
      DELETE: (id: string) => `${API_PREFIX}/master-data/materials/delete/${id}`,
      IMPORT: `${API_PREFIX}/master-data/materials/import`,
    },
    KEYWORDS: {
      LIST:   `${API_PREFIX}/master-data/keywords/list`,
      CREATE: `${API_PREFIX}/master-data/keywords/create`,
      UPDATE: (id: string) => `${API_PREFIX}/master-data/keywords/update/${id}`,
      DELETE: (id: string) => `${API_PREFIX}/master-data/keywords/delete/${id}`,
      IMPORT: `${API_PREFIX}/master-data/keywords/import`,
    },
    RFP_TEAM: {
      LIST:   `${API_PREFIX}/master-data/rfp-team/list`,
      CREATE: `${API_PREFIX}/master-data/rfp-team/create`,
      UPDATE: (id: string) => `${API_PREFIX}/master-data/rfp-team/update/${id}`,
      DELETE: (id: string) => `${API_PREFIX}/master-data/rfp-team/delete/${id}`,
      IMPORT: `${API_PREFIX}/master-data/rfp-team/import`,
    },
    RFP_TEAM_COLUMNS: {
      LIST:    `${API_PREFIX}/master-data/rfp-team-columns/list`,
      ALL:     `${API_PREFIX}/master-data/rfp-team-columns/all`,
      CREATE:  `${API_PREFIX}/master-data/rfp-team-columns/create`,
      UPDATE:  (id: string) => `${API_PREFIX}/master-data/rfp-team-columns/update/${id}`,
      DELETE:  (id: string) => `${API_PREFIX}/master-data/rfp-team-columns/delete/${id}`,
      REORDER: `${API_PREFIX}/master-data/rfp-team-columns/reorder`,
    },
  },
  // ==================== SYSTEM SETTINGS (routes/system_settings_routes.py) ====================
  SYSTEM_SETTINGS: {
    LIST: `${API_PREFIX}/system-settings/list`,
    REVEAL: (key: string) => `${API_PREFIX}/system-settings/${encodeURIComponent(key)}/reveal`,
    UPDATE: (key: string) => `${API_PREFIX}/system-settings/${encodeURIComponent(key)}`,
    RELOAD_CACHE: `${API_PREFIX}/system-settings/reload-cache`,
    SEED: `${API_PREFIX}/system-settings/seed`,
  },
} as const

// Type helper for endpoint values
export type EndpointValue = string | ((...args: any[]) => string)
