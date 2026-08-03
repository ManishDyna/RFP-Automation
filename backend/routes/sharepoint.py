"""
SharePoint routes — resolve the browser-openable SharePoint folder URL
for a given RFP so the UI can deep-link users into the right folder.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from middleware.auth import require_permission
from helpers.core_helper import (
    get_sharepoint_rfp_path,
    get_rfp_company_name,
)
from helpers.sharepoint_helper import GraphClient
from services.system_settings_service import get_setting

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sharepoint", tags=["sharepoint"])


@router.get("/rfp-folder")
async def get_rfp_sharepoint_folder(
    rfp_id: str = Query(..., description="RFP ID / title used as the folder name"),
    company: str | None = Query(None, description="Company name (resolved from DB if omitted)"),
    user: dict = Depends(require_permission("rfp.sharepoint.view")),
):
    """Return the SharePoint webUrl for an RFP's folder.

    Response:
      200 → {"ok": true, "url": "https://.../ALLRFPs/<company>/<rfp_id>"}
      404 → folder does not exist on SharePoint yet
    """
    rfp_id = (rfp_id or "").strip()
    if not rfp_id:
        raise HTTPException(status_code=400, detail="rfp_id is required")

    company_name = (company or "").strip() or get_rfp_company_name(rfp_id)
    if not company_name:
        raise HTTPException(
            status_code=404,
            detail="Company for this RFP could not be resolved.",
        )

    folder_path = get_sharepoint_rfp_path(rfp_id, company_name)

    try:
        graph_client = GraphClient(
            get_setting("CLIENT_ID", ""),
            get_setting("CLIENT_SECRET", ""),
            get_setting("TENANT_ID", ""),
            get_setting("SHAREPOINT_HOSTNAME", ""),
            get_setting("SITE_PATH", ""),
            get_setting("DRIVE_NAME", ""),
        )
        web_url = graph_client.get_folder_web_url(folder_path)
    except Exception as e:
        logger.exception("SharePoint folder lookup failed for %s / %s", rfp_id, company_name)
        raise HTTPException(status_code=502, detail=f"SharePoint lookup failed: {e}")

    if not web_url:
        raise HTTPException(
            status_code=404,
            detail="SharePoint folder for this RFP is not available yet.",
        )

    return JSONResponse({"ok": True, "url": web_url, "company": company_name})
