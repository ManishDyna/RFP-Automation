"""
Actionable Messages callback endpoint.
Receives Adaptive Card responses from Outlook and saves them to Dataverse.
Also provides a query endpoint for the dashboard to check response status.
"""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime
import json
import jwt
import requests

from helpers.dataverse_helper import DataverseClient
from config.config import (
    TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL,
    ACTIONABLE_CARD_ACTIONS_APP_ID, ACTIONABLE_CARD_APP_ID_URI,
)
from services.system_settings_service import get_setting
from services.master_data_service import get_all_rfp_team_for_emails
from services.rfp_team_columns_service import get_all_columns, get_input_columns
from helpers.email_helper import _build_input_widget_indexed, _resolve_button_url


router = APIRouter(prefix="/api/actionable-card", tags=["Actionable Cards"])

# Dataverse client for this module
_DATAVERSE = DataverseClient(
    tenant_id=TENANT_ID,
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    resource_url=RESOURCE_URL,
)

# ── Actionable Message Token Verification (Microsoft Entra ID) ──
# Microsoft retired the legacy EAT token (issued by substrate.office.com) on
# 2026-06-08. Outlook's "Actions" service now calls this endpoint with a
# Microsoft Entra ID (v2.0) bearer token. We validate signature + expiry +
# issuer + audience + the caller (`azp` = Microsoft's fixed Actions app id).
#   https://learn.microsoft.com/en-us/outlook/actionable-messages/enable-entra-token-for-actionable-messages
_ENTRA_OPENID_URL = f"https://login.microsoftonline.com/{TENANT_ID}/v2.0/.well-known/openid-configuration"
_ENTRA_ISSUER = f"https://login.microsoftonline.com/{TENANT_ID}/v2.0"
_JWKS_CLIENT = None


def _get_jwks_client():
    global _JWKS_CLIENT
    if _JWKS_CLIENT is None:
        config = requests.get(_ENTRA_OPENID_URL, timeout=10).json()
        jwks_uri = config["jwks_uri"]
        _JWKS_CLIENT = jwt.PyJWKClient(jwks_uri)
    return _JWKS_CLIENT


def _verify_actionable_message_token(auth_header: str) -> dict:
    """
    Verify the Microsoft Entra ID bearer token sent by Outlook's Actions service
    with Action.Http submissions (post-EAT migration, 2026-06-08).

    Validated:
      - signature: RS256, key from the tenant's Entra v2.0 JWKS
      - exp:       not expired
      - iss:       https://login.microsoftonline.com/<TENANT_ID>/v2.0
      - aud:       our app's Application ID URI (ACTIONABLE_CARD_APP_ID_URI)
      - azp:       Microsoft Actions app id (ACTIONABLE_CARD_ACTIONS_APP_ID)

    NOTE: the acting user's email is in `preferred_username` — the Entra `sub`
    is an opaque pairwise id, NOT the email (unlike the old substrate token).
    """
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = auth_header[len("Bearer "):]

    # The audience (AppIdUri) is produced by the Part-1 provider migration. Until
    # it's configured we cannot validate `aud`, so fail loudly rather than accept
    # a token blindly.
    expected_aud = get_setting("ACTIONABLE_CARD_APP_ID_URI", ACTIONABLE_CARD_APP_ID_URI)
    if not expected_aud:
        raise HTTPException(
            status_code=500,
            detail="ACTIONABLE_CARD_APP_ID_URI not configured — complete the Entra "
                   "provider migration (Part 1) and set the AppIdUri.",
        )

    try:
        jwks_client = _get_jwks_client()
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        decoded = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=expected_aud,
            issuer=_ENTRA_ISSUER,
            options={"verify_exp": True, "verify_aud": True, "verify_iss": True},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

    # Confirm Microsoft's Actions service is the caller (not another app that
    # happens to hold a token for our audience). v2.0 tokens use `azp`.
    actions_app = get_setting("ACTIONABLE_CARD_ACTIONS_APP_ID", ACTIONABLE_CARD_ACTIONS_APP_ID)
    azp = decoded.get("azp") or decoded.get("appid")
    if actions_app and azp != actions_app:
        raise HTTPException(status_code=401, detail=f"Unexpected caller azp={azp}")

    print(f"✅ Entra token verified. user={decoded.get('preferred_username')}, azp={azp}")
    return decoded


def _build_not_in_team_card(name: str, rfp_id: str) -> dict:
    """Return a card shown to users who are not part of the RFP team."""
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.0",
        "padding": "Default",
        "body": [
            {"type": "TextBlock", "text": f"Dear {name or 'User'},", "wrap": True, "size": "Small"},
            {"type": "TextBlock",
             "text": "You don't have permission to reply to this RFP.",
             "wrap": True, "spacing": "Small", "weight": "Bolder", "color": "Attention"},
            {"type": "TextBlock",
             "text": f"Your email is not part of the RFP team for **{rfp_id}**. "
                     "Please contact the RFP administrator if you believe this is an error.",
             "wrap": True, "spacing": "Small", "size": "Small", "isSubtle": True},
            {"type": "TextBlock", "text": "Best Regards,",
             "wrap": True, "spacing": "Medium", "separator": True, "size": "Small"},
            {"type": "TextBlock", "text": "Automation System",
             "wrap": True, "spacing": "None", "size": "Small"},
        ],
    }


def _get_all_responses_for_rfp(rfp_id: str) -> list:
    """Query Dataverse for all responses for a given RFP."""
    try:
        result = _DATAVERSE.query_rows(
            get_setting("RFP_RESPONSE_TABLE_API", ""),
            filter_expr=f"cr673_rfp_id eq '{rfp_id}'",
            top=50,
            table_logical_name=get_setting("RFP_RESPONSE_TABLE_LOGICAL", ""),
            use_display_names=True,
        )
        if result and "value" in result:
            return result["value"]
    except Exception as e:
        print(f"⚠ Could not query RFP responses: {e}")
    return []


