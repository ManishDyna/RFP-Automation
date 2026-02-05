from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from services.user_service import authenticate_user, list_users, update_user, get_user_by_email
from config.config import FORGOT_PASSWORD_FLOW_URL
import hmac, hashlib, base64, time, json

router = APIRouter(tags=["Auth"])


@router.post("/login")
async def login(request: Request):
    data = await request.json()
    email = (data.get("email") or "").strip()
    password = (data.get("password") or "").strip()
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required")

    user = authenticate_user(email=email, password=password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    request.session["user"] = user
    request.session["last_activity"] = int(time.time())
    return JSONResponse({"ok": True, "redirect": "/dashboard"})


@router.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return JSONResponse({"ok": True, "redirect": "/login"})


@router.post("/session/refresh")
async def refresh_session(request: Request):
    """Refresh the current session to extend its lifetime"""
    if not request.session.get("user"):
        return JSONResponse(status_code=401, content={"ok": False, "message": "No active session"})
    
    # Update session timestamp to extend lifetime
    user = request.session.get("user")
    request.session["user"] = user  # This will update the session timestamp
    request.session["last_activity"] = int(time.time())
    
    return JSONResponse({"ok": True, "message": "Session refreshed"})


@router.get("/session/status")
async def session_status(request: Request):
    """Check if session is still valid"""
    if not request.session.get("user"):
        return JSONResponse(status_code=401, content={"valid": False, "message": "No active session"})

    return JSONResponse({
        "valid": True,
        "user": request.session.get("user"),
        "last_activity": request.session.get("last_activity", int(time.time()))
    })


def _sign_token(secret: str, payload: dict, ttl_seconds: int = 1800) -> str:
    data = dict(payload or {})
    data["exp"] = int(time.time()) + ttl_seconds
    raw = json.dumps(data, separators=(",", ":"))
    sig = hmac.new(secret.encode(), raw.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=") + "." + base64.urlsafe_b64encode(sig).decode().rstrip("=")


@router.post("/forgot")
async def forgot(request: Request):
    body = await request.json()
    email = (body.get("email") or "").strip()
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")

    # 1) Check if user exists in Dataverse
    users = get_user_by_email(email) or []
    print(users)
    if not users:
        # Return 404 so client can show a helpful message
        raise HTTPException(status_code=404, detail="Email not found")

    # 2) Build reset URL with HMAC token
    secret = request.app.state.__dict__.get("secret_key", "change-me-please")
    token = _sign_token(secret, {"email": email}, ttl_seconds=1800)
    base_url = str(request.base_url).rstrip("/")
    reset_link = f"{base_url}/reset-password?token={token}"

    # 3) Send to Power Automate
    payload = {
    "to": email,
    "subject": "Reset your password",
    "body": f"""<!DOCTYPE html>
    <html>
    <body style="margin:0;padding:0;background:#f6f9fc;font-family:Arial,Helvetica,sans-serif;color:#111;">
        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
        <tr>
            <td align="center" style="padding:24px;">
            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="600" style="max-width:600px;background:#ffffff;border:1px solid #eaeaea;border-radius:8px;">
                <tr>
                <td style="padding:24px;">
                    <h2 style="margin:0 0 12px 0;font-size:20px;color:#111;">Reset your password</h2>
                    <p style="margin:0 0 16px 0;color:#444;">We received a request to reset your password. Click the button below to set a new one.</p>
                    <p style="margin:24px 0;">
                    <a href="{reset_link}" target="_blank" style="background:#4f46e5;color:#ffffff;text-decoration:none;padding:12px 20px;border-radius:6px;display:inline-block;">Reset Password</a>
                    </p>
                    <p style="margin:0 0 8px 0;color:#444;">If the button doesn’t work, copy and paste this link into your browser:</p>
                    <p style="word-break:break-all;color:#0066cc;">
                    <a href="{reset_link}" target="_blank" style="color:#0066cc;">{reset_link}</a>
                    </p>
                    <p style="margin-top:16px;color:#666;font-size:13px;">This link will expire in 30 minutes. If you didn't request this, you can safely ignore this email.</p>
                    <p style="margin-top:24px;color:#666;font-size:13px;">Thanks,<br/>Bahra E-bidding Automation</p>
                </td>
                </tr>
            </table>
            </td>
        </tr>
        </table>
    </body>
    </html>"""
    }
    import requests
    resp = requests.post(FORGOT_PASSWORD_FLOW_URL, json=payload)
    # Log response details for debugging
    print("FORGOT FLOW status:", resp.status_code)
    try:
        print("FORGOT FLOW body:", resp.text[:500])
    except Exception:
        pass

    # Treat 2xx as success; otherwise bubble up detail
    if not (200 <= resp.status_code < 300):
        raise HTTPException(status_code=502, detail=f"Flow error: {resp.status_code} {resp.text}")
    return JSONResponse({"ok": True})


def _verify_token(secret: str, token: str) -> dict:
    try:
        raw_b64, sig_b64 = token.split(".", 1)
        raw = base64.urlsafe_b64decode(raw_b64 + "==")
        sig = base64.urlsafe_b64decode(sig_b64 + "==")
        good = hmac.new(secret.encode(), raw, hashlib.sha256).digest()
        if not hmac.compare_digest(sig, good):
            raise ValueError("bad signature")
        data = json.loads(raw.decode())
        if int(data.get("exp", 0)) < int(time.time()):
            raise ValueError("expired")
        return data
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or expired token")


@router.post("/reset-password")
async def reset_password_post(request: Request):
    body = await request.json()
    token = (body.get("token") or "").strip()
    new_password = (body.get("password") or "")
    if not token:
        raise HTTPException(status_code=400, detail="Token is required")
    if not new_password:
        raise HTTPException(status_code=400, detail="Password is required")

    secret = request.app.state.__dict__.get("secret_key", "change-me-please")
    data = _verify_token(secret, token)
    email = (data.get("email") or "").strip()
    # Find user and update password
    users = get_user_by_email(email) or []
    if not users:
        raise HTTPException(status_code=404, detail="User not found")
    record_id = users[0].get("record_id")
    ok = update_user(record_id, {"password": str(new_password)})
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to update password")
    return JSONResponse({"ok": True})


