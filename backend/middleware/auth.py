"""
Auth middleware - Reusable FastAPI dependencies for authentication and authorization.
Replaces manual session checks in each endpoint.
"""

from fastapi import Request, HTTPException, Depends


def get_current_user(request: Request) -> dict:
    """
    Extract and validate current user from session.
    Use as a FastAPI dependency to require authentication.

    Usage:
        @router.get("/endpoint")
        async def my_endpoint(user: dict = Depends(get_current_user)):
            ...
    """
    user = request.session.get("user") if hasattr(request, "session") else None
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def get_request_ip(request: Request) -> str:
    """Extract client IP from request, handling proxies."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def require_permission(permission_key: str):
    """
    Factory: returns a FastAPI dependency that checks for a specific permission.

    The returned dependency ensures the user is authenticated AND has the
    required permission based on their role's assigned permissions.

    Usage:
        @router.get("/roles/list")
        async def list_roles(user: dict = Depends(require_permission("role_management.view"))):
            ...
    """
    def checker(user: dict = Depends(get_current_user)) -> dict:
        # Check permissions list from session
        permissions = user.get("permissions") or []
        if permission_key in permissions:
            return user

        raise HTTPException(
            status_code=403,
            detail=f"Access denied. Required permission: {permission_key}"
        )

    return checker


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """
    FastAPI dependency that requires the user to be an Admin.

    Usage:
        @router.post("/admin-only")
        async def admin_endpoint(user: dict = Depends(require_admin)):
            ...
    """
    role = (user.get("role") or "").strip().lower()
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
