"""
Master Data API Routes - Material Master Codes and Keywords management.

All routes require the 'master_data.*' permissions defined in
services/permission_definitions.py.
"""

import io
import json

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import JSONResponse

from middleware.auth import require_permission, get_request_ip
from services.audit_service import log_event, AuditAction, AuditCategory
from services.master_data_service import (
    # Materials
    list_materials,
    get_material,
    material_code_exists,
    create_material,
    update_material,
    delete_material,
    bulk_import_materials,
    # Keywords
    list_keywords,
    get_keyword,
    keyword_exists,
    create_keyword,
    update_keyword,
    delete_keyword,
    bulk_import_keywords,
    # RFP Team
    list_rfp_team,
    get_rfp_team_member,
    rfp_team_member_exists,
    create_rfp_team_member,
    update_rfp_team_member,
    delete_rfp_team_member,
    bulk_import_rfp_team,
)
from services.rfp_team_columns_service import (
    list_columns as list_team_columns,
    get_column as get_team_column,
    column_key_exists,
    create_column as create_team_column,
    update_column as update_team_column,
    delete_column as delete_team_column,
    reorder_columns as reorder_team_columns,
    get_all_columns as get_all_team_columns,
)

router = APIRouter(prefix="/api/master-data", tags=["master-data"])


# ============================================================
# Helpers
# ============================================================

def _add_master_data_action(action: str) -> str:
    return f"MASTER_DATA_{action}"


# ============================================================
# Material Master — CRUD
# ============================================================

@router.get("/materials/list")
async def api_list_materials(
    request: Request,
    search: str = "",
    page: int = 1,
    page_size: int = 100,
    user: dict = Depends(require_permission("master_data.view")),
):
    try:
        result = list_materials(search=search or None, page=page, page_size=page_size)
        return JSONResponse({"ok": True, **result})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/materials/create")
async def api_create_material(
    request: Request,
    user: dict = Depends(require_permission("master_data.create")),
):
    data = await request.json()
    code = (data.get("material_code") or "").strip()
    description = (data.get("description") or "").strip()

    if not code:
        raise HTTPException(status_code=400, detail="material_code is required")

    if material_code_exists(code):
        raise HTTPException(status_code=409, detail=f"Material code '{code}' already exists")

    ok = create_material(code, description)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to create material")

    log_event(
        action=_add_master_data_action("MATERIAL_CREATED"),
        category=AuditCategory.SYSTEM,
        actor_email=user.get("email", ""),
        actor_name=user.get("name", ""),
        target_type="MaterialMaster",
        target_id=code,
        details=json.dumps({"material_code": code, "description": description}),
        ip_address=get_request_ip(request),
    )

    return JSONResponse({"ok": True, "message": f"Material '{code}' created successfully"})


