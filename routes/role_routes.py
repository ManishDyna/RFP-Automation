"""
Role Management API endpoints.
All routes are prefixed with /api/roles or /api/permissions.
"""

import json
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse

from middleware.auth import get_current_user, require_permission, require_admin, get_request_ip
from services.dynamic_role_service import (
    list_roles,
    get_role,
    create_role,
    update_role,
    delete_role,
    toggle_role_status,
    hard_delete_role,
    get_role_permissions,
    get_all_permissions_count_by_role,
    set_role_permissions,
    seed_default_roles,
    invalidate_role_cache,
)
from services.permission_definitions import PERMISSIONS, PERMISSION_GROUPS, MODULE_LABELS, PERMISSION_CATEGORIES
from services.audit_service import log_event, AuditAction, AuditCategory

router = APIRouter(prefix="/api", tags=["Roles"])


# ==================== ROLE CRUD ====================

@router.get("/roles/list")
async def api_list_roles(
    request: Request,
    user: dict = Depends(require_permission("role_management.view")),
):
    """List all roles."""
    try:
        roles = list_roles(top=1000)

        # Single bulk query instead of N+1 per-role queries
        perm_counts = get_all_permissions_count_by_role()
        for role in roles:
            role_name = role.get("name", "")
            role["permissions_count"] = perm_counts.get(role_name, 0)

        return JSONResponse({"ok": True, "roles": roles})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/roles/{record_id}")
