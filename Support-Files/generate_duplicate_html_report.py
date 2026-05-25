"""
Duplicate RFP HTML Report Generator (READ-ONLY)
================================================
Produces a single self-contained HTML dashboard so you can review the
duplicate-RFP situation visually before any cleanup runs.

The report shows:
  1. Executive overview     - row counts, duplicate counts, projected size after cleanup
  2. Per-RFP differences    - sortable / filterable table with every duplicate pair
                              and what's different between keeper and duplicate
  3. Authoritative sources  - where in the system the original portal RFP data lives
                              (local Excel files, master-sync preview CSVs)
  4. Recommended actions    - per-field update plan with the rationale

No Dataverse writes. No portal calls. Safe to run any time.

Usage:
    python Support-Files/generate_duplicate_html_report.py
"""

import csv
import glob
import html
import json
import os
import sys
from collections import defaultdict, Counter
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from config.config import (                                          # noqa: E402
    TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL,
    RFP_ACTIVITY_LOG_TABLE_API, RFP_ACTIVITY_LOG_TABLE_LOGICAL,
    OUTPUT_DIR,
)
from helpers.dataverse_helper import DataverseClient                 # noqa: E402

# Reuse the analysis logic from the existing read-only script
sys.path.insert(0, os.path.join(PROJECT_ROOT, "Support-Files"))
from analyze_duplicate_rfps import (                                 # noqa: E402
    normalize_rfp_id, match_key, _is_blank, _val, pick_keeper,
    merge_field, is_conflict, _matched_data_signature,
    ALL_FIELDS, IDENTITY_FIELDS, WORKFLOW_FIELDS, CRITICAL_CONFLICT_FIELDS,
    CASE_INSENSITIVE_FIELDS,
)


ALLRFPS_DIR = os.path.join(PROJECT_ROOT, "ALLRFPs")
OUTPUT_REPORT_DIR = os.path.join(PROJECT_ROOT, "Support-Files", "output")


# ─────────────────────────────────────────────────────────────────────────────
# Local-file lookup: does ALLRFPs/<company>/<rfp_id>/downloaded-rfp/<...>.xlsx exist?
# ─────────────────────────────────────────────────────────────────────────────

def build_local_file_index():
    """Scan ALLRFPs and return:
       { normalized_lower_rfp_id : [list of file paths] }
    Looks at folder name AND filename so we catch both naming styles."""
    index = defaultdict(list)
    if not os.path.isdir(ALLRFPS_DIR):
        return index
    for company in os.listdir(ALLRFPS_DIR):
        company_dir = os.path.join(ALLRFPS_DIR, company)
        if not os.path.isdir(company_dir):
            continue
        for rfp_folder in os.listdir(company_dir):
            rfp_dir = os.path.join(company_dir, rfp_folder)
            if not os.path.isdir(rfp_dir):
                continue
            # Index by folder name (commonly the RFP_ID)
            key = match_key(rfp_folder)
            # Pick the actual downloaded file inside, if present
            files_here = []
            for root, _, files in os.walk(rfp_dir):
                for fn in files:
                    if fn.lower().endswith((".xlsx", ".xls")):
                        files_here.append(os.path.join(root, fn))
                        # Also index by filename (without ext)
                        stem = os.path.splitext(fn)[0]
                        index[match_key(stem)].append(os.path.join(root, fn))
            for fp in files_here:
                index[key].append(fp)
    # Dedup
    return {k: sorted(set(v)) for k, v in index.items()}


# ─────────────────────────────────────────────────────────────────────────────
# master_rfp_preview lookup: portal_value vs db_value for specific RFP IDs
# ─────────────────────────────────────────────────────────────────────────────