@router.put("/materials/update/{record_id}")
async def api_update_material(
    request: Request,
    record_id: str,
    user: dict = Depends(require_permission("master_data.edit")),
):
    data = await request.json()
    code = (data.get("material_code") or "").strip()
    description = (data.get("description") or "").strip()

    if not code:
        raise HTTPException(status_code=400, detail="material_code is required")

    existing = get_material(record_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Material not found")

    if material_code_exists(code, exclude_record_id=record_id):
        raise HTTPException(status_code=409, detail=f"Material code '{code}' already exists")

    ok = update_material(record_id, code, description)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to update material")

    log_event(
        action=_add_master_data_action("MATERIAL_UPDATED"),
        category=AuditCategory.SYSTEM,
        actor_email=user.get("email", ""),
        actor_name=user.get("name", ""),
        target_type="MaterialMaster",
        target_id=record_id,
        details=json.dumps({"material_code": code, "description": description}),
        ip_address=get_request_ip(request),
    )

    return JSONResponse({"ok": True, "message": "Material updated successfully"})


@router.delete("/materials/delete/{record_id}")
async def api_delete_material(
    request: Request,
    record_id: str,
    user: dict = Depends(require_permission("master_data.delete")),
):
    existing = get_material(record_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Material not found")

    ok = delete_material(record_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to delete material")

    log_event(
        action=_add_master_data_action("MATERIAL_DELETED"),
        category=AuditCategory.SYSTEM,
        actor_email=user.get("email", ""),
        actor_name=user.get("name", ""),
        target_type="MaterialMaster",
        target_id=record_id,
        details=json.dumps({"material_code": existing.get("material_code", "")}),
        ip_address=get_request_ip(request),
    )

    return JSONResponse({"ok": True, "message": "Material deleted successfully"})


@router.post("/materials/import")
async def api_import_materials(
    request: Request,
    file: UploadFile = File(...),
    user: dict = Depends(require_permission("master_data.create")),
):
    """
    Bulk import materials from a CSV or Excel file.
    Required column:  material_code
    Optional column:  description
    """
    filename = file.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower()

    try:
        contents = await file.read()
        if ext in ("xlsx", "xls"):
            df = pd.read_excel(io.BytesIO(contents), dtype=str)
        elif ext == "csv":
            df = pd.read_csv(io.BytesIO(contents), dtype=str)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type. Use .csv, .xlsx, or .xls")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read file: {e}")

    # Normalise column headers to lowercase for flexible matching
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    if "material_code" not in df.columns:
        raise HTTPException(
            status_code=400,
            detail=f"File must have a 'material_code' column. Found: {list(df.columns)}",
        )

    rows = df.to_dict("records")
    result = bulk_import_materials(rows)

    log_event(
        action=_add_master_data_action("MATERIALS_IMPORTED"),
        category=AuditCategory.SYSTEM,
        actor_email=user.get("email", ""),
        actor_name=user.get("name", ""),
        target_type="MaterialMaster",
        target_id="bulk",
        details=json.dumps({
            "file": filename,
            "created": result["created"],
            "skipped": result["skipped"],
            "failed": result["failed"],
        }),
        ip_address=get_request_ip(request),
    )

    return JSONResponse({"ok": True, **result})  # materials import


# ============================================================
# Keywords — CRUD
# ============================================================

@router.get("/keywords/list")
async def api_list_keywords(
    request: Request,
    search: str = "",
    page: int = 1,
    page_size: int = 200,
    user: dict = Depends(require_permission("master_data.view")),
):
    try:
        result = list_keywords(search=search or None, page=page, page_size=page_size)
        return JSONResponse({"ok": True, **result})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/keywords/create")
async def api_create_keyword(
    request: Request,
    user: dict = Depends(require_permission("master_data.create")),
):
    data = await request.json()
    kw = (data.get("keyword") or "").strip().upper()

    if not kw:
        raise HTTPException(status_code=400, detail="keyword is required")

    if keyword_exists(kw):
        raise HTTPException(status_code=409, detail=f"Keyword '{kw}' already exists")

    ok = create_keyword(kw)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to create keyword")

    log_event(
        action=_add_master_data_action("KEYWORD_CREATED"),
        category=AuditCategory.SYSTEM,
        actor_email=user.get("email", ""),
        actor_name=user.get("name", ""),
        target_type="Keyword",
        target_id=kw,
        details=json.dumps({"keyword": kw}),
        ip_address=get_request_ip(request),
    )

    return JSONResponse({"ok": True, "message": f"Keyword '{kw}' created successfully"})


@router.put("/keywords/update/{record_id}")
async def api_update_keyword(
    request: Request,
    record_id: str,
    user: dict = Depends(require_permission("master_data.edit")),
):
    data = await request.json()
    kw = (data.get("keyword") or "").strip().upper()

    if not kw:
        raise HTTPException(status_code=400, detail="keyword is required")

    existing = get_keyword(record_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Keyword not found")

    if keyword_exists(kw, exclude_record_id=record_id):
        raise HTTPException(status_code=409, detail=f"Keyword '{kw}' already exists")

    ok = update_keyword(record_id, kw)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to update keyword")

    log_event(
        action=_add_master_data_action("KEYWORD_UPDATED"),
        category=AuditCategory.SYSTEM,
        actor_email=user.get("email", ""),
        actor_name=user.get("name", ""),
        target_type="Keyword",
        target_id=record_id,
        details=json.dumps({"keyword": kw}),
        ip_address=get_request_ip(request),
    )

    return JSONResponse({"ok": True, "message": "Keyword updated successfully"})


@router.delete("/keywords/delete/{record_id}")
async def api_delete_keyword(
    request: Request,
    record_id: str,
    user: dict = Depends(require_permission("master_data.delete")),
):
    existing = get_keyword(record_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Keyword not found")

    ok = delete_keyword(record_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to delete keyword")

    log_event(
        action=_add_master_data_action("KEYWORD_DELETED"),
        category=AuditCategory.SYSTEM,
        actor_email=user.get("email", ""),
        actor_name=user.get("name", ""),
        target_type="Keyword",
        target_id=record_id,
        details=json.dumps({"keyword": existing.get("keyword", "")}),
        ip_address=get_request_ip(request),
    )

    return JSONResponse({"ok": True, "message": "Keyword deleted successfully"})


@router.post("/keywords/import")
async def api_import_keywords(
    request: Request,
    file: UploadFile = File(...),
    user: dict = Depends(require_permission("master_data.create")),
):
    """
    Bulk import keywords from a CSV or Excel file.
    Required column: keyword  (single column, one keyword per row)
    """
    filename = file.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower()

    try:
        contents = await file.read()
        if ext in ("xlsx", "xls"):
            df = pd.read_excel(io.BytesIO(contents), dtype=str)
        elif ext == "csv":
            df = pd.read_csv(io.BytesIO(contents), dtype=str)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type. Use .csv, .xlsx, or .xls")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read file: {e}")

    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Accept first column OR named 'keyword'/'keywords'
    kw_col = None
    for candidate in ("keyword", "keywords"):
        if candidate in df.columns:
            kw_col = candidate
            break
    if kw_col is None and len(df.columns) > 0:
        kw_col = df.columns[0]

    if kw_col is None:
        raise HTTPException(status_code=400, detail="File must have at least one column with keywords")

    keywords_list = [
        str(v).strip() for v in df[kw_col].dropna().tolist() if str(v).strip()
    ]

    result = bulk_import_keywords(keywords_list)

    log_event(
        action=_add_master_data_action("KEYWORDS_IMPORTED"),
        category=AuditCategory.SYSTEM,
        actor_email=user.get("email", ""),
        actor_name=user.get("name", ""),
        target_type="Keyword",
        target_id="bulk",
        details=json.dumps({
            "file": filename,
            "created": result["created"],
            "skipped": result["skipped"],
            "failed": result["failed"],
        }),
        ip_address=get_request_ip(request),
    )

    return JSONResponse({"ok": True, **result})  # keywords import


# ============================================================
# RFP Team Column Definitions — CRUD + Reorder
# ============================================================

@router.get("/rfp-team-columns/list")
async def api_list_rfp_team_columns(
    request: Request,
    search: str = "",
    page: int = 1,
    page_size: int = 100,
    user: dict = Depends(require_permission("master_data.view")),
):
    try:
        result = list_team_columns(search=search or None, page=page, page_size=page_size)
        return JSONResponse({"ok": True, **result})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rfp-team-columns/all")
async def api_get_all_rfp_team_columns(
    request: Request,
    user: dict = Depends(require_permission("master_data.view")),
):
    """Return all active columns sorted by sort_order (used by frontend forms)."""
    try:
        columns = get_all_team_columns()
        return JSONResponse({"ok": True, "columns": columns})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rfp-team-columns/create")
async def api_create_rfp_team_column(
    request: Request,
    user: dict = Depends(require_permission("master_data.create")),
):
    data = await request.json()
    key = (data.get("column_key") or "").strip().lower()
    label = (data.get("column_label") or "").strip()

    if not key or not label:
        raise HTTPException(status_code=400, detail="column_key and column_label are required")

    # Validate column_key format: lowercase alphanumeric + underscores
    import re
    if not re.match(r'^[a-z][a-z0-9_]*$', key):
        raise HTTPException(
            status_code=400,
            detail="column_key must start with a letter and contain only lowercase letters, numbers, and underscores"
        )

    if column_key_exists(key):
        raise HTTPException(status_code=409, detail=f"Column key '{key}' already exists")

    ok = create_team_column(data)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to create column definition")

    log_event(
        action=_add_master_data_action("RFP_TEAM_COLUMN_CREATED"),
        category=AuditCategory.SYSTEM,
        actor_email=user.get("email", ""),
        actor_name=user.get("name", ""),
        target_type="RFPTeamColumn",
        target_id=key,
        details=json.dumps({"column_key": key, "column_label": label, "column_type": data.get("column_type", "text")}),
        ip_address=get_request_ip(request),
    )

    return JSONResponse({"ok": True, "message": f"Column '{label}' created successfully"})


@router.put("/rfp-team-columns/update/{record_id}")
async def api_update_rfp_team_column(
    request: Request,
    record_id: str,
    user: dict = Depends(require_permission("master_data.edit")),
):
    data = await request.json()
    label = (data.get("column_label") or "").strip()

    if not label:
        raise HTTPException(status_code=400, detail="column_label is required")

    existing = get_team_column(record_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Column definition not found")

    ok = update_team_column(record_id, data)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to update column definition")

    log_event(
        action=_add_master_data_action("RFP_TEAM_COLUMN_UPDATED"),
        category=AuditCategory.SYSTEM,
        actor_email=user.get("email", ""),
        actor_name=user.get("name", ""),
        target_type="RFPTeamColumn",
        target_id=record_id,
        details=json.dumps({"column_label": label, "column_type": data.get("column_type", "")}),
        ip_address=get_request_ip(request),
    )

    return JSONResponse({"ok": True, "message": "Column definition updated successfully"})


@router.delete("/rfp-team-columns/delete/{record_id}")
async def api_delete_rfp_team_column(
    request: Request,
    record_id: str,
    user: dict = Depends(require_permission("master_data.delete")),
):
    existing = get_team_column(record_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Column definition not found")

    # Block deletion of protected columns (e.g. email)
    if str(existing.get("is_protected", "")).lower() == "true":
        raise HTTPException(
            status_code=403,
            detail=f"Column '{existing.get('column_label', '')}' is protected and cannot be deleted"
        )

    ok = delete_team_column(record_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to delete column definition")

    log_event(
        action=_add_master_data_action("RFP_TEAM_COLUMN_DELETED"),
        category=AuditCategory.SYSTEM,
        actor_email=user.get("email", ""),
        actor_name=user.get("name", ""),
        target_type="RFPTeamColumn",
        target_id=record_id,
        details=json.dumps({"column_key": existing.get("column_key", ""), "column_label": existing.get("column_label", "")}),
        ip_address=get_request_ip(request),
    )

    return JSONResponse({"ok": True, "message": "Column definition deleted successfully"})


@router.post("/rfp-team-columns/reorder")
async def api_reorder_rfp_team_columns(
    request: Request,
    user: dict = Depends(require_permission("master_data.edit")),
):
    data = await request.json()
    ordered_ids = data.get("ordered_ids", [])

    if not ordered_ids or not isinstance(ordered_ids, list):
        raise HTTPException(status_code=400, detail="ordered_ids must be a non-empty list of record IDs")

    ok = reorder_team_columns(ordered_ids)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to reorder columns")

    log_event(
        action=_add_master_data_action("RFP_TEAM_COLUMNS_REORDERED"),
        category=AuditCategory.SYSTEM,
        actor_email=user.get("email", ""),
        actor_name=user.get("name", ""),
        target_type="RFPTeamColumn",
        target_id="reorder",
        details=json.dumps({"count": len(ordered_ids)}),
        ip_address=get_request_ip(request),
    )

    return JSONResponse({"ok": True, "message": "Columns reordered successfully"})


# ============================================================
# RFP Team — CRUD
# ============================================================

@router.get("/rfp-team/list")
async def api_list_rfp_team(
    request: Request,
    search: str = "",
    page: int = 1,
    page_size: int = 100,
    user: dict = Depends(require_permission("master_data.view")),
):
    try:
        result = list_rfp_team(search=search or None, page=page, page_size=page_size)
        return JSONResponse({"ok": True, **result})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rfp-team/create")
async def api_create_rfp_team_member(
    request: Request,
    user: dict = Depends(require_permission("master_data.create")),
):
    data = await request.json()
    product = (data.get("product") or "").strip()
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()

    if not product or not name or not email:
        raise HTTPException(status_code=400, detail="product, name, and email are all required")

    if rfp_team_member_exists(product, email):
        raise HTTPException(status_code=409, detail=f"Team member with product '{product}' and email '{email}' already exists")

    # Collect extra dynamic fields (anything beyond the core 3 fields)
    known_keys = {"product", "name", "email"}
    extra_fields = {k: v for k, v in data.items() if k not in known_keys and v}

    ok = create_rfp_team_member(product, name, email, extra_fields=extra_fields or None)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to create team member")

    log_event(
        action=_add_master_data_action("RFP_TEAM_CREATED"),
        category=AuditCategory.SYSTEM,
        actor_email=user.get("email", ""),
        actor_name=user.get("name", ""),
        target_type="RFPTeam",
        target_id=email,
        details=json.dumps({"product": product, "name": name, "email": email, **extra_fields}),
        ip_address=get_request_ip(request),
    )

    return JSONResponse({"ok": True, "message": f"Team member '{name}' created successfully"})


@router.put("/rfp-team/update/{record_id}")
async def api_update_rfp_team_member(
    request: Request,
    record_id: str,
    user: dict = Depends(require_permission("master_data.edit")),
):
    data = await request.json()
    product = (data.get("product") or "").strip()
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()

    if not product or not name or not email:
        raise HTTPException(status_code=400, detail="product, name, and email are all required")

    existing = get_rfp_team_member(record_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Team member not found")

    if rfp_team_member_exists(product, email, exclude_record_id=record_id):
        raise HTTPException(status_code=409, detail=f"Team member with product '{product}' and email '{email}' already exists")

    # Collect extra dynamic fields (anything beyond the core 3 fields)
    known_keys = {"product", "name", "email"}
    extra_fields = {k: v for k, v in data.items() if k not in known_keys}

    ok = update_rfp_team_member(record_id, product, name, email, extra_fields=extra_fields if extra_fields else None)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to update team member")

    log_event(
        action=_add_master_data_action("RFP_TEAM_UPDATED"),
        category=AuditCategory.SYSTEM,
        actor_email=user.get("email", ""),
        actor_name=user.get("name", ""),
        target_type="RFPTeam",
        target_id=record_id,
        details=json.dumps({"product": product, "name": name, "email": email, **extra_fields}),
        ip_address=get_request_ip(request),
    )

    return JSONResponse({"ok": True, "message": "Team member updated successfully"})


@router.delete("/rfp-team/delete/{record_id}")
async def api_delete_rfp_team_member(
    request: Request,
    record_id: str,
    user: dict = Depends(require_permission("master_data.delete")),
):
    existing = get_rfp_team_member(record_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Team member not found")

    ok = delete_rfp_team_member(record_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to delete team member")

    log_event(
        action=_add_master_data_action("RFP_TEAM_DELETED"),
        category=AuditCategory.SYSTEM,
        actor_email=user.get("email", ""),
        actor_name=user.get("name", ""),
        target_type="RFPTeam",
        target_id=record_id,
        details=json.dumps({
            "product": existing.get("product", ""),
            "name": existing.get("name", ""),
            "email": existing.get("email", ""),
        }),
        ip_address=get_request_ip(request),
    )

    return JSONResponse({"ok": True, "message": "Team member deleted successfully"})


@router.post("/rfp-team/import")
async def api_import_rfp_team(
    request: Request,
    file: UploadFile = File(...),
    user: dict = Depends(require_permission("master_data.create")),
):
    """
    Bulk import RFP team members from a CSV or Excel file.
    Required columns: product, name, email
    """
    filename = file.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower()

    try:
        contents = await file.read()
        if ext in ("xlsx", "xls"):
            df = pd.read_excel(io.BytesIO(contents), dtype=str)
        elif ext == "csv":
            df = pd.read_csv(io.BytesIO(contents), dtype=str)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type. Use .csv, .xlsx, or .xls")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read file: {e}")

    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    for required_col in ("product", "name", "email"):
        if required_col not in df.columns:
            raise HTTPException(
                status_code=400,
                detail=f"File must have a '{required_col}' column. Found: {list(df.columns)}",
            )

    rows = df.to_dict("records")
    result = bulk_import_rfp_team(rows)

    log_event(
        action=_add_master_data_action("RFP_TEAM_IMPORTED"),
        category=AuditCategory.SYSTEM,
        actor_email=user.get("email", ""),
        actor_name=user.get("name", ""),
        target_type="RFPTeam",
        target_id="bulk",
        details=json.dumps({
            "file": filename,
            "created": result["created"],
            "skipped": result["skipped"],
            "failed": result["failed"],
        }),
        ip_address=get_request_ip(request),
    )

    return JSONResponse({"ok": True, **result})
