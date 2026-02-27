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

    return JSONResponse({"ok": True, **result})


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

    return JSONResponse({"ok": True, **result})
