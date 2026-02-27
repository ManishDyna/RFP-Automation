"""
Master Data Service - CRUD operations for Material Master codes and Keywords.

Materials are stored in cr673_bahra_material_master.
Keywords   are stored in cr673_bahra_keywords.

Both tables are queried with use_display_names=True so all
field names in payloads match the display names defined in
setup_master_data_tables.py.
"""

import requests
from datetime import datetime, timezone
from typing import Optional, List, Dict

from helpers.core_helper import DATAVERSE
from config.config import (
    MATERIAL_MASTER_TABLE_API,
    MATERIAL_MASTER_TABLE_LOGICAL,
    KEYWORDS_TABLE_API,
    KEYWORDS_TABLE_LOGICAL,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _get_primary_id(table_logical: str) -> str:
    try:
        url = f"{DATAVERSE.api_url}EntityDefinitions(LogicalName='{table_logical}')?$select=PrimaryIdAttribute"
        resp = requests.get(url, headers=DATAVERSE._headers())
        return resp.json().get("PrimaryIdAttribute", "")
    except Exception:
        return ""


def _extract_record_id(row: dict, pk_logical: str) -> str:
    """Get the primary key value from a row dict (display-name-mapped row)."""
    try:
        colmap = DATAVERSE.get_column_mapping(pk_logical.replace("id", ""))
        logical_to_display = {v: k for k, v in colmap.items()}
        pk_display = logical_to_display.get(pk_logical)
        return (row.get(pk_display) if pk_display else None) or row.get(pk_logical, "")
    except Exception:
        return row.get(pk_logical, "")


def _hard_delete(table_api: str, record_id: str) -> bool:
    """Permanently delete a row from Dataverse."""
    url = f"{DATAVERSE.api_url}{table_api}({record_id})"
    resp = requests.delete(url, headers=DATAVERSE._headers())
    return resp.status_code in (200, 204)


# ---------------------------------------------------------------------------
# Material Master
# ---------------------------------------------------------------------------

def list_materials(search: Optional[str] = None, page: int = 1, page_size: int = 100) -> dict:
    """
    Return paginated materials.
    Response: {"materials": [...], "total": int, "page": int, "page_size": int}
    """
    filter_expr = "cr673_is_active eq 'true'"
    if search:
        escaped = search.replace("'", "''")
        filter_expr += (
            f" and (contains(cr673_material_code,'{escaped}')"
            f" or contains(cr673_description,'{escaped}'))"
        )

    skip = (page - 1) * page_size

    result = DATAVERSE.query_rows(
        table_api_name=MATERIAL_MASTER_TABLE_API,
        filter_expr=filter_expr,
        select="material_code,description,is_active,created_date,updated_date",
        top=page_size,
        skip=skip,
        order_by="created_date desc",
        table_logical_name=MATERIAL_MASTER_TABLE_LOGICAL,
        use_display_names=True,
    )

    rows = result.get("value", []) if isinstance(result, dict) else []

    # Attach record_id
    pk_logical = f"{MATERIAL_MASTER_TABLE_LOGICAL}id"
    for row in rows:
        row["record_id"] = row.get(pk_logical) or row.get("record_id", "")

    return {"materials": rows, "page": page, "page_size": page_size}


def get_material(record_id: str) -> Optional[dict]:
    pk_logical = f"{MATERIAL_MASTER_TABLE_LOGICAL}id"
    url = f"{DATAVERSE.api_url}{MATERIAL_MASTER_TABLE_API}({record_id})"
    resp = requests.get(url, headers=DATAVERSE._headers())
    if resp.status_code != 200:
        return None

    row = resp.json()
    try:
        colmap = DATAVERSE.get_column_mapping(MATERIAL_MASTER_TABLE_LOGICAL)
        logical_to_display = {v: k for k, v in colmap.items()}
        mapped = {logical_to_display.get(k, k): v for k, v in row.items()}
        mapped["record_id"] = record_id
        return mapped
    except Exception:
        row["record_id"] = record_id
        return row


def material_code_exists(code: str, exclude_record_id: str = "") -> bool:
    """Check whether a material_code already exists (for duplicate prevention)."""
    escaped = code.strip().replace("'", "''")
    filter_expr = f"cr673_material_code eq '{escaped}' and cr673_is_active eq 'true'"
    result = DATAVERSE.query_rows(
        table_api_name=MATERIAL_MASTER_TABLE_API,
        filter_expr=filter_expr,
        select="material_code",
        top=5,
        table_logical_name=MATERIAL_MASTER_TABLE_LOGICAL,
        use_display_names=True,
    )
    rows = result.get("value", []) if isinstance(result, dict) else []
    pk_logical = f"{MATERIAL_MASTER_TABLE_LOGICAL}id"
    for row in rows:
        rid = row.get(pk_logical, "")
        if rid != exclude_record_id:
            return True
    return False


def create_material(code: str, description: str = "") -> bool:
    data = {
        "material_code": code.strip(),
        "description": description.strip(),
        "is_active": "true",
        "created_date": _now_iso(),
        "updated_date": _now_iso(),
    }
    return DATAVERSE.insert_row(
        table_api_name=MATERIAL_MASTER_TABLE_API,
        data=data,
        table_logical_name=MATERIAL_MASTER_TABLE_LOGICAL,
        use_display_names=True,
    )


def update_material(record_id: str, code: str, description: str = "") -> bool:
    data = {
        "material_code": code.strip(),
        "description": description.strip(),
        "updated_date": _now_iso(),
    }
    return DATAVERSE.update_row(
        table_api_name=MATERIAL_MASTER_TABLE_API,
        record_id=record_id,
        data=data,
        table_logical_name=MATERIAL_MASTER_TABLE_LOGICAL,
        use_display_names=True,
    )


def delete_material(record_id: str) -> bool:
    return _hard_delete(MATERIAL_MASTER_TABLE_API, record_id)


def bulk_import_materials(rows: List[Dict]) -> dict:
    """
    Insert a list of {"material_code": ..., "description": ...} dicts.
    Skips duplicates. Returns {created, skipped, failed, errors}.
    """
    created = skipped = failed = 0
    errors: List[str] = []

    for row in rows:
        code = str(row.get("material_code") or "").strip()
        desc = str(row.get("description") or "").strip()

        if not code:
            skipped += 1
            continue

        if material_code_exists(code):
            skipped += 1
            continue

        try:
            ok = create_material(code, desc)
            if ok:
                created += 1
            else:
                failed += 1
                errors.append(f"Insert failed for code '{code}'")
        except Exception as e:
            failed += 1
            errors.append(f"Error for code '{code}': {str(e)[:100]}")

    return {"created": created, "skipped": skipped, "failed": failed, "errors": errors}


def get_all_materials_for_matching() -> List[str]:
    """
    Return all active material codes as a flat list.
    Used by download_rfp.py instead of reading from SharePoint CSV.
    """
    try:
        rows = DATAVERSE.get_all_rows(
            table_api_name=MATERIAL_MASTER_TABLE_API,
            select_columns=["material_code", "is_active"],
            table_logical_name=MATERIAL_MASTER_TABLE_LOGICAL,
            use_display_names=True,
        )
        return [
            str(r.get("material_code", "")).strip()
            for r in rows
            if str(r.get("is_active", "")).lower() == "true"
            and r.get("material_code")
        ]
    except Exception as e:
        print(f"[MasterData] Could not fetch materials from Dataverse: {e}")
        return []


# ---------------------------------------------------------------------------
# Keywords
# ---------------------------------------------------------------------------

def list_keywords(search: Optional[str] = None, page: int = 1, page_size: int = 200) -> dict:
    filter_expr = "cr673_is_active eq 'true'"
    if search:
        escaped = search.replace("'", "''")
        filter_expr += f" and contains(cr673_keyword,'{escaped}')"

    skip = (page - 1) * page_size

    result = DATAVERSE.query_rows(
        table_api_name=KEYWORDS_TABLE_API,
        filter_expr=filter_expr,
        select="keyword,is_active,created_date,updated_date",
        top=page_size,
        skip=skip,
        order_by="created_date desc",
        table_logical_name=KEYWORDS_TABLE_LOGICAL,
        use_display_names=True,
    )

    rows = result.get("value", []) if isinstance(result, dict) else []
    pk_logical = f"{KEYWORDS_TABLE_LOGICAL}id"
    for row in rows:
        row["record_id"] = row.get(pk_logical) or row.get("record_id", "")

    return {"keywords": rows, "page": page, "page_size": page_size}


def get_keyword(record_id: str) -> Optional[dict]:
    url = f"{DATAVERSE.api_url}{KEYWORDS_TABLE_API}({record_id})"
    resp = requests.get(url, headers=DATAVERSE._headers())
    if resp.status_code != 200:
        return None
    row = resp.json()
    try:
        colmap = DATAVERSE.get_column_mapping(KEYWORDS_TABLE_LOGICAL)
        logical_to_display = {v: k for k, v in colmap.items()}
        mapped = {logical_to_display.get(k, k): v for k, v in row.items()}
        mapped["record_id"] = record_id
        return mapped
    except Exception:
        row["record_id"] = record_id
        return row


def keyword_exists(kw: str, exclude_record_id: str = "") -> bool:
    escaped = kw.strip().upper().replace("'", "''")
    filter_expr = f"cr673_keyword eq '{escaped}' and cr673_is_active eq 'true'"
    result = DATAVERSE.query_rows(
        table_api_name=KEYWORDS_TABLE_API,
        filter_expr=filter_expr,
        select="keyword",
        top=5,
        table_logical_name=KEYWORDS_TABLE_LOGICAL,
        use_display_names=True,
    )
    rows = result.get("value", []) if isinstance(result, dict) else []
    pk_logical = f"{KEYWORDS_TABLE_LOGICAL}id"
    for row in rows:
        rid = row.get(pk_logical, "")
        if rid != exclude_record_id:
            return True
    return False


def create_keyword(keyword: str) -> bool:
    data = {
        "keyword": keyword.strip().upper(),
        "is_active": "true",
        "created_date": _now_iso(),
        "updated_date": _now_iso(),
    }
    return DATAVERSE.insert_row(
        table_api_name=KEYWORDS_TABLE_API,
        data=data,
        table_logical_name=KEYWORDS_TABLE_LOGICAL,
        use_display_names=True,
    )


def update_keyword(record_id: str, keyword: str) -> bool:
    data = {
        "keyword": keyword.strip().upper(),
        "updated_date": _now_iso(),
    }
    return DATAVERSE.update_row(
        table_api_name=KEYWORDS_TABLE_API,
        record_id=record_id,
        data=data,
        table_logical_name=KEYWORDS_TABLE_LOGICAL,
        use_display_names=True,
    )


def delete_keyword(record_id: str) -> bool:
    return _hard_delete(KEYWORDS_TABLE_API, record_id)


def bulk_import_keywords(keywords: List[str]) -> dict:
    """
    Insert a list of keyword strings. Normalises to UPPER, skips blanks and duplicates.
    Returns {created, skipped, failed, errors}.
    """
    created = skipped = failed = 0
    errors: List[str] = []

    for kw in keywords:
        kw = str(kw).strip().upper()
        if not kw:
            skipped += 1
            continue

        if keyword_exists(kw):
            skipped += 1
            continue

        try:
            ok = create_keyword(kw)
            if ok:
                created += 1
            else:
                failed += 1
                errors.append(f"Insert failed for keyword '{kw}'")
        except Exception as e:
            failed += 1
            errors.append(f"Error for keyword '{kw}': {str(e)[:100]}")

    return {"created": created, "skipped": skipped, "failed": failed, "errors": errors}


def get_all_keywords_for_matching() -> List[str]:
    """
    Return all active keywords as a flat uppercase list.
    Used by download_rfp.py instead of reading from SharePoint CSV.
    """
    try:
        rows = DATAVERSE.get_all_rows(
            table_api_name=KEYWORDS_TABLE_API,
            select_columns=["keyword", "is_active"],
            table_logical_name=KEYWORDS_TABLE_LOGICAL,
            use_display_names=True,
        )
        return [
            str(r.get("keyword", "")).strip().upper()
            for r in rows
            if str(r.get("is_active", "")).lower() == "true"
            and r.get("keyword")
        ]
    except Exception as e:
        print(f"[MasterData] Could not fetch keywords from Dataverse: {e}")
        return []