def _parse_emails(email_field: str) -> list:
    """Split a (possibly comma-separated) email-field value into a normalized
    lowercase list. 'Alice@Co.com, bob@co.com ' → ['alice@co.com', 'bob@co.com']."""
    if not email_field:
        return []
    out = []
    seen = set()
    for part in str(email_field).replace(";", ",").split(","):
        e = part.strip().lower()
        if e and e not in seen:
            out.append(e)
            seen.add(e)
    return out


def _first_response_per_row(rfp_responses: list, team_table: list) -> dict:
    """
    Row-level first-response-wins.

    Each team-table row is a responsibility unit; the row's email field may list
    multiple alternates (comma-separated). Within a row's alternates, the EARLIEST
    non-empty answer wins. Each row needs its own answer for the RFP to complete.

    Caller must pre-filter rfp_responses by cr673_rfp_id.

    Returns: {responsibility_id: {<input fields>, name, email, submitted_at, product}}

    Matching logic (newest → oldest fallback):
      1. Response carries explicit responsibility_id → exact match.
      2. Legacy responses (no responsibility_id): match by (product, submitter_email
         in the row's alternates list). If multiple team rows share a product,
         attribute the response to the first row whose alternates include the
         submitter — gives sensible behavior for data created before this feature.
    """
    # Index team rows for fast lookup
    rows_by_id = {}
    rows_by_product = {}
    for m in team_table:
        rid = m.get("record_id")
        prod = m.get("product")
        if not rid or not prod or prod == "All":
            continue
        emails = _parse_emails(m.get("email", ""))
        entry = {"record_id": rid, "product": prod, "emails": emails, "name": m.get("name", "")}
        rows_by_id[rid] = entry
        rows_by_product.setdefault(prod, []).append(entry)

    winners = {}
    for r in rfp_responses:
        r_email = (r.get("cr673_email") or "").lower()
        r_name = r.get("cr673_name", "")
        submitted_at = r.get("cr673_submitted_at", "") or ""
        raw_json = r.get("cr673_response_data") or r.get("response_data", "")

        parsed_products = []
        if raw_json:
            try:
                parsed = json.loads(raw_json)
                if isinstance(parsed, dict) and isinstance(parsed.get("products"), list):
                    parsed_products = parsed["products"]
            except (json.JSONDecodeError, TypeError):
                parsed_products = []

        # Legacy: single-product rows stored fields at top level
        if not parsed_products:
            legacy_product = r.get("cr673_product", "")
            if legacy_product:
                parsed_products = [{
                    "product": legacy_product,
                    "results": r.get("cr673_results", ""),
                    "remarks": r.get("cr673_remarks", ""),
                }]

        for p_resp in parsed_products:
            product = (p_resp.get("product") or "").strip()
            if not product:
                continue
            has_value = any(
                str(v).strip()
                for k, v in p_resp.items()
                if k not in ("product", "responsibility_id")
            )
            if not has_value:
                continue

            # Determine ALL team-table rows this single response satisfies.
            # Storage is keyed by (rfp, email, product), so ksagov.tenders'
            # single "TBS and BED" answer is stored once — but the team table
            # has TWO TBS and BED rows (Mohammad + Intikhab), both with
            # ksagov.tenders as an alternate. By design, one shared-inbox
            # answer should mark BOTH team rows as answered (same product +
            # same email + same RFP = one response covers all matching rows).
            matching_rids: set = set()
            explicit_rid = p_resp.get("responsibility_id")
            if explicit_rid and explicit_rid in rows_by_id:
                matching_rids.add(explicit_rid)
            for candidate in rows_by_product.get(product, []):
                if r_email in candidate["emails"]:
                    matching_rids.add(candidate["record_id"])
            if not matching_rids:
                # Submitter isn't in any team row for this product — skip
                continue

            for resp_id in matching_rids:
                existing = winners.get(resp_id)
                if existing is None:
                    keep = True
                elif submitted_at and existing.get("submitted_at"):
                    keep = submitted_at < existing["submitted_at"]
                else:
                    keep = False
                if keep:
                    winners[resp_id] = {
                        **{k: v for k, v in p_resp.items() if k not in ("product", "responsibility_id")},
                        "name": r_name,
                        "email": r_email,
                        "submitted_at": submitted_at,
                        "product": product,
                        "responsibility_id": resp_id,
                    }
    return winners


def _uploaded_products_globally(rfp_responses: list) -> set:
    """Products with at least one uploaded file from ANY assignee for this RFP."""
    uploaded = set()
    for r in rfp_responses:
        raw_json = r.get("cr673_response_data") or r.get("response_data", "")
        if not raw_json:
            continue
        try:
            parsed = json.loads(raw_json)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(parsed, dict):
            continue
        files = parsed.get("uploaded_files")
        if isinstance(files, list):
            for entry in files:
                if isinstance(entry, dict) and entry.get("product"):
                    uploaded.add(entry["product"])
    return uploaded


def _uploads_by_responder(rfp_responses: list) -> set:
    """Set of (email_lower, product) pairs that have at least one uploaded file.

    Used by the consolidated email to render the per-row 'View Files' button
    only next to the specific responder who uploaded — not for every row of
    the same product.
    """
    uploaded = set()
    for r in rfp_responses:
        email = (r.get("cr673_email") or "").strip().lower()
        if not email:
            continue
        raw_json = r.get("cr673_response_data") or r.get("response_data", "")
        if not raw_json:
            continue
        try:
            parsed = json.loads(raw_json)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(parsed, dict):
            continue
        files = parsed.get("uploaded_files")
        if isinstance(files, list):
            for entry in files:
                if isinstance(entry, dict) and entry.get("product"):
                    uploaded.add((email, entry["product"]))
    return uploaded


