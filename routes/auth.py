from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse, HTMLResponse
from services.user_service import authenticate_user, list_users, update_user, get_user_by_email
from services.system_settings_service import get_setting
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
    "isHtml": True,
    "body": f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background-color:#f4f6f9;font-family:'Segoe UI',Arial,Helvetica,sans-serif;">
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color:#f4f6f9;">
        <tr>
            <td align="center" style="padding:40px 20px;">
                <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="600" style="max-width:600px;background-color:#ffffff;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
                    <!-- Header -->
                    <tr>
                        <td style="background-color:#4f46e5;padding:30px 40px;border-radius:12px 12px 0 0;text-align:center;">
                            <h1 style="margin:0;font-size:24px;color:#ffffff;font-weight:600;">Bahra E-Bidding</h1>
                        </td>
                    </tr>
                    <!-- Body -->
                    <tr>
                        <td style="padding:40px;">
                            <h2 style="margin:0 0 16px 0;font-size:22px;color:#1a1a2e;font-weight:600;">Reset Your Password</h2>
                            <p style="margin:0 0 24px 0;font-size:15px;color:#555555;line-height:1.6;">
                                We received a request to reset your password for your Bahra E-Bidding account. Click the button below to set a new password.
                            </p>
                            <!-- Button -->
                            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                                <tr>
                                    <td align="center" style="padding:8px 0 32px 0;">
                                        <a href="{reset_link}" target="_blank"
                                           style="background-color:#4f46e5;color:#ffffff;text-decoration:none;padding:14px 36px;border-radius:8px;font-size:16px;font-weight:600;display:inline-block;letter-spacing:0.5px;">
                                            Reset Password
                                        </a>
                                    </td>
                                </tr>
                            </table>
                            <!-- Link fallback -->
                            <p style="margin:0 0 8px 0;font-size:13px;color:#888888;">If the button above doesn't work, copy and paste the link below into your browser:</p>
                            <p style="margin:0 0 24px 0;word-break:break-all;font-size:13px;">
                                <a href="{reset_link}" target="_blank" style="color:#4f46e5;text-decoration:underline;">{reset_link}</a>
                            </p>
                            <!-- Divider -->
                            <hr style="border:none;border-top:1px solid #eeeeee;margin:24px 0;">
                            <p style="margin:0 0 8px 0;font-size:13px;color:#999999;line-height:1.5;">
                                This link will expire in <strong>30 minutes</strong>. If you didn't request a password reset, you can safely ignore this email.
                            </p>
                        </td>
                    </tr>
                    <!-- Footer -->
                    <tr>
                        <td style="background-color:#f9fafb;padding:24px 40px;border-radius:0 0 12px 12px;text-align:center;">
                            <p style="margin:0;font-size:13px;color:#888888;">
                                Thanks,<br><strong>Bahra E-Bidding Automation Team</strong>
                            </p>
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
    resp = requests.post(get_setting("FORGOT_PASSWORD_FLOW_URL", ""), json=payload)
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


