"""
Dynamic Role Service - CRUD operations for roles and role-permission mappings.
Replaces the hardcoded RBAC in role_service.py with a Dataverse-backed dynamic system.

Roles are stored in cr673_bahra_roles.
Role-permission mappings are stored in cr673_bahra_role_permissions.
"""

import time
import json
import requests
import threading
from datetime import datetime, timezone
from typing import Optional, Dict, List

from helpers.core_helper import DATAVERSE
from services.system_settings_service import get_setting
from services.permission_definitions import PERMISSIONS, DEFAULT_ROLES


# ==================== CACHE ====================

_ROLE_PERMISSIONS_CACHE: Dict[str, Dict] = {}
# Structure: {"role_name_lower": {"permissions": ["perm1", "perm2"], "ts": timestamp}}
_CACHE_LOCK = threading.Lock()

_ROLES_LIST_CACHE = {"data": None, "ts": 0}
_ROLES_LIST_LOCK = threading.Lock()
_ROLES_CACHE_TTL = 300  # 5 minutes


def _invalidate_roles_list_cache():
    _ROLES_LIST_CACHE["data"] = None
    _ROLES_LIST_CACHE["ts"] = 0


def invalidate_role_cache(role_name: Optional[str] = None):
    """Clear cached permissions. If role_name given, clear only that role."""
    with _CACHE_LOCK:
        if role_name:
            _ROLE_PERMISSIONS_CACHE.pop(role_name.strip().lower(), None)
        else:
            _ROLE_PERMISSIONS_CACHE.clear()
    _invalidate_roles_list_cache()


def _get_cached_permissions(role_name: str) -> Optional[List[str]]:
    """Get cached permissions for a role, or None if expired/missing."""
    key = role_name.strip().lower()
    with _CACHE_LOCK:
        entry = _ROLE_PERMISSIONS_CACHE.get(key)
        if entry and (time.time() - entry["ts"]) < get_setting('RBAC_CACHE_TTL_SECONDS', 300):
            return entry["permissions"]
    return None


def _set_cached_permissions(role_name: str, permissions: List[str]):
    """Cache permissions for a role."""
    key = role_name.strip().lower()
    with _CACHE_LOCK:
        _ROLE_PERMISSIONS_CACHE[key] = {
            "permissions": permissions,
            "ts": time.time(),
        }


# ==================== COLUMN MAPPING HELPERS ====================

def _get_roles_column_mapping():
    return DATAVERSE.get_column_mapping(get_setting('ROLES_TABLE_LOGICAL', 'cr673_bahra_roles'))


def _get_perms_column_mapping():
    return DATAVERSE.get_column_mapping(get_setting('ROLE_PERMISSIONS_TABLE_LOGICAL', 'cr673_bahra_role_permissions'))


def _get_primary_id(table_logical: str) -> str:
    """Get primary ID attribute name for a table (cached)."""
    from helpers.metadata_cache import get_primary_id
    return get_primary_id(table_logical)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ==================== ROLE CRUD ====================

def list_roles(top: int = 100, filters: Optional[Dict[str, str]] = None, force_refresh: bool = False) -> List[Dict]:
    """List all roles from Dataverse with TTL caching (no-filter queries only)."""
    from time import time as _now
    now = _now()

    # Use cache for unfiltered queries
    if not force_refresh and not filters:
        if _ROLES_LIST_CACHE["data"] is not None and (now - _ROLES_LIST_CACHE["ts"]) < _ROLES_CACHE_TTL:
            return _ROLES_LIST_CACHE["data"]

    col_map = _get_roles_column_mapping()
    reverse_map = {v: k for k, v in col_map.items()}
    primary_id = _get_primary_id(get_setting('ROLES_TABLE_LOGICAL', 'cr673_bahra_roles'))

    # Build filter
    filter_parts = []
    if filters:
        for display_name, value in filters.items():
            if not value:
                continue
            logical = col_map.get(display_name, display_name)
            escaped = str(value).replace("'", "''")
            filter_parts.append(f"{logical} eq '{escaped}'")

    filter_expr = " and ".join(filter_parts) if filter_parts else None

    result = DATAVERSE.query_rows(
        table_api_name=get_setting('ROLES_TABLE_API', 'cr673_bahra_roleses'),
        filter_expr=filter_expr,
        top=top,
        table_logical_name=get_setting('ROLES_TABLE_LOGICAL', 'cr673_bahra_roles'),
        use_display_names=False,
    )
    rows = result.get("value", []) if isinstance(result, dict) else []

    mapped = []
    for row in rows:
        item = {}
        for key, value in row.items():
            if key.startswith("@") or key.startswith("_"):
                continue
            display = reverse_map.get(key, key)
            item[display] = value
        if primary_id and primary_id in row:
            item["record_id"] = row[primary_id]
        mapped.append(item)

    # Cache unfiltered results
    if not filters:
        with _ROLES_LIST_LOCK:
            _ROLES_LIST_CACHE["data"] = mapped
            _ROLES_LIST_CACHE["ts"] = now

    return mapped