def _build_refresh_card(
    rfp_id: str,
    company_name: str,
    products: list,
    name: str,
    email: str,
    winners_by_row: dict,
    uploaded_products_global: set,
    responded_count: int,
    total_count: int,
    callback_url: str,
    team_table: list = None,
    is_team_member: bool = True,
) -> dict:
    """
    Adaptive Card for refresh/post-submit display.

    Row-level first-response-wins:
      • One row per team-table responsibility (NOT deduped by product — two team
        rows for the same product render as two card rows).
      • A row's email field may list multiple alternates (comma-separated).
        Within those alternates, first-response-wins.
      • Editable when: current user's email is in the row's alternates AND no
        answer for that row yet.
      • Otherwise: shows the winner's answer (if any) or "Pending".

    winners_by_row: {responsibility_id: response} from _first_response_per_row()
    uploaded_products_global: products with any uploaded files (any responder).
    is_team_member: when False, recipient isn't a team member — lock everything.
    """
    user_email_key = (email or "").lower()
    refresh_url = callback_url + "/refresh"

    columns = get_all_columns()
    input_columns = get_input_columns()

    if team_table is None:
        team_table = get_all_rfp_team_for_emails()

    # Build the list of responsibility rows to render
    team_rows = []
    for m in team_table:
        rid = m.get("record_id")
        prod = m.get("product")
        if not rid or not prod or prod == "All":
            continue
        team_rows.append({
            "record_id": rid,
            "product": prod,
            "name": m.get("name") or "",
            "emails": _parse_emails(m.get("email", "")),
            "raw_email": m.get("email", ""),
        })
    # Stable, grouped order: by product then name
    team_rows.sort(key=lambda r: (r["product"], r["name"]))

    # Assign editable indices for THIS user's pending rows (preserves card order)
    editable_idx_map = {}  # responsibility_id → idx
    next_idx = 0
    for r in team_rows:
        is_alt = user_email_key in r["emails"]
        already_won = r["record_id"] in winners_by_row
        if is_team_member and is_alt and not already_won:
            editable_idx_map[r["record_id"]] = next_idx
            next_idx += 1

    # --- Table header ---
    header_cols = []
    for col in columns:
        header_cols.append({
            "type": "Column", "width": 1, "padding": "None",
            "items": [{"type": "TextBlock", "text": col.get("column_label", col["column_key"]),
                        "weight": "Bolder", "wrap": True}],
        })
    header_row = {
        "type": "ColumnSet",
        "style": "emphasis",
        "padding": "None",
        "columns": header_cols,
    }

    data_rows = []
    for r in team_rows:
        rid = r["record_id"]
        product = r["product"]
        winner = winners_by_row.get(rid)
        row_responded = winner is not None
        current_user_is_alt = user_email_key in r["emails"]
        is_editable_for_me = rid in editable_idx_map

        if row_responded:
            display_name = winner.get("name") or ""
        elif current_user_is_alt:
            display_name = name
        else:
            display_name = r["name"] or " / ".join(r["emails"]) or "—"

        # Email column ALWAYS shows the team-row's full alternates list, so
        # every recipient can see all the people responsible for a product
        # — not just whoever happened to win the response.
        display_email = ", ".join(r["emails"]) if r["emails"] else "—"

        # Upload button signs token with the CURRENT user's identity
        row_ctx = {
            "rfp_id": rfp_id,
            "company_name": company_name,
            "product": product,
            "name": name if current_user_is_alt else display_name,
            "email": email if current_user_is_alt else display_email,
        }

        row_columns = []
        for col in columns:
            key = col["column_key"]
            if col.get("column_type") == "button":
                url_template = col.get("dropdown_options", "") or ""
                is_upload_btn = "{upload_url}" in url_template

                if is_upload_btn:
                    if product in uploaded_products_global:
                        item = {"type": "TextBlock", "text": "Uploaded ✓",
                                "color": "Good", "weight": "Bolder", "wrap": True, "size": "Small"}
                    elif current_user_is_alt:
                        btn_url = _resolve_button_url(url_template, row_ctx, rfp_id) or "https://example.com"
                        item = {
                            "type": "ActionSet",
                            "actions": [{
                                "type": "Action.OpenUrl",
                                "title": col.get("column_label", key),
                                "url": btn_url,
                            }],
                        }
                    else:
                        item = {"type": "TextBlock", "text": "—",
                                "color": "Default", "wrap": True, "size": "Small", "isSubtle": True}
                else:
                    btn_url = _resolve_button_url(url_template, row_ctx, rfp_id) or "https://example.com"
                    item = {
                        "type": "ActionSet",
                        "actions": [{
                            "type": "Action.OpenUrl",
                            "title": col.get("column_label", key),
                            "url": btn_url,
                        }],
                    }
            elif col.get("column_category") == "input":
                if is_editable_for_me:
                    item = _build_input_widget_indexed(col, editable_idx_map[rid])
                elif row_responded:
                    value = winner.get(key, "") or "Pending"
                    color = "Good" if value != "Pending" else "Accent"
                    item = {"type": "TextBlock", "text": value,
                            "color": color, "wrap": True, "size": "Small"}
                else:
                    item = {"type": "TextBlock", "text": "Pending",
                            "color": "Accent", "wrap": True, "size": "Small"}
            else:
                if key == "product":
                    value = product
                elif key == "name":
                    value = display_name
                elif key == "email":
                    value = display_email
                else:
                    value = ""
                item = {"type": "TextBlock", "text": value, "wrap": True,
                        "size": "Small", "weight": "Bolder" if key != "email" else "Default"}
            row_columns.append({
                "type": "Column", "width": 1, "padding": "None",
                "items": [item],
            })
        data_rows.append({
            "type": "ColumnSet",
            "separator": True,
            "padding": "None",
            "columns": row_columns,
        })

    # Submit body must carry responsibility_id per editable row so the backend can
    # attribute each answer to the right team-table row. Parallel arrays:
    #   products[i], responsibility_ids[i], results_i, remarks_i, ...
    submit_rows = sorted(editable_idx_map.items(), key=lambda kv: kv[1])
    submit_responsibility_ids = [rid for rid, _ in submit_rows]
    rid_to_row = {r["record_id"]: r for r in team_rows}
    submit_products = [rid_to_row[rid]["product"] for rid in submit_responsibility_ids]
    user_assigned = set(products or [])

    refresh_body = json.dumps({
        "rfp_id": rfp_id,
        "products": products,
        "name": name,
        "email": email,
        "company_name": company_name,
    })

    refresh_action = {
        "type": "Action.Http",
        "title": "Refresh Status",
        "method": "POST",
        "url": refresh_url,
        "headers": [{"name": "Content-Type", "value": "application/json"}],
        "body": refresh_body,
    }

    status_text = f"Team responses: {responded_count}/{total_count} responsibilities answered."

    actions = [refresh_action]
    if submit_responsibility_ids:
        submit_body = {
            "rfp_id": rfp_id,
            "products": submit_products,
            "responsibility_ids": submit_responsibility_ids,
            "name": name,
            "email": email,
            "company_name": company_name,
        }
        for idx in range(len(submit_responsibility_ids)):
            for col in input_columns:
                field_id = f"{col['column_key']}_{idx}"
                submit_body[field_id] = "{{" + field_id + ".value}}"
        submit_action = {
            "type": "Action.Http",
            "title": "Submit All Responses",
            "method": "POST",
            "url": callback_url,
            "headers": [{"name": "Content-Type", "value": "application/json"}],
            "body": json.dumps(submit_body),
            "style": "positive",
            "isPrimary": True,
        }
        actions = [submit_action, refresh_action]

    products_text = ", ".join(f"**{p}**" for p in (products or []))
    if not user_assigned:
        instruction_text = "You can refresh to see the team's response status."
    elif not submit_responsibility_ids and user_assigned:
        instruction_text = "Your responsibilities have already been answered by your co-assignees. Thank you."
    else:
        instruction_text = "Please fill in your Results and Remarks for each pending row below."
    body_items = [
        {"type": "TextBlock", "text": f"Dear {name},",
         "wrap": True, "size": "Small"},
        {"type": "TextBlock", "text": f"Kindly advise us regarding the attached RFP file for {products_text}.",
         "wrap": True, "spacing": "Small", "size": "Small"},
        {"type": "TextBlock", "text": instruction_text,
         "wrap": True, "spacing": "Small", "size": "Small"},
        {"type": "TextBlock", "text": "Your Products", "weight": "Bolder",
         "separator": True, "spacing": "Medium"},
        header_row,
        *data_rows,
        {"type": "TextBlock", "text": status_text,
         "isSubtle": True, "wrap": True, "spacing": "Medium", "size": "Small"},
        {"type": "TextBlock", "text": "Best Regards,",
         "wrap": True, "spacing": "Medium", "separator": True, "size": "Small"},
        {"type": "TextBlock", "text": "Automation System",
         "wrap": True, "spacing": "None", "size": "Small"},
    ]
    card = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.0",
        "padding": "Default",
        "body": body_items,
        "actions": actions,
    }

    return card


