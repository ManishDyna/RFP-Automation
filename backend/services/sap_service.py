"""
SAP service - SAP password management operations.
Moved from Dashboard/backend/sap_password.py
"""

from datetime import datetime
from typing import Dict, List

from helpers.core_helper import DATAVERSE
from services.system_settings_service import get_setting


def create_sap_password_record(password: str, user_email: str, username: str | None = None) -> bool:
    """Insert a new SAP password row into Dataverse using display names."""
    now_iso = datetime.utcnow().isoformat()
    data: Dict[str, str] = {
        "password": str(password),
        "created": now_iso,
        "updated": now_iso,
        "created_by": user_email or "",
        "updated_by": user_email or "",
        "username": username or "",
    }
    return DATAVERSE.insert_row(
        table_api_name=get_setting('SAP_PASSWORD_TABLE_API', 'cr673_bahra_sap_infomations'),
        data=data,
        table_logical_name=get_setting('SAP_PASSWORD_TABLE_LOGICAL', 'cr673_bahra_sap_infomation'),
        use_display_names=True,
    )


# ===== Short-lived cache for SAP password logs =====
_SAP_LOGS_CACHE = {"data": None, "ts": 0, "top": None}
_SAP_LOGS_TTL_SECONDS = get_setting('SAP_LOGS_TTL_SECONDS', 300)


def invalidate_sap_password_cache():
    _SAP_LOGS_CACHE["data"] = None
    _SAP_LOGS_CACHE["ts"] = 0
    _SAP_LOGS_CACHE["top"] = None


def list_sap_password_records(top: int = 200) -> List[Dict]:
    """Fetch recent SAP password records using display names."""
    try:
        rows = DATAVERSE.get_rows_from_dataverse(
            table_api_name=get_setting('SAP_PASSWORD_TABLE_API', 'cr673_bahra_sap_infomations'),
            select_columns=["id", "username", "password", "created", "updated", "created_by", "updated_by"],
            top=top,
            # Newest first. `id` is a Dataverse autonumber (sap-{SEQNUM:4}) — the same
            # key credentials_provider uses, so the top row is the one the next login uses.
            order_by="id desc",
            table_logical_name=get_setting('SAP_PASSWORD_TABLE_LOGICAL', 'cr673_bahra_sap_infomation'),
            use_display_names=True,
        )
        return rows or []
    except Exception:
        return []


def list_sap_password_records_cached(force_refresh: bool = False, top: int = 200) -> List[Dict]:
    from time import time as _now
    now = _now()
    if not force_refresh and _SAP_LOGS_CACHE["data"] is not None and _SAP_LOGS_CACHE["top"] == top and (now - _SAP_LOGS_CACHE["ts"]) < _SAP_LOGS_TTL_SECONDS:
        return _SAP_LOGS_CACHE["data"]
    data = list_sap_password_records(top=top)
    _SAP_LOGS_CACHE["data"] = data
    _SAP_LOGS_CACHE["ts"] = now
    _SAP_LOGS_CACHE["top"] = top
    return data
