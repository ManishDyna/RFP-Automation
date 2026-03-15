"""
Permission Definitions - Single source of truth for all system permissions.
Each permission is a dot-separated key: "module.action"
"""

# All available permissions in the system
PERMISSIONS = {
    # User Management
    "user_management.view": "View user list",
    "user_management.create": "Create new users",
    "user_management.edit": "Edit existing users",
    "user_management.delete": "Delete users",
    "user_management.activate": "Activate/deactivate users",

    # Role Management
    "role_management.view": "View roles and permissions",
    "role_management.create": "Create new roles",
    "role_management.edit": "Edit roles and assign permissions",
    "role_management.delete": "Delete roles",

    # SAP
    "sap_password.view": "View SAP password logs",
    "sap_password.change": "Change SAP password",

    # Schedule
    "schedule_automation.view": "View automation schedules",
    "schedule_automation.manage": "Create/edit/delete schedules",

    # Analytics
    "analytics.view": "View analytics dashboard",

    # RFP Operations
    "rfp.view": "View RFP insights and details",
    "rfp.download": "Download RFPs from portal",
    "rfp.submit": "Submit RFPs",
    "rfp.decline": "Decline RFPs",

    # Dashboard
    "dashboard.view": "View main dashboard",

    # Logs
    "logs.view": "View automation activity logs",
    "audit_logs.view": "View audit trail logs",

    # Material Insights
    "material_insights.view": "View material insights",

    # Master Data Management
    "master_data.view":   "View material codes, keywords, and RFP team assignments",
    "master_data.create": "Add new material codes, keywords, or RFP team members",
    "master_data.edit":   "Edit material codes, keywords, or RFP team members",
    "master_data.delete": "Delete material codes, keywords, or RFP team members",

    # System Settings
    "system_settings.view": "View system settings and configuration",
    "system_settings.edit": "Edit system settings and configuration",
}

# Group permissions by module for UI display
PERMISSION_GROUPS = {}
for key, description in PERMISSIONS.items():
    module = key.split(".")[0]
    if module not in PERMISSION_GROUPS:
        PERMISSION_GROUPS[module] = {}
    PERMISSION_GROUPS[module][key] = description

# Human-readable module names for UI
MODULE_LABELS = {
    "user_management": "User Management",
    "role_management": "Role Management",
    "sap_password": "SAP Password",
    "schedule_automation": "Schedule & Automation",
    "analytics": "Analytics",
    "rfp": "RFP Operations",
    "dashboard": "Dashboard",
    "logs": "Activity Logs",
    "audit_logs": "Audit Trail",
    "material_insights": "Material Insights",
    "master_data": "Master Data Management",
    "system_settings": "System Settings",
}

# Default role templates for seeding
DEFAULT_ROLES = {
    "Admin": {
        "description": "Full system access - all permissions granted",
        "is_system": True,
        "permissions": list(PERMISSIONS.keys()),
    },
    "RFP Bidder": {
        "description": "Can view and work with RFPs, restricted from admin features",
        "is_system": True,
        "permissions": [
            "rfp.view",
            "rfp.download",
            "rfp.submit",
            "rfp.decline",
            "dashboard.view",
            "logs.view",
            "material_insights.view",
        ],
    },
}
