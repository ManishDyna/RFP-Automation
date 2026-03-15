"""
User Lifecycle Service - Manages user account status, lockout, and password policies.
Backed by the cr673_bahra_user_status Dataverse table.
"""

import re
import requests
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict

from helpers.core_helper import DATAVERSE
from services.system_settings_service import get_setting


# ==================== HELPERS ====================

def _get_column_mapping():
    return DATAVERSE.get_column_mapping(get_setting('USER_STATUS_TABLE_LOGICAL', 'cr673_bahra_user_status'))


def _build_user_filter(user_id: str) -> str:
    """Build OData filter using display name (query_rows maps it to logical name)."""
    return f"user_id eq '{user_id}'"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_display(row: dict) -> dict:
    """Convert a Dataverse row to display-name dict."""
    col_map = _get_column_mapping()
    reverse_map = {v: k for k, v in col_map.items()}
    result = {}
    for key, value in row.items():
        if key.startswith("@") or key.startswith("_"):
            continue
        display = reverse_map.get(key, key)
        result[display] = value
    return result


# ==================== GET / CREATE STATUS ====================

def get_user_status(user_id: str) -> Optional[Dict]:
    """
    Get the user_status record for a user. Returns None if not found.
    """
    filter_expr = _build_user_filter(user_id)
    result = DATAVERSE.query_rows(
        table_api_name=get_setting('USER_STATUS_TABLE_API', 'cr673_bahra_user_statuses'),
        filter_expr=filter_expr,
        top=1,
        table_logical_name=get_setting('USER_STATUS_TABLE_LOGICAL', 'cr673_bahra_user_status'),
        use_display_names=True,
    )
    rows = result.get("value", []) if isinstance(result, dict) else []
    if not rows:
        return None
    return rows[0]


def get_or_create_user_status(user_id: str) -> Dict:
    """Get existing status or create a default one for the user."""
    status = get_user_status(user_id)
    if status:
        return status

    # Create default status
    data = {
        "user_id": str(user_id),
        "is_active": "true",
        "failed_attempts": "0",
        "locked_until": "",
        "last_login": "",
        "password_changed_at": "",
        "deactivated_by": "",
        "deactivated_at": "",
        "created_date": _now_iso(),
        "update_date": _now_iso(),
    }
    DATAVERSE.insert_row(
        table_api_name=get_setting('USER_STATUS_TABLE_API', 'cr673_bahra_user_statuses'),
        data=data,
        table_logical_name=get_setting('USER_STATUS_TABLE_LOGICAL', 'cr673_bahra_user_status'),
        use_display_names=True,
    )
    # Re-fetch to get record_id
    return get_user_status(user_id) or data


def _get_status_record_id(user_id: str) -> Optional[str]:
    """Get the Dataverse record ID for a user's status record."""
    col_map = _get_column_mapping()
    user_id_logical = col_map.get("user_id", "cr673_user_id")
    filter_expr = f"{user_id_logical} eq '{user_id}'"

    # Get primary key attribute
    try:
        meta_url = f"{DATAVERSE.api_url}EntityDefinitions(LogicalName='{get_setting('USER_STATUS_TABLE_LOGICAL', 'cr673_bahra_user_status')}')?$select=PrimaryIdAttribute"
        resp = requests.get(meta_url, headers=DATAVERSE._headers())
        primary_id_attr = resp.json().get("PrimaryIdAttribute", "")
    except Exception:
        primary_id_attr = ""

    result = DATAVERSE.query_rows(
        table_api_name=get_setting('USER_STATUS_TABLE_API', 'cr673_bahra_user_statuses'),
        filter_expr=filter_expr,
        top=1,
        table_logical_name=get_setting('USER_STATUS_TABLE_LOGICAL', 'cr673_bahra_user_status'),
        use_display_names=False,
    )
    rows = result.get("value", []) if isinstance(result, dict) else []
    if rows and primary_id_attr:
        return rows[0].get(primary_id_attr)
    return None


def _update_status_field(user_id: str, updates: Dict) -> bool:
    """Update fields on a user's status record."""
    record_id = _get_status_record_id(user_id)
    if not record_id:
        # Create first, then update
        get_or_create_user_status(user_id)
        record_id = _get_status_record_id(user_id)
        if not record_id:
            return False

    updates["update_date"] = _now_iso()
    return DATAVERSE.update_row(
        table_api_name=get_setting('USER_STATUS_TABLE_API', 'cr673_bahra_user_statuses'),
        record_id=record_id,
        data=updates,
        table_logical_name=get_setting('USER_STATUS_TABLE_LOGICAL', 'cr673_bahra_user_status'),
        use_display_names=True,
    )