async def api_get_role(
    request: Request,
    record_id: str,
    user: dict = Depends(require_permission("role_management.view")),
):
    """Get a single role with its permissions."""
    role = get_role(record_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    role_name = role.get("name", "")
    role["permissions"] = get_role_permissions(role_name)
    return JSONResponse({"ok": True, "role": role})


@router.post("/roles/create")
async def api_create_role(
    request: Request,
    user: dict = Depends(require_permission("role_management.create")),
):
    """Create a new role."""
    data = await request.json()
    name = (data.get("name") or "").strip()
    description = (data.get("description") or "").strip()
    permissions = data.get("permissions", [])

    if not name:
        raise HTTPException(status_code=400, detail="Role name is required")

    # Check for duplicate name
    from services.dynamic_role_service import get_role_by_name
    existing = get_role_by_name(name)
    if existing:
        raise HTTPException(status_code=409, detail=f"Role '{name}' already exists")

    success = create_role({"name": name, "description": description})
    if not success:
        raise HTTPException(status_code=500, detail="Failed to create role")

    # Set permissions if provided
    if permissions:
        new_role = get_role_by_name(name)
        if new_role and new_role.get("record_id"):
            set_role_permissions(new_role["record_id"], name, permissions)

    # Audit log
    log_event(
        action=AuditAction.ROLE_CREATED,
        category=AuditCategory.ROLE,
        actor_email=user.get("email", ""),
        actor_name=user.get("name", ""),
        target_type="Role",
        target_id=name,
        details=json.dumps({"name": name, "description": description, "permissions_count": len(permissions)}),
        ip_address=get_request_ip(request),
    )

    return JSONResponse({"ok": True, "message": f"Role '{name}' created successfully"})


@router.put("/roles/update/{record_id}")
async def api_update_role(
    request: Request,
    record_id: str,
    user: dict = Depends(require_permission("role_management.edit")),
):
    """Update a role's name and/or description."""
    data = await request.json()
    role = get_role(record_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    updates = {}
    if "name" in data:
        updates["name"] = (data["name"] or "").strip()
    if "description" in data:
        updates["description"] = (data["description"] or "").strip()

    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    success = update_role(record_id, updates)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update role")

    # Audit log
    log_event(
        action=AuditAction.ROLE_UPDATED,
        category=AuditCategory.ROLE,
        actor_email=user.get("email", ""),
        actor_name=user.get("name", ""),
        target_type="Role",
        target_id=record_id,
        details=json.dumps({"old_name": role.get("name"), "updates": updates}),
        ip_address=get_request_ip(request),
    )

    return JSONResponse({"ok": True, "message": "Role updated successfully"})


@router.delete("/roles/delete/{record_id}")
async def api_delete_role(
    request: Request,
    record_id: str,
    user: dict = Depends(require_permission("role_management.delete")),
):
    """Soft-delete a role. System roles cannot be deleted."""
    role = get_role(record_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    result = delete_role(record_id)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to delete role"))

    # Audit log
    log_event(
        action=AuditAction.ROLE_DELETED,
        category=AuditCategory.ROLE,
        actor_email=user.get("email", ""),
        actor_name=user.get("name", ""),
        target_type="Role",
        target_id=record_id,
        details=json.dumps({"name": role.get("name")}),
        ip_address=get_request_ip(request),
    )

    return JSONResponse({"ok": True, "message": f"Role '{role.get('name')}' deactivated"})


@router.patch("/roles/toggle-status/{record_id}")
async def api_toggle_role_status(
    request: Request,
    record_id: str,
    user: dict = Depends(require_permission("role_management.edit")),
):
    """Toggle a role's active/inactive status. System roles cannot be toggled."""
    role = get_role(record_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    result = toggle_role_status(record_id)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to toggle role status"))

    new_status = "activated" if result.get("is_active") else "deactivated"

    log_event(
        action=AuditAction.ROLE_UPDATED,
        category=AuditCategory.ROLE,
        actor_email=user.get("email", ""),
        actor_name=user.get("name", ""),
        target_type="Role",
        target_id=record_id,
        details=json.dumps({"name": role.get("name"), "action": new_status}),
        ip_address=get_request_ip(request),
    )

    return JSONResponse({"ok": True, "is_active": result.get("is_active"), "message": f"Role '{role.get('name')}' {new_status}"})


@router.delete("/roles/hard-delete/{record_id}")
async def api_hard_delete_role(
    request: Request,
    record_id: str,
    user: dict = Depends(require_permission("role_management.delete")),
):
    """Permanently delete a role and all its permissions. Cannot be undone."""
    role = get_role(record_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    role_name = role.get("name", "")
    result = hard_delete_role(record_id)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to permanently delete role"))

    log_event(
        action=AuditAction.ROLE_DELETED,
        category=AuditCategory.ROLE,
        actor_email=user.get("email", ""),
        actor_name=user.get("name", ""),
        target_type="Role",
        target_id=record_id,
        details=json.dumps({"name": role_name, "action": "permanently_deleted"}),
        ip_address=get_request_ip(request),
    )

    return JSONResponse({"ok": True, "message": f"Role '{role_name}' permanently deleted"})


# ==================== ROLE PERMISSIONS ====================

@router.get("/roles/{record_id}/permissions")
async def api_get_role_permissions(
    request: Request,
    record_id: str,
    user: dict = Depends(require_permission("role_management.view")),
):
    """Get all permission keys assigned to a role."""
    role = get_role(record_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    permissions = get_role_permissions(role.get("name", ""))
    return JSONResponse({"ok": True, "permissions": permissions})


@router.put("/roles/{record_id}/permissions")
async def api_set_role_permissions(
    request: Request,
    record_id: str,
    user: dict = Depends(require_permission("role_management.edit")),
):
    """Set (replace) all permissions for a role."""
    data = await request.json()
    permission_keys = data.get("permissions", [])

    role = get_role(record_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    role_name = role.get("name", "")
    old_permissions = get_role_permissions(role_name)

    set_role_permissions(record_id, role_name, permission_keys)

    # Audit log
    log_event(
        action=AuditAction.ROLE_PERMISSIONS_UPDATED,
        category=AuditCategory.ROLE,
        actor_email=user.get("email", ""),
        actor_name=user.get("name", ""),
        target_type="Role",
        target_id=record_id,
        details=json.dumps({
            "role_name": role_name,
            "old_count": len(old_permissions),
            "new_count": len(permission_keys),
            "added": [p for p in permission_keys if p not in old_permissions],
            "removed": [p for p in old_permissions if p not in permission_keys],
        }),
        ip_address=get_request_ip(request),
    )

    return JSONResponse({"ok": True, "message": f"Permissions updated for role '{role_name}'"})


# ==================== PERMISSIONS REGISTRY ====================

@router.get("/permissions/list")
async def api_list_permissions(
    request: Request,
    user: dict = Depends(require_permission("role_management.view")),
):
    """List all available permissions grouped by category (mirrors sidebar layout)."""
    return JSONResponse({
        "ok": True,
        "permissions": PERMISSIONS,
        "groups": PERMISSION_CATEGORIES,
    })


# ==================== SEEDING ====================

@router.post("/roles/seed")
async def api_seed_roles(
    request: Request,
    user: dict = Depends(require_admin),
):
    """Seed default roles and permissions. Admin-only, one-time setup."""
    result = seed_default_roles()

    # Audit log
    log_event(
        action=AuditAction.SEED_ROLES,
        category=AuditCategory.SYSTEM,
        actor_email=user.get("email", ""),
        actor_name=user.get("name", ""),
        target_type="System",
        target_id="seed",
        details=json.dumps(result),
        ip_address=get_request_ip(request),
    )

    return JSONResponse({"ok": True, "result": result})
