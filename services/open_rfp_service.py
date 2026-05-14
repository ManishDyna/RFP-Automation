"""
Open RFP service — tracks which team members have responded to an RFP's
actionable card email, and lets an authorized user re-send the card to
non-responders.

Backed by:
  - cr673_bahra_rfps_v2              (master RFP rows; filter on Email_Status)
  - cr6db_cr673_bahra_rfp_response   (one row per responding bidder)
  - cr673_bahra_rfp_team             (live team / recipient list)
  - cr673_bahra_rfp_reminder_for_info (history of reminders we sent)
"""
from __future__ import annotations

import json
import threading
from collections import OrderedDict
from datetime import datetime
from typing import Any, Dict, List

from helpers.core_helper import DATAVERSE
from services.system_settings_service import get_setting
from services.master_data_service import get_all_rfp_team_for_emails
from services.audit_service import log_event, AuditCategory


# --------------------------------------------------------------------------
# Dedupe guard: prevent double-click double-sends within a short window.
# --------------------------------------------------------------------------
_REMINDER_DEDUPE: Dict[tuple, datetime] = {}
_REMINDER_LOCK = threading.Lock()
_DEDUPE_WINDOW_SECONDS = 10


def _mdy_now() -> str:
    return datetime.now().strftime("%#m/%#d/%Y %#I:%M %p")


# --------------------------------------------------------------------------
# Team grouping (mirrors helpers/email_helper.py lines ~547-558)
# --------------------------------------------------------------------------

def _group_team_by_email(team: List[Dict[str, Any]]) -> "OrderedDict[str, Dict[str, Any]]":
    grouped: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
    for member in team:
        em = (member.get("email") or "").strip()
        if not em:
            continue
        em_lower = em.lower()
        if em_lower not in grouped:
            grouped[em_lower] = {
                "name": member.get("name", ""),
                "email": em,
                "products": [],
                "readonly": bool(member.get("readonly", False)),
            }
        product = member.get("product")
        if product:
            grouped[em_lower]["products"].append(product)
    return grouped


# --------------------------------------------------------------------------
# RFP master list — only RFPs we actually sent the actionable card for.
# --------------------------------------------------------------------------

def get_rfps_with_email_sent() -> List[Dict[str, Any]]:
    rfp_table_api = get_setting("RFP_ACTIVITY_LOG_TABLE_API", "cr673_bahra_rfps_v2s")
    rfp_table_logical = get_setting("RFP_ACTIVITY_LOG_TABLE_LOGICAL", "cr673_bahra_rfps_v2")
    response_table_api = get_setting("RFP_RESPONSE_TABLE_API", "cr6db_cr673_bahra_rfp_responses")
    response_table_logical = get_setting("RFP_RESPONSE_TABLE_LOGICAL", "cr6db_cr673_bahra_rfp_response")

    now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        rows = DATAVERSE.get_all_rows(
            table_api_name=rfp_table_api,
            select_columns=[
                "RFP_ID", "Company_Name", "RFP_End_Date", "owner_name",
                "Email_Sent_At", "Email_Status", "participated", "Link",
            ],
            filter_expr=(
                "Email_Status ne null and Email_Status ne '' "
                f"and RFP_End_Date ge {now_iso}"
            ),
            table_logical_name=rfp_table_logical,
            use_display_names=True,
        ) or []
    except Exception as e:
        print(f"[open_rfp] Could not fetch RFP master rows: {e}")
        rows = []

    try:
        team = get_all_rfp_team_for_emails()
    except Exception as e:
        print(f"[open_rfp] Could not fetch RFP team: {e}")
        team = []
    total_team_emails = len({(m.get("email") or "").lower() for m in team if m.get("email")})

    # Single bulk query for ALL response rows — aggregate per-RFP in Python
    # (avoids the N+1 query that made the page hang).
    responded_emails_by_rfp: Dict[str, set] = {}
    try:
        resp_rows = DATAVERSE.get_all_rows(
            table_api_name=response_table_api,
            select_columns=["cr673_rfp_id", "cr673_email"],
            table_logical_name=response_table_logical,
            use_display_names=True,
        ) or []
        for r in resp_rows:
            rfp_id = (r.get("cr673_rfp_id") or "").strip()
            email = (r.get("cr673_email") or "").lower()
            if not rfp_id or not email:
                continue
            responded_emails_by_rfp.setdefault(rfp_id, set()).add(email)
    except Exception as e:
        print(f"[open_rfp] Could not fetch response rows: {e}")

    result: List[Dict[str, Any]] = []
    for row in rows:
        rfp_id = (row.get("RFP_ID") or "").strip()
        if not rfp_id:
            continue

        responded_emails = responded_emails_by_rfp.get(rfp_id, set())
        responded_count = len(responded_emails)
        pending_count = max(0, total_team_emails - responded_count)

        result.append({
            "rfp_id": rfp_id,
            "company_name": row.get("Company_Name", "") or "",
            "rfp_end_date": row.get("RFP_End_Date", "") or "",
            "owner_name": row.get("owner_name", "") or "",
            "email_sent_at": row.get("Email_Sent_At", "") or "",
            "email_status": row.get("Email_Status", "") or "",
            "participated": row.get("participated", "") or "",
            "link": row.get("Link", "") or "",
            "total_recipients": total_team_emails,
            "responded_count": responded_count,
            "pending_count": pending_count,
        })

    result.sort(key=lambda r: r.get("email_sent_at", ""), reverse=True)
    return result