def get_role(record_id: str) -> Optional[Dict]:
    """Get a single role by its record ID."""
    roles = list_roles(top=1000)
    for role in roles:
        if role.get("record_id") == record_id:
            return role
    return None


def get_role_by_name(name: str) -> Optional[Dict]:
    """Get a role by its name (case-insensitive)."""
    roles = list_roles(filters={"name": name})
    return roles[0] if roles else None


def create_role(payload: Dict) -> bool:
    """Create a new role in Dataverse."""
    data = dict(payload)
    data.setdefault("is_active", "true")
    data.setdefault("is_system", "false")
    data["created_date"] = _now_iso()
    data["update_date"] = _now_iso()

    # Ensure string types
    for key in data:
        data[key] = str(data[key])

    result = DATAVERSE.insert_row(
        table_api_name=get_setting('ROLES_TABLE_API', 'cr673_bahra_roleses'),
        data=data,
        table_logical_name=get_setting('ROLES_TABLE_LOGICAL', 'cr673_bahra_roles'),
        use_display_names=True,
    )
    _invalidate_roles_list_cache()
    return result


def update_role(record_id: str, updates: Dict) -> bool:
    """Update a role's name/description."""
    updates["update_date"] = _now_iso()
    for key in updates:
        updates[key] = str(updates[key])

    result = DATAVERSE.update_row(
        table_api_name=get_setting('ROLES_TABLE_API', 'cr673_bahra_roleses'),
        record_id=record_id,
        data=updates,
        table_logical_name=get_setting('ROLES_TABLE_LOGICAL', 'cr673_bahra_roles'),
        use_display_names=True,
    )

    # Invalidate cache for this role
    role = get_role(record_id)
    if role:
        invalidate_role_cache(role.get("name"))

    return result


def delete_role(record_id: str) -> Dict:
    """
    Soft-delete a role (set is_active=False).
    Prevents deleting the Admin role.
    Returns {"ok": bool, "error": str}.
    """
    role = get_role(record_id)
    if not role:
        return {"ok": False, "error": "Role not found"}

    if (role.get("name", "")).lower() == "admin":
        return {"ok": False, "error": "Cannot delete the Admin role"}

    result = update_role(record_id, {"is_active": "false"})
    if role.get("name"):
        invalidate_role_cache(role["name"])

    return {"ok": result, "error": "" if result else "Failed to deactivate role"}


def toggle_role_status(record_id: str) -> Dict:
    """
    Toggle a role's active/inactive status.
    Prevents toggling the Admin role.
    Returns {"ok": bool, "is_active": bool, "error": str}.
    """
    role = get_role(record_id)
    if not role:
        return {"ok": False, "is_active": False, "error": "Role not found"}

    if (role.get("name", "")).lower() == "admin":
        return {"ok": False, "is_active": True, "error": "Cannot toggle the Admin role"}

    currently_active = str(role.get("is_active", "true")).lower() != "false"
    new_status = "false" if currently_active else "true"

    result = update_role(record_id, {"is_active": new_status})
    if role.get("name"):
        invalidate_role_cache(role["name"])

    return {
        "ok": result,
        "is_active": not currently_active,
        "error": "" if result else "Failed to toggle role status",
    }


