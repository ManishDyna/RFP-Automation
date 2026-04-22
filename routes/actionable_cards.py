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
)
from services.system_settings_service import get_setting
from services.master_data_service import get_all_rfp_team_for_emails
from services.rfp_team_columns_service import get_all_columns, get_input_columns
from helpers.email_helper import _build_input_widget_indexed

router = APIRouter(prefix="/api/actionable-card", tags=["Actionable Cards"])

# Dataverse client for this module
_DATAVERSE = DataverseClient(
    tenant_id=TENANT_ID,
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    resource_url=RESOURCE_URL,
)

# ── Actionable Message Token Verification ──
# Outlook sends tokens from substrate.office.com (not Entra ID)
# The JWKS keys are fetched from the substrate OpenID configuration
_SUBSTRATE_OPENID_URL = "https://substrate.office.com/sts/common/.well-known/openid-configuration"
_JWKS_CLIENT = None


def _get_jwks_client():
    global _JWKS_CLIENT
    if _JWKS_CLIENT is None:
        config = requests.get(_SUBSTRATE_OPENID_URL, timeout=10).json()
        jwks_uri = config["jwks_uri"]
        _JWKS_CLIENT = jwt.PyJWKClient(jwks_uri)
    return _JWKS_CLIENT


def _verify_actionable_message_token(auth_header: str) -> dict:
    """
    Verify the bearer token sent by Outlook with Action.Http submissions.
    Token comes from substrate.office.com with:
      - iss: https://substrate.office.com/sts/
      - aud: the callback URL
      - sub: the user's email
    """
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = auth_header[len("Bearer "):]

    try:
        jwks_client = _get_jwks_client()
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        decoded = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={
                "verify_exp": True,
                "verify_aud": False,  # Audience is the callback URL, varies per deployment
                "verify_iss": False,  # Issuer is substrate.office.com
            },
        )
        print(f"✅ Token verified. sub={decoded.get('sub')}, aud={decoded.get('aud')}")
        return decoded
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


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