def _maybe_fire_consolidated_email(rfp_id: str, rfp_team: list, all_responses: list,
                                    winners_by_row: dict, company_name: str) -> bool:
    """Fire the consolidated 'all-responded' email AT MOST ONCE per RFP.

    Idempotency guard: the master row's `all_responses_at` field. Set after
    a successful send; subsequent calls see it populated and short-circuit.
    Called from BOTH /response (when the final submission flips state) and
    /response/refresh (catches up if the trigger was missed — e.g. server
    restart between save and notify, or fan-out fix deployed mid-cycle).

    Returns True if the email was sent or had already been sent for this RFP;
    False if the conditions weren't met or send failed.
    """
    team_row_ids = {
        m.get("record_id") for m in rfp_team
        if m.get("record_id") and m.get("product") and m["product"] != "All"
    }
    all_responded = bool(team_row_ids) and team_row_ids.issubset(set(winners_by_row.keys()))
    if not all_responded:
        return False

    table_api = get_setting("RFP_ACTIVITY_LOG_TABLE_API", "cr673_bahra_rfps_v2s")
    table_logical = get_setting("RFP_ACTIVITY_LOG_TABLE_LOGICAL", "cr673_bahra_rfps_v2")

    try:
        activity = _DATAVERSE.query_rows(
            table_api,
            filter_expr=f"RFP_ID eq '{rfp_id}'",
            top=1,
            table_logical_name=table_logical,
            use_display_names=True,
        )
    except Exception as e:
        print(f"[consolidated] Could not query activity log for {rfp_id}: {e}")
        return False

    if not (activity and activity.get("value")):
        print(f"[consolidated] No activity log row found for {rfp_id}; skipping")
        return False
    activity_row = activity["value"][0]
    if (activity_row.get("all_responses_at") or "").strip():
        return True  # already fired previously — idempotent no-op

    # Build the responses payload — one entry per team-table responsibility,
    # sorted by product then row name so duplicate-product rows stay grouped.
    row_lookup = {m["record_id"]: m for m in rfp_team if m.get("record_id")}
    responded_row_ids = set(winners_by_row.keys()) & team_row_ids
    ordered_row_ids = sorted(
        responded_row_ids,
        key=lambda rid: (
            row_lookup.get(rid, {}).get("product", ""),
            row_lookup.get(rid, {}).get("name", ""),
        ),
    )
    uploads_by_responder = _uploads_by_responder(all_responses)
    responses_for_email = []
    for rid in ordered_row_ids:
        win = winners_by_row.get(rid)
        team_row = row_lookup.get(rid, {})
        if not win:
            continue
        product = team_row.get("product", win.get("product", ""))
        win_email = (win.get("email", "") or "").strip().lower()
        responses_for_email.append({
            "product": product,
            "name": win.get("name") or team_row.get("name", ""),
            "email": win.get("email", ""),
            "_has_uploads": (win_email, product) in uploads_by_responder,
            **{
                k: v for k, v in win.items()
                if k not in ("name", "email", "submitted_at", "product", "responsibility_id")
            },
        })

    rfp_end_date = (
        activity_row.get("RFP_End_Date")
        or activity_row.get("RFP End Date")
        or activity_row.get("rfp_end_date")
        or "-"
    )

    try:
        from helpers.email_helper import send_consolidated_response_email
        send_consolidated_response_email(rfp_id, responses_for_email, company_name, rfp_end_date)
    except Exception as e:
        print(f"[consolidated] Send failed for {rfp_id}: {e}")
        return False

    # Mark as fired so neither /response nor /response/refresh re-sends it.
    _resp_timestamps = [
        r.get("cr673_submitted_at", "") for r in all_responses
        if r.get("cr673_submitted_at")
    ]
    fired_at = max(_resp_timestamps) if _resp_timestamps else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pk_logical = f"{table_logical}id"
    try:
        colmap = _DATAVERSE.get_column_mapping(table_logical)
        l2d = {v: k for k, v in colmap.items()}
    except Exception:
        l2d = {}
    pk_display = l2d.get(pk_logical)
    activity_record_id = (activity_row.get(pk_display) if pk_display else None) or activity_row.get(pk_logical)
    if activity_record_id:
        try:
            _DATAVERSE.update_row(
                table_api,
                activity_record_id,
                {"all_responses_at": fired_at},
                table_logical_name=table_logical,
                use_display_names=True,
            )
        except Exception as e:
            print(f"[consolidated] Could not set all_responses_at for {rfp_id}: {e}")

    print(f"✅ Consolidated email sent for {rfp_id} — {len(responses_for_email)} products covered")
    return True


