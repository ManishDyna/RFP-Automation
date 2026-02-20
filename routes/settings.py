"""
Settings API routes - admin-only endpoints for reading and updating
application configuration stored in Dataverse.

Endpoints (all prefixed with /api/settings):
  GET  /api/settings/all     - Return all settings grouped by section
  POST /api/settings/save    - Save a batch of setting updates to Dataverse
  POST /api/settings/reload  - Force reload settings cache and re-patch config
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from services.role_service import has_access_to_feature
from helpers.settings_helper import (
    get_settings_grouped,
    save_settings_batch,
    load_settings_from_dataverse,
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["Settings"])


def _require_admin(request: Request) -> dict:
    """Check that the current session user is an admin. Raises 403 otherwise."""
    user = request.session.get("user") if hasattr(request, "session") else None
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if not has_access_to_feature(user, "user_management"):
        raise HTTPException(status_code=403, detail="Access denied. Admin access required.")
    return user


@router.get("/all")
def get_all_settings(request: Request):
    """
    Return all settings grouped by section.

    Response:
    {
      "email": [{"key": "EMAIL_TO_NEW_RFP", "label": "...", "value": "...", ...}],
      "sharepoint": [...],
      ...
    }
    """
    _require_admin(request)
    try:
        grouped = get_settings_grouped()
        return JSONResponse({"ok": True, "data": grouped})
    except Exception as e:
        logger.error(f"Failed to retrieve settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve settings: {e}")


@router.post("/save")
async def save_settings(request: Request):
    """
    Save a batch of setting updates to Dataverse.

    Request body:
    {
      "updates": {
        "EMAIL_TO_NEW_RFP": "newemail@example.com",
        "COMPANY_OPTIONS": "[\"Company A\", \"Company B\"]"
      }
    }

    Response:
    {
      "ok": true,
      "saved": ["EMAIL_TO_NEW_RFP", "COMPANY_OPTIONS"],
      "failed": []
    }
    """
    _require_admin(request)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    updates = body.get("updates")
    if not isinstance(updates, dict) or not updates:
        raise HTTPException(status_code=400, detail="'updates' must be a non-empty dict")

    try:
        result = save_settings_batch(updates)
        ok = len(result.get("failed", [])) == 0
        return JSONResponse({
            "ok": ok,
            "saved": result.get("saved", []),
            "failed": result.get("failed", []),
        })
    except Exception as e:
        logger.error(f"Failed to save settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save settings: {e}")


@router.post("/reload")
def reload_settings(request: Request):
    """
    Force-reload settings from Dataverse and re-patch the config module.

    Use this after making changes directly in Dataverse, or to pick up
    changes made by other app instances.
    """
    _require_admin(request)
    try:
        cache = load_settings_from_dataverse(force=True)
        return JSONResponse({"ok": True, "loaded": len(cache)})
    except Exception as e:
        logger.error(f"Failed to reload settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reload settings: {e}")
