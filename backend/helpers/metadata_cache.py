"""
Centralized cache for Dataverse table metadata (PrimaryIdAttribute).
Eliminates duplicate metadata API calls across services.
"""

import requests
from typing import Dict

from helpers.core_helper import DATAVERSE

_primary_id_cache: Dict[str, str] = {}


def get_primary_id(table_logical_name: str) -> str:
    """
    Get PrimaryIdAttribute for a Dataverse table.
    Cached per process lifetime (metadata never changes at runtime).
    """
    if table_logical_name in _primary_id_cache:
        return _primary_id_cache[table_logical_name]

    try:
        url = f"{DATAVERSE.api_url}EntityDefinitions(LogicalName='{table_logical_name}')?$select=PrimaryIdAttribute"
        resp = requests.get(url, headers=DATAVERSE._headers())
        resp.raise_for_status()
        primary_id = resp.json().get("PrimaryIdAttribute", "")
    except Exception:
        primary_id = ""

    _primary_id_cache[table_logical_name] = primary_id
    return primary_id