# ==================== LOGIN TRACKING ====================

def update_last_login(user_id: str) -> bool:
    """Record a successful login timestamp."""
    return _update_status_field(user_id, {"last_login": _now_iso()})


def record_failed_login(user_id: str) -> bool:
    """
    Increment failed_attempts. If threshold reached, set locked_until.
    Returns True if the account is now locked.
    """
    status = get_or_create_user_status(user_id)
    current_attempts = int(status.get("failed_attempts") or 0)
    new_attempts = current_attempts + 1

    updates = {"failed_attempts": str(new_attempts)}

    if new_attempts >= get_setting('ACCOUNT_LOCKOUT_THRESHOLD', 5):
        lock_until = datetime.now(timezone.utc) + timedelta(minutes=get_setting('ACCOUNT_LOCKOUT_DURATION_MINUTES', 30))
        updates["locked_until"] = lock_until.isoformat()

    _update_status_field(user_id, updates)
    return new_attempts >= get_setting('ACCOUNT_LOCKOUT_THRESHOLD', 5)


def clear_failed_attempts(user_id: str) -> bool:
    """Reset failed attempts and locked_until after successful login."""
    return _update_status_field(user_id, {
        "failed_attempts": "0",
        "locked_until": "",
    })


def is_account_locked(user_id: str) -> tuple:
    """
    Check if account is locked.
    Returns (is_locked: bool, minutes_remaining: int).
    """
    status = get_user_status(user_id)
    if not status:
        return False, 0

    locked_until = status.get("locked_until")
    if not locked_until:
        return False, 0

    try:
        lock_time = datetime.fromisoformat(locked_until.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        if now < lock_time:
            remaining = (lock_time - now).total_seconds() / 60
            return True, int(remaining) + 1
    except (ValueError, TypeError):
        pass

    return False, 0


# ==================== ACTIVATE / DEACTIVATE ====================

def is_user_active(user_id: str) -> bool:
    """Check if user account is active."""
    status = get_user_status(user_id)
    if not status:
        return True  # Default: active if no status record exists

    is_active = status.get("is_active")
    if isinstance(is_active, bool):
        return is_active
    return str(is_active).lower() in ("true", "1", "yes")


def activate_user(user_id: str, admin_email: str = "") -> bool:
    """Activate a user account."""
    return _update_status_field(user_id, {
        "is_active": "true",
        "deactivated_by": "",
        "deactivated_at": "",
    })


def deactivate_user(user_id: str, admin_email: str = "") -> bool:
    """Deactivate a user account."""
    return _update_status_field(user_id, {
        "is_active": "false",
        "deactivated_by": str(admin_email),
        "deactivated_at": _now_iso(),
    })


def unlock_user(user_id: str) -> bool:
    """Admin unlock - clear lockout and failed attempts."""
    return _update_status_field(user_id, {
        "failed_attempts": "0",
        "locked_until": "",
    })


# ==================== PASSWORD POLICIES ====================

def check_password_expiry(user_id: str) -> tuple:
    """
    Check if user's password has expired.
    Returns (is_expired: bool, days_since_change: int).
    """
    if get_setting('PASSWORD_MAX_AGE_DAYS', 90) <= 0:
        return False, 0

    status = get_user_status(user_id)
    if not status:
        return False, 0

    changed_at = status.get("password_changed_at")
    if not changed_at:
        return False, 0  # Never set = not enforced yet

    try:
        changed_time = datetime.fromisoformat(changed_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        days_since = (now - changed_time).days
        return days_since >= get_setting('PASSWORD_MAX_AGE_DAYS', 90), days_since
    except (ValueError, TypeError):
        return False, 0


def update_password_changed(user_id: str) -> bool:
    """Mark password as changed now."""
    return _update_status_field(user_id, {"password_changed_at": _now_iso()})


def validate_password_strength(password: str) -> tuple:
    """
    Validate password against configured policies.
    Returns (is_valid: bool, error_message: str).
    """
    if len(password) < get_setting('PASSWORD_MIN_LENGTH', 8):
        return False, f"Password must be at least {get_setting('PASSWORD_MIN_LENGTH', 8)} characters long"

    if get_setting('PASSWORD_REQUIRE_UPPERCASE', True) and not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"

    if get_setting('PASSWORD_REQUIRE_NUMBER', True) and not re.search(r"\d", password):
        return False, "Password must contain at least one number"

    return True, ""
