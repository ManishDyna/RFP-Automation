"""
Role service - Role-based access control (RBAC) helper functions.

Backward-compatible wrapper that delegates to the dynamic RBAC system
(dynamic_role_service.py) while preserving the original API surface.

All existing calls to is_admin(), is_rfp_bidder(), and has_access_to_feature()
continue to work unchanged.
"""

from services.dynamic_role_service import user_has_permission, get_user_permissions


# Map old feature names to new granular permission keys
_FEATURE_TO_PERMISSION = {
    "user_management": "user_management.view",
    "sap_password": "sap_password.change",
    "sap_password_logs": "sap_password.view",
    "schedule_automation": "schedule_automation.manage",
    "analytics": "analytics.view",
}


def is_admin(user: dict) -> bool:
    """Check if user has Admin role."""
    if not user:
        return False
    role = (user.get("role") or "").strip()
    return role.lower() == "admin"


def is_rfp_bidder(user: dict) -> bool:
    """Check if user has RFP Bidder role."""
    if not user:
        return False
    role = (user.get("role") or "").strip()
    return role.lower() in ("rfpbidder", "rfp bidder")


def has_access_to_feature(user: dict, feature: str) -> bool:
    """
    Check if user has access to a specific feature.
    Delegates to the dynamic permission system.

    Features (backward compat):
        'user_management', 'sap_password', 'sap_password_logs',
        'schedule_automation', 'analytics'

    Also accepts direct permission keys like 'rfp.view', 'role_management.edit', etc.
    """
    if not user:
        return False

    # Map old feature name to new permission key, or pass through directly
    permission_key = _FEATURE_TO_PERMISSION.get(feature, feature)
    return user_has_permission(user, permission_key)