# --------------------------------------------------------------------------
# Per-RFP response status + member detail (used by the modal popup)
# --------------------------------------------------------------------------

def _fetch_rfp_master_row(rfp_id: str) -> Dict[str, Any]:
    table_api = get_setting("RFP_ACTIVITY_LOG_TABLE_API", "cr673_bahra_rfps_v2s")
    table_logical = get_setting("RFP_ACTIVITY_LOG_TABLE_LOGICAL", "cr673_bahra_rfps_v2")
    try:
        result = DATAVERSE.query_rows(
            table_api,
            filter_expr=f"RFP_ID eq '{rfp_id}'",
            top=1,
            table_logical_name=table_logical,
            use_display_names=True,
        )
        if result and result.get("value"):
            return result["value"][0]
    except Exception as e:
        print(f"[open_rfp] Could not fetch RFP {rfp_id}: {e}")
    return {}


def _fetch_responses(rfp_id: str) -> List[Dict[str, Any]]:
    table_api = get_setting("RFP_RESPONSE_TABLE_API", "cr6db_cr673_bahra_rfp_responses")
    table_logical = get_setting("RFP_RESPONSE_TABLE_LOGICAL", "cr6db_cr673_bahra_rfp_response")
    try:
        result = DATAVERSE.query_rows(
            table_api,
            filter_expr=f"cr673_rfp_id eq '{rfp_id}'",
            top=200,
            table_logical_name=table_logical,
            use_display_names=True,
        )
        if result and "value" in result:
            return result["value"]
    except Exception as e:
        print(f"[open_rfp] Could not fetch responses for {rfp_id}: {e}")
    return []


def get_reminder_history(rfp_id: str) -> List[Dict[str, Any]]:
    table_api = get_setting("BAHRA_RFP_REMINDER_API", "cr673_bahra_rfp_reminder_for_infos")
    table_logical = get_setting("BAHRA_RFP_REMINDER_LOGICAL", "cr673_bahra_rfp_reminder_for_info")
    # NOTE: the reminder table was created with short display names ("rfp_id",
    # "sent_at", …). We MUST use display-name keys here — passing logical
    # names like "cr673_rfp_id" trips a naive substring-replace inside the
    # helper that double-prefixes them to "cr673_cr673_rfp_id".
    try:
        result = DATAVERSE.query_rows(
            table_api,
            filter_expr=f"rfp_id eq '{rfp_id}'",
            top=200,
            table_logical_name=table_logical,
            use_display_names=True,
        )
        rows = (result or {}).get("value", []) or []
    except Exception as e:
        print(f"[open_rfp] Could not fetch reminder history for {rfp_id}: {e}")
        rows = []

    history: List[Dict[str, Any]] = []
    for r in rows:
        history.append({
            "rfp_id": r.get("rfp_id", "") or "",
            "company_name": r.get("company_name", "") or "",
            "product": r.get("product", "") or "",
            "recipient_email": r.get("recipient_email", "") or "",
            "recipient_name": r.get("recipient_name", "") or "",
            "sent_at": r.get("sent_at", "") or "",
            "sent_by_email": r.get("sent_by_email", "") or "",
            "sent_by_name": r.get("sent_by_name", "") or "",
            "status": r.get("status", "") or "",
            "error_message": r.get("error_message", "") or "",
        })

    history.sort(key=lambda h: h.get("sent_at", ""), reverse=True)
    return history


