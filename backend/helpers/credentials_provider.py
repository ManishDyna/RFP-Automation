from typing import Tuple
import os

# Env fallbacks — only used when Dataverse has no rows and no earlier read succeeded.
CFG_USERNAME = os.getenv("BAHRA_SAP_USERNAME", "")
CFG_PASSWORD = os.getenv("BAHRA_SAP_PASSWORD", "")

# Direct Dataverse access (no imports from dashboard/core_helper)
from helpers.dataverse_helper import DataverseClient
from services.system_settings_service import get_setting

# The last pair a *successful* Dataverse read returned. This is NOT a cache:
# every call to get_sap_credentials() queries Dataverse. It exists only so a
# transient Dataverse failure at login time re-uses the last good pair instead
# of sending the (normally empty) env fallbacks to Ariba.
_LAST_GOOD = {"value": None}


def _dataverse_client() -> DataverseClient:
    return DataverseClient(
        tenant_id=get_setting("TENANT_ID", ""),
        client_id=get_setting("CLIENT_ID", ""),
        client_secret=get_setting("CLIENT_SECRET", ""),
        resource_url=get_setting("RESOURCE_URL", ""),
    )


def get_sap_credentials() -> Tuple[str, str]:
    """
    Return the latest (username, password) from Dataverse.

    Queried fresh on EVERY call. The automation must log in with whatever the
    dashboard's "Change SAP Password" dialog saved most recently, so nothing
    here is cached by time or bound at import. `id` is a Dataverse autonumber
    (sap-{SEQNUM:4}), so `id desc` yields the newest row.
    """
    try:
        dv = _dataverse_client()
        rows = dv.get_rows_from_dataverse(
            table_api_name=get_setting("SAP_PASSWORD_TABLE_API", "cr673_bahra_sap_infomations"),
            select_columns=["id", "username", "password", "created"],
            top=1,
            order_by="id desc",
            table_logical_name=get_setting("SAP_PASSWORD_TABLE_LOGICAL", "cr673_bahra_sap_infomation"),
            use_display_names=True,
        ) or []
    except Exception as e:
        if _LAST_GOOD["value"]:
            print(f"[SAP creds] WARNING: Dataverse read failed ({e}); re-using the last successfully read pair")
            return _LAST_GOOD["value"]
        print(f"[SAP creds] WARNING: Dataverse read failed ({e}); falling back to environment values")
        return CFG_USERNAME, CFG_PASSWORD

    if rows:
        r = rows[0]
        username = (r.get("username") or "").strip() or CFG_USERNAME
        password = (r.get("password") or "").strip() or CFG_PASSWORD
        # Never print the password.
        print(
            f"[SAP creds] user={username or '<empty>'} , Pass={password or '<empty>'}"
            f"record={r.get('id') or '?'} created={r.get('created') or '?'}"
        )
    else:
        username, password = CFG_USERNAME, CFG_PASSWORD
        print("[SAP creds] WARNING: no rows in Dataverse; using environment values")

    _LAST_GOOD["value"] = (username, password)
    return username, password