@router.post("/response")
async def receive_card_response(request: Request):
    """
    Receive an Adaptive Card form submission from Outlook.
    Supports grouped submissions: one person submits responses for multiple products at once.
    Verifies the bearer token, extracts the response, and saves to Dataverse.
    When all team members have responded, sends a consolidated email.
    """
    print(f"📩 /response endpoint hit! Method={request.method}, URL={request.url}")
    print(f"📩 Headers: Authorization={'present' if request.headers.get('Authorization') else 'MISSING'}")
    # Step 1: Verify the bearer token from Microsoft
    auth_header = request.headers.get("Authorization", "")
    try:
        claims = _verify_actionable_message_token(auth_header)
    except Exception as e:
        print(f"❌ Token verification FAILED: {e}")
        raise
    # Entra token: email is in preferred_username/upn — `sub` is an opaque id.
    submitter_email = claims.get("preferred_username") or claims.get("upn") or claims.get("email") or "unknown"

    # Step 2: Parse the JSON body
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    rfp_id = body.get("rfp_id", "")
    name = body.get("name", "")
    expected_email = body.get("email", "")
    company_name = body.get("company_name", "")

    # Support both old (single product) and new (multiple products) format
    products = body.get("products", [])
    if not products:
        # Backward compat: single product format
        single_product = body.get("product", "")
        products = [single_product] if single_product else []

    # Step 3: Verify that the submitter matches the expected email
    submitter_user = submitter_email.lower().split("@")[0]
    expected_user = expected_email.lower().split("@")[0] if expected_email else ""
    if expected_user and submitter_user != expected_user:
        raise HTTPException(
            status_code=403,
            detail=f"Token email ({submitter_email}) does not match expected ({expected_email})",
        )

    # Step 3a: Reject submitters who aren't an alternate in any team-table row
    # OR an active delegation target for this specific RFP. The delegations
    # table is the per-RFP override surface — its targets are legitimate
    # responders even though they were never added to the master team table.
    rfp_team_pre = get_all_rfp_team_for_emails()
    team_emails_pre = set()
    for m in rfp_team_pre:
        for e in _parse_emails(m.get("email", "")):
            team_emails_pre.add(e)
    try:
        from services.open_rfp_service import get_active_delegations
        for d in get_active_delegations(rfp_id):
            new_em = (d.get("new_email") or "").lower()
            if new_em:
                team_emails_pre.add(new_em)
    except Exception as e:
        print(f"[/response] Could not load delegations for {rfp_id}: {e}")
    submitter_key_pre = (expected_email or submitter_email).lower()
    if submitter_key_pre not in team_emails_pre:
        print(f"⛔ Non-team submitter rejected: {submitter_key_pre} (RFP {rfp_id})")
        return JSONResponse(
            content=_build_not_in_team_card(name, rfp_id),
            status_code=200,
            headers={"CARD-UPDATE-IN-BODY": "true"},
        )

    # Step 4: Extract per-row responses from indexed fields.
    # Parallel arrays in the body:
    #   products[i], responsibility_ids[i] → identify which team row this answer is for
    #   results_i, remarks_i, ...           → the actual answer values for row i
    responsibility_ids = body.get("responsibility_ids", []) or []
    input_cols = get_input_columns()
    per_product_responses = []
    for idx, product in enumerate(products):
        row_data_entry = {}
        for col in input_cols:
            key = col["column_key"]
            indexed_key = f"{key}_{idx}"
            row_data_entry[key] = body.get(indexed_key, "") or body.get(key, "")
        rid = responsibility_ids[idx] if idx < len(responsibility_ids) else ""
        per_product_responses.append({
            "responsibility_id": rid,
            "product": product,
            **row_data_entry,
        })

    # Step 5: Per-product upsert.
    # Logical unique key = (cr673_rfp_id, cr673_email, cr673_product).
    # The shared inbox (e.g. ksagov.tenders) submits answers for several
    # products across many clicks; each product gets its OWN row, so a later
    # submit can never wipe an earlier one. Blank rows in the form are
    # silently ignored — only products the user actually answered are written.
    # Uploaded files travel with their product row inside cr673_response_data.
    resp_email = expected_email or submitter_email
    table_api = get_setting("RFP_RESPONSE_TABLE_API", "")
    table_logical = get_setting("RFP_RESPONSE_TABLE_LOGICAL", "")

    def _has_any_input(entry: dict) -> bool:
        for col in input_cols:
            k = col["column_key"]
            if k in ("responsibility_id", "product"):
                continue
            if (entry.get(k) or "").strip():
                return True
        return False

    # Resolve PK column once for any updates we have to do below.
    try:
        colmap = _DATAVERSE.get_column_mapping(table_logical)
        logical_to_display = {v: k for k, v in colmap.items()}
    except Exception:
        logical_to_display = {}
    pk_logical = f"{table_logical}id"
    pk_display = logical_to_display.get(pk_logical)

    saved_count = 0
    skipped_blank = 0
    submitted_at_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for entry in per_product_responses:
        if not _has_any_input(entry):
            skipped_blank += 1
            continue

        product_str = (entry.get("product") or "").strip()
        if not product_str:
            skipped_blank += 1
            continue

        # Look up existing row for THIS product, preserving any uploaded_files
        # already attached to it. We escape single quotes in product to keep the
        # OData filter syntactically valid (e.g. "TBS and BED" is safe; future
        # product names might contain ').
        product_for_filter = product_str.replace("'", "''")
        existing_record_id = None
        existing_uploaded_files: list = []
        try:
            existing = _DATAVERSE.query_rows(
                table_api,
                filter_expr=(
                    f"cr673_rfp_id eq '{rfp_id}' "
                    f"and cr673_email eq '{resp_email}' "
                    f"and cr673_product eq '{product_for_filter}'"
                ),
                top=1,
                table_logical_name=table_logical,
                use_display_names=True,
            )
            if existing and existing.get("value"):
                existing_row = existing["value"][0]
                existing_record_id = (
                    (existing_row.get(pk_display) if pk_display else None)
                    or existing_row.get(pk_logical)
                )
                raw = existing_row.get("cr673_response_data") or ""
                if raw:
                    try:
                        parsed = json.loads(raw)
                        if isinstance(parsed, dict):
                            files = parsed.get("uploaded_files", []) or []
                            if isinstance(files, list):
                                existing_uploaded_files = files
                    except (json.JSONDecodeError, TypeError):
                        pass
        except Exception as e:
            print(f"[/response] Lookup failed for {rfp_id}/{resp_email}/{product_str}: {e}")

        # JSON travels alongside the flat columns for forward compatibility:
        # readers that already parse cr673_response_data (the chain logic,
        # _first_response_per_row's preferred path) keep working unchanged.
        per_product_json = {
            "products": [entry],
            "uploaded_files": existing_uploaded_files,
        }

        row_data = {
            "cr673_rfp_id": rfp_id,
            "cr673_product": product_str,
            "cr673_name": name,
            "cr673_email": resp_email,
            "cr673_results": entry.get("results", "") or "",
            "cr673_remarks": entry.get("remarks", "") or "",
            "cr673_response_data": json.dumps(per_product_json),
            "cr673_submitted_at": submitted_at_str,
            "cr673_company_name": company_name,
        }

        try:
            if existing_record_id:
                _DATAVERSE.update_row(
                    table_api,
                    existing_record_id,
                    row_data,
                    table_logical_name=table_logical,
                    use_display_names=True,
                )
            else:
                _DATAVERSE.insert_row(
                    table_api,
                    row_data,
                    table_logical_name=table_logical,
                    use_display_names=True,
                )
            saved_count += 1
        except Exception as e:
            print(f"❌ Failed to save response for product '{product_str}': {e}")
            raise HTTPException(status_code=500, detail="Failed to save response")

    print(
        f"[/response] SAVED rfp={rfp_id} email={resp_email} "
        f"saved={saved_count} skipped_blank={skipped_blank}"
    )

    # Step 5: Check completion — every team-table ROW (responsibility) has at least
    # one response from one of its alternates. RFP-scoped via _get_all_responses_for_rfp.
    rfp_team = rfp_team_pre
    all_responses = _get_all_responses_for_rfp(rfp_id)
    winners_by_row = _first_response_per_row(all_responses, rfp_team)
    uploaded_products_global = _uploaded_products_globally(all_responses)
    team_row_ids = {
        m.get("record_id") for m in rfp_team
        if m.get("record_id") and m.get("product") and m["product"] != "All"
    }
    responded_row_ids = set(winners_by_row.keys()) & team_row_ids
    all_responded = bool(team_row_ids) and team_row_ids.issubset(set(winners_by_row.keys()))

    # Step 5a: Update response metrics on RFP activity log
    try:
        RFP_ACTIVITY_LOG_TABLE_API = get_setting("RFP_ACTIVITY_LOG_TABLE_API", "cr673_bahra_rfps_v2s")
        RFP_ACTIVITY_LOG_TABLE_LOGICAL = get_setting("RFP_ACTIVITY_LOG_TABLE_LOGICAL", "cr673_bahra_rfps_v2")

        # Calculate response timestamps. Note: `all_responses_at` is intentionally
        # NOT set here — that field is the idempotency guard for the consolidated
        # email and is owned exclusively by _maybe_fire_consolidated_email below.
        _resp_timestamps = [
            r.get("cr673_submitted_at", "") for r in all_responses
            if r.get("cr673_submitted_at")
        ]
        _first_response = min(_resp_timestamps) if _resp_timestamps else ""

        # Find the activity log record for this RFP
        _activity = _DATAVERSE.query_rows(
            RFP_ACTIVITY_LOG_TABLE_API,
            filter_expr=f"RFP_ID eq '{rfp_id}'",
            top=1,
            table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL,
            use_display_names=True,
        )
        if _activity and "value" in _activity and len(_activity["value"]) > 0:
            _act_row = _activity["value"][0]
            _pk_logical = f"{RFP_ACTIVITY_LOG_TABLE_LOGICAL}id"
            try:
                _colmap = _DATAVERSE.get_column_mapping(RFP_ACTIVITY_LOG_TABLE_LOGICAL)
                _l2d = {v: k for k, v in _colmap.items()}
            except Exception:
                _l2d = {}
            _pk_display = _l2d.get(_pk_logical)
            _act_id = (_act_row.get(_pk_display) if _pk_display else None) or _act_row.get(_pk_logical)
            if _act_id:
                _DATAVERSE.update_row(
                    RFP_ACTIVITY_LOG_TABLE_API,
                    _act_id,
                    {
                        "response_count": str(len(responded_row_ids)),
                        "first_response_at": _first_response,
                    },
                    table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL,
                    use_display_names=True,
                )
    except Exception as e:
        print(f"⚠ Could not update response metrics on activity log: {e}")

    # Step 5b: Fire consolidated-response email if this submission completed the RFP.
    # The helper is idempotent (uses all_responses_at as a guard), so submitting
    # again later or refreshing won't trigger a duplicate send.
    _maybe_fire_consolidated_email(
        rfp_id=rfp_id,
        rfp_team=rfp_team,
        all_responses=all_responses,
        winners_by_row=winners_by_row,
        company_name=company_name,
    )

    # Step 6: Return updated card using shared builder.
    # If the just-saved submission isn't reflected in winners yet (Dataverse read-after-write
    # can lag), patch it in so the submitter sees their answer immediately.
    submitter_key = (expected_email or submitter_email).lower()
    submitted_at_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for p_resp in per_product_responses:
        rid = (p_resp.get("responsibility_id") or "").strip()
        if not rid:
            continue
        has_value = any(
            str(v).strip()
            for k, v in p_resp.items()
            if k not in ("product", "responsibility_id")
        )
        if not has_value:
            continue
        if rid not in winners_by_row:
            winners_by_row[rid] = {
                **{k: v for k, v in p_resp.items() if k not in ("product", "responsibility_id")},
                "name": name,
                "email": expected_email or submitter_email,
                "submitted_at": submitted_at_now,
                "product": p_resp.get("product", ""),
                "responsibility_id": rid,
            }

    refresh_card = _build_refresh_card(
        rfp_id=rfp_id,
        company_name=company_name,
        products=products,
        name=name,
        email=expected_email or submitter_email,
        winners_by_row=winners_by_row,
        uploaded_products_global=uploaded_products_global,
        responded_count=len(set(winners_by_row.keys()) & team_row_ids),
        total_count=len(team_row_ids),
        callback_url=get_setting("ACTIONABLE_CARD_CALLBACK_URL", ""),
        team_table=rfp_team,
        is_team_member=True,
    )

    return JSONResponse(
        content=refresh_card,
        status_code=200,
        headers={"CARD-UPDATE-IN-BODY": "true"},
    )