@router.get("/reset-password")
async def reset_password_page(request: Request):
    """Serve the reset password form page (opened from email link)"""
    return HTMLResponse("""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reset Password - Bahra E-Bidding</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { min-height: 100vh; display: flex; align-items: center; justify-content: center; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); font-family: 'Segoe UI', Arial, Helvetica, sans-serif; padding: 20px; }
        .card { background: #fff; border-radius: 16px; box-shadow: 0 20px 60px rgba(0,0,0,0.15); width: 100%; max-width: 440px; overflow: hidden; }
        .card-header { background: #4f46e5; padding: 32px; text-align: center; }
        .card-header h1 { color: #fff; font-size: 22px; font-weight: 600; }
        .card-body { padding: 36px 32px; }
        .card-body h2 { font-size: 20px; color: #1a1a2e; margin-bottom: 8px; }
        .card-body p { font-size: 14px; color: #666; margin-bottom: 24px; line-height: 1.5; }
        .form-group { margin-bottom: 20px; }
        .form-group label { display: block; font-size: 13px; font-weight: 600; color: #374151; margin-bottom: 6px; }
        .form-group input { width: 100%; padding: 12px 14px; border: 1.5px solid #d1d5db; border-radius: 8px; font-size: 15px; transition: border-color 0.2s, box-shadow 0.2s; outline: none; }
        .form-group input:focus { border-color: #4f46e5; box-shadow: 0 0 0 3px rgba(79,70,229,0.1); }
        .btn { width: 100%; padding: 13px; background: #4f46e5; color: #fff; border: none; border-radius: 8px; font-size: 15px; font-weight: 600; cursor: pointer; transition: background 0.2s; letter-spacing: 0.3px; }
        .btn:hover { background: #4338ca; }
        .btn:disabled { background: #a5b4fc; cursor: not-allowed; }
        .alert { padding: 12px 16px; border-radius: 8px; font-size: 14px; margin-top: 16px; display: none; }
        .alert-danger { background: #fef2f2; color: #dc2626; border: 1px solid #fecaca; }
        .alert-success { background: #f0fdf4; color: #16a34a; border: 1px solid #bbf7d0; }
        .spinner { display: inline-block; width: 16px; height: 16px; border: 2px solid #fff; border-top-color: transparent; border-radius: 50%; animation: spin 0.6s linear infinite; margin-right: 8px; vertical-align: middle; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .back-link { display: block; text-align: center; margin-top: 20px; color: #4f46e5; text-decoration: none; font-size: 14px; font-weight: 500; }
        .back-link:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="card">
        <div class="card-header">
            <h1>Bahra E-Bidding</h1>
        </div>
        <div class="card-body">
            <h2>Set New Password</h2>
            <p>Enter your new password below to reset your account password.</p>
            <form id="resetForm">
                <div class="form-group">
                    <label for="newPwd">New Password</label>
                    <input type="password" id="newPwd" placeholder="Enter new password" required minlength="6">
                </div>
                <div class="form-group">
                    <label for="confirmPwd">Confirm Password</label>
                    <input type="password" id="confirmPwd" placeholder="Confirm new password" required minlength="6">
                </div>
                <button type="submit" class="btn" id="submitBtn">Reset Password</button>
            </form>
            <div class="alert alert-danger" id="errorAlert"></div>
            <div class="alert alert-success" id="successAlert"></div>
            <a href="http://localhost:3000/login" class="back-link">Back to Login</a>
        </div>
    </div>
    <script>
    (function(){
        const form = document.getElementById('resetForm');
        const btn = document.getElementById('submitBtn');
        const errorAlert = document.getElementById('errorAlert');
        const successAlert = document.getElementById('successAlert');
        const params = new URLSearchParams(window.location.search);
        const token = params.get('token');

        if (!token) {
            errorAlert.textContent = 'Invalid or missing reset token. Please request a new password reset link.';
            errorAlert.style.display = 'block';
            btn.disabled = true;
        }

        form.addEventListener('submit', async function(e) {
            e.preventDefault();
            errorAlert.style.display = 'none';
            successAlert.style.display = 'none';

            const password = document.getElementById('newPwd').value;
            const confirm = document.getElementById('confirmPwd').value;

            if (password.length < 6) {
                errorAlert.textContent = 'Password must be at least 6 characters long.';
                errorAlert.style.display = 'block';
                return;
            }
            if (password !== confirm) {
                errorAlert.textContent = 'Passwords do not match.';
                errorAlert.style.display = 'block';
                return;
            }

            btn.disabled = true;
            btn.innerHTML = '<span class="spinner"></span> Resetting...';

            try {
                const res = await fetch('/reset-password', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ token: token, password: password })
                });
                const data = await res.json().catch(() => ({}));
                if (!res.ok) throw new Error(data.detail || 'Failed to reset password');

                successAlert.textContent = 'Password reset successfully! Redirecting to login...';
                successAlert.style.display = 'block';
                form.style.display = 'none';
                setTimeout(() => { window.location.href = 'http://localhost:3000/login'; }, 2000);
            } catch(err) {
                errorAlert.textContent = err.message;
                errorAlert.style.display = 'block';
                btn.disabled = false;
                btn.textContent = 'Reset Password';
            }
        });
    })();
    </script>
</body>
</html>""")


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


