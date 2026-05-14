"""
HMAC-signed JWT helpers for the per-RFP upload link.

The Adaptive Card embeds a signed token in the Upload button's URL so the
upload page knows who is uploading what for which RFP without requiring
the user to log in. The token is HS256-signed with a server-only secret
(`UPLOAD_TOKEN_SECRET`).
"""
from datetime import datetime, timedelta

import jwt
from fastapi import HTTPException

from services.system_settings_service import get_setting


def _get_secret() -> str:
    secret = get_setting("UPLOAD_TOKEN_SECRET", "")
    if not secret:
        raise RuntimeError(
            "UPLOAD_TOKEN_SECRET is not configured. "
            "Set it via System Settings or in config/config.py."
        )
    return secret


def sign_upload_token(
    rfp_id: str,
    email: str,
    product: str,
    company_name: str,
    ttl_hours: int = 72,
) -> str:
    now = datetime.utcnow()
    payload = {
        "rfp_id": rfp_id,
        "email": email,
        "product": product,
        "company_name": company_name,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=ttl_hours)).timestamp()),
    }
    return jwt.encode(payload, _get_secret(), algorithm="HS256")


def verify_upload_token(token: str) -> dict:
    try:
        return jwt.decode(token, _get_secret(), algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Upload link has expired. Please request a new one.")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid upload link: {e}")