def _parse_response_data(raw: str) -> Dict[str, Dict[str, str]]:
    """Parse cr673_response_data JSON → {product_lower: {results, remarks, ...}}.
    Returns an empty dict if the JSON is missing or malformed."""
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except Exception:
        return {}
    out: Dict[str, Dict[str, str]] = {}
    for entry in (parsed or {}).get("products", []) or []:
        product = (entry.get("product") or "").strip()
        if not product:
            continue
        out[product.lower()] = {k: (v or "") for k, v in entry.items() if k != "product"}
    return out


def get_rfp_response_status(rfp_id: str) -> Dict[str, Any]:
    master = _fetch_rfp_master_row(rfp_id)
    responses = _fetch_responses(rfp_id)
    history = get_reminder_history(rfp_id)
    try:
        team = get_all_rfp_team_for_emails()
    except Exception as e:
        print(f"[open_rfp] Could not fetch RFP team: {e}")
        team = []

    grouped = _group_team_by_email(team)

    # Index responses by email
    resp_by_email: Dict[str, Dict[str, Any]] = {}
    for r in responses:
        em = (r.get("cr673_email") or "").lower()
        if em:
            resp_by_email[em] = r

    # Reminder counts/last per email
    reminder_count_by_email: Dict[str, int] = {}
    last_reminder_by_email: Dict[str, str] = {}
    for h in history:
        em = (h.get("recipient_email") or "").lower()
        if not em:
            continue
        reminder_count_by_email[em] = reminder_count_by_email.get(em, 0) + 1
        prev = last_reminder_by_email.get(em, "")
        if h.get("sent_at", "") > prev:
            last_reminder_by_email[em] = h.get("sent_at", "")

    # Build per-(member, product) rows so the popup mirrors the email's
    # Products | Email | Results | Remarks | Status layout.
    rows: List[Dict[str, Any]] = []
    for em_lower, info in grouped.items():
        resp = resp_by_email.get(em_lower)
        responded = resp is not None
        products_by_product = _parse_response_data(
            (resp or {}).get("cr673_response_data", "")
        ) if responded else {}
        legacy_results = (resp or {}).get("cr673_results", "") if responded else ""
        legacy_remarks = (resp or {}).get("cr673_remarks", "") if responded else ""

        member_products = info["products"] or [""]
        for product in member_products:
            product_key = (product or "").lower()
            per_product = products_by_product.get(product_key)
            if per_product:
                results = per_product.get("results", "")
                remarks = per_product.get("remarks", "")
            elif responded:
                # Response exists but no per-product breakdown for THIS product
                # → fall back to the legacy top-level results/remarks fields.
                results = legacy_results
                remarks = legacy_remarks
            else:
                results = ""
                remarks = ""
            rows.append({
                "email": info["email"],
                "name": info["name"],
                "product": product or "-",
                "readonly": info["readonly"],
                "status": "responded" if responded else "pending",
                "results": results,
                "remarks": remarks,
                "responded_at": (resp or {}).get("cr673_submitted_at", "") or "",
                "reminder_count": reminder_count_by_email.get(em_lower, 0),
                "last_reminder_at": last_reminder_by_email.get(em_lower, ""),
                "former": False,
            })

    # Surface responders whose email is NOT in the live team table — could
    # be because the team was reconfigured after they submitted, the email
    # was changed, or the response was created in a different EMAIL_MODE.
    # Without this, a real response would silently vanish from the popup.
    seen_emails = {r["email"].lower() for r in rows}
    for em_lower, resp in resp_by_email.items():
        if em_lower in seen_emails:
            continue
        responded_at = resp.get("cr673_submitted_at", "") or ""
        responder_name = resp.get("cr673_name", "") or ""
        responder_email = resp.get("cr673_email", "") or em_lower
        products_by_product = _parse_response_data(resp.get("cr673_response_data", "") or "")
        legacy_results = resp.get("cr673_results", "") or ""
        legacy_remarks = resp.get("cr673_remarks", "") or ""
        if products_by_product:
            for product_key, per_product in products_by_product.items():
                rows.append({
                    "email": responder_email,
                    "name": responder_name,
                    "product": product_key or "-",
                    "readonly": True,
                    "status": "responded",
                    "results": per_product.get("results", "") or legacy_results,
                    "remarks": per_product.get("remarks", "") or legacy_remarks,
                    "responded_at": responded_at,
                    "reminder_count": reminder_count_by_email.get(em_lower, 0),
                    "last_reminder_at": last_reminder_by_email.get(em_lower, ""),
                    "former": True,
                })
        else:
            # Single legacy row when there's no per-product JSON
            product_str = resp.get("cr673_product", "") or "-"
            for product in [p.strip() for p in product_str.split(",") if p.strip()] or ["-"]:
                rows.append({
                    "email": responder_email,
                    "name": responder_name,
                    "product": product,
                    "readonly": True,
                    "status": "responded",
                    "results": legacy_results,
                    "remarks": legacy_remarks,
                    "responded_at": responded_at,
                    "reminder_count": reminder_count_by_email.get(em_lower, 0),
                    "last_reminder_at": last_reminder_by_email.get(em_lower, ""),
                    "former": True,
                })
        seen_emails.add(em_lower)

    # Historical reminder recipients no longer on the team and with no
    # response — surface them as pending rows so the audit trail is visible.
    for em_lower in reminder_count_by_email:
        if em_lower in seen_emails:
            continue
        rows.append({
            "email": em_lower,
            "name": "",
            "product": "-",
            "readonly": True,
            "status": "pending",
            "results": "",
            "remarks": "",
            "responded_at": "",
            "reminder_count": reminder_count_by_email[em_lower],
            "last_reminder_at": last_reminder_by_email.get(em_lower, ""),
            "former": True,
        })

    return {
        "rfp": {
            "rfp_id": rfp_id,
            "company_name": master.get("Company_Name", "") or "",
            "rfp_end_date": master.get("RFP_End_Date", "") or "",
            "owner_name": master.get("owner_name", "") or "",
            "email_sent_at": master.get("Email_Sent_At", "") or "",
            "email_status": master.get("Email_Status", "") or "",
            "participated": master.get("participated", "") or "",
            "link": master.get("Link", "") or "",
        },
        "rows": rows,
        "reminders": history,
    }


