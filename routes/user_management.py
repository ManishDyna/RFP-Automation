from fastapi import APIRouter, HTTPException, Query
from services.user_service import list_users, get_user, create_user, update_user, delete_user
from services.role_service import has_access_to_feature
from fastapi.responses import HTMLResponse
from fastapi import Request
from fastapi.templating import Jinja2Templates
import os
from config.config import COMPANY_OPTIONS

router = APIRouter(prefix="/users", tags=["Users"])
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # one level up
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

templates = Jinja2Templates(directory=TEMPLATES_DIR)
templates.env.globals["COMPANY_OPTIONS"] = COMPANY_OPTIONS

_USERS_CACHE = {"data": None, "ts": 0, "top": None}
_USERS_TTL_SECONDS = 300

def _users_cached(list_fn, force_refresh: bool, top: int):
    from time import time as _now
    now = _now()
    if not force_refresh and _USERS_CACHE["data"] is not None and _USERS_CACHE["top"] == top and (now - _USERS_CACHE["ts"]) < _USERS_TTL_SECONDS:
        return _USERS_CACHE["data"]
    data = list_fn(top=top)
    _USERS_CACHE["data"] = data
    _USERS_CACHE["ts"] = now
    _USERS_CACHE["top"] = top
    return data

def _invalidate_users_cache():
    _USERS_CACHE["data"] = None
    _USERS_CACHE["ts"] = 0
    _USERS_CACHE["top"] = None

@router.get("/user-list", response_class=HTMLResponse)
async def user_management(request: Request, refresh: int = Query(0), top: int = Query(200)):
    if not request.session.get("user"):
        return HTMLResponse(status_code=302, headers={"Location": "/login"})
    # Role-based access check
    user = request.session.get("user")
    if not has_access_to_feature(user, "user_management"):
        return HTMLResponse(status_code=403, content="Access denied. Admin access required.")
    users = _users_cached(list_users, force_refresh=bool(refresh), top=top)
    headers = {"Cache-Control": "private, max-age=30"}
    return templates.TemplateResponse(
        "user-management.html",
        {"request": request, "users": users, "user": user},
        headers=headers
    )

@router.get("/detail/{record_id}")
def api_get_user(request: Request, record_id: str):
    # Role-based access check
    user = request.session.get("user") if hasattr(request, 'session') else None
    if not user or not has_access_to_feature(user, "user_management"):
        raise HTTPException(403, "Access denied. Admin access required.")
    u = get_user(record_id)
    if not u:
        raise HTTPException(404, "User not found")
    return u

@router.post("")
def api_create_user(request: Request, payload: dict):
    # Role-based access check
    user = request.session.get("user") if hasattr(request, 'session') else None
    if not user or not has_access_to_feature(user, "user_management"):
        raise HTTPException(403, "Access denied. Admin access required.")
    ok = create_user(payload)
    if not ok:
        raise HTTPException(400, "Create failed")
    # Invalidate cache so list reflects the new user immediately
    _invalidate_users_cache()
    return {"ok": True}

@router.put("/{record_id}")
def api_update_user(request: Request, record_id: str, updates: dict):
    # Role-based access check
    user = request.session.get("user") if hasattr(request, 'session') else None
    if not user or not has_access_to_feature(user, "user_management"):
        raise HTTPException(403, "Access denied. Admin access required.")
    ok = update_user(record_id, updates)
    # Invalidate cache so list reflects updates immediately
    if ok:
        _invalidate_users_cache()
    return {"ok": ok}

@router.delete("/{record_id}")
def api_delete_user(request: Request, record_id: str):
    # Role-based access check
    user = request.session.get("user") if hasattr(request, 'session') else None
    if not user or not has_access_to_feature(user, "user_management"):
        raise HTTPException(403, "Access denied. Admin access required.")
    ok = delete_user(record_id)
    # Invalidate cache so list reflects deletion immediately
    if ok:
        _invalidate_users_cache()
    return {"ok": ok}