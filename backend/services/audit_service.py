"""
Audit Service - Logs all authentication, user management, and role events
to the cr673_bahra_audit_logs Dataverse table.

Events are logged in a fire-and-forget manner to never block main operations.
"""

import threading
from datetime import datetime, timezone
from typing import Optional, Dict, List

from helpers.core_helper import DATAVERSE
from services.system_settings_service import get_setting


# ==================== AUDIT EVENT CONSTANTS ====================

class AuditCategory:
    AUTH = "AUTH"
    USER = "USER"
    ROLE = "ROLE"
    RFP = "RFP"
    SYSTEM = "SYSTEM"


class AuditAction:
    # Auth
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    LOGIN_FAILED = "LOGIN_FAILED"
    PASSWORD_CHANGED = "PASSWORD_CHANGED"
    PASSWORD_RESET = "PASSWORD_RESET"
    # User
    USER_CREATED = "USER_CREATED"
    USER_UPDATED = "USER_UPDATED"
    USER_DELETED = "USER_DELETED"
    USER_ACTIVATED = "USER_ACTIVATED"
    USER_DEACTIVATED = "USER_DEACTIVATED"
    USER_UNLOCKED = "USER_UNLOCKED"
    # Role
    ROLE_CREATED = "ROLE_CREATED"
    ROLE_UPDATED = "ROLE_UPDATED"
    ROLE_DELETED = "ROLE_DELETED"
    ROLE_PERMISSIONS_UPDATED = "ROLE_PERMISSIONS_UPDATED"
    # System
    SEED_ROLES = "SEED_ROLES"
    SETTING_UPDATED = "SETTING_UPDATED"
    SETTING_REVEALED = "SETTING_REVEALED"


# Display columns expected on the Dataverse table
DISPLAY_COLUMNS = [
    "action",
    "category",
    "actor_email",
    "actor_name",
    "target_type",
    "target_id",
    "details",
    "ip_address",
    "created_date",
]


# ==================== WRITE (fire-and-forget) ====================

def log_event(
    action: str,
    category: str,
    actor_email: str = "",
    actor_name: str = "",
    target_type: str = "",
    target_id: str = "",
    details: str = "",
    ip_address: str = "",
):
    """
    Insert an audit log entry into Dataverse.
    Runs in a background thread so it never blocks the caller.
    """
    row = {
        "action": str(action),
        "category": str(category),
        "actor_email": str(actor_email),
        "actor_name": str(actor_name),
        "target_type": str(target_type),
        "target_id": str(target_id),
        "details": str(details)[:4000],  # Truncate to avoid Dataverse limits
        "ip_address": str(ip_address),
        "created_date": datetime.now(timezone.utc).isoformat(),
    }

    def _insert():
        try:
            DATAVERSE.insert_row(
                table_api_name=get_setting('AUDIT_LOG_TABLE_API', 'cr673_bahra_audit_logses'),
                data=row,
                table_logical_name=get_setting('AUDIT_LOG_TABLE_LOGICAL', 'cr673_bahra_audit_logs'),
                use_display_names=True,
            )
        except Exception as e:
            print(f"[AUDIT] Failed to log event: {e}")

    thread = threading.Thread(target=_insert, daemon=True)
    thread.start()


# ==================== READ (paginated queries) ====================

def _get_column_mapping():
    """Get and cache column mapping for audit log table."""
    return DATAVERSE.get_column_mapping(get_setting('AUDIT_LOG_TABLE_LOGICAL', 'cr673_bahra_audit_logs'))


def _build_filter_parts(filters: Optional[Dict[str, str]] = None) -> List[str]:
    """Build OData filter parts from a dict of display_name: value."""
    if not filters:
        return []

    col_map = _get_column_mapping()
    parts = []

    for display_name, value in filters.items():
        if not value:
            continue
        logical = col_map.get(display_name, display_name)
        escaped = str(value).replace("'", "''")
        parts.append(f"{logical} eq '{escaped}'")

    return parts