# --------------------------------------------------------------------------
# Send reminder
# --------------------------------------------------------------------------

def _build_graph_client():
    """Build a SharePoint GraphClient using the same pattern as the
    consolidated-response email flow."""
    from helpers.sharepoint_helper import GraphClient
    _client_id = get_setting("CLIENT_ID", "")
    _client_secret = get_setting("CLIENT_SECRET", "")
    _tenant_id = get_setting("TENANT_ID", "")
    _sp_hostname = get_setting("SHAREPOINT_HOSTNAME", "bahracables.sharepoint.com")
    _site_path = get_setting("SITE_PATH", "/sites/LiveSite/RFPAutomation")
    _drive_name = get_setting("DRIVE_NAME", "Documents")
    graph = GraphClient(_client_id, _client_secret, _tenant_id,
                        _sp_hostname, _site_path, _drive_name)
    graph.auth()
    graph.resolve_site_and_drive()
    return graph


def _record_reminder_row(
    rfp_id: str,
    company_name: str,
    product: str,
    recipient_email: str,
    recipient_name: str,
    sent_by_email: str,
    sent_by_name: str,
    status: str,
    error_message: str,
) -> None:
    table_api = get_setting("BAHRA_RFP_REMINDER_API", "cr673_bahra_rfp_reminder_for_infos")
    table_logical = get_setting("BAHRA_RFP_REMINDER_LOGICAL", "cr673_bahra_rfp_reminder_for_info")
    now_str = _mdy_now()
    # Use the table's display-name keys (matches how the table was created and
    # how get_reminder_history reads them back).
    row = {
        "name": f"{rfp_id} -> {recipient_email} @ {now_str}",
        "rfp_id": rfp_id,
        "company_name": company_name,
        "product": product,
        "recipient_email": recipient_email,
        "recipient_name": recipient_name,
        "sent_at": now_str,
        "sent_by_email": sent_by_email,
        "sent_by_name": sent_by_name,
        "status": status,
        "error_message": error_message or "",
    }
    try:
        DATAVERSE.insert_row(
            table_api_name=table_api,
            data=row,
            table_logical_name=table_logical,
            use_display_names=True,
        )
    except Exception as e:
        print(f"[open_rfp] Failed to insert reminder row for {rfp_id} -> {recipient_email}: {e}")


