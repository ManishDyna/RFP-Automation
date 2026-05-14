"""
Open RFP routes — list of RFPs we emailed actionable cards for, per-RFP team
response status, and the reminder-send endpoint.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from middleware.auth import require_permission
from services.open_rfp_service import (
    get_rfps_with_email_sent,
    get_rfp_response_status,
    send_rfp_reminder,
)

router = APIRouter(prefix="/api/open-rfp", tags=["open-rfp"])


class RemindBody(BaseModel):
    emails: List[str]


@router.get("/list")
async def list_open_rfps(
    user: dict = Depends(require_permission("rfp.open.view")),
):
    try:
        data = get_rfps_with_email_sent()
        return JSONResponse({"ok": True, "rfps": data, "total": len(data)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{rfp_id}/status")
async def rfp_response_status(
    rfp_id: str,
    user: dict = Depends(require_permission("rfp.open.view")),
):
    try:
        data = get_rfp_response_status(rfp_id)
        return JSONResponse({"ok": True, **data})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{rfp_id}/remind")
async def remind_rfp(
    rfp_id: str,
    body: RemindBody,
    request: Request,
    user: dict = Depends(require_permission("rfp.open.remind")),
):
    emails = body.emails or []
    if not emails:
        raise HTTPException(status_code=400, detail="emails is required")
    actor_email = (user.get("email") or "").strip()
    actor_name = (user.get("name") or user.get("full_name") or actor_email).strip()
    try:
        result = send_rfp_reminder(
            rfp_id=rfp_id,
            recipient_emails=emails,
            actor_email=actor_email,
            actor_name=actor_name,
        )
        return JSONResponse({"ok": True, **result})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