def _build_refresh_card(
    rfp_id: str,
    company_name: str,
    products: list,
    name: str,
    email: str,
    response_lookup: dict,
    user_has_submitted: bool,
    responded_count: int,
    total_count: int,
    callback_url: str,
    team_table: list = None,
) -> dict:
    """
    Build the Adaptive Card JSON for refresh/post-submit display.
    Shows the person's own products with their responses (read-only if submitted,
    editable if not yet submitted), plus a team status summary.
    """
    user_email_key = email.lower()
    refresh_url = callback_url + "/refresh"

    columns = get_all_columns()
    input_columns = get_input_columns()

    if team_table is None:
        team_table = get_all_rfp_team_for_emails()

    # Get this user's response data (per-product)
    user_resp = response_lookup.get(user_email_key, {})
    user_product_responses = {}  # product → {results: ..., remarks: ...}
    if "products" in user_resp and isinstance(user_resp["products"], list):
        for p_resp in user_resp["products"]:
            user_product_responses[p_resp.get("product", "")] = p_resp
    elif user_resp:
        # Legacy: single response applies to all products
        for p in products:
            user_product_responses[p] = user_resp

    # --- Build list of all team member rows (one row per person+product) ---
    all_member_rows = [
        {"product": m["product"], "email": m.get("email", ""), "name": m.get("name", "")}
        for m in team_table
        if m.get("product") and m["product"] != "All"
    ]

    # --- Build table header (showing all products) ---
    header_cols = []
    for col in columns:
        if col["column_key"] == "email":
            continue
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
    editable_idx = 0
    for member_row in all_member_rows:
        row_product = member_row["product"]
        row_email = member_row["email"]
        row_name = member_row["name"]
        # This row is editable if product belongs to current person AND email matches
        is_own = row_product in products and row_email.lower() == user_email_key

        # Find response for this row's person+product
        product_response = {}
        if is_own:
            product_response = user_product_responses.get(row_product, {})
        else:
            # Look up this specific person's response
            other_resp = response_lookup.get(row_email.lower(), {})
            if other_resp:
                if "products" in other_resp and isinstance(other_resp["products"], list):
                    for pr in other_resp["products"]:
                        if pr.get("product") == row_product:
                            product_response = pr
                            break
                elif other_resp.get("results") or other_resp.get("remarks"):
                    product_response = other_resp

        row_columns = []
        for col in columns:
            key = col["column_key"]
            if key == "email":
                continue
            if col.get("column_category") == "input":
                if is_own and not user_has_submitted:
                    # Editable for own unsubmitted products
                    item = _build_input_widget_indexed(col, editable_idx)
                else:
                    # Show actual response or "Pending"
                    value = product_response.get(key, "") or "Pending"
                    color = "Good" if value != "Pending" else "Accent"
                    item = {"type": "TextBlock", "text": value,
                            "color": color, "wrap": True, "size": "Small"}
            else:
                display_name = name if is_own else row_name or row_email
                value = row_product if key == "product" else (display_name if key == "name" else "")
                item = {"type": "TextBlock", "text": value, "wrap": True,
                        "size": "Small", "weight": "Bolder"}
            row_columns.append({
                "type": "Column", "width": 1, "padding": "None",
                "items": [item],
            })
        if is_own and not user_has_submitted:
            editable_idx += 1
        data_rows.append({
            "type": "ColumnSet",
            "separator": True,
            "padding": "None",
            "columns": row_columns,
        })

    # Refresh payload
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

    status_text = f"Team responses: {responded_count}/{total_count} received."

    actions = [refresh_action]
    if not user_has_submitted and products:
        submit_body = {
            "rfp_id": rfp_id,
            "products": products,
            "name": name,
            "email": email,
            "company_name": company_name,
        }
        for idx in range(len(products)):
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

    products_text = ", ".join(f"**{p}**" for p in products)
    if not products:
        instruction_text = "You can refresh to see the team's response status."
    elif user_has_submitted:
        instruction_text = "Your response has been submitted. You can refresh to see team status."
    else:
        instruction_text = "Please fill in your Results and Remarks for each product below."
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
    submitter_email = claims.get("sub") or claims.get("preferred_username") or claims.get("upn", "unknown")

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

    # Step 4: Extract per-product responses from indexed fields
    input_cols = get_input_columns()
    per_product_responses = []
    for idx, product in enumerate(products):
        product_data = {}
        for col in input_cols:
            key = col["column_key"]
            # Try indexed field first (results_0, remarks_0), then fallback to non-indexed
            indexed_key = f"{key}_{idx}"
            product_data[key] = body.get(indexed_key, "") or body.get(key, "")
        per_product_responses.append({
            "product": product,
            **product_data,
        })

    # Build combined response_data JSON with all product responses
    response_data = {"products": per_product_responses}

    # Backward compat: first product's results/remarks for legacy fields
    first_results = per_product_responses[0].get("results", "") if per_product_responses else ""
    first_remarks = per_product_responses[0].get("remarks", "") if per_product_responses else ""

    # Step 5: Upsert to Dataverse (one row per email per RFP)
    row_data = {
        "cr673_rfp_id": rfp_id,
        "cr673_product": ", ".join(products),
        "cr673_name": name,
        "cr673_email": expected_email or submitter_email,
        "cr673_results": first_results,
        "cr673_remarks": first_remarks,
        "cr673_response_data": json.dumps(response_data),
        "cr673_submitted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "cr673_company_name": company_name,
    }

    try:
        existing = _DATAVERSE.query_rows(
            get_setting("RFP_RESPONSE_TABLE_API", ""),
            filter_expr=f"cr673_rfp_id eq '{rfp_id}' and cr673_email eq '{expected_email or submitter_email}'",
            top=1,
            table_logical_name=get_setting("RFP_RESPONSE_TABLE_LOGICAL", ""),
            use_display_names=True,
        )

        if existing and "value" in existing and len(existing["value"]) > 0:
            existing_row = existing["value"][0]
            pk_logical = f"{get_setting('RFP_RESPONSE_TABLE_LOGICAL', '')}id"
            try:
                colmap = _DATAVERSE.get_column_mapping(get_setting("RFP_RESPONSE_TABLE_LOGICAL", ""))
                logical_to_display = {v: k for k, v in colmap.items()}
            except Exception:
                logical_to_display = {}
            pk_display = logical_to_display.get(pk_logical)
            record_id = (
                (existing_row.get(pk_display) if pk_display else None)
                or existing_row.get(pk_logical)
            )
            if record_id:
                _DATAVERSE.update_row(
                    get_setting("RFP_RESPONSE_TABLE_API", ""),
                    record_id,
                    row_data,
                    table_logical_name=get_setting("RFP_RESPONSE_TABLE_LOGICAL", ""),
                    use_display_names=True,
                )
        else:
            _DATAVERSE.insert_row(
                get_setting("RFP_RESPONSE_TABLE_API", ""),
                row_data,
                table_logical_name=get_setting("RFP_RESPONSE_TABLE_LOGICAL", ""),
                use_display_names=True,
            )
    except Exception as e:
        print(f"❌ Failed to save response to Dataverse: {e}")
        raise HTTPException(status_code=500, detail="Failed to save response")

    # Step 5: Check if all team members have responded
    rfp_team = get_all_rfp_team_for_emails()
    all_responses = _get_all_responses_for_rfp(rfp_id)
    responded_emails = {r.get("cr673_email", "").lower() for r in all_responses}
    team_emails = {m.get("email", "").lower() for m in rfp_team if m.get("email")}
    all_responded = team_emails.issubset(responded_emails)

    # Step 5a: Update response metrics on RFP activity log
    try:
        RFP_ACTIVITY_LOG_TABLE_API = get_setting("RFP_ACTIVITY_LOG_TABLE_API", "cr673_bahra_rfps_v2s")
        RFP_ACTIVITY_LOG_TABLE_LOGICAL = get_setting("RFP_ACTIVITY_LOG_TABLE_LOGICAL", "cr673_bahra_rfps_v2")

        # Calculate response timestamps
        _resp_timestamps = [
            r.get("cr673_submitted_at", "") for r in all_responses
            if r.get("cr673_submitted_at")
        ]
        _first_response = min(_resp_timestamps) if _resp_timestamps else ""
        _all_responses_at = max(_resp_timestamps) if all_responded and _resp_timestamps else ""

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
                _update = {
                    "response_count": str(len(responded_emails & team_emails)),
                    "first_response_at": _first_response,
                }
                if _all_responses_at:
                    _update["all_responses_at"] = _all_responses_at
                _DATAVERSE.update_row(
                    RFP_ACTIVITY_LOG_TABLE_API,
                    _act_id,
                    _update,
                    table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL,
                    use_display_names=True,
                )
    except Exception as e:
        print(f"⚠ Could not update response metrics on activity log: {e}")

    if all_responded and len(team_emails) > 0:
        # All team members have responded - send consolidated email with attachments + Decline button
        try:
            from helpers.email_helper import send_consolidated_response_email
            RFP_ACTIVITY_LOG_TABLE_API = get_setting("RFP_ACTIVITY_LOG_TABLE_API", "cr673_bahra_rfps_v2s")
            RFP_ACTIVITY_LOG_TABLE_LOGICAL = get_setting("RFP_ACTIVITY_LOG_TABLE_LOGICAL", "cr673_bahra_rfps_v2")

            responses_for_email = []
            for r in all_responses:
                r_email = r.get("cr673_email", "")
                r_name = r.get("cr673_name", "")
                # Parse response_data which now contains per-product responses
                raw_json = r.get("cr673_response_data") or r.get("response_data", "")
                parsed = {}
                if raw_json:
                    try:
                        parsed = json.loads(raw_json)
                    except (json.JSONDecodeError, TypeError):
                        parsed = {}

                # New format: {"products": [{"product": "Cables", "results": "Yes", ...}, ...]}
                if "products" in parsed and isinstance(parsed["products"], list):
                    for p_resp in parsed["products"]:
                        responses_for_email.append({
                            "product": p_resp.get("product", ""),
                            "name": r_name,
                            "email": r_email,
                            **{k: v for k, v in p_resp.items() if k != "product"},
                        })
                else:
                    # Legacy single-product format
                    resp_item = {
                        "product": r.get("cr673_product", ""),
                        "name": r_name,
                        "email": r_email,
                    }
                    if parsed:
                        resp_item.update(parsed)
                    else:
                        resp_item["results"] = r.get("cr673_results", "")
                        resp_item["remarks"] = r.get("cr673_remarks", "")
                    responses_for_email.append(resp_item)

            # Look up RFP end date from Dataverse activity log
            rfp_end_date = "-"
            try:
                activity = _DATAVERSE.query_rows(
                    RFP_ACTIVITY_LOG_TABLE_API,
                    filter_expr=f"RFP_ID eq '{rfp_id}'",
                    top=1,
                    table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL,
                    use_display_names=True,
                )
                if activity and "value" in activity and len(activity["value"]) > 0:
                    row = activity["value"][0]
                    rfp_end_date = row.get("RFP_End_Date") or row.get("RFP End Date") or row.get("rfp_end_date") or "-"
                    print(f"📅 End date lookup for {rfp_id}: '{rfp_end_date}' (available keys: {list(row.keys())[:10]})")
                else:
                    print(f"⚠ No activity log record found for {rfp_id}")
            except Exception as e:
                print(f"⚠ End date lookup failed for {rfp_id}: {e}")

            send_consolidated_response_email(rfp_id, responses_for_email, company_name, rfp_end_date)
        except Exception as e:
            print(f"⚠ Could not send consolidated email: {e}")

    # Step 6: Return updated card using shared builder
    response_lookup = {}
    for r in all_responses:
        r_email = r.get("cr673_email", "").lower()
        # Try new JSON field first, fallback to legacy fields
        raw_json = r.get("cr673_response_data") or r.get("response_data", "")
        if raw_json:
            try:
                fields = json.loads(raw_json)
            except (json.JSONDecodeError, TypeError):
                fields = {"results": r.get("cr673_results", ""), "remarks": r.get("cr673_remarks", "")}
        else:
            fields = {"results": r.get("cr673_results", ""), "remarks": r.get("cr673_remarks", "")}
        response_lookup[r_email] = fields
    # Ensure the current submission is in the lookup (in case query didn't return it yet)
    submitter_key = (expected_email or submitter_email).lower()
    if submitter_key not in response_lookup:
        response_lookup[submitter_key] = response_data

    refresh_card = _build_refresh_card(
        rfp_id=rfp_id,
        company_name=company_name,
        products=products,
        name=name,
        email=expected_email or submitter_email,
        response_lookup=response_lookup,
        user_has_submitted=True,
        responded_count=len(responded_emails & team_emails),
        total_count=len(team_emails),
        callback_url=get_setting("ACTIONABLE_CARD_CALLBACK_URL", ""),
        team_table=rfp_team,
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
    opener_email = claims.get("sub") or claims.get("preferred_username") or claims.get("upn", "unknown")

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

    # Step 3: Query Dataverse for latest responses
    all_responses = _get_all_responses_for_rfp(rfp_id)

    # Step 4: Build response lookup (supports new multi-product format)
    response_lookup = {}
    for r in all_responses:
        r_email = r.get("cr673_email", "").lower()
        raw_json = r.get("cr673_response_data") or r.get("response_data", "")
        if raw_json:
            try:
                fields = json.loads(raw_json)
            except (json.JSONDecodeError, TypeError):
                fields = {"results": r.get("cr673_results", ""), "remarks": r.get("cr673_remarks", "")}
        else:
            fields = {"results": r.get("cr673_results", ""), "remarks": r.get("cr673_remarks", "")}
        response_lookup[r_email] = fields

    # Step 5: Check if current user has already submitted
    user_email_key = (expected_email or opener_email).lower()
    user_has_submitted = user_email_key in response_lookup

    rfp_team = get_all_rfp_team_for_emails()
    team_emails = {m.get("email", "").lower() for m in rfp_team if m.get("email")}
    responded_count = len(set(response_lookup.keys()) & team_emails)

    print(f"🔄 Refresh: rfp={rfp_id}, user={user_email_key}, submitted={user_has_submitted}, {responded_count}/{len(team_emails)}")

    # If products not in the refresh body, look them up from team table
    if not products:
        products = [m["product"] for m in rfp_team if m.get("email", "").lower() == user_email_key]

    # Step 6: Build and return the updated card
    card = _build_refresh_card(
        rfp_id=rfp_id,
        company_name=company_name,
        products=products,
        name=name,
        email=expected_email or opener_email,
        response_lookup=response_lookup,
        user_has_submitted=user_has_submitted,
        responded_count=responded_count,
        total_count=len(team_emails),
        callback_url=get_setting("ACTIONABLE_CARD_CALLBACK_URL", ""),
        team_table=rfp_team,
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
    user_email = claims.get("sub") or claims.get("preferred_username") or claims.get("upn", "unknown")

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

    return JSONResponse(content={
        "ok": True,
        "rfp_id": rfp_id,
        "total_members": len(rfp_team),
        "responses_received": len(response_map),
        "team_status": team_status,
    })