def hard_delete_role(record_id: str) -> Dict:
    """
    Permanently delete a role and all its permission mappings from Dataverse.
    Prevents deleting the Admin role.
    Returns {"ok": bool, "error": str}.
    """
    role = get_role(record_id)
    if not role:
        return {"ok": False, "error": "Role not found"}

    if (role.get("name", "")).lower() == "admin":
        return {"ok": False, "error": "Cannot permanently delete the Admin role"}

    role_name = role.get("name", "")

    # 1. Delete all permission mappings for this role
    if role_name:
        _delete_role_permissions(role_name)
        invalidate_role_cache(role_name)

    # 2. Hard-delete the role record itself
    try:
        DATAVERSE.delete_row(
            table_api_name=get_setting('ROLES_TABLE_API', 'cr673_bahra_roleses'),
            record_id=record_id,
        )
        return {"ok": True, "error": ""}
    except Exception as e:
        return {"ok": False, "error": f"Failed to permanently delete role: {str(e)}"}


# ==================== ROLE-PERMISSION MAPPING ====================

def get_role_permissions(role_name: str) -> List[str]:
    """
    Get all permission keys for a role. Results are cached.
    Returns list of permission_key strings.
    """
    if not role_name:
        return []

    # Check cache first
    cached = _get_cached_permissions(role_name)
    if cached is not None:
        return cached

    # Query Dataverse
    col_map = _get_perms_column_mapping()
    role_name_logical = col_map.get("role_name", "cr673_role_name")
    perm_key_logical = col_map.get("permission_key", "cr673_permission_key")
    escaped_name = role_name.replace("'", "''")
    filter_expr = f"{role_name_logical} eq '{escaped_name}'"

    try:
        result = DATAVERSE.query_rows(
            table_api_name=get_setting('ROLE_PERMISSIONS_TABLE_API', 'cr673_bahra_role_permissionses'),
            filter_expr=filter_expr,
            select=perm_key_logical,
            top=5000,
            table_logical_name=get_setting('ROLE_PERMISSIONS_TABLE_LOGICAL', 'cr673_bahra_role_permissions'),
            use_display_names=False,
        )
        rows = result.get("value", []) if isinstance(result, dict) else []
        permissions = [row.get(perm_key_logical, "") for row in rows if row.get(perm_key_logical)]
    except Exception as e:
        print(f"[RBAC] Failed to fetch permissions for role '{role_name}': {e}")
        permissions = []

    _set_cached_permissions(role_name, permissions)
    return permissions


def get_all_permissions_count_by_role() -> Dict[str, int]:
    """
    Fetch ALL permission mappings in a single query and return counts grouped by role.
    Used to avoid N+1 queries when listing roles with their permission counts.
    """
    col_map = _get_perms_column_mapping()
    role_name_logical = col_map.get("role_name", "cr673_role_name")
    perm_key_logical = col_map.get("permission_key", "cr673_permission_key")

    try:
        result = DATAVERSE.query_rows(
            table_api_name=get_setting('ROLE_PERMISSIONS_TABLE_API', 'cr673_bahra_role_permissionses'),
            select=f"{role_name_logical},{perm_key_logical}",
            top=5000,
            table_logical_name=get_setting('ROLE_PERMISSIONS_TABLE_LOGICAL', 'cr673_bahra_role_permissions'),
            use_display_names=False,
        )
        rows = result.get("value", []) if isinstance(result, dict) else []
    except Exception as e:
        print(f"[RBAC] Failed to fetch all permissions: {e}")
        return {}

    counts: Dict[str, int] = {}
    for row in rows:
        role = row.get(role_name_logical, "")
        if role:
            counts[role] = counts.get(role, 0) + 1
    return counts


def set_role_permissions(role_id: str, role_name: str, permission_keys: List[str]) -> bool:
    """
    Replace all permissions for a role.
    Deletes existing mappings, then inserts new ones.
    """
    # 1. Delete existing permissions for this role
    _delete_role_permissions(role_name)

    # 2. Insert new permissions
    for perm_key in permission_keys:
        if perm_key not in PERMISSIONS:
            continue  # Skip invalid permission keys
        data = {
            "role_id": str(role_id),
            "role_name": str(role_name),
            "permission_key": str(perm_key),
            "created_date": _now_iso(),
        }
        try:
            DATAVERSE.insert_row(
                table_api_name=get_setting('ROLE_PERMISSIONS_TABLE_API', 'cr673_bahra_role_permissionses'),
                data=data,
                table_logical_name=get_setting('ROLE_PERMISSIONS_TABLE_LOGICAL', 'cr673_bahra_role_permissions'),
                use_display_names=True,
            )
        except Exception as e:
            print(f"[RBAC] Failed to insert permission '{perm_key}' for role '{role_name}': {e}")

    # 3. Invalidate cache
    invalidate_role_cache(role_name)
    return True