@router.post("/response/refresh")
async def refresh_card_status(request: Request):
    """
    Auto-invoked by Outlook when user opens the email (via autoInvokeAction).
    Also called by the manual "Refresh Status" button.
    Returns the latest card showing who has responded.
    Must respond within 2 seconds (Outlook timeout).
    """
   
    # Step 1: Verify the bearer token
    auth_header = request.headers.get("Authorization", "")
    claims = _verify_actionable_message_token(auth_header)
    # Entra token: email is in preferred_username/upn — `sub` is an opaque id.
    opener_email = claims.get("preferred_username") or claims.get("upn") or claims.get("email") or "unknown"

    # Step 2: Parse the JSON body (contains rfp_id, product, name, email, company_name)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    rfp_id = body.get("rfp_id", "")
    name = body.get("name", "")
    expected_email = body.get("email", "")
    company_name = body.get("company_name", "")

    # Support both old (single product) and new (multiple products) format
    products = body.get("products", [])
    if not products:
        single_product = body.get("product", "")
        products = [single_product] if single_product else []

    # Step 3: Query Dataverse for latest responses (scoped to this rfp_id)
    all_responses = _get_all_responses_for_rfp(rfp_id)
    rfp_team = get_all_rfp_team_for_emails()
    winners_by_row = _first_response_per_row(all_responses, rfp_team)
    uploaded_products_global = _uploaded_products_globally(all_responses)

    # Catch-up trigger: if all responsibilities are answered but the
    # consolidated email never fired (e.g. timing race when state flipped,
    # server restart between save and notify, or fan-out fix deployed mid-
    # cycle), the helper sends it now and marks all_responses_at so it
    # won't fire again on the next refresh.
    _maybe_fire_consolidated_email(
        rfp_id=rfp_id,
        rfp_team=rfp_team,
        all_responses=all_responses,
        winners_by_row=winners_by_row,
        company_name=company_name,
    )

    user_email_key = (expected_email or opener_email).lower()

    # An email is a "team member" if it appears in ANY row's email list (after comma-split).
    team_emails = set()
    for m in rfp_team:
        for e in _parse_emails(m.get("email", "")):
            team_emails.add(e)

    team_row_ids = {
        m.get("record_id") for m in rfp_team
        if m.get("record_id") and m.get("product") and m["product"] != "All"
    }
    responded_rows_count = len(set(winners_by_row.keys()) & team_row_ids)

    is_team_member = user_email_key in team_emails

    print(f"🔄 Refresh: rfp={rfp_id}, user={user_email_key}, in_team={is_team_member}, "
          f"rows={responded_rows_count}/{len(team_row_ids)}")

    # If products not in the refresh body, look them up from team rows where the user is an alternate
    if not products:
        products = [
            m["product"] for m in rfp_team
            if user_email_key in _parse_emails(m.get("email", ""))
        ]

    # Step 6: Build and return the updated card
    card = _build_refresh_card(
        rfp_id=rfp_id,
        company_name=company_name,
        products=products,
        name=name,
        email=expected_email or opener_email,
        winners_by_row=winners_by_row,
        uploaded_products_global=uploaded_products_global,
        responded_count=responded_rows_count,
        total_count=len(team_row_ids),
        callback_url=get_setting("ACTIONABLE_CARD_CALLBACK_URL", ""),
        team_table=rfp_team,
        is_team_member=is_team_member,
    )

    return JSONResponse(
        content=card,
        status_code=200,
        headers={"CARD-UPDATE-IN-BODY": "true"},
    )


