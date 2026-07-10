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

_DELEGATION_DEDUPE: Dict[tuple, datetime] = {}
_DELEGATION_LOCK = threading.Lock()


def _mdy_now() -> str:
    return datetime.now().strftime("%#m/%#d/%Y %#I:%M %p")


def _parse_mdy(s: str) -> datetime:
    """Parse our MDY storage format back to a datetime so chronological
    sorts work across months (string sort breaks: '11/2/...' < '5/17/...')."""
    try:
        return datetime.strptime((s or "").strip(), "%m/%d/%Y %I:%M %p")
    except Exception:
        return datetime.min


# --------------------------------------------------------------------------
# Team grouping (mirrors helpers/email_helper.py lines ~547-558)
# --------------------------------------------------------------------------

def _parse_emails(email_field: str) -> List[str]:
    """Split a (possibly comma/semicolon-separated) email field into a
    deduped, lowercased list. Mirrors routes/actionable_cards._parse_emails
    so the modal honours the same first-response-wins alternates semantics
    the actionable card already uses."""
    if not email_field:
        return []
    out: List[str] = []
    seen: set = set()
    for part in str(email_field).replace(";", ",").split(","):
        e = part.strip().lower()
        if e and e not in seen:
            out.append(e)
            seen.add(e)
    return out


def _group_team_by_email(team: List[Dict[str, Any]]) -> "OrderedDict[str, Dict[str, Any]]":
    """Group team members by their PRIMARY email (first parsed alternate).

    A team row's email column may list comma-separated alternates with
    first-response-wins semantics. We key by the primary so callers can do
    single-email lookups (Remind/Delegate, response matching), but also
    expose the full alternates list so all addresses on the row are
    visible and any of them can satisfy the response."""
    grouped: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
    for member in team:
        raw_email = (member.get("email") or "").strip()
        if not raw_email:
            continue
        alternates = _parse_emails(raw_email)
        if not alternates:
            continue
        primary = alternates[0]
        if primary not in grouped:
            grouped[primary] = {
                "name": member.get("name", ""),
                "email": raw_email,
                "primary_email": primary,
                "alternates": list(alternates),
                "products": [],
                "readonly": bool(member.get("readonly", False)),
            }
        else:
            for alt in alternates:
                if alt not in grouped[primary]["alternates"]:
                    grouped[primary]["alternates"].append(alt)
        product = member.get("product")
        if product and product not in grouped[primary]["products"]:
            grouped[primary]["products"].append(product)
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


def get_active_delegations(rfp_id: str) -> List[Dict[str, Any]]:
    """Fetch all active delegations for an RFP, oldest first (so chains apply
    in the order they were created)."""
    table_api = get_setting("RFP_DELEGATION_TABLE_API", "cr673_bahra_rfp_delegationses")
    table_logical = get_setting("RFP_DELEGATION_TABLE_LOGICAL", "cr673_bahra_rfp_delegations")
    # Display-name filter — see [[project_email_table_columns]] note on
    # cr673_bahra_rfp_reminder_for_info: this table was created with short
    # display names too, so passing "cr673_rfp_id" trips the naive
    # substring-replace in DataverseClient and double-prefixes to
    # "cr673_cr673_rfp_id".
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
        print(f"[open_rfp] Could not fetch delegations for {rfp_id}: {e}")
        rows = []

    out: List[Dict[str, Any]] = []
    for r in rows:
        if str(r.get("is_active", "true")).lower() == "false":
            continue
        out.append({
            "rfp_id": r.get("rfp_id", "") or "",
            "product": r.get("product", "") or "",
            "original_email": r.get("original_email", "") or "",
            "original_name": r.get("original_name", "") or "",
            "new_email": r.get("new_email", "") or "",
            "new_name": r.get("new_name", "") or "",
            "delegated_by_email": r.get("delegated_by_email", "") or "",
            "delegated_by_name": r.get("delegated_by_name", "") or "",
            "delegated_at": r.get("delegated_at", "") or "",
        })
    out.sort(key=lambda d: _parse_mdy(d.get("delegated_at", "")))
    return out


