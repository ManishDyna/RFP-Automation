"""
Master Data Service - CRUD operations for Material Master codes and Keywords.

Materials are stored in cr673_bahra_material_master.
Keywords   are stored in cr673_bahra_keywords.

Both tables are queried with use_display_names=True so all
field names in payloads match the display names defined in
setup_master_data_tables.py.
"""

import json
import requests
from datetime import datetime, timezone
from typing import Optional, List, Dict

from helpers.core_helper import DATAVERSE
from services.system_settings_service import get_setting


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
    filter_expr = "is_active eq 'true'"
    if search:
        escaped = search.replace("'", "''")
        filter_expr += (
            f" and (contains(material_code,'{escaped}')"
            f" or contains(description,'{escaped}'))"
        )

    skip = (page - 1) * page_size

    result = DATAVERSE.query_rows(
        table_api_name=get_setting('MATERIAL_MASTER_TABLE_API', 'cr673_bahra_material_masters'),
        filter_expr=filter_expr,
        select="material_code,description,is_active,created_date,updated_date",
        top=page_size,
        skip=skip,
        order_by="created_date desc",
        table_logical_name=get_setting('MATERIAL_MASTER_TABLE_LOGICAL', 'cr673_bahra_material_master'),
        use_display_names=True,
    )

    rows = result.get("value", []) if isinstance(result, dict) else []

    # Attach record_id (uses display-name-aware helper)
    pk_logical = f"{get_setting('MATERIAL_MASTER_TABLE_LOGICAL', 'cr673_bahra_material_master')}id"
    for row in rows:
        row["record_id"] = _extract_record_id(row, pk_logical)

    return {"materials": rows, "page": page, "page_size": page_size}


def get_material(record_id: str) -> Optional[dict]:
    pk_logical = f"{get_setting('MATERIAL_MASTER_TABLE_LOGICAL', 'cr673_bahra_material_master')}id"
    url = f"{DATAVERSE.api_url}{get_setting('MATERIAL_MASTER_TABLE_API', 'cr673_bahra_material_masters')}({record_id})"
    resp = requests.get(url, headers=DATAVERSE._headers())
    if resp.status_code != 200:
        return None

    row = resp.json()
    try:
        colmap = DATAVERSE.get_column_mapping(get_setting('MATERIAL_MASTER_TABLE_LOGICAL', 'cr673_bahra_material_master'))
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
    filter_expr = f"material_code eq '{escaped}' and is_active eq 'true'"
    result = DATAVERSE.query_rows(
        table_api_name=get_setting('MATERIAL_MASTER_TABLE_API', 'cr673_bahra_material_masters'),
        filter_expr=filter_expr,
        select="material_code",
        top=5,
        table_logical_name=get_setting('MATERIAL_MASTER_TABLE_LOGICAL', 'cr673_bahra_material_master'),
        use_display_names=True,
    )
    rows = result.get("value", []) if isinstance(result, dict) else []
    pk_logical = f"{get_setting('MATERIAL_MASTER_TABLE_LOGICAL', 'cr673_bahra_material_master')}id"
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
        table_api_name=get_setting('MATERIAL_MASTER_TABLE_API', 'cr673_bahra_material_masters'),
        data=data,
        table_logical_name=get_setting('MATERIAL_MASTER_TABLE_LOGICAL', 'cr673_bahra_material_master'),
        use_display_names=True,
    )


def update_material(record_id: str, code: str, description: str = "") -> bool:
    data = {
        "material_code": code.strip(),
        "description": description.strip(),
        "updated_date": _now_iso(),
    }
    return DATAVERSE.update_row(
        table_api_name=get_setting('MATERIAL_MASTER_TABLE_API', 'cr673_bahra_material_masters'),
        record_id=record_id,
        data=data,
        table_logical_name=get_setting('MATERIAL_MASTER_TABLE_LOGICAL', 'cr673_bahra_material_master'),
        use_display_names=True,
    )


