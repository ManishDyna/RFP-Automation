"""
Role-based access control (RBAC) helper functions.

The user role is stored in the bahra_user table (cr673_bahra_users) in the 'role' column.
During authentication, the role is fetched from the database and stored in the session.
These functions check the role from the user dict which comes from the session.

Flow:
1. Database: cr673_bahra_users table -> role column
2. Authentication: authenticate_user() fetches role from database
3. Session: role stored in request.session["user"]["role"]
4. Role checking: These functions read from user.get("role")
"""

def is_admin(user: dict) -> bool:
    """
    Check if user has Admin role.
    Role is read from user dict which comes from session (originally from bahra_user table).
    """
    if not user:
        return False
    role = (user.get("role") or "").strip()
    return role.lower() == "admin"

def is_rfp_bidder(user: dict) -> bool:
    """
    Check if user has RFP Bidder role.
    Role is read from user dict which comes from session (originally from bahra_user table).
    """
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