@router.post("/decline")
async def decline_rfp_from_card(request: Request):
    """
    Receive a Decline action from the consolidated Adaptive Card email.
    Verifies the bearer token, then triggers the RFP decline automation.
    Returns an updated card showing that the decline has been initiated.
    """
    import threading

    # Step 1: Verify the bearer token from Microsoft
    auth_header = request.headers.get("Authorization", "")
    claims = _verify_actionable_message_token(auth_header)
    # Entra token: email is in preferred_username/upn — `sub` is an opaque id.
    user_email = claims.get("preferred_username") or claims.get("upn") or claims.get("email") or "unknown"

    # Step 2: Parse the JSON body
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    rfp_id = body.get("rfp_id", "")
    company_name = body.get("company_name", "")

    if not rfp_id:
        raise HTTPException(status_code=400, detail="rfp_id is required")

    print(f"🔴 Decline requested by {user_email} for RFP: {rfp_id} ({company_name})")

    # Step 3: Trigger decline automation in background thread
    def _run_decline():
        import asyncio
        from automation_logic import run_automation_decline
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(run_automation_decline(rfp_id, company_name or None))
        except Exception as e:
            print(f"❌ Decline automation failed for {rfp_id}: {e}")
        finally:
            loop.close()

    thread = threading.Thread(target=_run_decline, daemon=True)
    thread.start()

    # Step 4: Return updated card confirming decline initiated
    card = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.0",
        "body": [
            {"type": "TextBlock", "text": "Dear Team,", "wrap": True},
            {"type": "TextBlock", "text": f"RFP **{rfp_id}** decline has been initiated by {user_email}.",
             "wrap": True, "spacing": "Small", "weight": "Bolder", "color": "Attention"},
            {"type": "TextBlock", "text": "The automation is running in the background. You will receive a confirmation email once the decline is complete.",
             "wrap": True, "spacing": "Small", "isSubtle": True},
            {"type": "TextBlock", "text": "Best Regards,\nAutomation System",
             "wrap": True, "spacing": "Medium", "separator": True},
        ],
        "padding": "None",
    }

    return JSONResponse(
        content=card,
        status_code=200,
        headers={"CARD-UPDATE-IN-BODY": "true"},
    )