def delete_material(record_id: str) -> bool:
    return _hard_delete(get_setting('MATERIAL_MASTER_TABLE_API', 'cr673_bahra_material_masters'), record_id)


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
            table_api_name=get_setting('MATERIAL_MASTER_TABLE_API', 'cr673_bahra_material_masters'),
            select_columns=["material_code", "is_active"],
            table_logical_name=get_setting('MATERIAL_MASTER_TABLE_LOGICAL', 'cr673_bahra_material_master'),
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
    filter_expr = "is_active eq 'true'"
    if search:
        escaped = search.replace("'", "''")
        filter_expr += f" and contains(keyword,'{escaped}')"

    skip = (page - 1) * page_size

    result = DATAVERSE.query_rows(
        table_api_name=get_setting('KEYWORDS_TABLE_API', 'cr673_bahra_keywordses'),
        filter_expr=filter_expr,
        select="keyword,is_active,created_date,updated_date",
        top=page_size,
        skip=skip,
        order_by="created_date desc",
        table_logical_name=get_setting('KEYWORDS_TABLE_LOGICAL', 'cr673_bahra_keywords'),
        use_display_names=True,
    )

    rows = result.get("value", []) if isinstance(result, dict) else []
    pk_logical = f"{get_setting('KEYWORDS_TABLE_LOGICAL', 'cr673_bahra_keywords')}id"
    for row in rows:
        row["record_id"] = _extract_record_id(row, pk_logical)

    return {"keywords": rows, "page": page, "page_size": page_size}


def get_keyword(record_id: str) -> Optional[dict]:
    url = f"{DATAVERSE.api_url}{get_setting('KEYWORDS_TABLE_API', 'cr673_bahra_keywordses')}({record_id})"
    resp = requests.get(url, headers=DATAVERSE._headers())
    if resp.status_code != 200:
        return None
    row = resp.json()
    try:
        colmap = DATAVERSE.get_column_mapping(get_setting('KEYWORDS_TABLE_LOGICAL', 'cr673_bahra_keywords'))
        logical_to_display = {v: k for k, v in colmap.items()}
        mapped = {logical_to_display.get(k, k): v for k, v in row.items()}
        mapped["record_id"] = record_id
        return mapped
    except Exception:
        row["record_id"] = record_id
        return row


def keyword_exists(kw: str, exclude_record_id: str = "") -> bool:
    escaped = kw.strip().upper().replace("'", "''")
    filter_expr = f"keyword eq '{escaped}' and is_active eq 'true'"
    result = DATAVERSE.query_rows(
        table_api_name=get_setting('KEYWORDS_TABLE_API', 'cr673_bahra_keywordses'),
        filter_expr=filter_expr,
        select="keyword",
        top=5,
        table_logical_name=get_setting('KEYWORDS_TABLE_LOGICAL', 'cr673_bahra_keywords'),
        use_display_names=True,
    )
    rows = result.get("value", []) if isinstance(result, dict) else []
    pk_logical = f"{get_setting('KEYWORDS_TABLE_LOGICAL', 'cr673_bahra_keywords')}id"
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
        table_api_name=get_setting('KEYWORDS_TABLE_API', 'cr673_bahra_keywordses'),
        data=data,
        table_logical_name=get_setting('KEYWORDS_TABLE_LOGICAL', 'cr673_bahra_keywords'),
        use_display_names=True,
    )


def update_keyword(record_id: str, keyword: str) -> bool:
    data = {
        "keyword": keyword.strip().upper(),
        "updated_date": _now_iso(),
    }
    return DATAVERSE.update_row(
        table_api_name=get_setting('KEYWORDS_TABLE_API', 'cr673_bahra_keywordses'),
        record_id=record_id,
        data=data,
        table_logical_name=get_setting('KEYWORDS_TABLE_LOGICAL', 'cr673_bahra_keywords'),
        use_display_names=True,
    )


def delete_keyword(record_id: str) -> bool:
    return _hard_delete(get_setting('KEYWORDS_TABLE_API', 'cr673_bahra_keywordses'), record_id)


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
            table_api_name=get_setting('KEYWORDS_TABLE_API', 'cr673_bahra_keywordses'),
            select_columns=["keyword", "is_active"],
            table_logical_name=get_setting('KEYWORDS_TABLE_LOGICAL', 'cr673_bahra_keywords'),
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


# ---------------------------------------------------------------------------
# RFP Team
# ---------------------------------------------------------------------------

