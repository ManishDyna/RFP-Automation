"""
System Settings Routes - API endpoints for dynamic configuration management.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from middleware.auth import require_permission, require_admin, get_request_ip, get_current_user
from services.system_settings_service import (
    get_all_settings,
    get_sections,
    reveal_setting,
    update_setting,
    invalidate_settings_cache,
    get_setting_entry,
)

router = APIRouter(prefix="/api/system-settings", tags=["System Settings"])


class UpdateSettingBody(BaseModel):
    value: str


@router.get("/list")
async def list_settings(user: dict = Depends(require_permission("system_settings.view"))):
    """List all system settings grouped by section. Sensitive values are masked."""
    settings = get_all_settings()
    sections = get_sections()
    return {"ok": True, "settings": settings, "sections": sections}


@router.get("/{key}/reveal")
async def reveal_setting_value(
    key: str,
    user: dict = Depends(require_permission("system_settings.edit")),
):
    """Reveal the unmasked value of a sensitive setting."""
    entry = get_setting_entry(key)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")

    actor_email = user.get("email", "")
    value = reveal_setting(key, actor_email=actor_email)
    return {"ok": True, "key": key, "value": value}


@router.put("/{key}")
async def update_setting_value(
    key: str,
    body: UpdateSettingBody,
    user: dict = Depends(require_permission("system_settings.edit")),
):
    """Update a single system setting value."""
    actor_email = user.get("email", "")
    result = update_setting(key, body.value, actor_email=actor_email)

    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Update failed"))

    return {"ok": True, "message": f"Setting '{key}' updated successfully"}


@router.post("/reload-cache")
async def reload_cache(user: dict = Depends(require_permission("system_settings.edit"))):
    """Force invalidate the settings cache."""
    invalidate_settings_cache()
    return {"ok": True, "message": "Settings cache reloaded"}


@router.post("/seed")
async def seed_settings_endpoint(user: dict = Depends(require_admin)):
    """Run the seed script to populate settings from config.py. Idempotent."""
    try:
        from seed_system_settings import seed_settings
        seed_settings()
        return {"ok": True, "message": "Settings seeded successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Seed failed: {e}")