def list_audit_logs(
    top: int = 50,
    skip: int = 0,
    filters: Optional[Dict[str, str]] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict]:
    """
    Query audit logs with pagination and filters.

    Args:
        top: Number of records to return
        skip: Number of records to skip (offset)
        filters: Dict of {display_column_name: value} for equality filters
        date_from: ISO date string for >= filter on created_date
        date_to: ISO date string for <= filter on created_date

    Returns:
        List of audit log records with display names
    """
    col_map = _get_column_mapping()
    reverse_map = {v: k for k, v in col_map.items()}

    # Build filter expression
    filter_parts = _build_filter_parts(filters)

    # Date range filters
    if date_from or date_to:
        created_date_logical = col_map.get("created_date", "cr673_created_date")
        if date_from:
            filter_parts.append(f"{created_date_logical} ge '{date_from}'")
        if date_to:
            filter_parts.append(f"{created_date_logical} le '{date_to}'")

    filter_expr = " and ".join(filter_parts) if filter_parts else None

    # Build select columns
    select_logical = []
    for dc in DISPLAY_COLUMNS:
        logical = col_map.get(dc)
        if logical:
            select_logical.append(logical)

    # Get primary key attribute
    try:
        meta_url = f"{DATAVERSE.api_url}EntityDefinitions(LogicalName='{get_setting('AUDIT_LOG_TABLE_LOGICAL', 'cr673_bahra_audit_logs')}')?$select=PrimaryIdAttribute"
        import requests as req
        resp = req.get(meta_url, headers=DATAVERSE._headers())
        primary_id_attr = resp.json().get("PrimaryIdAttribute", "")
        if primary_id_attr and primary_id_attr not in select_logical:
            select_logical.append(primary_id_attr)
    except Exception:
        primary_id_attr = ""

    select_expr = ",".join(select_logical) if select_logical else None

    # Order by created_date desc
    created_logical = col_map.get("created_date", "cr673_created_date")
    order_by = f"{created_logical} desc"

    result = DATAVERSE.query_rows(
        table_api_name=get_setting('AUDIT_LOG_TABLE_API', 'cr673_bahra_audit_logses'),
        filter_expr=filter_expr,
        select=select_expr,
        top=top,
        skip=skip,
        order_by=order_by,
        table_logical_name=get_setting('AUDIT_LOG_TABLE_LOGICAL', 'cr673_bahra_audit_logs'),
        use_display_names=False,  # We handle mapping ourselves
    )

    rows = result.get("value", []) if isinstance(result, dict) else []

    # Map logical names back to display names
    mapped_rows = []
    for row in rows:
        mapped = {}
        for logical_key, value in row.items():
            if logical_key.startswith("@") or logical_key.startswith("_"):
                continue
            display_key = reverse_map.get(logical_key, logical_key)
            mapped[display_key] = value
        # Ensure record_id is set
        if primary_id_attr and primary_id_attr in row:
            mapped["record_id"] = row[primary_id_attr]
        mapped_rows.append(mapped)

    return mapped_rows


def count_audit_logs(
    filters: Optional[Dict[str, str]] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> int:
    """Count audit log records matching the given filters."""
    filter_parts = _build_filter_parts(filters)

    col_map = _get_column_mapping()
    if date_from or date_to:
        created_date_logical = col_map.get("created_date", "cr673_created_date")
        if date_from:
            filter_parts.append(f"{created_date_logical} ge '{date_from}'")
        if date_to:
            filter_parts.append(f"{created_date_logical} le '{date_to}'")

    filter_expr = " and ".join(filter_parts) if filter_parts else None

    try:
        return DATAVERSE.count_rows(
            table_api_name=get_setting('AUDIT_LOG_TABLE_API', 'cr673_bahra_audit_logses'),
            filter_expr=filter_expr,
            table_logical_name=get_setting('AUDIT_LOG_TABLE_LOGICAL', 'cr673_bahra_audit_logs'),
            use_display_names=False,
        )
    except Exception as e:
        print(f"[AUDIT] Count failed: {e}")
        return 0
