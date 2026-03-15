"""
User service - User management operations.
Moved from Dashboard/backend/user_management.py
"""

from typing import List, Dict, Optional
from datetime import datetime
import requests

from helpers.core_helper import DATAVERSE
from services.system_settings_service import get_setting

# Display column names used for user management
DISPLAY_COLUMNS = [
    "created_date",
    "email",
    "mobile_number",
    "name",
    "role",
    "password",
    "update_date",
]


def _get_primary_id_attribute(table_logical_name: str) -> str:
    """Fetch the primary id logical attribute name for a Dataverse table."""
    url = f"{DATAVERSE.api_url}EntityDefinitions(LogicalName='{table_logical_name}')?$select=PrimaryIdAttribute"
    resp = requests.get(url, headers=DATAVERSE._headers())
    resp.raise_for_status()
    return resp.json()["PrimaryIdAttribute"]


def _get_column_map() -> Dict[str, str]:
    """Returns display_name -> logical_name mapping for the users table."""
    return DATAVERSE.get_column_mapping(get_setting('USERS_TABLE_LOGICAL', 'cr673_bahra_users'))


def _build_filter_expr(filters: Optional[Dict[str, str]]) -> Optional[str]:
    """Build an OData $filter using DISPLAY column names."""
    if not filters:
        return None
    column_map = _get_column_map()
    parts: List[str] = []
    for disp, val in filters.items():
        logical = column_map.get(disp, disp)
        if isinstance(val, str):
            val = val.replace("'", "''")
            parts.append(f"{logical} eq '{val}'")
        else:
            parts.append(f"{logical} eq {val}")
    return " and ".join(parts) if parts else None


def _row_to_display(
    row: Dict,
    column_map: Dict[str, str],
    primary_id_attr: str
) -> Dict:
    """Convert a raw row with logical keys into a dict using DISPLAY column names."""
    out: Dict = {"record_id": row.get(primary_id_attr)}
    for disp in DISPLAY_COLUMNS:
        logical = column_map.get(disp, disp)
        out[disp] = row.get(logical)
    return out


def _fmt_iso(s: str | None) -> str:
    if not s:
        return ""
    try:
        dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return str(s)[:19]


def list_users(
    top: int = 5000,
    filters: Optional[Dict[str, str]] = None,
    select_display_columns: Optional[List[str]] = None
) -> List[Dict]:
    """List users from Dataverse."""
    select_display_columns = select_display_columns or DISPLAY_COLUMNS
    primary_id_attr = _get_primary_id_attribute(get_setting('USERS_TABLE_LOGICAL', 'cr673_bahra_users'))
    filter_expr = _build_filter_expr(filters)

    result = DATAVERSE.query_rows(
        table_api_name=get_setting('USERS_TABLE_API', 'cr673_bahra_userses'),
        filter_expr=filter_expr,
        select=None,
        top=top,
        table_logical_name=get_setting('USERS_TABLE_LOGICAL', 'cr673_bahra_users'),
        use_display_names=False
    )
    rows = result.get("value", [])
    colmap = _get_column_map()

    out: List[Dict] = []
    for r in rows:
        disp_row = _row_to_display(r, colmap, primary_id_attr)
        disp_row["created_display"] = _fmt_iso(disp_row.get("created_date"))
        disp_row["updated_display"] = _fmt_iso(disp_row.get("update_date"))
        if select_display_columns:
            disp_row = {
                "record_id": disp_row["record_id"],
                **{k: disp_row.get(k) for k in select_display_columns}
            }
        out.append(disp_row)
    return out


def get_user(record_id: str) -> Optional[Dict]:
    """Fetch single user by Dataverse GUID (record_id)."""
    primary_id_attr = _get_primary_id_attribute(get_setting('USERS_TABLE_LOGICAL', 'cr673_bahra_users'))
    filter_expr = f"{primary_id_attr} eq {record_id}"
    result = DATAVERSE.query_rows(
        table_api_name=get_setting('USERS_TABLE_API', 'cr673_bahra_userses'),
        filter_expr=filter_expr,
        select=None,
        top=1,
        table_logical_name=get_setting('USERS_TABLE_LOGICAL', 'cr673_bahra_users'),
        use_display_names=False
    )
    rows = result.get("value", [])
    if not rows:
        return None
    colmap = _get_column_map()
    return _row_to_display(rows[0], colmap, primary_id_attr)


def create_user(payload: Dict) -> bool:
    """Insert a user using DISPLAY column keys."""
    data = dict(payload or {})
    now_iso = datetime.utcnow().isoformat()
    data.setdefault("created_date", now_iso)
    data.setdefault("update_date", now_iso)

    for field in ["email", "name", "mobile_number", "role", "password"]:
        if field in data and data[field] is not None:
            data[field] = str(data[field])

    return DATAVERSE.insert_row(
        table_api_name=get_setting('USERS_TABLE_API', 'cr673_bahra_userses'),
        data=data,
        table_logical_name=get_setting('USERS_TABLE_LOGICAL', 'cr673_bahra_users'),
        use_display_names=True
    )


def update_user(record_id: str, updates: Dict) -> bool:
    """Update a user by Dataverse GUID (record_id)."""
    data = dict(updates or {})
    data.setdefault("update_date", datetime.utcnow().isoformat())

    for field in ["email", "name", "mobile_number", "role", "password"]:
        if field in data and data[field] is not None:
            data[field] = str(data[field])

    return DATAVERSE.update_row(
        table_api_name=get_setting('USERS_TABLE_API', 'cr673_bahra_userses'),
        record_id=record_id,
        data=data,
        table_logical_name=get_setting('USERS_TABLE_LOGICAL', 'cr673_bahra_users'),
        use_display_names=True
    )


def get_user_by_email(email: str) -> Optional[List[Dict]]:
    """Get user by email address."""
    try:
        users = list_users(filters={"email": email}, top=1)
        return users if users else None
    except Exception:
        return None


def delete_user(record_id: str) -> bool:
    """Delete a user by Dataverse GUID (record_id)."""
    url = f"{DATAVERSE.api_url}{get_setting('USERS_TABLE_API', 'cr673_bahra_userses')}({record_id})"
    resp = requests.delete(url, headers=DATAVERSE._headers())
    if resp.status_code in (200, 204):
        return True
    raise Exception(f"Delete failed: {resp.status_code} {resp.text}")


def authenticate_user(email: str, password: str) -> Optional[Dict]:
    """Authenticate user by email and password."""
    try:
        print(f"[DEBUG] authenticate_user called with email='{email}'")

        # First, check if user exists by email only
        users_by_email = list_users(filters={"email": email}, top=1)
        print(f"[DEBUG] Users found by email only: {len(users_by_email) if users_by_email else 0}")
        if users_by_email:
            print(f"[DEBUG] User in DB: email='{users_by_email[0].get('email')}', password='{users_by_email[0].get('password')}'")
            print(f"[DEBUG] Provided password: '{password}'")

        # Now check with both email and password
        users = list_users(filters={"email": email, "password": password}, top=1)
        print(f"[DEBUG] Users found with email+password: {len(users) if users else 0}")

        if not users:
            print("[DEBUG] No matching user found - returning None")
            return None
        user = users[0]
        print(f"[DEBUG] Login successful for: {user.get('email')}")
        return {
            "name": user.get("name"),
            "email": user.get("email"),
            "role": user.get("role"),
            "mobile": user.get("mobile_number"),
            "record_id": user.get("record_id"),
        }
    except Exception as e:
        print(f"[DEBUG] authenticate_user exception: {e}")
        return None
