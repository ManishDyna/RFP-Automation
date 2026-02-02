"""
Role service - Role-based access control (RBAC) helper functions.
Moved from Dashboard/backend/role_management.py
"""


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
    Features: 'user_management', 'sap_password', 'sap_password_logs',
              'schedule_automation', 'analytics'
    """
    if not user:
        return False

    # Admin has access to everything
    if is_admin(user):
        return True

    # RFP Bidder restrictions
    if is_rfp_bidder(user):
        restricted_features = [
            'user_management',
            'sap_password',
            'sap_password_logs',
            'schedule_automation',
            'analytics'
        ]
        return feature not in restricted_features

    # Default: deny access for unknown roles
    return False