def send_rfp_reminder(
    rfp_id: str,
    recipient_emails: List[str],
    actor_email: str,
    actor_name: str,
) -> Dict[str, Any]:
    rfp_id = (rfp_id or "").strip()
    if not rfp_id:
        return {"results": [], "reminded_count": 0, "error": "rfp_id is required"}

    requested_emails = [
        (e or "").strip()
        for e in (recipient_emails or [])
        if e and (e or "").strip()
    ]
    if not requested_emails:
        return {"results": [], "reminded_count": 0, "error": "No recipient emails provided"}

    # 1. Idempotency guard — drop any (rfp_id, email) sent within the dedupe window
    now = datetime.now()
    cutoff = now.timestamp() - _DEDUPE_WINDOW_SECONDS
    accepted: List[str] = []
    skipped: List[str] = []
    with _REMINDER_LOCK:
        # Sweep stale entries
        for k, ts in list(_REMINDER_DEDUPE.items()):
            if ts.timestamp() < cutoff:
                _REMINDER_DEDUPE.pop(k, None)
        for em in requested_emails:
            key = (rfp_id, em.lower())
            if key in _REMINDER_DEDUPE:
                skipped.append(em)
            else:
                _REMINDER_DEDUPE[key] = now
                accepted.append(em)

    if not accepted:
        return {
            "results": [{"email": e, "status": "Skipped", "error": "Duplicate within 10s"} for e in skipped],
            "reminded_count": 0,
        }

    # 2. Look up RFP master row for company/end-date context
    master = _fetch_rfp_master_row(rfp_id)
    company_name = (master.get("Company_Name") or "").strip()
    rfp_end_date = (master.get("RFP_End_Date") or "-").strip() or "-"

    # 3. Build the per-email recipient list (preserve products per email)
    try:
        team = get_all_rfp_team_for_emails()
    except Exception as e:
        print(f"[open_rfp] Could not fetch RFP team: {e}")
        team = []

    grouped = _group_team_by_email(team)
    accepted_lower = {e.lower() for e in accepted}

    filtered_recipients: List[Dict[str, Any]] = []
    members_by_email: Dict[str, Dict[str, Any]] = {}
    for em_lower, info in grouped.items():
        if em_lower not in accepted_lower:
            continue
        members_by_email[em_lower] = info
        # Expand each (email, product) back to a member dict so existing
        # grouping inside send_actionable_rfp_emails still works.
        products = info["products"] or [""]
        for product in products:
            filtered_recipients.append({
                "product": product,
                "name": info["name"],
                "email": info["email"],
                "readonly": info["readonly"],
            })

    if not filtered_recipients:
        # No matching members — record failures for visibility
        results = [
            {"email": e, "status": "Failed", "error": "Email not in current RFP team"}
            for e in accepted
        ]
        for em in accepted:
            _record_reminder_row(
                rfp_id, company_name, "", em, "",
                actor_email, actor_name,
                "Failed", "Email not in current RFP team",
            )
        return {"results": results, "reminded_count": 0}

    # 4. Send the actionable card — wraps the whole batch (one Graph call per email)
    overall_status = "Sent"
    overall_error = ""
    try:
        from helpers.email_helper import send_actionable_rfp_emails
        graph_client = _build_graph_client()
        send_actionable_rfp_emails(
            rfp_id=rfp_id,
            company_name=company_name,
            rfp_end_date=rfp_end_date,
            matched_csv_path=None,
            graph_client=graph_client,
            recipients_override=filtered_recipients,
            subject_prefix="Reminder: ",
        )
    except Exception as e:
        overall_status = "Failed"
        overall_error = str(e)[:1900]
        print(f"[open_rfp] Reminder send failed for {rfp_id}: {e}")

    # 5. Record one Dataverse reminder row per recipient + collect results
    results: List[Dict[str, Any]] = []
    for em_lower, info in members_by_email.items():
        product_str = ", ".join(info["products"]) if info["products"] else ""
        _record_reminder_row(
            rfp_id, company_name, product_str,
            info["email"], info["name"],
            actor_email, actor_name,
            overall_status, overall_error,
        )
        results.append({
            "email": info["email"],
            "name": info["name"],
            "status": overall_status,
            "error": overall_error if overall_status == "Failed" else "",
        })

    for em in skipped:
        results.append({"email": em, "status": "Skipped", "error": "Duplicate within 10s"})

    # 6. Audit log — one entry per call, summarising everything
    try:
        log_event(
            action="RFP_REMINDER_SENT",
            category=AuditCategory.RFP,
            actor_email=actor_email,
            actor_name=actor_name,
            target_type="rfp",
            target_id=rfp_id,
            details=json.dumps({
                "rfp_id": rfp_id,
                "status": overall_status,
                "error": overall_error,
                "recipients": results,
            })[:4000],
        )
    except Exception as e:
        print(f"[open_rfp] Audit log failed: {e}")

    reminded_count = sum(1 for r in results if r["status"] == "Sent")
    return {"results": results, "reminded_count": reminded_count}
