"""
Per-RFP file upload page reached from the Adaptive Card "Upload" button.

Flow:
  1. Card embeds: GET /upload?token=<JWT>
  2. Page (inline HTML) presents two file inputs: TIR + Pricing.
  3. Submit -> POST /api/rfp-upload (multipart) with token + both files.
  4. Token is verified, both files are streamed to SharePoint's TDS-files
     folder for that RFP, and the upload is recorded in the existing
     RFP response row (`cr673_response_data.uploaded_files`).
"""
import json
import os
import re
import tempfile
from datetime import datetime

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

from config.config import (
    CLIENT_ID, CLIENT_SECRET, RESOURCE_URL, TENANT_ID,
)
from helpers.core_helper import clean_rfp_title, get_sharepoint_rfp_tds_path
from helpers.dataverse_helper import DataverseClient
from helpers.sharepoint_helper import GraphClient
from helpers.upload_token import verify_upload_token
from services.system_settings_service import get_setting

router = APIRouter(tags=["RFP Upload"])

_DATAVERSE = DataverseClient(
    tenant_id=TENANT_ID,
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    resource_url=RESOURCE_URL,
)

# ── Preview mode ─────────────────────────────────────────────────────────────
# Sentinel token that bypasses JWT verification and runs the upload page in a
# demo mode. Files uploaded via this path land in a dedicated SharePoint folder
# (no real RFP/Dataverse pollution). The link is exposed in the admin Add Column
# dialog so admins can test the whole upload flow without sending a real email.
PREVIEW_TOKEN = "DEMO_PREVIEW"
PREVIEW_RFP_ID = "PREVIEW-UPLOADS"
PREVIEW_COMPANY = "DEMO"
PREVIEW_PRODUCT = "Demo Product"
PREVIEW_EMAIL = "preview@admin.demo"


def _preview_claims() -> dict:
    return {
        "rfp_id": PREVIEW_RFP_ID,
        "email": PREVIEW_EMAIL,
        "product": PREVIEW_PRODUCT,
        "company_name": PREVIEW_COMPANY,
    }


def _safe_name(name: str) -> str:
    name = os.path.basename(name or "file")
    return re.sub(r'[<>:"/\\|?*]', "_", name).strip().rstrip(".") or "file"


def _make_graph_client() -> GraphClient:
    client = GraphClient(
        get_setting("CLIENT_ID", ""),
        get_setting("CLIENT_SECRET", ""),
        get_setting("TENANT_ID", ""),
        get_setting("SHAREPOINT_HOSTNAME", ""),
        get_setting("SITE_PATH", ""),
        get_setting("DRIVE_NAME", ""),
    )
    client.auth()
    client.resolve_site_and_drive()
    return client


