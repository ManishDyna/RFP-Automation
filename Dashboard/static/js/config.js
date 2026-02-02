window.APP_CONFIG = Object.freeze({
    // Base URLs
    AUTOMATION_BASE_URL: 'http://localhost:8100',

    // Automation API endpoints (separate port)
    API_DOWNLOAD_RFP: 'http://localhost:8100/download-rfp',
    API_SUBMIT_RFP: 'http://localhost:8100/dashboard/submit-rfp',
    API_DECLINE_RFP: 'http://localhost:8100/decline-rfp',
    API_AUTOMATION_STATUS: 'http://localhost:8100/automation/status',
    API_SYNC_PORTAL: 'http://localhost:8100/sync_portal_data',

    // Dashboard-local endpoints
    API_PROFILE: '/dashboard/profile',
    API_SAP_PASSWORD: '/dashboard/sap-password',
    API_SCHEDULE_SAVE: '/dashboard/schedule-automation',
    API_SCHEDULE_LATEST: '/dashboard/schedule-automation/latest',

    // Timeouts and delays (milliseconds)
    AUTOMATION_TIMEOUT_MS: 300000, // 5 minutes
    LOGIN_REDIRECT_DELAY_MS: 1000,
    REFRESH_DELAY_MS: 1500,
    STATUS_RESET_DELAY_MS: 3000,
    ALERT_DISMISS_MS: 5000,
    
    // Session management timeouts (milliseconds)
    SESSION_TIMEOUT_MS: 7200000, // 2 hours
    IDLE_TIMEOUT_MS: 1800000, // 30 minutes
    SESSION_WARNING_MS: 300000, // 5 minutes
    SESSION_REFRESH_MS: 300000, // 5 minutes
});


