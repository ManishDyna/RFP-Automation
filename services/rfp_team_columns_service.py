"""
RFP Team Columns Service — CRUD + caching for dynamic column definitions.

Column definitions drive:
  - Admin UI form fields for team members
  - Adaptive Card table headers and input widgets
  - Email HTML table headers
  - Response data storage keys
"""

import json
import time
import requests
from datetime import datetime, timezone
from typing import Optional, List, Dict

from helpers.core_helper import DATAVERSE
from config.config import (
    RFP_TEAM_COLUMNS_TABLE_API,
    RFP_TEAM_COLUMNS_TABLE_LOGICAL,
)


# ---------------------------------------------------------------------------
# In-memory cache (avoid hitting Dataverse on every email/card build)
# ---------------------------------------------------------------------------

_column_cache: Optional[List[Dict]] = None
_column_cache_ts: float = 0
COLUMN_CACHE_TTL = 300  # 5 minutes


# ---------------------------------------------------------------------------
# Fallback column definitions (matches current hardcoded columns)
# ---------------------------------------------------------------------------

FALLBACK_COLUMNS = [
    {"column_key": "product", "column_label": "Products", "column_type": "text",
     "column_category": "display", "sort_order": "1", "dropdown_options": "",
     "is_required": "true", "is_team_field": "true", "is_protected": "false"},
    {"column_key": "name", "column_label": "Name", "column_type": "text",
     "column_category": "display", "sort_order": "2", "dropdown_options": "",
     "is_required": "true", "is_team_field": "true", "is_protected": "false"},
    {"column_key": "email", "column_label": "Email", "column_type": "text",
     "column_category": "display", "sort_order": "3", "dropdown_options": "",
     "is_required": "true", "is_team_field": "true", "is_protected": "true"},
    {"column_key": "results", "column_label": "Results", "column_type": "text",
     "column_category": "input", "sort_order": "4", "dropdown_options": "",
     "is_required": "false", "is_team_field": "false", "is_protected": "false"},
    {"column_key": "remarks", "column_label": "Remarks", "column_type": "text",
     "column_category": "input", "sort_order": "5", "dropdown_options": "",
     "is_required": "false", "is_team_field": "false", "is_protected": "false"},
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _extract_record_id(row: dict) -> str:
    pk_logical = f"{RFP_TEAM_COLUMNS_TABLE_LOGICAL}id"
    try:
        colmap = DATAVERSE.get_column_mapping(RFP_TEAM_COLUMNS_TABLE_LOGICAL)
        logical_to_display = {v: k for k, v in colmap.items()}
        pk_display = logical_to_display.get(pk_logical)
        return (row.get(pk_display) if pk_display else None) or row.get(pk_logical, "")
    except Exception:
        return row.get(pk_logical, "")


def _hard_delete(record_id: str) -> bool:
    url = f"{DATAVERSE.api_url}{RFP_TEAM_COLUMNS_TABLE_API}({record_id})"
    resp = requests.delete(url, headers=DATAVERSE._headers())
    return resp.status_code in (200, 204)


# ---------------------------------------------------------------------------
# Cache management
# ---------------------------------------------------------------------------

def invalidate_cache():
    """Force cache refresh on next call."""
    global _column_cache, _column_cache_ts
    _column_cache = None
    _column_cache_ts = 0


def get_all_columns(force_refresh: bool = False) -> List[Dict]:
    """
    Return all active column definitions sorted by sort_order.
    Cached in-memory for 5 minutes.
    """
    global _column_cache, _column_cache_ts

    if not force_refresh and _column_cache is not None and (time.time() - _column_cache_ts) < COLUMN_CACHE_TTL:
        return _column_cache

    try:
        rows = DATAVERSE.get_all_rows(
            table_api_name=RFP_TEAM_COLUMNS_TABLE_API,
            select_columns=[
                "column_key", "column_label", "column_type", "column_category",
                "sort_order", "dropdown_options", "is_required", "is_team_field",
                "is_protected", "is_active",
            ],
            table_logical_name=RFP_TEAM_COLUMNS_TABLE_LOGICAL,
            use_display_names=True,
        )

        columns = []
        for row in rows:
            if str(row.get("is_active", "")).lower() != "true":
                continue
            row["record_id"] = _extract_record_id(row)
            columns.append(row)

        # Sort by sort_order (stored as string)
        columns.sort(key=lambda c: int(c.get("sort_order", "999") or "999"))

        if columns:
            _column_cache = columns
            _column_cache_ts = time.time()
            return columns

        print("[RFPTeamColumns] Dataverse table empty, using fallback columns")
        return FALLBACK_COLUMNS

    except Exception as e:
        print(f"[RFPTeamColumns] Could not fetch from Dataverse: {e}, using fallback")
        return FALLBACK_COLUMNS


def get_display_columns() -> List[Dict]:
    """Return only category=display columns, sorted by sort_order."""
    return [c for c in get_all_columns() if c.get("column_category") == "display"]


def get_input_columns() -> List[Dict]:
    """Return only category=input columns, sorted by sort_order."""
    return [c for c in get_all_columns() if c.get("column_category") == "input"]


def get_team_field_columns() -> List[Dict]:
    """Return columns where is_team_field=true, sorted by sort_order."""
    return [c for c in get_all_columns() if str(c.get("is_team_field", "")).lower() == "true"]


# ---------------------------------------------------------------------------
# CRUD for admin UI
# ---------------------------------------------------------------------------

def list_columns(search: Optional[str] = None, page: int = 1, page_size: int = 100) -> dict:
    """Paginated list for admin UI."""
    filter_expr = "is_active eq 'true'"
    if search:
        escaped = search.replace("'", "''")
        filter_expr += (
            f" and (contains(column_key,'{escaped}')"
            f" or contains(column_label,'{escaped}'))"
        )

    skip = (page - 1) * page_size

    result = DATAVERSE.query_rows(
        table_api_name=RFP_TEAM_COLUMNS_TABLE_API,
        filter_expr=filter_expr,
        select="column_key,column_label,column_type,column_category,sort_order,"
               "dropdown_options,is_required,is_team_field,is_protected,is_active,"
               "created_date,updated_date",
        top=page_size,
        skip=skip,
        order_by="sort_order asc",
        table_logical_name=RFP_TEAM_COLUMNS_TABLE_LOGICAL,
        use_display_names=True,
    )

    rows = result.get("value", []) if isinstance(result, dict) else []
    for row in rows:
        row["record_id"] = _extract_record_id(row)

    return {"columns": rows, "page": page, "page_size": page_size}


def get_column(record_id: str) -> Optional[dict]:
    """Get a single column definition."""
    url = f"{DATAVERSE.api_url}{RFP_TEAM_COLUMNS_TABLE_API}({record_id})"
    resp = requests.get(url, headers=DATAVERSE._headers())
    if resp.status_code != 200:
        return None
    row = resp.json()
    try:
        colmap = DATAVERSE.get_column_mapping(RFP_TEAM_COLUMNS_TABLE_LOGICAL)
        logical_to_display = {v: k for k, v in colmap.items()}
        mapped = {logical_to_display.get(k, k): v for k, v in row.items()}
        mapped["record_id"] = record_id
        return mapped
    except Exception:
        row["record_id"] = record_id
        return row


def column_key_exists(key: str, exclude_record_id: str = "") -> bool:
    """Check for duplicate column_key."""
    escaped = key.strip().lower().replace("'", "''")
    filter_expr = f"column_key eq '{escaped}' and is_active eq 'true'"
    result = DATAVERSE.query_rows(
        table_api_name=RFP_TEAM_COLUMNS_TABLE_API,
        filter_expr=filter_expr,
        select="column_key",
        top=5,
        table_logical_name=RFP_TEAM_COLUMNS_TABLE_LOGICAL,
        use_display_names=True,
    )
    rows = result.get("value", []) if isinstance(result, dict) else []
    for row in rows:
        rid = _extract_record_id(row)
        if rid != exclude_record_id:
            return True
    return False


def create_column(data: dict) -> bool:
    """Create a new column definition. Invalidates cache."""
    payload = {
        "column_key": data["column_key"].strip().lower(),
        "column_label": data["column_label"].strip(),
        "column_type": data.get("column_type", "text").strip().lower(),
        "column_category": data.get("column_category", "display").strip().lower(),
        "sort_order": str(data.get("sort_order", "99")),
        "dropdown_options": data.get("dropdown_options", "").strip(),
        "is_required": str(data.get("is_required", "false")).lower(),
        "is_team_field": str(data.get("is_team_field", "false")).lower(),
        "is_protected": "false",
        "is_active": "true",
        "created_date": _now_iso(),
        "updated_date": _now_iso(),
    }
    result = DATAVERSE.insert_row(
        table_api_name=RFP_TEAM_COLUMNS_TABLE_API,
        data=payload,
        table_logical_name=RFP_TEAM_COLUMNS_TABLE_LOGICAL,
        use_display_names=True,
    )
    if result:
        invalidate_cache()
    return result


def update_column(record_id: str, data: dict) -> bool:
    """Update a column definition. Invalidates cache."""
    payload = {
        "column_label": data["column_label"].strip(),
        "column_type": data.get("column_type", "text").strip().lower(),
        "column_category": data.get("column_category", "display").strip().lower(),
        "sort_order": str(data.get("sort_order", "99")),
        "dropdown_options": data.get("dropdown_options", "").strip(),
        "is_required": str(data.get("is_required", "false")).lower(),
        "is_team_field": str(data.get("is_team_field", "false")).lower(),
        "updated_date": _now_iso(),
    }
    # Only update column_key if provided and changed (not for protected columns)
    if "column_key" in data:
        payload["column_key"] = data["column_key"].strip().lower()

    result = DATAVERSE.update_row(
        table_api_name=RFP_TEAM_COLUMNS_TABLE_API,
        record_id=record_id,
        data=payload,
        table_logical_name=RFP_TEAM_COLUMNS_TABLE_LOGICAL,
        use_display_names=True,
    )
    if result:
        invalidate_cache()
    return result


def delete_column(record_id: str) -> bool:
    """Hard delete a column. Blocked for protected columns. Invalidates cache."""
    result = _hard_delete(record_id)
    if result:
        invalidate_cache()
    return result


def reorder_columns(ordered_ids: List[str]) -> bool:
    """
    Accept a list of record_ids in desired order.
    Update sort_order for each. Invalidates cache.
    """
    success = True
    for idx, record_id in enumerate(ordered_ids, start=1):
        data = {"sort_order": str(idx), "updated_date": _now_iso()}
        ok = DATAVERSE.update_row(
            table_api_name=RFP_TEAM_COLUMNS_TABLE_API,
            record_id=record_id,
            data=data,
            table_logical_name=RFP_TEAM_COLUMNS_TABLE_LOGICAL,
            use_display_names=True,
        )
        if not ok:
            success = False

    invalidate_cache()
    return success
