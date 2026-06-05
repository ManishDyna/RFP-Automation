from time import time as _now
from typing import Tuple
import os

# Env fallbacks if Dataverse has no rows
CFG_USERNAME = os.getenv("BAHRA_SAP_USERNAME", "")
CFG_PASSWORD = os.getenv("BAHRA_SAP_PASSWORD", "")

# Direct Dataverse access (no imports from dashboard/core_helper)
from helpers.dataverse_helper import DataverseClient
from services.system_settings_service import get_setting

_CREDS_CACHE = {"value": None, "ts": 0}
_TTL_SECONDS = 300  # seconds

def _dataverse_client() -> DataverseClient:
    return DataverseClient(
        tenant_id=get_setting("TENANT_ID", ""),
        client_id=get_setting("CLIENT_ID", ""),
        client_secret=get_setting("CLIENT_SECRET", ""),
        resource_url=get_setting("RESOURCE_URL", ""),
    )

def get_sap_credentials(force_refresh: bool = False) -> Tuple[str, str]:
    """
    Return latest (username, password) from Dataverse; fallback to env.
    Cached briefly to reduce calls.
    """
    now = _now()
    if (not force_refresh) and _CREDS_CACHE["value"] and (now - _CREDS_CACHE["ts"]) < _TTL_SECONDS:
        return _CREDS_CACHE["value"]

    try:
        dv = _dataverse_client()
        rows = dv.get_rows_from_dataverse(
            table_api_name=get_setting("SAP_PASSWORD_TABLE_API", "cr673_bahra_sap_infomations"),
            select_columns=["username", "password"],
            top=1,
            order_by="id desc",
            table_logical_name=get_setting("SAP_PASSWORD_TABLE_LOGICAL", "cr673_bahra_sap_infomation"),
            use_display_names=True,
        ) or []
    except Exception:
        rows = []

    if rows:
        r = rows[0]
        username = (r.get("username") or "").strip() or CFG_USERNAME
        password = (r.get("password") or "").strip() or CFG_PASSWORD
    else:
        username, password = CFG_USERNAME, CFG_PASSWORD

    _CREDS_CACHE["value"] = (username, password)
    _CREDS_CACHE["ts"] = now
    return _CREDS_CACHE["value"]

def get_username() -> str:
    return get_sap_credentials()[0]

def get_password() -> str:
    return get_sap_credentials()[1]