def _insert_delegation_row(
    rfp_id: str,
    product: str,
    original_email: str,
    original_name: str,
    new_email: str,
    new_name: str,
    actor_email: str,
    actor_name: str,
) -> bool:
    table_api = get_setting("RFP_DELEGATION_TABLE_API", "cr673_bahra_rfp_delegationses")
    table_logical = get_setting("RFP_DELEGATION_TABLE_LOGICAL", "cr673_bahra_rfp_delegations")
    now_str = _mdy_now()
    row = {
        "name": f"{rfp_id} | {product} | {original_email} -> {new_email}"[:500],
        "rfp_id": rfp_id,
        "product": product,
        "original_email": original_email,
        "original_name": original_name,
        "new_email": new_email,
        "new_name": new_name,
        "delegated_by_email": actor_email,
        "delegated_by_name": actor_name,
        "delegated_at": now_str,
        "is_active": "true",
    }
    try:
        return bool(DATAVERSE.insert_row(
            table_api_name=table_api,
            data=row,
            table_logical_name=table_logical,
            use_display_names=True,
        ))
    except Exception as e:
        print(f"[open_rfp] Failed to insert delegation row for {rfp_id} -> {new_email}: {e}")
        return False


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

    # Reminder counts/last per email. Historical records may have stored a
    # comma-separated composite string as recipient_email, so explode every
    # record through _parse_emails and count under each individual address.
    # Lookups by primary email then work whether the record was written
    # before or after the multi-email fix.
    reminder_count_by_email: Dict[str, int] = {}
    last_reminder_by_email: Dict[str, str] = {}
    for h in history:
        raw_em = h.get("recipient_email", "") or ""
        addresses = _parse_emails(raw_em)
        if not addresses and raw_em:
            addresses = [raw_em.lower()]
        sent_at = h.get("sent_at", "")
        for em in addresses:
            if not em:
                continue
            reminder_count_by_email[em] = reminder_count_by_email.get(em, 0) + 1
            prev = last_reminder_by_email.get(em, "")
            if sent_at > prev:
                last_reminder_by_email[em] = sent_at

    # Build per-(member, product) rows so the popup mirrors the email's
    # Products | Email | Results | Remarks | Status layout.
    # First-response-wins: a team row is satisfied as soon as ANY of its
    # alternates submits a response. Track which response emails get
    # consumed so the "responders not in team" fallback below doesn't
    # re-surface them as duplicate Former rows.
    rows: List[Dict[str, Any]] = []
    consumed_response_emails: set = set()
    for primary_lower, info in grouped.items():
        resp = None
        responder_name = info["name"]
        for alt in info["alternates"]:
            if alt in resp_by_email:
                resp = resp_by_email[alt]
                responder_name = resp.get("cr673_name", "") or info["name"]
                consumed_response_emails.add(alt)
                break
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
                "email": info["primary_email"],
                "alternates": list(info["alternates"]),
                "name": responder_name,
                "product": product or "-",
                "readonly": info["readonly"],
                "status": "responded" if responded else "pending",
                "results": results,
                "remarks": remarks,
                "responded_at": (resp or {}).get("cr673_submitted_at", "") or "",
                "reminder_count": reminder_count_by_email.get(primary_lower, 0),
                "last_reminder_at": last_reminder_by_email.get(primary_lower, ""),
                "former": False,
            })

    # Pre-fetch delegations so we know which emails will get a proper
    # chain row further down — those should not be surfaced here as
    # "stranger responder" rows.
    delegations = get_active_delegations(rfp_id)
    delegated_to_emails = {
        (d.get("new_email") or "").lower()
        for d in delegations
        if d.get("new_email")
    }

    # Surface responders whose email is NOT consumed by any team row — could
    # be because the team was reconfigured after they submitted, the email
    # was changed, or the response was created in a different EMAIL_MODE.
    # Without this, a real response would silently vanish from the popup.
    # We also skip emails that will be rendered as a chain's final recipient
    # below — their response gets attached to the chain row instead.
    for em_lower, resp in resp_by_email.items():
        if em_lower in consumed_response_emails:
            continue
        if em_lower in delegated_to_emails:
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
                    "alternates": [em_lower],
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
                    "alternates": [em_lower],
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
        consumed_response_emails.add(em_lower)

    # `delegations` and `delegated_to_emails` were pre-fetched above so
    # responder-not-in-team would already skip chain finals. The same set
    # also keeps intermediate-hop delegates out of the historical-reminder
    # fallback below (their hops live in Reminder History only).

    # Historical reminder recipients no longer on the team and with no
    # response — surface them as pending rows so the audit trail is visible.
    # An email "belongs to a team row" if it appears in ANY row's alternates
    # (covers both primary and CC/portal addresses).
    team_addresses_seen: set = set()
    for r in rows:
        for alt in (r.get("alternates") or []):
            team_addresses_seen.add(alt)
        team_addresses_seen.add((r.get("email") or "").lower())
    for em_lower in reminder_count_by_email:
        if em_lower in team_addresses_seen:
            continue
        if em_lower in consumed_response_emails:
            continue
        if em_lower in delegated_to_emails:
            continue
        rows.append({
            "email": em_lower,
            "alternates": [em_lower],
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

    # Collapse delegation chains so the modal shows only the *current*
    # state of each (product, original_email) chain — not every hop.
    # For A -> B -> C we render: A strikethrough "→ Delegated to C" and a
    # single pending row for C ("Delegated from A"). B is hidden here;
    # the full hop-by-hop trail stays visible in the Reminder History
    # section below.
    #
    # Walk in chronological order; for each delegation, look for an existing
    # chain whose current tip matches the new "original_email" and extend it.
    # Otherwise start a new chain.
    chains: Dict[tuple, Dict[str, Any]] = {}
    for d in delegations:
        prod_lower = (d.get("product") or "").lower()
        old_lower = (d.get("original_email") or "").lower()

        extend_key = None
        for key, chain in chains.items():
            if key[0] != prod_lower:
                continue
            if (chain["final_email"] or "").lower() == old_lower:
                extend_key = key
                break

        if extend_key is not None:
            chain = chains[extend_key]
            chain["final_email"] = d["new_email"]
            chain["final_name"] = d["new_name"]
            chain["delegated_at"] = d["delegated_at"]
            chain["delegated_by"] = d["delegated_by_name"] or d["delegated_by_email"]
        else:
            chains[(prod_lower, old_lower)] = {
                "product": d["product"],
                "original_email": d["original_email"],
                "original_name": d["original_name"],
                "final_email": d["new_email"],
                "final_name": d["new_name"],
                "delegated_at": d["delegated_at"],
                "delegated_by": d["delegated_by_name"] or d["delegated_by_email"],
            }

    for (prod_lower, old_lower), chain in chains.items():
        new_lower = (chain["final_email"] or "").lower()

        # If the chain's final recipient has submitted a response, mirror
        # it onto the chain row instead of showing them as pending. Their
        # response was saved to cr6db_cr673_bahra_rfp_response (keyed by
        # cr673_email) by the actionable-card /response handler, which
        # now accepts delegates as a valid submitter for this RFP.
        chain_resp = resp_by_email.get(new_lower)
        if chain_resp is not None:
            chain_products = _parse_response_data(
                chain_resp.get("cr673_response_data", "") or ""
            )
            per_product = chain_products.get(prod_lower)
            if per_product:
                chain_results = per_product.get("results", "") or ""
                chain_remarks = per_product.get("remarks", "") or ""
            else:
                chain_results = chain_resp.get("cr673_results", "") or ""
                chain_remarks = chain_resp.get("cr673_remarks", "") or ""
            chain_status = "responded"
            chain_responded_at = chain_resp.get("cr673_submitted_at", "") or ""
        else:
            chain_results = ""
            chain_remarks = ""
            chain_status = "pending"
            chain_responded_at = ""

        rows.append({
            "email": chain["final_email"],
            "alternates": [new_lower] if new_lower else [],
            "name": chain["final_name"],
            "product": chain["product"] or "-",
            "readonly": False,
            "status": chain_status,
            "results": chain_results,
            "remarks": chain_remarks,
            "responded_at": chain_responded_at,
            "reminder_count": reminder_count_by_email.get(new_lower, 0),
            "last_reminder_at": last_reminder_by_email.get(new_lower, ""),
            "former": False,
            "delegated_from_email": chain["original_email"],
            "delegated_from_name": chain["original_name"],
        })

        # Match the chain back to its source team row. old_lower may be
        # either a primary email (post-fix delegations) or a composite
        # email string (pre-fix delegations) — check both the row's primary
        # email and its alternates list to handle either form.
        old_parsed = set(_parse_emails(old_lower)) or {old_lower}
        for r in rows:
            if (r.get("product") or "").lower() != prod_lower:
                continue
            if r.get("delegated_to_email"):
                continue
            row_emails = {(r.get("email") or "").lower()}
            row_emails.update((r.get("alternates") or []))
            if not (old_parsed & row_emails):
                continue
            r["delegated_to_email"] = chain["final_email"]
            r["delegated_to_name"] = chain["final_name"]
            r["delegated_at"] = chain["delegated_at"]
            r["delegated_by"] = chain["delegated_by"]
            break

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

    # 5. Record one Dataverse reminder row per recipient + collect results.
    # Store the primary (single) email — not the composite team-table value —
    # so future reminder-count lookups can match a clean key.
    results: List[Dict[str, Any]] = []
    for em_lower, info in members_by_email.items():
        product_str = ", ".join(info["products"]) if info["products"] else ""
        primary = info.get("primary_email") or em_lower
        _record_reminder_row(
            rfp_id, company_name, product_str,
            primary, info["name"],
            actor_email, actor_name,
            overall_status, overall_error,
        )
        results.append({
            "email": primary,
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


# --------------------------------------------------------------------------
# Delegate recipient — per-RFP override that hands off a product line to a
# different email. Master cr673_bahra_rfp_team is NEVER touched.
# --------------------------------------------------------------------------

def delegate_rfp_recipient(
    rfp_id: str,
    product: str,
    original_email: str,
    new_email: str,
    new_name: str,
    actor_email: str,
    actor_name: str,
) -> Dict[str, Any]:
    rfp_id = (rfp_id or "").strip()
    product = (product or "").strip()
    original_email = (original_email or "").strip()
    new_email = (new_email or "").strip()
    new_name = (new_name or "").strip()

    if not rfp_id:
        return {"ok": False, "error": "rfp_id is required"}
    if not product:
        return {"ok": False, "error": "product is required"}
    if not original_email:
        return {"ok": False, "error": "original_email is required"}
    if not new_email or "@" not in new_email:
        return {"ok": False, "error": "new_email is required and must be a valid email"}
    if not new_name:
        return {"ok": False, "error": "new_name is required"}
    if new_email.lower() == original_email.lower():
        return {"ok": False, "error": "new_email must differ from original_email"}

    # Idempotency guard — drop double-clicks within the dedupe window
    now = datetime.now()
    cutoff = now.timestamp() - _DEDUPE_WINDOW_SECONDS
    key = (rfp_id, product.lower(), new_email.lower())
    with _DELEGATION_LOCK:
        for k, ts in list(_DELEGATION_DEDUPE.items()):
            if ts.timestamp() < cutoff:
                _DELEGATION_DEDUPE.pop(k, None)
        if key in _DELEGATION_DEDUPE:
            return {"ok": False, "error": "Duplicate request within 10s — already in progress"}
        _DELEGATION_DEDUPE[key] = now

    # Validate the (product, original_email) pair is an active remindable row.
    # Pulls live response status so we honour any prior delegations in the chain.
    status = get_rfp_response_status(rfp_id)
    matching_row = None
    for r in status.get("rows", []):
        if (r.get("product") or "").lower() != product.lower():
            continue
        if (r.get("email") or "").lower() != original_email.lower():
            continue
        if r.get("delegated_to_email"):
            continue  # already delegated away — must delegate from the chain tip
        if r.get("status") != "pending":
            continue  # only pending rows can be delegated
        if r.get("former"):
            continue
        matching_row = r
        break
    if not matching_row:
        return {
            "ok": False,
            "error": "No active pending row matches the given (product, original_email). It may already be delegated or responded.",
        }

    original_name = (matching_row.get("name") or "").strip()
    company_name = (status.get("rfp", {}).get("company_name") or "").strip()
    rfp_end_date = (status.get("rfp", {}).get("rfp_end_date") or "-").strip() or "-"

    # 1. Insert delegation row first so the popup reflects it even if the email fails
    inserted = _insert_delegation_row(
        rfp_id=rfp_id,
        product=product,
        original_email=original_email,
        original_name=original_name,
        new_email=new_email,
        new_name=new_name,
        actor_email=actor_email,
        actor_name=actor_name,
    )
    if not inserted:
        return {"ok": False, "error": "Failed to record delegation in Dataverse"}

    # 2. Send the actionable card to the new recipient with a delegation banner
    email_status = "Sent"
    email_error = ""
    try:
        from helpers.email_helper import send_actionable_rfp_emails
        graph_client = _build_graph_client()
        send_actionable_rfp_emails(
            rfp_id=rfp_id,
            company_name=company_name,
            rfp_end_date=rfp_end_date,
            matched_csv_path=None,
            graph_client=graph_client,
            recipients_override=[{
                "product": product,
                "name": new_name,
                "email": new_email,
                "readonly": False,
            }],
            subject_prefix="Delegated: ",
            delegation_banner=f"This RFP was delegated to you by {actor_name or actor_email}.",
        )
    except Exception as e:
        email_status = "Failed"
        email_error = str(e)[:1900]
        print(f"[open_rfp] Delegation email send failed for {rfp_id} -> {new_email}: {e}")

    # 3. Mirror into the reminder history table so the existing UI surfaces it
    _record_reminder_row(
        rfp_id, company_name, product,
        new_email, new_name,
        actor_email, actor_name,
        "Delegated" if email_status == "Sent" else "Failed",
        email_error or (f"Delegated from {original_email}"),
    )

    # 4. Audit log
    try:
        log_event(
            action="RFP_DELEGATED",
            category=AuditCategory.RFP,
            actor_email=actor_email,
            actor_name=actor_name,
            target_type="rfp",
            target_id=rfp_id,
            details=json.dumps({
                "rfp_id": rfp_id,
                "product": product,
                "original_email": original_email,
                "original_name": original_name,
                "new_email": new_email,
                "new_name": new_name,
                "email_status": email_status,
                "email_error": email_error,
            })[:4000],
        )
    except Exception as e:
        print(f"[open_rfp] Audit log failed: {e}")

    return {
        "ok": True,
        "delegation": {
            "rfp_id": rfp_id,
            "product": product,
            "original_email": original_email,
            "original_name": original_name,
            "new_email": new_email,
            "new_name": new_name,
        },
        "email_status": email_status,
        "error": email_error,
    }
