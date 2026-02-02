"""
JSON API endpoints for React frontend.
All routes are prefixed with /api
"""

from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import JSONResponse
from services.user_service import (
    authenticate_user, list_users, get_user, create_user, update_user, delete_user, get_user_by_email
)
from services.dashboard_service import (
    get_dashboard_data_cached, get_all_rfp_data_cached, get_logs_data_cached
)
from services.sap_service import create_sap_password_record, list_sap_password_records_cached
from services.role_service import has_access_to_feature
from config.config import FORGOT_PASSWORD_FLOW_URL
import time
import hmac
import hashlib
import base64
import json

router = APIRouter(prefix="/api", tags=["API"])


# ==================== AUTH ENDPOINTS ====================

@router.post("/login")
async def api_login(request: Request):
    """Login endpoint for React frontend"""
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
async def api_logout(request: Request):
    """Logout endpoint"""
    request.session.clear()
    return JSONResponse({"ok": True, "redirect": "/login"})


@router.get("/session/status")
async def api_session_status(request: Request):
    """Check if session is valid - returns 'valid' field for React frontend"""
    if not request.session.get("user"):
        return JSONResponse(status_code=401, content={"valid": False, "message": "No active session"})

    return JSONResponse({
        "valid": True,
        "user": request.session.get("user"),
        "last_activity": request.session.get("last_activity", int(time.time()))
    })


@router.post("/session/refresh")
async def api_refresh_session(request: Request):
    """Refresh the current session"""
    if not request.session.get("user"):
        return JSONResponse(status_code=401, content={"ok": False, "message": "No active session"})

    user = request.session.get("user")
    request.session["user"] = user
    request.session["last_activity"] = int(time.time())
    return JSONResponse({"ok": True, "message": "Session refreshed"})


