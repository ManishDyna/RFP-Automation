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

    # Role Management
    "role_management.view": "View roles and permissions",
    "role_management.create": "Create new roles",
    "role_management.edit": "Edit roles and assign permissions",
    "role_management.delete": "Delete roles",

    # SAP
    "sap_password.view": "View SAP password logs",
    "sap_password.change": "Change SAP password",

    # Schedule
    "schedule_automation.manage": "Manage automation schedules",

    # Analytics
    "analytics.view": "View analytics dashboard",

    # RFP Operations
    "rfp.view": "View RFP insights and details",
    "rfp.download": "Download RFPs from portal",
    "rfp.submit": "Submit RFPs",
    "rfp.decline": "Decline RFPs",
    "rfp.open.view": "View Open RFP reminder tracker page",
    "rfp.open.remind": "Send reminder emails to RFP team members who haven't responded",

    # Dashboard
    "dashboard.view": "View main dashboard",

    # Logs
    "logs.view": "View automation activity logs",
    "audit_logs.view": "View audit trail logs",

    # Material Insights
    "material_insights.view": "View material insights",

    # Master Data — Material Master
    "material_master.view":   "View material codes",
    "material_master.create": "Add new material codes",
    "material_master.edit":   "Edit material codes",
    "material_master.delete": "Delete material codes",

    # Master Data — Keyword Master
    "keyword_master.view":   "View keywords",
    "keyword_master.create": "Add new keywords",
    "keyword_master.edit":   "Edit keywords",
    "keyword_master.delete": "Delete keywords",

    # Master Data — RFP Team
    "rfp_team.view":   "View RFP team assignments",
    "rfp_team.create": "Add RFP team members",
    "rfp_team.edit":   "Edit RFP team members",
    "rfp_team.delete": "Delete RFP team members",

    # Master Data — Column Configuration
    "column_config.view":   "View column configuration",
    "column_config.create": "Add column definitions",
    "column_config.edit":   "Edit column definitions",
    "column_config.delete": "Delete column definitions",

    # System Settings
    "system_settings.view": "View system settings and configuration",
    "system_settings.edit": "Edit system settings and configuration",
}

# Group permissions by module (kept for backward compatibility)
PERMISSION_GROUPS = {}
for key, description in PERMISSIONS.items():
    module = key.split(".")[0]
    if module not in PERMISSION_GROUPS:
        PERMISSION_GROUPS[module] = {}
    PERMISSION_GROUPS[module][key] = description

# Human-readable module names (kept for backward compatibility)
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
    "material_master": "Material Master",
    "keyword_master": "Keyword Master",
    "rfp_team": "RFP Team",
    "column_config": "Column Configuration",
    "system_settings": "System Settings",
}

# --------------------------------------------------------------------------
# Permission Categories — mirrors sidebar layout for role creation/edit UI
# --------------------------------------------------------------------------
PERMISSION_CATEGORIES = {
    "sidebar_menus": {
        "label": "Sidebar Menus",
        "permissions": {
            "dashboard.view":           "Dashboard",
            "rfp.view":                 "RFP Insights",
            "material_insights.view":   "Material Insights",
            "logs.view":                "Activity Logs",
            "rfp.open.view":            "Open RFP",
            "analytics.view":           "Analytics",
            "sap_password.view":        "SAP Logs",
            "system_settings.view":     "View System Settings",
            "audit_logs.view":          "Audit Logs",
            "schedule_automation.manage": "Schedule & Automation",
        },
    },
    "rfp_operations": {
        "label": "RFP Operations",
        "permissions": {
            "rfp.download":    "Download RFP",
            "rfp.submit":      "Submit RFP",
            "rfp.decline":     "Decline RFP",
            "rfp.open.remind": "Send RFP Reminder",
        },
    },
    "user_management": {
        "label": "User Management",
        "permissions": {
            "user_management.view":   "View Users",
            "user_management.create": "Create Users",
            "user_management.edit":   "Edit Users",
            "user_management.delete": "Delete Users",
        },
    },
    "role_management": {
        "label": "Role Management",
        "permissions": {
            "role_management.view":   "View Roles",
            "role_management.create": "Create Roles",
            "role_management.edit":   "Edit Roles",
            "role_management.delete": "Delete Roles",
        },
    },
    "master_data": {
        "label": "Master Data",
        "permissions": {
            "material_master.view":   "View Material Master",
            "material_master.create": "Add Material Codes",
            "material_master.edit":   "Edit Material Codes",
            "material_master.delete": "Delete Material Codes",
            "keyword_master.view":    "View Keyword Master",
            "keyword_master.create":  "Add Keywords",
            "keyword_master.edit":    "Edit Keywords",
            "keyword_master.delete":  "Delete Keywords",
            "rfp_team.view":          "View RFP Team",
            "rfp_team.create":        "Add RFP Team Members",
            "rfp_team.edit":          "Edit RFP Team Members",
            "rfp_team.delete":        "Delete RFP Team Members",
            "column_config.view":     "View Column Configuration",
            "column_config.create":   "Add Column Definitions",
            "column_config.edit":     "Edit Column Definitions",
            "column_config.delete":   "Delete Column Definitions",
        },
    },
    "system_settings": {
        "label": "System Settings",
        "permissions": {
            "system_settings.edit": "Edit System Settings",
        },
    },
    "sap_password": {
        "label": "SAP Password",
        "permissions": {
            "sap_password.change": "Change SAP Password",
        },
    },
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
            "rfp.open.view",
            "dashboard.view",
            "logs.view",
            "material_insights.view",
        ],
    },
}