def _append_upload_records(rfp_id: str, email: str, product: str, company_name: str, new_entries: list):
    """Read the RFP response row, append new uploads to response_data.uploaded_files, upsert."""
    table_api = get_setting("RFP_RESPONSE_TABLE_API", "")
    table_logical = get_setting("RFP_RESPONSE_TABLE_LOGICAL", "")

    existing = _DATAVERSE.query_rows(
        table_api,
        filter_expr=f"cr673_rfp_id eq '{rfp_id}' and cr673_email eq '{email}'",
        top=1,
        table_logical_name=table_logical,
        use_display_names=True,
    )

    response_data = {"products": [], "uploaded_files": []}
    record_id = None

    if existing and "value" in existing and len(existing["value"]) > 0:
        row = existing["value"][0]
        raw = row.get("cr673_response_data") or row.get("Response Data") or ""
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    response_data["products"] = parsed.get("products", [])
                    response_data["uploaded_files"] = parsed.get("uploaded_files", [])
            except (json.JSONDecodeError, TypeError):
                pass

        pk_logical = f"{table_logical}id"
        try:
            colmap = _DATAVERSE.get_column_mapping(table_logical)
            logical_to_display = {v: k for k, v in colmap.items()}
        except Exception:
            logical_to_display = {}
        pk_display = logical_to_display.get(pk_logical)
        record_id = (row.get(pk_display) if pk_display else None) or row.get(pk_logical)

    response_data["uploaded_files"].extend(new_entries)

    row_data = {
        "cr673_rfp_id": rfp_id,
        "cr673_email": email,
        "cr673_product": product,
        "cr673_company_name": company_name,
        "cr673_response_data": json.dumps(response_data),
        "cr673_submitted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    if record_id:
        _DATAVERSE.update_row(
            table_api, record_id, row_data,
            table_logical_name=table_logical, use_display_names=True,
        )
    else:
        _DATAVERSE.insert_row(
            table_api, row_data,
            table_logical_name=table_logical, use_display_names=True,
        )


def _render_error_page(message: str, status: int = 400) -> HTMLResponse:
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Upload Error</title>
<style>
body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f5f6fa; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }}
.card {{ background: #fff; padding: 32px 36px; border-radius: 12px; box-shadow: 0 12px 40px rgba(0,0,0,0.08); max-width: 480px; }}
h1 {{ color: #dc2626; font-size: 20px; margin: 0 0 12px; }}
p {{ color: #374151; font-size: 14px; line-height: 1.5; }}
</style></head>
<body><div class="card"><h1>Upload Error</h1><p>{message}</p></div></body></html>"""
    return HTMLResponse(html, status_code=status)


@router.get("/upload")
async def upload_page(token: str = ""):
    """Render the TIR + Pricing upload form."""
    if not token:
        return _render_error_page("Missing token. Open this page from the Upload button in your RFP email.", 400)

    if token == PREVIEW_TOKEN:
        claims = _preview_claims()
        is_preview = True
    else:
        try:
            claims = verify_upload_token(token)
        except HTTPException as e:
            return _render_error_page(e.detail, e.status_code)
        is_preview = False

    rfp_id = claims.get("rfp_id", "")
    email = claims.get("email", "")
    product = claims.get("product", "")
    company_name = claims.get("company_name", "")

    preview_banner = (
        '<div style="background:#fef3c7;border:1px solid #f59e0b;color:#92400e;'
        'padding:10px 14px;margin:0 0 16px;border-radius:6px;font-size:13px;'
        'font-weight:600;">'
        '⚠ PREVIEW MODE — This is a demo. Files you upload here are saved to '
        'the demo folder (not a real RFP) so you can verify the upload flow works.'
        '</div>'
    ) if is_preview else ""

    html = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Upload RFP Files - {rfp_id}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ min-height: 100vh; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); font-family: 'Segoe UI', Arial, sans-serif; padding: 24px; display: flex; align-items: center; justify-content: center; }}
.card {{ background: #fff; border-radius: 14px; box-shadow: 0 20px 60px rgba(0,0,0,0.18); width: 100%; max-width: 520px; overflow: hidden; }}
.card-header {{ background: #4f46e5; color: #fff; padding: 24px 32px; }}
.card-header h1 {{ font-size: 20px; font-weight: 600; margin: 0 0 4px; }}
.card-header .sub {{ font-size: 13px; opacity: 0.85; }}
.card-body {{ padding: 28px 32px 32px; }}
.meta {{ background: #f3f4f6; border-radius: 8px; padding: 14px 16px; font-size: 13px; margin-bottom: 22px; }}
.meta div {{ margin: 3px 0; color: #374151; }}
.meta span {{ color: #6b7280; display: inline-block; min-width: 86px; }}
.meta b {{ color: #1f2937; }}
.field {{ margin-bottom: 18px; }}
.field label {{ display: block; font-size: 13px; font-weight: 600; color: #374151; margin-bottom: 6px; }}
.field input[type=file] {{ width: 100%; padding: 10px 12px; border: 1.5px dashed #c7d2fe; border-radius: 8px; font-size: 13px; background: #fafbff; cursor: pointer; }}
.field .hint {{ font-size: 11px; color: #6b7280; margin-top: 4px; }}
.btn {{ width: 100%; padding: 13px; background: #4f46e5; color: #fff; border: none; border-radius: 8px; font-size: 15px; font-weight: 600; cursor: pointer; margin-top: 6px; }}
.btn:hover {{ background: #4338ca; }}
.btn:disabled {{ background: #a5b4fc; cursor: not-allowed; }}
.alert {{ padding: 12px 14px; border-radius: 8px; font-size: 13px; margin-top: 16px; display: none; }}
.alert.err {{ background: #fef2f2; color: #b91c1c; border: 1px solid #fecaca; }}
.alert.ok {{ background: #f0fdf4; color: #15803d; border: 1px solid #bbf7d0; }}
.spinner {{ display: inline-block; width: 14px; height: 14px; border: 2px solid #fff; border-top-color: transparent; border-radius: 50%; animation: spin 0.6s linear infinite; margin-right: 8px; vertical-align: -2px; }}
@keyframes spin {{ to {{ transform: rotate(360deg); }} }}
</style></head>
<body>
<div class="card">
  <div class="card-header">
    <h1>Upload RFP Files</h1>
    <div class="sub">TIR & Pricing for your assigned product</div>
  </div>
  <div class="card-body">
    {preview_banner}
    <div class="meta">
      <div><span>RFP ID:</span><b>{rfp_id}</b></div>
      <div><span>Product:</span><b>{product}</b></div>
      <div><span>Recipient:</span><b>{email}</b></div>
      <div><span>Company:</span><b>{company_name}</b></div>
    </div>
    <form id="upForm">
      <input type="hidden" name="token" value="{token}">
      <div class="field">
        <label for="tir">TIR File <span style="color:#dc2626">*</span></label>
        <input type="file" id="tir" name="tir_file" required accept=".pdf,.doc,.docx,.xls,.xlsx,.png,.jpg,.jpeg,.zip">
        <div class="hint">Max 25 MB. Accepted: PDF, Word, Excel, images, ZIP.</div>
      </div>
      <div class="field">
        <label for="pricing">Pricing File <span style="color:#dc2626">*</span></label>
        <input type="file" id="pricing" name="pricing_file" required accept=".pdf,.doc,.docx,.xls,.xlsx,.png,.jpg,.jpeg,.zip">
        <div class="hint">Max 25 MB.</div>
      </div>
      <button type="submit" class="btn" id="submitBtn">Upload Both Files</button>
      <div class="alert err" id="errAlert"></div>
      <div class="alert ok" id="okAlert"></div>
    </form>
  </div>
</div>
<script>
(function(){{
  const form = document.getElementById('upForm');
  const btn = document.getElementById('submitBtn');
  const errAlert = document.getElementById('errAlert');
  const okAlert = document.getElementById('okAlert');
  const MAX_BYTES = 25 * 1024 * 1024;

  form.addEventListener('submit', async function(e){{
    e.preventDefault();
    errAlert.style.display = 'none';
    okAlert.style.display = 'none';

    const tir = document.getElementById('tir').files[0];
    const pricing = document.getElementById('pricing').files[0];
    if (!tir || !pricing) {{
      errAlert.textContent = 'Please select both files.';
      errAlert.style.display = 'block';
      return;
    }}
    for (const f of [tir, pricing]) {{
      if (f.size > MAX_BYTES) {{
        errAlert.textContent = 'File too large: ' + f.name + ' (max 25 MB).';
        errAlert.style.display = 'block';
        return;
      }}
    }}

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>Uploading...';

    const fd = new FormData(form);
    try {{
      const res = await fetch('/api/rfp-upload', {{ method: 'POST', body: fd }});
      const data = await res.json().catch(() => ({{}}));
      if (!res.ok) {{
        errAlert.textContent = (data && data.detail) ? data.detail : 'Upload failed (' + res.status + ').';
        errAlert.style.display = 'block';
        btn.disabled = false;
        btn.textContent = 'Upload Both Files';
        return;
      }}
      okAlert.innerHTML = 'Uploaded successfully:<br>&bull; ' + (data.tir || '?') + '<br>&bull; ' + (data.pricing || '?');
      okAlert.style.display = 'block';
      btn.textContent = 'Uploaded';
    }} catch (err) {{
      errAlert.textContent = 'Network error: ' + err.message;
      errAlert.style.display = 'block';
      btn.disabled = false;
      btn.textContent = 'Upload Both Files';
    }}
  }});
}})();
</script>
</body></html>"""
    return HTMLResponse(html)


@router.post("/api/rfp-upload")
async def submit_upload(
    token: str = Form(...),
    tir_file: UploadFile = File(...),
    pricing_file: UploadFile = File(...),
):
    if token == PREVIEW_TOKEN:
        claims = _preview_claims()
        is_preview = True
    else:
        claims = verify_upload_token(token)
        is_preview = False

    rfp_id = claims["rfp_id"]
    email = claims["email"]
    product = claims["product"]
    company_name = claims["company_name"]

    tds_folder = get_sharepoint_rfp_tds_path(clean_rfp_title(rfp_id), company_name)
    graph_client = _make_graph_client()

    new_entries = []
    temp_paths = []
    try:
        for kind, upload in (("tir", tir_file), ("pricing", pricing_file)):
            original = _safe_name(upload.filename or f"{kind}.bin")
            ext = os.path.splitext(original)[1] or ""
            safe_product = re.sub(r'[<>:"/\\|?*\s]+', "_", product).strip("_") or "product"
            dest_filename = f"{clean_rfp_title(rfp_id)}__{safe_product}__{kind}__{original}"

            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                content = await upload.read()
                tmp.write(content)
                tmp_path = tmp.name
            temp_paths.append(tmp_path)

            res = graph_client.upload_file_as(tmp_path, tds_folder, dest_filename)
            if getattr(res, "status_code", 0) not in (200, 201, 202):
                raise HTTPException(
                    status_code=502,
                    detail=f"SharePoint rejected {kind} upload: {getattr(res, 'status_code', '?')} {getattr(res, 'text', '')[:200]}",
                )

            new_entries.append({
                "kind": kind,
                "filename": dest_filename,
                "original_filename": original,
                "sp_path": f"{tds_folder}/{dest_filename}",
                "product": product,
                "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "size_bytes": len(content),
            })

        if not is_preview:
            _append_upload_records(rfp_id, email, product, company_name, new_entries)
    finally:
        for p in temp_paths:
            try:
                os.unlink(p)
            except OSError:
                pass

    return {
        "ok": True,
        "tir": new_entries[0]["filename"],
        "pricing": new_entries[1]["filename"],
        "sp_folder": tds_folder,
        "preview": is_preview,
    }