def list_rfp_team(search: Optional[str] = None, page: int = 1, page_size: int = 100) -> dict:
    # NOTE: use display names in filters (not cr673_ prefixed) because
    # DataverseClient.query_rows does naive .replace(display, logical) which
    # would double-prefix e.g. cr673_product → cr673_cr673_product.
    filter_expr = "is_active eq 'true'"
    if search:
        escaped = search.replace("'", "''")
        filter_expr += (
            f" and (contains(product,'{escaped}')"
            f" or contains(name,'{escaped}')"
            f" or contains(email,'{escaped}'))"
        )

    skip = (page - 1) * page_size

    result = DATAVERSE.query_rows(
        table_api_name=get_setting('RFP_TEAM_DV_TABLE_API', 'cr673_bahra_rfp_teams'),
        filter_expr=filter_expr,
        select="product,name,email,extra_data,is_active,created_date,updated_date",
        top=page_size,
        skip=skip,
        order_by="created_date desc",
        table_logical_name=get_setting('RFP_TEAM_DV_TABLE_LOGICAL', 'cr673_bahra_rfp_team'),
        use_display_names=True,
    )

    rows = result.get("value", []) if isinstance(result, dict) else []
    pk_logical = f"{get_setting('RFP_TEAM_DV_TABLE_LOGICAL', 'cr673_bahra_rfp_team')}id"
    for row in rows:
        row["record_id"] = _extract_record_id(row, pk_logical)
        # Merge extra_data JSON into the row for frontend consumption
        extra_raw = row.pop("extra_data", "") or ""
        if extra_raw:
            try:
                extra = json.loads(extra_raw)
                row.update(extra)
            except (json.JSONDecodeError, TypeError):
                pass

    return {"rfp_team": rows, "page": page, "page_size": page_size}


def get_rfp_team_member(record_id: str) -> Optional[dict]:
    url = f"{DATAVERSE.api_url}{get_setting('RFP_TEAM_DV_TABLE_API', 'cr673_bahra_rfp_teams')}({record_id})"
    resp = requests.get(url, headers=DATAVERSE._headers())
    if resp.status_code != 200:
        return None
    row = resp.json()
    try:
        colmap = DATAVERSE.get_column_mapping(get_setting('RFP_TEAM_DV_TABLE_LOGICAL', 'cr673_bahra_rfp_team'))
        logical_to_display = {v: k for k, v in colmap.items()}
        mapped = {logical_to_display.get(k, k): v for k, v in row.items()}
        mapped["record_id"] = record_id
        return mapped
    except Exception:
        row["record_id"] = record_id
        return row


def rfp_team_member_exists(product: str, email: str, exclude_record_id: str = "") -> bool:
    """Check if a product+email combination already exists."""
    escaped_product = product.strip().replace("'", "''")
    escaped_email = email.strip().lower().replace("'", "''")
    # Use display names in filters (see note in list_rfp_team)
    filter_expr = (
        f"product eq '{escaped_product}' and "
        f"email eq '{escaped_email}' and "
        f"is_active eq 'true'"
    )
    result = DATAVERSE.query_rows(
        table_api_name=get_setting('RFP_TEAM_DV_TABLE_API', 'cr673_bahra_rfp_teams'),
        filter_expr=filter_expr,
        select="product,email",
        top=5,
        table_logical_name=get_setting('RFP_TEAM_DV_TABLE_LOGICAL', 'cr673_bahra_rfp_team'),
        use_display_names=True,
    )
    rows = result.get("value", []) if isinstance(result, dict) else []
    if not exclude_record_id:
        return len(rows) > 0
    pk_logical = f"{get_setting('RFP_TEAM_DV_TABLE_LOGICAL', 'cr673_bahra_rfp_team')}id"
    for row in rows:
        rid = _extract_record_id(row, pk_logical)
        if rid and rid != exclude_record_id:
            return True
    return False


def create_rfp_team_member(product: str, name: str, email: str, extra_fields: Dict = None) -> bool:
    data = {
        "product": product.strip(),
        "name": name.strip(),
        "email": email.strip().lower(),
        "is_active": "true",
        "created_date": _now_iso(),
        "updated_date": _now_iso(),
    }
    # Pack extra dynamic fields into extra_data JSON
    if extra_fields:
        data["extra_data"] = json.dumps(extra_fields)
    return DATAVERSE.insert_row(
        table_api_name=get_setting('RFP_TEAM_DV_TABLE_API', 'cr673_bahra_rfp_teams'),
        data=data,
        table_logical_name=get_setting('RFP_TEAM_DV_TABLE_LOGICAL', 'cr673_bahra_rfp_team'),
        use_display_names=True,
    )