def _delete_role_permissions(role_name: str):
    """Delete all permission mappings for a role."""
    col_map = _get_perms_column_mapping()
    role_name_logical = col_map.get("role_name", "cr673_role_name")
    escaped_name = role_name.replace("'", "''")
    filter_expr = f"{role_name_logical} eq '{escaped_name}'"
    primary_id = _get_primary_id(get_setting('ROLE_PERMISSIONS_TABLE_LOGICAL', 'cr673_bahra_role_permissions'))

    try:
        result = DATAVERSE.query_rows(
            table_api_name=get_setting('ROLE_PERMISSIONS_TABLE_API', 'cr673_bahra_role_permissionses'),
            filter_expr=filter_expr,
            select=primary_id,
            top=5000,
            table_logical_name=get_setting('ROLE_PERMISSIONS_TABLE_LOGICAL', 'cr673_bahra_role_permissions'),
            use_display_names=False,
        )
        rows = result.get("value", []) if isinstance(result, dict) else []
        record_ids = [row.get(primary_id) for row in rows if row.get(primary_id)]

        if record_ids:
            table_api = get_setting('ROLE_PERMISSIONS_TABLE_API', 'cr673_bahra_role_permissionses')
            DATAVERSE.batch_delete(table_api, record_ids)
    except Exception as e:
        print(f"[RBAC] Failed to delete permissions for role '{role_name}': {e}")


# ==================== PERMISSION CHECKING ====================

def get_user_permissions(user: dict) -> List[str]:
    """
    Get the list of permission keys for a user based on their role.
    Admin users get all permissions.
    """
    if not user:
        return []

    role_name = (user.get("role") or "").strip()
    if not role_name:
        return []

    return get_role_permissions(role_name)


def user_has_permission(user: dict, permission_key: str) -> bool:
    """
    Check if a user has a specific permission.
    This is the primary authorization check function.
    """
    if not user:
        return False

    role_name = (user.get("role") or "").strip()
    if not role_name:
        return False

    # Check session-cached permissions first (faster than DB)
    session_perms = user.get("permissions")
    if isinstance(session_perms, list):
        return permission_key in session_perms

    # Fallback: check from Dataverse (via cache)
    permissions = get_role_permissions(role_name)
    return permission_key in permissions


# ==================== SEEDING ====================

def seed_default_roles() -> Dict:
    """
    Create default roles and their permissions if they don't exist.
    Returns {"created": [...], "skipped": [...], "errors": [...]}.
    """
    result = {"created": [], "skipped": [], "errors": []}

    for role_name, config in DEFAULT_ROLES.items():
        existing = get_role_by_name(role_name)
        if existing:
            # Role exists - update permissions if needed
            rid = existing.get("record_id")
            if rid:
                set_role_permissions(rid, role_name, config["permissions"])
                result["skipped"].append(f"{role_name} (exists, permissions synced)")
            continue

        # Create role
        try:
            success = create_role({
                "name": role_name,
                "description": config["description"],
                "is_system": str(config.get("is_system", False)).lower(),
            })
            if not success:
                result["errors"].append(f"Failed to create role: {role_name}")
                continue

            # Get the newly created role to get its record_id
            new_role = get_role_by_name(role_name)
            if new_role and new_role.get("record_id"):
                set_role_permissions(
                    new_role["record_id"],
                    role_name,
                    config["permissions"],
                )
                result["created"].append(role_name)
            else:
                result["errors"].append(f"Created role '{role_name}' but couldn't fetch record_id")
        except Exception as e:
            result["errors"].append(f"Error creating '{role_name}': {str(e)}")

    return result
