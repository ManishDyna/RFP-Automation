"""
Per-RFP file upload page reached from the Adaptive Card "Upload" button.

Flow:
  1. Card embeds: GET /upload?token=<JWT>
  2. Page (inline HTML) presents two multi-file inputs: TIR + Pricing.
  3. Submit -> POST /api/rfp-upload (multipart) with token + lists of files.
  4. Token is verified. TIR files stream to the RFP's TDS-files folder;
     Pricing files stream to the RFP's pricing-files folder. All uploads
     are recorded in the existing RFP response row
     (`cr673_response_data.uploaded_files`).
"""
import json
import os
import re
import tempfile
from datetime import datetime

from typing import List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

from config.config import (
    CLIENT_ID, CLIENT_SECRET, RESOURCE_URL, TENANT_ID,
)
from helpers.core_helper import (
    clean_rfp_title,
    get_sharepoint_rfp_pricing_path,
    get_sharepoint_rfp_tds_path,
)
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
.meta .row {{ display: flex; margin: 3px 0; color: #374151; gap: 8px; }}
.meta .row .k {{ color: #6b7280; flex: 0 0 86px; }}
.meta .row .v {{ color: #1f2937; font-weight: 600; word-break: break-word; overflow-wrap: anywhere; flex: 1; }}
.field {{ margin-bottom: 18px; }}
.field label {{ display: block; font-size: 13px; font-weight: 600; color: #374151; margin-bottom: 6px; }}
.field input[type=file] {{ width: 100%; padding: 10px 12px; border: 1.5px dashed #c7d2fe; border-radius: 8px; font-size: 13px; background: #fafbff; cursor: pointer; }}
.field .hint {{ font-size: 11px; color: #6b7280; margin-top: 4px; }}
.btn {{ width: 100%; padding: 13px; background: #4f46e5; color: #fff; border: none; border-radius: 8px; font-size: 15px; font-weight: 600; cursor: pointer; margin-top: 6px; }}
.btn:hover {{ background: #4338ca; }}
.btn:disabled {{ background: #a5b4fc; cursor: not-allowed; }}
.alert {{ padding: 14px 16px; border-radius: 8px; font-size: 13px; margin-top: 16px; display: none; line-height: 1.45; word-break: break-word; overflow-wrap: anywhere; }}
.alert.err {{ background: #fef2f2; color: #b91c1c; border: 1px solid #fecaca; }}
.alert.ok {{ background: #f0fdf4; color: #15803d; border: 1px solid #bbf7d0; }}
.alert.ok .group-title {{ font-weight: 700; margin-top: 8px; margin-bottom: 4px; color: #14532d; }}
.alert.ok .group-title:first-child {{ margin-top: 0; }}
.alert.ok ul {{ list-style: none; padding: 0; margin: 0 0 4px; }}
.alert.ok li {{ padding: 6px 0; border-bottom: 1px dashed #bbf7d0; }}
.alert.ok li:last-child {{ border-bottom: none; }}
.alert.ok .fname {{ font-weight: 600; color: #14532d; display: block; }}
.alert.ok .fpath {{ font-family: ui-monospace, "Consolas", "Menlo", monospace; font-size: 11px; color: #15803d; opacity: 0.85; display: block; margin-top: 2px; word-break: break-all; }}
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
      <div class="row"><div class="k">RFP ID:</div><div class="v">{rfp_id}</div></div>
      <div class="row"><div class="k">Product:</div><div class="v">{product}</div></div>
      <div class="row"><div class="k">Recipient:</div><div class="v">{email}</div></div>
      <div class="row"><div class="k">Company:</div><div class="v">{company_name}</div></div>
    </div>
    <form id="upForm">
      <input type="hidden" name="token" value="{token}">
      <div class="field">
        <label for="tir">TIR Files <span style="color:#dc2626">*</span></label>
        <input type="file" id="tir" name="tir_files" required multiple accept=".pdf,.doc,.docx,.xls,.xlsx,.png,.jpg,.jpeg,.zip">
        <div class="hint">Select one or more files. Max 25 MB each. Accepted: PDF, Word, Excel, images, ZIP.</div>
      </div>
      <div class="field">
        <label for="pricing">Pricing Files <span style="color:#dc2626">*</span></label>
        <input type="file" id="pricing" name="pricing_files" required multiple accept=".pdf,.doc,.docx,.xls,.xlsx,.png,.jpg,.jpeg,.zip">
        <div class="hint">Select one or more files. Max 25 MB each.</div>
      </div>
      <button type="submit" class="btn" id="submitBtn">Upload Files</button>
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

    const tirFiles = Array.from(document.getElementById('tir').files);
    const pricingFiles = Array.from(document.getElementById('pricing').files);
    if (tirFiles.length === 0 || pricingFiles.length === 0) {{
      errAlert.textContent = 'Please select at least one TIR file and one Pricing file.';
      errAlert.style.display = 'block';
      return;
    }}
    for (const f of tirFiles.concat(pricingFiles)) {{
      if (f.size > MAX_BYTES) {{
        errAlert.textContent = 'File too large: ' + f.name + ' (max 25 MB).';
        errAlert.style.display = 'block';
        return;
      }}
    }}

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>Uploading...';

    const fd = new FormData();
    fd.append('token', form.querySelector('input[name=token]').value);
    for (const f of tirFiles) fd.append('tir_files', f);
    for (const f of pricingFiles) fd.append('pricing_files', f);

    try {{
      const res = await fetch('/api/rfp-upload', {{ method: 'POST', body: fd }});
      const data = await res.json().catch(() => ({{}}));
      if (!res.ok) {{
        errAlert.textContent = (data && data.detail) ? data.detail : 'Upload failed (' + res.status + ').';
        errAlert.style.display = 'block';
        btn.disabled = false;
        btn.textContent = 'Upload Files';
        return;
      }}
      const esc = s => String(s == null ? '' : s)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
      const renderList = items => {{
        if (!items || items.length === 0) return '<ul><li><span class="fname">(none)</span></li></ul>';
        return '<ul>' + items.map(it => {{
          const name = typeof it === 'string' ? it : (it.filename || '');
          const path = typeof it === 'object' && it ? (it.sp_path || '') : '';
          return '<li><span class="fname">' + esc(name) + '</span>'
               + (path ? '<span class="fpath">' + esc(path) + '</span>' : '')
               + '</li>';
        }}).join('') + '</ul>';
      }};
      okAlert.innerHTML =
        '<div class="group-title">TIR uploaded (' + (data.tir_files || []).length + ')</div>' +
        renderList(data.tir_files) +
        '<div class="group-title">Pricing uploaded (' + (data.pricing_files || []).length + ')</div>' +
        renderList(data.pricing_files);
      okAlert.style.display = 'block';
      btn.textContent = 'Uploaded';
    }} catch (err) {{
      errAlert.textContent = 'Network error: ' + err.message;
      errAlert.style.display = 'block';
      btn.disabled = false;
      btn.textContent = 'Upload Files';
    }}
  }});
}})();
</script>
</body></html>"""
    return HTMLResponse(html)


@router.post("/api/rfp-upload")
async def submit_upload(
    token: str = Form(...),
    tir_files: List[UploadFile] = File(...),
    pricing_files: List[UploadFile] = File(...),
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

    if not tir_files or not pricing_files:
        raise HTTPException(status_code=400, detail="At least one TIR file and one Pricing file are required.")

    rfp_title = clean_rfp_title(rfp_id)
    tds_folder = get_sharepoint_rfp_tds_path(rfp_title, company_name)
    pricing_folder = get_sharepoint_rfp_pricing_path(rfp_title, company_name)
    graph_client = _make_graph_client()
    safe_product = re.sub(r'[<>:"/\\|?*\s]+', "_", product).strip("_") or "product"

    new_entries = []
    temp_paths = []
    try:
        for kind, uploads, dest_folder in (
            ("tir", tir_files, tds_folder),
            ("pricing", pricing_files, pricing_folder),
        ):
            for upload in uploads:
                original = _safe_name(upload.filename or f"{kind}.bin")
                ext = os.path.splitext(original)[1] or ""
                dest_filename = f"{rfp_title}__{safe_product}__{kind}__{original}"

                with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                    content = await upload.read()
                    tmp.write(content)
                    tmp_path = tmp.name
                temp_paths.append(tmp_path)

                res = graph_client.upload_file_as(tmp_path, dest_folder, dest_filename)
                if getattr(res, "status_code", 0) not in (200, 201, 202):
                    raise HTTPException(
                        status_code=502,
                        detail=f"SharePoint rejected {kind} upload '{original}': {getattr(res, 'status_code', '?')} {getattr(res, 'text', '')[:200]}",
                    )

                new_entries.append({
                    "kind": kind,
                    "filename": dest_filename,
                    "original_filename": original,
                    "sp_path": f"{dest_folder}/{dest_filename}",
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

    def _summarize(kind: str):
        return [
            {"filename": e["filename"], "sp_path": e["sp_path"]}
            for e in new_entries if e["kind"] == kind
        ]

    return {
        "ok": True,
        "tir_files": _summarize("tir"),
        "pricing_files": _summarize("pricing"),
        "tds_folder": tds_folder,
        "pricing_folder": pricing_folder,
        "preview": is_preview,
    }