def update_rfp_team_member(record_id: str, product: str, name: str, email: str, extra_fields: Dict = None) -> bool:
    data = {
        "product": product.strip(),
        "name": name.strip(),
        "email": email.strip().lower(),
        "updated_date": _now_iso(),
    }
    # Pack extra dynamic fields into extra_data JSON
    if extra_fields is not None:
        data["extra_data"] = json.dumps(extra_fields) if extra_fields else ""
    return DATAVERSE.update_row(
        table_api_name=get_setting('RFP_TEAM_DV_TABLE_API', 'cr673_bahra_rfp_teams'),
        record_id=record_id,
        data=data,
        table_logical_name=get_setting('RFP_TEAM_DV_TABLE_LOGICAL', 'cr673_bahra_rfp_team'),
        use_display_names=True,
    )


def delete_rfp_team_member(record_id: str) -> bool:
    return _hard_delete(get_setting('RFP_TEAM_DV_TABLE_API', 'cr673_bahra_rfp_teams'), record_id)


def bulk_import_rfp_team(rows: List[Dict]) -> dict:
    """
    Insert a list of {"product": ..., "name": ..., "email": ...} dicts.
    Skips duplicates. Returns {created, skipped, failed, errors}.
    """
    created = skipped = failed = 0
    errors: List[str] = []

    for row in rows:
        product = str(row.get("product") or "").strip()
        name = str(row.get("name") or "").strip()
        email = str(row.get("email") or "").strip().lower()

        if not product or not name or not email:
            skipped += 1
            continue

        if rfp_team_member_exists(product, email):
            skipped += 1
            continue

        try:
            ok = create_rfp_team_member(product, name, email)
            if ok:
                created += 1
            else:
                failed += 1
                errors.append(f"Insert failed for {name} ({email})")
        except Exception as e:
            failed += 1
            errors.append(f"Error for {name}: {str(e)[:100]}")

    return {"created": created, "skipped": skipped, "failed": failed, "errors": errors}


def get_all_rfp_team_for_emails() -> List[Dict[str, str]]:
    """
    Return all active RFP team members as a list of dicts:
    [{"product": ..., "name": ..., "email": ...}, ...]

    This is the dynamic replacement for config.RFP_TEAM_TABLE.
    Applies EMAIL_MODE logic: in dev mode, overrides all emails with DEV_EMAIL.
    Falls back to the static config table if Dataverse fetch fails.
    """
    from config.config import RFP_TEAM_TABLE as STATIC_FALLBACK

    try:
        rows = DATAVERSE.get_all_rows(
            table_api_name=get_setting('RFP_TEAM_DV_TABLE_API', 'cr673_bahra_rfp_teams'),
            select_columns=["product", "name", "email", "extra_data", "is_active"],
            table_logical_name=get_setting('RFP_TEAM_DV_TABLE_LOGICAL', 'cr673_bahra_rfp_team'),
            use_display_names=True,
        )
        team = []
        for r in rows:
            if str(r.get("is_active", "")).lower() != "true":
                continue
            if not r.get("product") or not r.get("name") or not r.get("email"):
                continue
            member = {
                "product": str(r.get("product", "")).strip(),
                "name": str(r.get("name", "")).strip(),
                "email": (
                    get_setting('DEV_EMAIL', 'KSAGov.tenders@bahra-cables.com') if get_setting('EMAIL_MODE', 'dev') != "prod"
                    else str(r.get("email", "")).strip()
                ),
            }
            # Merge extra_data fields into member dict
            extra_raw = r.get("extra_data", "") or ""
            if extra_raw:
                try:
                    extra = json.loads(extra_raw)
                    member.update(extra)
                except (json.JSONDecodeError, TypeError):
                    pass
            team.append(member)

        if team:
            return team
        print("[RFPTeam] Dataverse table empty, using static fallback")
        return STATIC_FALLBACK
    except Exception as e:
        print(f"[RFPTeam] Could not fetch from Dataverse: {e}, using static fallback")
        return STATIC_FALLBACK