def build_master_preview_index():
    """Scan master_rfp_preview_*.csv files and return:
       { normalized_lower_rfp_id : { field : portal_value } }
    Latest entry wins if multiple files reference the same RFP_ID."""
    out = defaultdict(dict)
    src_files = sorted(glob.glob(os.path.join(OUTPUT_REPORT_DIR, "master_rfp_preview_*.csv")))
    for src in src_files:
        try:
            with open(src, encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rid = (row.get("rfp_id") or "").strip()
                    if not rid:
                        continue
                    key = match_key(rid)
                    fld = (row.get("field") or "").strip()
                    portal_val = (row.get("portal_value") or "").strip()
                    if fld and portal_val:
                        out[key][fld] = {
                            "portal_value": portal_val,
                            "db_value": (row.get("db_value") or "").strip(),
                            "status": (row.get("status") or "").strip(),
                            "source_file": os.path.basename(src),
                        }
        except Exception as e:
            print(f"  [WARN] could not read {src}: {e}")
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Pair-level diff (mirrors analyze_duplicate_rfps.py but returns structured data)
# ─────────────────────────────────────────────────────────────────────────────

def diff_pair(keeper, dup):
    diffs = []
    critical_count = 0
    metadata_differs = False
    for fld in ALL_FIELDS:
        kv = _val(keeper, fld)
        dv = _val(dup, fld)
        merged, src = merge_field(fld, kv, dv)
        conf = is_conflict(fld, kv, dv)
        kb = _is_blank(kv); db = _is_blank(dv)
        d = {"field": fld, "keeper": kv, "dup": dv, "merged": merged, "merge_source": src,
             "category": None}
        if kb and db:
            continue
        if fld == "RFP_ID":
            d["category"] = "rfp_id_format" if normalize_rfp_id(dv) != dv else "ok"
        elif kb and not db:
            d["category"] = "merge_takes_from_dup"
        elif db and not kb:
            d["category"] = "merge_keeps_keeper"
        elif fld == "Matched_Data":
            if conf:
                d["category"] = "matched_data_real_conflict"
                critical_count += 1
            else:
                continue
        elif kv.lower() == dv.lower():
            d["category"] = "case_only"
        elif " ".join(kv.split()).lower() == " ".join(dv.split()).lower():
            d["category"] = "whitespace_only"
        elif conf:
            d["category"] = "precedence_resolved"
            if fld in CRITICAL_CONFLICT_FIELDS:
                critical_count += 1
        else:
            d["category"] = "metadata_differs"
            metadata_differs = True
        diffs.append(d)
    return diffs, critical_count, metadata_differs


# ─────────────────────────────────────────────────────────────────────────────
# HTML rendering
# ─────────────────────────────────────────────────────────────────────────────

CATEGORY_LABELS = {
    "rfp_id_format": ("RFP_ID format", "warn"),
    "merge_takes_from_dup": ("Keeper blank, merge takes from duplicate", "good"),
    "merge_keeps_keeper": ("Duplicate blank, merge keeps keeper", "good"),
    "case_only": ("Same value, case difference only", "muted"),
    "whitespace_only": ("Same value, whitespace difference only", "muted"),
    "precedence_resolved": ("Both have data, resolved by precedence rule", "warn"),
    "metadata_differs": ("Metadata differs — portal is source of truth", "danger"),
    "matched_data_real_conflict": ("Matched_Data materials differ", "danger"),
    "ok": ("OK", "good"),
}


def render_html(report):
    """Build the full HTML document as a string."""
    data_json = json.dumps(report, default=str)

    # The HTML uses a small bit of vanilla JS for sorting / filtering.
    # No external assets — fully self-contained.
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Duplicate RFP Report — Bahra RFPs V2</title>
<style>
  :root {{
    --bg: #f7f8fb;
    --card: #ffffff;
    --border: #e3e6ee;
    --text: #1a1f36;
    --muted: #6b7280;
    --primary: #2563eb;
    --good: #059669;
    --warn: #d97706;
    --danger: #dc2626;
    --good-bg: #ecfdf5;
    --warn-bg: #fffbeb;
    --danger-bg: #fef2f2;
    --muted-bg: #f3f4f6;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--bg); color: var(--text);
    font-size: 14px; line-height: 1.5;
  }}
  header {{
    background: linear-gradient(135deg, #1e40af, #2563eb);
    color: white; padding: 28px 40px;
  }}
  header h1 {{ margin: 0; font-size: 24px; font-weight: 600; }}
  header .meta {{ margin-top: 6px; opacity: 0.85; font-size: 13px; }}
  main {{ padding: 24px 40px 60px; max-width: 1600px; margin: 0 auto; }}
  section {{ margin-bottom: 32px; }}
  h2 {{
    margin: 0 0 12px; font-size: 17px; font-weight: 600;
    padding-bottom: 8px; border-bottom: 1px solid var(--border);
  }}
  h2 .count {{
    font-size: 12px; color: var(--muted); font-weight: 400;
    margin-left: 8px;
  }}
  .grid {{ display: grid; gap: 16px; }}
  .cards {{ grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }}
  .card {{
    background: var(--card); border: 1px solid var(--border);
    border-radius: 8px; padding: 16px;
  }}
  .card .label {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; }}
  .card .value {{ font-size: 28px; font-weight: 600; margin-top: 4px; }}
  .card .sub {{ color: var(--muted); font-size: 12px; margin-top: 4px; }}
  .card.good .value {{ color: var(--good); }}
  .card.warn .value {{ color: var(--warn); }}
  .card.danger .value {{ color: var(--danger); }}
  .badge {{
    display: inline-block; padding: 2px 8px; border-radius: 10px;
    font-size: 11px; font-weight: 500; margin: 1px 2px;
  }}
  .badge.good   {{ background: var(--good-bg);   color: var(--good); }}
  .badge.warn   {{ background: var(--warn-bg);   color: var(--warn); }}
  .badge.danger {{ background: var(--danger-bg); color: var(--danger); }}
  .badge.muted  {{ background: var(--muted-bg);  color: var(--muted); }}
  table {{
    width: 100%; border-collapse: collapse; background: var(--card);
    border: 1px solid var(--border); border-radius: 8px; overflow: hidden;
  }}
  th, td {{
    text-align: left; padding: 10px 12px; vertical-align: top;
    border-bottom: 1px solid var(--border); font-size: 13px;
  }}
  th {{
    background: #fafbfd; color: var(--muted); font-weight: 600;
    text-transform: uppercase; font-size: 11px; letter-spacing: 0.04em;
    cursor: pointer; user-select: none;
  }}
  th:hover {{ background: #f1f3f8; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover {{ background: #fafbfd; }}
  tr.expanded {{ background: #f6f9ff; }}
  .filter-row {{
    display: flex; gap: 12px; margin-bottom: 12px; flex-wrap: wrap;
    align-items: center;
  }}
  .filter-row input, .filter-row select {{
    padding: 8px 10px; border: 1px solid var(--border); border-radius: 6px;
    font-size: 13px; background: var(--card);
  }}
  .filter-row input[type=text] {{ min-width: 280px; }}
  .filter-row .summary {{ color: var(--muted); margin-left: auto; }}
  .toggle {{
    cursor: pointer; background: none; border: 1px solid var(--border);
    border-radius: 4px; padding: 2px 6px; font-size: 11px; color: var(--muted);
  }}
  .toggle:hover {{ background: #f1f3f8; }}
  .diff-detail {{
    display: none; background: #f8fafc; padding: 12px 16px;
    border-left: 3px solid var(--primary);
  }}
  .diff-detail.open {{ display: table-row; }}
  .diff-detail-inner {{ padding: 12px; }}
  .diff-list {{ margin: 8px 0 0; padding: 0; list-style: none; }}
  .diff-list li {{
    padding: 6px 0; border-bottom: 1px dashed var(--border); font-size: 13px;
  }}
  .diff-list li:last-child {{ border-bottom: none; }}
  .diff-field {{ font-family: ui-monospace, "SF Mono", Menlo, monospace; font-weight: 600; }}
  .diff-vals {{ color: var(--muted); margin-left: 8px; }}
  .diff-vals .kw {{ color: var(--text); font-family: ui-monospace, monospace; background: #fff; padding: 1px 4px; border-radius: 3px; border: 1px solid var(--border); }}
  .file-link {{
    display: block; font-family: ui-monospace, monospace;
    font-size: 11px; color: var(--primary); word-break: break-all;
    margin: 2px 0;
  }}
  .file-link.muted {{ color: var(--muted); }}
  .small {{ font-size: 12px; color: var(--muted); }}
  .pill {{
    display: inline-block; padding: 2px 8px; border-radius: 999px;
    font-size: 11px; background: var(--muted-bg); color: var(--text);
    margin-right: 4px;
  }}
  .pill.good   {{ background: var(--good-bg);   color: var(--good); }}
  .pill.warn   {{ background: var(--warn-bg);   color: var(--warn); }}
  .pill.danger {{ background: var(--danger-bg); color: var(--danger); }}
  code.mono {{ font-family: ui-monospace, monospace; font-size: 12px; }}
  .legend {{ display: flex; gap: 14px; flex-wrap: wrap; margin: 8px 0 0; }}
  .legend span {{ font-size: 11px; color: var(--muted); display: flex; align-items: center; gap: 4px; }}
  .legend span::before {{
    content: ""; width: 10px; height: 10px; border-radius: 2px; display: inline-block;
  }}
  .legend span.good::before   {{ background: var(--good); }}
  .legend span.warn::before   {{ background: var(--warn); }}
  .legend span.danger::before {{ background: var(--danger); }}
  .legend span.muted::before  {{ background: var(--muted); }}
  .src-icon {{ display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 10px; font-weight: 600; letter-spacing: 0.04em; margin: 1px 2px; }}
  .src-icon.has-local {{ background: var(--good-bg); color: var(--good); }}
  .src-icon.no-local  {{ background: var(--muted-bg); color: var(--muted); }}
  .src-icon.has-portal {{ background: #eef2ff; color: #4338ca; }}
  details.action-plan summary {{ cursor: pointer; padding: 6px 0; font-weight: 600; }}
  details.action-plan .action-row {{ padding: 6px 0 6px 16px; }}
  .scroll-x {{ overflow-x: auto; }}
</style>
</head>
<body>

<header>
  <h1>Duplicate RFP Report — Bahra RFPs V2</h1>
  <div class="meta">Generated {report['generated_at']} &nbsp;·&nbsp; READ-ONLY analysis &nbsp;·&nbsp; no Dataverse changes were made</div>
</header>

<main>

  <!-- ========== 1. OVERVIEW ========== -->
  <section>
    <h2>1. Overview</h2>
    <div class="grid cards">
      <div class="card">
        <div class="label">Total rows in table</div>
        <div class="value">{report['stats']['total_rows']:,}</div>
        <div class="sub">cr673_bahra_rfps_v2</div>
      </div>
      <div class="card good">
        <div class="label">Unique RFPs (after dedup)</div>
        <div class="value">{report['stats']['unique_rfps']:,}</div>
        <div class="sub">distinct normalized RFP IDs</div>
      </div>
      <div class="card warn">
        <div class="label">Duplicate pairs</div>
        <div class="value">{report['stats']['duplicate_pairs']:,}</div>
        <div class="sub">each appears twice in the table</div>
      </div>
      <div class="card danger">
        <div class="label">Stale rows to remove</div>
        <div class="value">{report['stats']['rows_to_delete']:,}</div>
        <div class="sub">double-space / case variants</div>
      </div>
      <div class="card">
        <div class="label">Projected table size</div>
        <div class="value">{report['stats']['projected_size']:,}</div>
        <div class="sub">after merge + cleanup</div>
      </div>
      <div class="card">
        <div class="label">Auto-merge clean</div>
        <div class="value">{report['stats']['auto_clean_pairs']:,}</div>
        <div class="sub">no judgement needed</div>
      </div>
      <div class="card warn">
        <div class="label">Pairs with metadata differences</div>
        <div class="value">{report['stats']['metadata_differs_pairs']:,}</div>
        <div class="sub">portal lookup recommended</div>
      </div>
      <div class="card danger">
        <div class="label">Pairs with true conflict</div>
        <div class="value">{report['stats']['true_conflict_pairs']:,}</div>
        <div class="sub">precedence rule decides</div>
      </div>
    </div>
  </section>

  <!-- ========== 2. AUTHORITATIVE PORTAL DATA IN THE SYSTEM ========== -->
  <section>
    <h2>2. Where authoritative portal data lives in the system</h2>
    <div class="grid cards">
      <div class="card">
        <div class="label">Downloaded RFP Excel files</div>
        <div class="value">{report['stats']['local_file_count']:,}</div>
        <div class="sub">in <code class="mono">ALLRFPs/&lt;Company&gt;/&lt;RFP_ID&gt;/downloaded-rfp/</code></div>
      </div>
      <div class="card good">
        <div class="label">Duplicate pairs with a local Excel file</div>
        <div class="value">{report['stats']['pairs_with_local_file']:,}</div>
        <div class="sub">of {report['stats']['duplicate_pairs']:,} — we have authoritative data for these</div>
      </div>
      <div class="card warn">
        <div class="label">Duplicate pairs with NO local file</div>
        <div class="value">{report['stats']['pairs_without_local_file']:,}</div>
        <div class="sub">would need a live portal lookup</div>
      </div>
      <div class="card">
        <div class="label">master_rfp_preview portal-comparison entries</div>
        <div class="value">{report['stats']['master_preview_pair_coverage']:,}</div>
        <div class="sub">pairs already analyzed against portal in older sync runs</div>
      </div>
    </div>
    <p class="small" style="margin-top: 14px;">
      <strong>What this means:</strong> The system already holds authoritative portal data for
      {report['stats']['pairs_with_local_file']:,} of {report['stats']['duplicate_pairs']:,} duplicate pairs in the
      <code class="mono">ALLRFPs/</code> tree. For these, the merge does not need a live portal
      call — the original downloaded Excel is the source of truth.
    </p>
    <p class="small">
      Per-RFP file paths and portal-comparison hits are shown in the table below (click any row to expand).
    </p>
  </section>

  <!-- ========== 3. PER-RFP DIFFERENCES ========== -->
  <section>
    <h2>3. Per-RFP differences <span class="count">({len(report['pairs'])} duplicate pairs)</span></h2>

    <div class="legend">
      <span class="good">Safe / clean</span>
      <span class="warn">Needs attention (metadata differs)</span>
      <span class="danger">True conflict (precedence-resolved, sanity-check recommended)</span>
      <span class="muted">Cosmetic only</span>
    </div>

    <div class="filter-row" style="margin-top: 12px;">
      <input type="text" id="search-input" placeholder="Search by RFP ID, company, owner, or any field value…">
      <select id="status-filter">
        <option value="">All pairs</option>
        <option value="metadata_differs">With metadata differs</option>
        <option value="true_conflict">With true conflict</option>
        <option value="has_local_file">With local Excel file</option>
        <option value="no_local_file">Without local Excel file</option>
        <option value="clean">Auto-merge clean only</option>
      </select>
      <button class="toggle" id="expand-all">Expand all</button>
      <button class="toggle" id="collapse-all">Collapse all</button>
      <span class="summary" id="filter-summary"></span>
    </div>

    <div class="scroll-x">
      <table id="pairs-table">
        <thead>
          <tr>
            <th data-sort="key">RFP ID (normalized)</th>
            <th data-sort="company">Company</th>
            <th data-sort="diffs">Diffs</th>
            <th data-sort="metadata">Metadata?</th>
            <th data-sort="critical">Conflicts?</th>
            <th data-sort="local">Local file?</th>
            <th>Status</th>
            <th></th>
          </tr>
        </thead>
        <tbody id="pairs-body"></tbody>
      </table>
    </div>
  </section>

  <!-- ========== 4. RECOMMENDED ACTIONS ========== -->
  <section>
    <h2>4. Recommended update plan (per field tier)</h2>
    <p class="small">
      The execute script will <strong>UPDATE</strong> each keeper row in place with values merged from its
      duplicate (only changing fields that need changing) and then <strong>DELETE</strong> the duplicate row
      after writing a full backup CSV. The merge does <em>not</em> blindly overwrite — fields are evaluated tier by tier.
    </p>
    <table>
      <thead>
        <tr>
          <th>Tier / Field</th>
          <th>Source rule</th>
          <th>Why</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><code class="mono">RFP_ID</code></td>
          <td>Always normalized whitespace, keeper's case preserved</td>
          <td>Eliminates the root cause of the duplicate</td>
        </tr>
        <tr>
          <td><strong>Tier 1 — Identity</strong><br><code class="mono">Link, owner_name, publish_time, RFP_End_Date, Company_Name, rfp_type</code></td>
          <td>Portal value if local Excel exists; else non-empty value from either row (keeper preferred on true tie)</td>
          <td>Many duplicates carry the Link / rfp_type that the keeper lacks — merge preserves these</td>
        </tr>
        <tr>
          <td><strong>Tier 2 — Workflow state</strong><br><code class="mono">Email_Status, participated, Email_Sent_At, Reminder_*_Sent</code></td>
          <td>Active state wins (sent &gt; blank, submitted &gt; yes &gt; no, etc.)</td>
          <td>Whichever row reflects the real workflow action keeps its value</td>
        </tr>
        <tr>
          <td><code class="mono">response_count, first_response_at, all_responses_at</code></td>
          <td>max() / earliest-first / latest-last</td>
          <td>Preserves the most-complete view of inbound responses</td>
        </tr>
        <tr>
          <td><code class="mono">Matched_Data</code></td>
          <td>Whichever JSON has more matched-material entries</td>
          <td>Material content is identical in 725/725 pairs — either side is safe; pick the richer one</td>
        </tr>
      </tbody>
    </table>
  </section>

</main>

<script>
const REPORT = {data_json};

const pairs = REPORT.pairs;
const body  = document.getElementById('pairs-body');
const search = document.getElementById('search-input');
const status = document.getElementById('status-filter');
const summary = document.getElementById('filter-summary');

let currentSort = {{ key: 'key', dir: 'asc' }};
let currentRows = [];

function badgeForCategory(cat) {{
  const labels = {json.dumps(CATEGORY_LABELS)};
  const entry = labels[cat] || [cat, 'muted'];
  return `<span class="badge ${{entry[1]}}">${{entry[0]}}</span>`;
}}

function renderDiffList(pair) {{
  if (!pair.diffs.length) {{
    return '<em>(no field-level differences detected)</em>';
  }}
  let out = '<ul class="diff-list">';
  for (const d of pair.diffs) {{
    const k = d.keeper === '' ? '<em class="kw">(blank)</em>' : '<span class="kw">' + escapeHtml(d.keeper.slice(0,140)) + '</span>';
    const u = d.dup    === '' ? '<em class="kw">(blank)</em>' : '<span class="kw">' + escapeHtml(d.dup.slice(0,140))    + '</span>';
    const m = d.merged === '' ? '<em class="kw">(blank)</em>' : '<span class="kw">' + escapeHtml(d.merged.slice(0,140)) + '</span>';
    out += `<li>
      <span class="diff-field">${{d.field}}</span>
      ${{badgeForCategory(d.category)}}
      <div class="diff-vals">
        <strong>keeper:</strong> ${{k}}<br>
        <strong>dup&nbsp;&nbsp;&nbsp;&nbsp;:</strong> ${{u}}<br>
        <strong>→ merged:</strong> ${{m}}  <span class="small">(from ${{d.merge_source}})</span>
      </div>
    </li>`;
  }}
  out += '</ul>';
  return out;
}}

function renderSources(pair) {{
  let html = '<strong>Local Excel files for this RFP ID:</strong> ';
  if (pair.local_files.length === 0) {{
    html += '<span class="src-icon no-local">NONE</span>';
  }} else {{
    html += `<span class="src-icon has-local">${{pair.local_files.length}} found</span><br>`;
    for (const fp of pair.local_files.slice(0, 5)) {{
      html += `<span class="file-link">${{escapeHtml(fp)}}</span>`;
    }}
    if (pair.local_files.length > 5) {{
      html += `<span class="small">… and ${{pair.local_files.length - 5}} more</span>`;
    }}
  }}
  if (Object.keys(pair.portal_comparisons || {{}}).length > 0) {{
    html += '<br><br><strong>Already analyzed against portal (master_rfp_preview):</strong><br>';
    for (const [fld, info] of Object.entries(pair.portal_comparisons)) {{
      html += `<div class="small">• <code class="mono">${{fld}}</code>: db=<code class="mono">${{escapeHtml(info.db_value)}}</code>  portal=<code class="mono">${{escapeHtml(info.portal_value)}}</code>  <span class="pill">${{info.status}}</span></div>`;
    }}
  }}
  return html;
}}

function escapeHtml(s) {{
  return String(s).replace(/[&<>"']/g, c => (
    {{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]
  ));
}}

function pairMatchesFilters(p) {{
  const q = search.value.trim().toLowerCase();
  if (q) {{
    const blob = (p.key + ' ' + p.company + ' ' + p.keeper_owner + ' ' + p.dup_owner + ' ' + p.keeper_rfp_id + ' ' + p.dup_rfp_id).toLowerCase();
    if (!blob.includes(q)) return false;
  }}
  const f = status.value;
  if (f === 'metadata_differs' && !p.metadata_differs) return false;
  if (f === 'true_conflict'    && !p.true_conflict_count) return false;
  if (f === 'has_local_file'   && !p.local_files.length) return false;
  if (f === 'no_local_file'    && p.local_files.length)  return false;
  if (f === 'clean'            && (p.metadata_differs || p.true_conflict_count)) return false;
  return true;
}}

function statusBadges(p) {{
  let out = '';
  if (p.true_conflict_count) out += '<span class="badge danger">conflict</span>';
  if (p.metadata_differs)    out += '<span class="badge warn">metadata</span>';
  if (!p.metadata_differs && !p.true_conflict_count) out += '<span class="badge good">clean</span>';
  return out;
}}

function render() {{
  let rows = pairs.filter(pairMatchesFilters);
  const sortKey = currentSort.key;
  const dir = currentSort.dir === 'asc' ? 1 : -1;
  rows.sort((a, b) => {{
    let va = a[sortKey] ?? 0, vb = b[sortKey] ?? 0;
    if (typeof va === 'string') va = va.toLowerCase();
    if (typeof vb === 'string') vb = vb.toLowerCase();
    if (va < vb) return -1 * dir;
    if (va > vb) return  1 * dir;
    return 0;
  }});
  currentRows = rows;

  let html = '';
  for (const p of rows) {{
    const localBadge = p.local_files.length
      ? `<span class="src-icon has-local">YES (${{p.local_files.length}})</span>`
      : '<span class="src-icon no-local">no</span>';
    html += `<tr data-key="${{p.key}}" data-expanded="0">
      <td><code class="mono">${{escapeHtml(p.key)}}</code><div class="small">keeper raw: <code class="mono">${{escapeHtml(p.keeper_rfp_id)}}</code><br>dup raw: <code class="mono">${{escapeHtml(p.dup_rfp_id)}}</code></div></td>
      <td>${{escapeHtml(p.company)}}</td>
      <td>${{p.diff_count}}</td>
      <td>${{p.metadata_differs ? '<span class="badge warn">yes</span>' : '<span class="badge good">no</span>'}}</td>
      <td>${{p.true_conflict_count ? '<span class="badge danger">' + p.true_conflict_count + '</span>' : '<span class="badge good">0</span>'}}</td>
      <td>${{localBadge}}</td>
      <td>${{statusBadges(p)}}</td>
      <td><button class="toggle" onclick="toggleDetail(this)">▸ Details</button></td>
    </tr>
    <tr class="diff-detail">
      <td colspan="8">
        <div class="diff-detail-inner">
          <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 24px;">
            <div>
              <strong>Field-level diff (${{p.diff_count}} entries):</strong>
              ${{renderDiffList(p)}}
            </div>
            <div>
              <strong>Authoritative sources:</strong><br>
              <div style="margin-top: 6px;">${{renderSources(p)}}</div>
              <br><strong>Run IDs:</strong>
              <div class="small">keeper: <code class="mono">${{p.keeper_runid}}</code></div>
              <div class="small">dup&nbsp;&nbsp;&nbsp; : <code class="mono">${{p.dup_runid}}</code></div>
            </div>
          </div>
        </div>
      </td>
    </tr>`;
  }}
  body.innerHTML = html;
  summary.textContent = `${{rows.length}} of ${{pairs.length}} pairs shown`;
}}

function toggleDetail(btn) {{
  const tr = btn.closest('tr');
  const detail = tr.nextElementSibling;
  const opened = detail.classList.toggle('open');
  tr.classList.toggle('expanded', opened);
  btn.textContent = opened ? '▾ Details' : '▸ Details';
}}

document.querySelectorAll('th[data-sort]').forEach(th => {{
  th.addEventListener('click', () => {{
    const key = th.dataset.sort;
    if (currentSort.key === key) {{
      currentSort.dir = currentSort.dir === 'asc' ? 'desc' : 'asc';
    }} else {{
      currentSort = {{ key, dir: 'asc' }};
    }}
    render();
  }});
}});

search.addEventListener('input', render);
status.addEventListener('change', render);

document.getElementById('expand-all').addEventListener('click', () => {{
  document.querySelectorAll('#pairs-body tr.diff-detail').forEach(tr => tr.classList.add('open'));
  document.querySelectorAll('#pairs-body tr[data-key]').forEach(tr => tr.classList.add('expanded'));
  document.querySelectorAll('#pairs-body button.toggle').forEach(b => b.textContent = '▾ Details');
}});
document.getElementById('collapse-all').addEventListener('click', () => {{
  document.querySelectorAll('#pairs-body tr.diff-detail').forEach(tr => tr.classList.remove('open'));
  document.querySelectorAll('#pairs-body tr[data-key]').forEach(tr => tr.classList.remove('expanded'));
  document.querySelectorAll('#pairs-body button.toggle').forEach(b => b.textContent = '▸ Details');
}});

render();
</script>

</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("Duplicate RFP HTML Report Generator (READ-ONLY)")
    print("=" * 70)
    print()

    print("Scanning local ALLRFPs/ tree for authoritative portal Excel files ...")
    local_index = build_local_file_index()
    print(f"  Indexed {sum(len(v) for v in local_index.values())} files across {len(local_index)} keys.")

    print("Scanning master_rfp_preview CSVs for portal-comparison data ...")
    master_index = build_master_preview_index()
    print(f"  Indexed portal-comparison entries for {len(master_index)} RFP IDs.")

    print("Fetching all rows from Dataverse ...")
    client = DataverseClient(TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL)
    rows = client.get_all_rows(
        table_api_name=RFP_ACTIVITY_LOG_TABLE_API,
        table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL,
        select_columns=ALL_FIELDS + ["RunID"],
        use_display_names=True,
    )
    print(f"  Fetched {len(rows)} rows.")

    # Group into duplicates
    groups = defaultdict(list)
    for r in rows:
        rid = (r.get("RFP_ID") or "").strip()
        if rid:
            groups[match_key(rid)].append(r)
    dup_groups = {k: v for k, v in groups.items() if len(v) > 1}

    auto_clean = 0
    metadata_differs_pairs = 0
    true_conflict_pairs = 0
    pairs_with_local_file = 0
    pairs_with_portal_compare = 0

    pair_records = []
    for key, items in sorted(dup_groups.items()):
        keeper, dups = pick_keeper(items)
        dup = dups[0]
        diffs, crit_count, meta_diff = diff_pair(keeper, dup)
        local_files = local_index.get(key, [])
        portal_comparisons = master_index.get(key, {})
        if local_files:
            pairs_with_local_file += 1
        if portal_comparisons:
            pairs_with_portal_compare += 1
        if crit_count:
            true_conflict_pairs += 1
        if meta_diff:
            metadata_differs_pairs += 1
        if not crit_count and not meta_diff:
            auto_clean += 1
        pair_records.append({
            "key": key,
            "company": keeper.get("Company_Name") or dup.get("Company_Name") or "",
            "keeper_rfp_id": keeper.get("RFP_ID") or "",
            "dup_rfp_id":    dup.get("RFP_ID") or "",
            "keeper_owner":  keeper.get("owner_name") or "",
            "dup_owner":     dup.get("owner_name") or "",
            "keeper_runid":  keeper.get("RunID") or "",
            "dup_runid":     dup.get("RunID") or "",
            "diff_count":    len(diffs),
            "diffs":         diffs,
            "true_conflict_count": crit_count,
            "metadata_differs":    meta_diff,
            "local_files":   local_files,
            "portal_comparisons": portal_comparisons,
        })

    report = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stats": {
            "total_rows": len(rows),
            "unique_rfps": len(groups),
            "duplicate_pairs": len(dup_groups),
            "rows_to_delete": len(dup_groups),
            "projected_size": len(rows) - len(dup_groups),
            "auto_clean_pairs": auto_clean,
            "metadata_differs_pairs": metadata_differs_pairs,
            "true_conflict_pairs": true_conflict_pairs,
            "local_file_count": sum(len(v) for v in local_index.values()),
            "pairs_with_local_file": pairs_with_local_file,
            "pairs_without_local_file": len(dup_groups) - pairs_with_local_file,
            "master_preview_pair_coverage": pairs_with_portal_compare,
        },
        "pairs": pair_records,
    }

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(OUTPUT_REPORT_DIR, f"duplicate_report_{ts}.html")
    os.makedirs(OUTPUT_REPORT_DIR, exist_ok=True)
    html_doc = render_html(report)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_doc)

    print()
    print("=" * 70)
    print("Report generated:")
    print(f"  {out_path}")
    print()
    print(f"  Open in your browser to view the dashboard.")
    print("=" * 70)
    print()
    print("Snapshot:")
    print(f"  Duplicate pairs                    : {len(dup_groups)}")
    print(f"  Auto-merge clean (no review needed): {auto_clean}")
    print(f"  Pairs with metadata differences    : {metadata_differs_pairs}")
    print(f"  Pairs with a true conflict         : {true_conflict_pairs}")
    print(f"  Pairs with a local Excel file      : {pairs_with_local_file}")
    print(f"  Pairs WITHOUT a local Excel file   : {len(dup_groups) - pairs_with_local_file}")
    print(f"  Pairs already in master_rfp_preview: {pairs_with_portal_compare}")


if __name__ == "__main__":
    main()