def _sign_token(secret: str, payload: dict, ttl_seconds: int = 1800) -> str:
    data = dict(payload or {})
    data["exp"] = int(time.time()) + ttl_seconds
    raw = json.dumps(data, separators=(",", ":"))
    sig = hmac.new(secret.encode(), raw.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=") + "." + base64.urlsafe_b64encode(sig).decode().rstrip("=")


@router.post("/forgot")
async def api_forgot(request: Request):
    """Forgot password endpoint"""
    body = await request.json()
    email = (body.get("email") or "").strip()
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")

    users = get_user_by_email(email) or []
    if not users:
        raise HTTPException(status_code=404, detail="Email not found")

    secret = request.app.state.__dict__.get("secret_key", "change-me-please")
    token = _sign_token(secret, {"email": email}, ttl_seconds=1800)
    base_url = str(request.base_url).rstrip("/")
    reset_link = f"{base_url}/reset-password?token={token}"

    payload = {
        "to": email,
        "subject": "Reset your password",
        "body": f"Click here to reset your password: {reset_link}"
    }
    import requests
    resp = requests.post(FORGOT_PASSWORD_FLOW_URL, json=payload)
    if not (200 <= resp.status_code < 300):
        raise HTTPException(status_code=502, detail=f"Flow error: {resp.status_code}")
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
async def api_reset_password(request: Request):
    """Reset password endpoint"""
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
    users = get_user_by_email(email) or []
    if not users:
        raise HTTPException(status_code=404, detail="User not found")
    record_id = users[0].get("record_id")
    ok = update_user(record_id, {"password": str(new_password)})
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to update password")
    return JSONResponse({"ok": True})


# ==================== DASHBOARD ENDPOINTS ====================

@router.get("/dashboard/data")
async def api_dashboard_data(request: Request, refresh: int = Query(0)):
    """Get dashboard data as JSON"""
    if not request.session.get("user"):
        raise HTTPException(status_code=401, detail="Not authenticated")

    data = get_dashboard_data_cached(force_refresh=bool(refresh))
    return JSONResponse(data)


@router.get("/dashboard/rfp-details")
async def api_rfp_details(
    request: Request,
    status: str = Query("downloaded"),
    search: str = Query(""),
    start_date: str = Query(""),
    end_date: str = Query(""),
    company: str = Query(""),
    refresh: int = Query(0),
):
    """Get RFP details as JSON"""
    if not request.session.get("user"):
        raise HTTPException(status_code=401, detail="Not authenticated")

    from datetime import datetime

    def _parse_date(s):
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                continue
        return None

    def _normalize_participation(raw_status):
        value = (raw_status or "").strip().lower()
        if value in ("submitted", "yes"):
            return "submitted"
        if value == "declined":
            return "declined"
        if value == "saved_draft":
            return "saved_draft"
        if value in ("", "no", "open", "not participated"):
            return "open"
        return "other"

    all_rfp_data = get_all_rfp_data_cached(force_refresh=bool(refresh))
    downloaded_rows = all_rfp_data.get("downloaded_rfps") or []

    detailed_rows = []
    for row in downloaded_rows:
        status_key = _normalize_participation(row.get("participated"))
        detailed_rows.append({**row, "status_key": status_key})

    # Filter by status
    selected_filter = (status or "downloaded").lower()
    filtered_rows = detailed_rows
    if selected_filter != "downloaded":
        filtered_rows = [r for r in filtered_rows if r["status_key"] == selected_filter]

    # Filter by company
    if company:
        filtered_rows = [r for r in filtered_rows if (r.get("Company_Name") or "") == company]

    # Filter by search
    if search:
        query = search.lower()
        filtered_rows = [
            r for r in filtered_rows
            if query in (r.get("RFP_ID") or "").lower()
            or query in (r.get("Company_Name") or "").lower()
            or query in (r.get("Owner_Name") or "").lower()
        ]

    # Filter by date range
    start_dt = _parse_date(start_date) if start_date else None
    end_dt = _parse_date(end_date) if end_date else None
    if start_dt or end_dt:
        def within_range(row):
            end_str = row.get("RFP_End_Date")
            if not end_str:
                return False
            parsed = _parse_date(end_str[:10]) if len(end_str) >= 10 else None
            if not parsed:
                return False
            if start_dt and parsed.date() < start_dt.date():
                return False
            if end_dt and parsed.date() > end_dt.date():
                return False
            return True
        filtered_rows = [r for r in filtered_rows if within_range(r)]

    # Count statuses
    from collections import Counter
    status_counts = Counter(r["status_key"] for r in detailed_rows)
    status_counts["downloaded"] = len(detailed_rows)

    # Get unique companies for filter dropdown
    unique_companies = list(set(r.get("Company_Name") or "" for r in detailed_rows if r.get("Company_Name")))
    unique_companies.sort()

    return JSONResponse({
        "rfps": filtered_rows,
        "status_counts": dict(status_counts),
        "total": len(detailed_rows),
        "total_rows": len(detailed_rows),
        "shown_rows": len(filtered_rows),
        "unique_companies": unique_companies
    })


@router.get("/dashboard/view-logs")
async def api_view_logs(request: Request, page: int = Query(1), page_size: int = Query(20)):
    """Get automation logs as JSON"""
    if not request.session.get("user"):
        raise HTTPException(status_code=401, detail="Not authenticated")

    # get_logs_data_cached returns a list directly, not a dict
    logs_list = get_logs_data_cached(force_refresh=False)
    if not isinstance(logs_list, list):
        logs_list = []

    # Map field names to what frontend expects
    mapped_logs = []
    for log in logs_list:
        mapped_logs.append({
            "id": log.get("RunID") or log.get("id"),
            "run_id": log.get("RunID", "-"),
            "event_time": log.get("formatted_timestamp") or log.get("Timestamp", "-"),
            "event_type": log.get("Category", "-"),
            "rfp_id": log.get("RFP_ID", "-"),
            "action": log.get("Action", "-"),
            "status": log.get("automation_status", "-"),
            "details": log.get("Message", "-"),
        })

    # Paginate
    start = (page - 1) * page_size
    end = start + page_size
    paginated = mapped_logs[start:end]

    return JSONResponse({
        "logs": paginated,
        "total": len(mapped_logs),
        "page": page,
        "page_size": page_size
    })


# ==================== PROFILE ENDPOINTS ====================

@router.get("/profile")
async def api_get_profile(request: Request):
    """Get current user profile"""
    if not request.session.get("user"):
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = request.session.get("user")
    return JSONResponse({
        "name": user.get("name"),
        "email": user.get("email"),
        "mobile": user.get("mobile") or user.get("mobile_number"),
        "role": user.get("role"),
        "record_id": user.get("record_id")
    })


@router.post("/profile/update")
async def api_update_profile(request: Request):
    """Update user profile"""
    if not request.session.get("user"):
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = request.session.get("user")
    body = await request.json()

    updates = {}
    session_updates = {}
    if "name" in body:
        updates["name"] = body["name"]
        session_updates["name"] = body["name"]
    if "mobile" in body:
        # Dataverse uses mobile_number, but frontend uses mobile
        updates["mobile_number"] = body["mobile"]
        session_updates["mobile"] = body["mobile"]

    if updates:
        ok = update_user(user.get("record_id"), updates)
        if ok:
            # Update session
            for k, v in session_updates.items():
                user[k] = v
            request.session["user"] = user
            return JSONResponse({"ok": True})
        raise HTTPException(status_code=500, detail="Failed to update profile")

    return JSONResponse({"ok": True})


@router.post("/profile/change-password")
async def api_change_password(request: Request):
    """Change user password"""
    if not request.session.get("user"):
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = request.session.get("user")
    body = await request.json()
    current_password = body.get("current_password")
    new_password = body.get("new_password")

    if not current_password or not new_password:
        raise HTTPException(status_code=400, detail="Current and new password required")

    # Verify current password
    auth_user = authenticate_user(user.get("email"), current_password)
    if not auth_user:
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    ok = update_user(user.get("record_id"), {"password": new_password})
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to change password")

    return JSONResponse({"ok": True})


# ==================== SAP PASSWORD ENDPOINTS ====================

@router.post("/sap/change-password")
async def api_sap_change_password(request: Request):
    """Change SAP password"""
    if not request.session.get("user"):
        raise HTTPException(status_code=401, detail="Not authenticated")

    body = await request.json()
    username = body.get("username")
    password = body.get("password")

    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password required")

    user = request.session.get("user")
    ok = create_sap_password_record(
        password=password,
        user_email=user.get("email"),
        username=username
    )
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to save SAP password")

    return JSONResponse({"ok": True})


@router.get("/dashboard/sap-password-logs")
async def api_sap_password_logs(request: Request):
    """Get SAP password change logs"""
    if not request.session.get("user"):
        raise HTTPException(status_code=401, detail="Not authenticated")

    logs = list_sap_password_records_cached(force_refresh=False)
    return JSONResponse({"logs": logs})


# ==================== USER MANAGEMENT ENDPOINTS ====================

@router.get("/users/user-list")
async def api_user_list(request: Request, refresh: int = Query(0)):
    """Get list of users as JSON"""
    if not request.session.get("user"):
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = request.session.get("user")
    if not has_access_to_feature(user, "user_management"):
        raise HTTPException(status_code=403, detail="Access denied. Admin access required.")

    users = list_users(top=200)
    return JSONResponse({"users": users})


@router.post("/users/create")
async def api_create_user(request: Request):
    """Create a new user"""
    if not request.session.get("user"):
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = request.session.get("user")
    if not has_access_to_feature(user, "user_management"):
        raise HTTPException(status_code=403, detail="Access denied. Admin access required.")

    body = await request.json()
    ok = create_user(body)
    if not ok:
        raise HTTPException(status_code=400, detail="Failed to create user")

    return JSONResponse({"ok": True})


@router.put("/users/update/{record_id}")
async def api_update_user(request: Request, record_id: str):
    """Update a user"""
    if not request.session.get("user"):
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = request.session.get("user")
    if not has_access_to_feature(user, "user_management"):
        raise HTTPException(status_code=403, detail="Access denied. Admin access required.")

    body = await request.json()
    ok = update_user(record_id, body)
    if not ok:
        raise HTTPException(status_code=400, detail="Failed to update user")

    return JSONResponse({"ok": True})


@router.delete("/users/delete/{record_id}")
async def api_delete_user(request: Request, record_id: str):
    """Delete a user"""
    if not request.session.get("user"):
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = request.session.get("user")
    if not has_access_to_feature(user, "user_management"):
        raise HTTPException(status_code=403, detail="Access denied. Admin access required.")

    ok = delete_user(record_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Failed to delete user")

    return JSONResponse({"ok": True})


# ==================== SCHEDULE ENDPOINTS ====================

@router.post("/schedule/save")
async def api_save_schedule(request: Request):
    """Save automation schedule"""
    if not request.session.get("user"):
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = request.session.get("user")
    if not has_access_to_feature(user, "schedule_automation"):
        raise HTTPException(status_code=403, detail="Access denied. Admin access required.")

    from helpers.core_helper import DATAVERSE
    from config.config import AUTOMATION_SCHEDULE_TABLE_API, AUTOMATION_SCHEDULE_TABLE_LOGICAL

    body = await request.json()

    # Get frequency maps for conversion
    def _get_frequency_maps():
        try:
            maps = DATAVERSE.get_choice_options(
                AUTOMATION_SCHEDULE_TABLE_LOGICAL,
                "cr673_frequency",
            )
            return maps
        except Exception:
            label_to_value = {
                "Month": 415300000,
                "Week": 415300001,
                "Day": 415300002,
                "Hour": 415300003,
                "Minute": 415300004,
                "Year": 415300005,
            }
            return {
                "label_to_value": label_to_value,
                "value_to_label": {v: k for k, v in label_to_value.items()}
            }

    try:
        freq_label = body.get("frequency")
        maps = _get_frequency_maps()
        freq_value = maps["label_to_value"].get(freq_label) if isinstance(freq_label, str) else freq_label
        if freq_value is None:
            raise HTTPException(status_code=400, detail="Unsupported frequency. Use Month, Week, Day, Hour, Minute, or Year.")

        # Get start_time and validate - empty string should be treated as None
        start_time = body.get("start_time")
        if isinstance(start_time, str):
            start_time = start_time.strip() or None

        data = {
            "job_name": body.get("job_name") or "RFP Automation",
            "interval": int(body.get("interval")) if body.get("interval") else 1,
            "frequency": int(freq_value),
            "timezone": body.get("timezone"),
            "start_time": start_time,
            "max_concurrency": int(body.get("max_concurrency") or 1),
            "notes": body.get("notes"),
            "is_active": bool(body.get("is_active", True)),
            "created_by": user.get("email"),
        }

        # Filter out None and empty string values
        data = {k: v for k, v in data.items() if v is not None and v != ""}

        ok = DATAVERSE.insert_row(
            table_api_name=AUTOMATION_SCHEDULE_TABLE_API,
            data=data,
            table_logical_name=AUTOMATION_SCHEDULE_TABLE_LOGICAL,
        )
        if not ok:
            raise HTTPException(status_code=500, detail="Failed to save schedule")

        return JSONResponse({"ok": True})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