@router.get("/responses/{rfp_id}")
async def get_rfp_responses(rfp_id: str):
    """
    Get all team responses for a specific RFP.
    Used by the dashboard to show response status.
    """
    all_responses = _get_all_responses_for_rfp(rfp_id)

    # Build response map: email -> response data (dynamic fields)
    response_map = {}
    for r in all_responses:
        email = r.get("cr673_email", "").lower()
        # Parse dynamic response_data JSON; fallback to legacy fields
        resp_entry = {
            "name": r.get("cr673_name", ""),
            "product": r.get("cr673_product", ""),
            "submitted_at": r.get("cr673_submitted_at", ""),
        }
        raw_json = r.get("cr673_response_data") or ""
        if raw_json:
            try:
                resp_entry.update(json.loads(raw_json))
            except Exception:
                pass
        # Fallback: legacy results/remarks
        if "results" not in resp_entry:
            resp_entry["results"] = r.get("cr673_results", "")
        if "remarks" not in resp_entry:
            resp_entry["remarks"] = r.get("cr673_remarks", "")
        response_map[email] = resp_entry

    # Build full team status with dynamic column values
    all_columns = get_all_columns()
    rfp_team = get_all_rfp_team_for_emails()
    team_status = []
    for member in rfp_team:
        email = member.get("email", "").lower()
        resp = response_map.get(email)
        entry = {
            "email": email,
            "responded": resp is not None,
            "submitted_at": resp["submitted_at"] if resp else "",
        }
        # Include all column values dynamically
        for col in all_columns:
            key = col["column_key"]
            if resp:
                entry[key] = resp.get(key, member.get(key, ""))
            else:
                entry[key] = member.get(key, "")
        team_status.append(entry)

    # Row-level summary (first-response-wins within each team-table row).
    # Each row is a responsibility unit. Two rows for the same product = two
    # separate responsibilities — both must be answered.
    winners_by_row = _first_response_per_row(all_responses, rfp_team)
    team_row_ids = {
        m.get("record_id") for m in rfp_team
        if m.get("record_id") and m.get("product") and m["product"] != "All"
    }
    rows_responded = sorted(set(winners_by_row.keys()) & team_row_ids)
    rows_pending_ids = team_row_ids - set(rows_responded)
    row_lookup = {m["record_id"]: m for m in rfp_team if m.get("record_id")}
    rows_pending = sorted(
        (
            {"product": row_lookup[rid].get("product", ""),
             "name": row_lookup[rid].get("name", ""),
             "email": row_lookup[rid].get("email", "")}
            for rid in rows_pending_ids if rid in row_lookup
        ),
        key=lambda x: (x["product"], x["name"]),
    )

    return JSONResponse(content={
        "ok": True,
        "rfp_id": rfp_id,
        "total_members": len(rfp_team),
        "responses_received": len(response_map),
        "team_status": team_status,
        "responsibilities_total": len(team_row_ids),
        "responsibilities_responded": len(rows_responded),
        "responsibilities_pending": rows_pending,
    })
