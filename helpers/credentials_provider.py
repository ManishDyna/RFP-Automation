from time import time as _now
from typing import Tuple
import os

# Env fallbacks if Dataverse has no rows
CFG_USERNAME = os.getenv("BAHRA_SAP_USERNAME", "")
CFG_PASSWORD = os.getenv("BAHRA_SAP_PASSWORD", "")

# Direct Dataverse access (no imports from dashboard/core_helper)
from helpers.dataverse_helper import DataverseClient
from config.config import (
    TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL,
    SAP_PASSWORD_TABLE_API, SAP_PASSWORD_TABLE_LOGICAL,
)

_CREDS_CACHE = {"value": None, "ts": 0}
_TTL_SECONDS = 300  # seconds

def _dataverse_client() -> DataverseClient:
    return DataverseClient(
        tenant_id=TENANT_ID,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        resource_url=RESOURCE_URL,
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
            table_api_name=SAP_PASSWORD_TABLE_API,
            select_columns=["username", "password"],
            top=1,
            order_by="id desc",
            table_logical_name=SAP_PASSWORD_TABLE_LOGICAL,
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