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
    ACTIONABLE_CARD_ORIGINATOR_ID,
    ACTIONABLE_CARD_CALLBACK_URL,
    RFP_RESPONSE_TABLE_API,
    RFP_RESPONSE_TABLE_LOGICAL,
    RFP_TEAM_TABLE,
)

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
            RFP_RESPONSE_TABLE_API,
            filter_expr=f"cr673_rfp_id eq '{rfp_id}'",
            top=50,
            table_logical_name=RFP_RESPONSE_TABLE_LOGICAL,
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
    product: str,
    name: str,
    email: str,
    response_lookup: dict,
    user_has_submitted: bool,
    responded_count: int,
    total_count: int,
    callback_url: str,
) -> dict:
    """
    Build the Adaptive Card JSON for refresh/post-submit display.
    Two modes:
    - Not submitted: shows live team table + input fields + Submit + Refresh buttons
    - Already submitted: shows live team table (read-only) + Refresh button
    """
    user_email_key = email.lower()
    refresh_url = callback_url + "/refresh"

    # Table header row
    header_row = {
        "type": "ColumnSet",
        "style": "emphasis",
        "padding": "None",
        "columns": [
            {"type": "Column", "width": "stretch", "padding": "None", "items": [{"type": "TextBlock", "text": "Products", "weight": "Bolder", "horizontalAlignment": "Center"}]},
            {"type": "Column", "width": "stretch", "padding": "None", "items": [{"type": "TextBlock", "text": "Name", "weight": "Bolder", "horizontalAlignment": "Center"}]},
            {"type": "Column", "width": "stretch", "padding": "None", "items": [{"type": "TextBlock", "text": "Results", "weight": "Bolder", "horizontalAlignment": "Center"}]},
            {"type": "Column", "width": "stretch", "padding": "None", "items": [{"type": "TextBlock", "text": "Remarks", "weight": "Bolder", "horizontalAlignment": "Center"}]},
        ],
    }

    # Data rows with actual response data
    data_rows = []
    for member in RFP_TEAM_TABLE:
        m_email = member.get("email", "").lower()
        is_current = m_email == user_email_key
        resp = response_lookup.get(m_email)
        has_responded = resp is not None

        # For current user who hasn't submitted: inline Input.Text fields
        if is_current and not user_has_submitted:
            results_item = {"type": "Input.Text", "id": "results", "placeholder": "Enter results..."}
            remarks_item = {"type": "Input.Text", "id": "remarks", "placeholder": "Enter remarks..."}
        else:
            results_text = resp["results"] if has_responded else "Pending"
            remarks_text = resp["remarks"] if has_responded else "Pending"
            results_color = "Good" if has_responded else "Warning"
            remarks_color = "Good" if has_responded else "Warning"
            results_item = {"type": "TextBlock", "text": results_text, "horizontalAlignment": "Center", "color": results_color}
            remarks_item = {"type": "TextBlock", "text": remarks_text or "-", "horizontalAlignment": "Center", "color": remarks_color, "wrap": True}

        row = {
            "type": "ColumnSet",
            "separator": True,
            "padding": "None",
            **({"style": "accent"} if is_current else {}),
            "columns": [
                {
                    "type": "Column", "width": "stretch", "padding": "None",
                    "items": [{"type": "TextBlock", "text": member["product"], "horizontalAlignment": "Center",
                               **({"weight": "Bolder"} if is_current else {})}],
                },
                {
                    "type": "Column", "width": "stretch", "padding": "None",
                    "items": [{"type": "TextBlock", "text": f"{member['name']} (You)" if is_current else member["name"],
                               "horizontalAlignment": "Center",
                               **({"weight": "Bolder"} if is_current else {})}],
                },
                {
                    "type": "Column", "width": "stretch", "padding": "None",
                    "items": [results_item],
                },
                {
                    "type": "Column", "width": "stretch", "padding": "None",
                    "items": [remarks_item],
                },
            ],
        }
        data_rows.append(row)

    # Common refresh payload (for autoInvokeAction and manual Refresh button)
    refresh_body = json.dumps({
        "rfp_id": rfp_id,
        "product": product,
        "name": name,
        "email": email,
        "company_name": company_name,
    })

    # Manual Refresh button
    refresh_action = {
        "type": "Action.Http",
        "title": "Refresh Status",
        "method": "POST",
        "url": refresh_url,
        "headers": [{"name": "Content-Type", "value": "application/json"}],
        "body": refresh_body,
    }

    status_text = f"Team responses: {responded_count}/{total_count} received."

    # Actions: Submit + Refresh if not yet submitted, only Refresh if already submitted
    actions = [refresh_action]
    if not user_has_submitted:
        submit_action = {
            "type": "Action.Http",
            "title": "Submit Response",
            "method": "POST",
            "url": callback_url,
            "headers": [{"name": "Content-Type", "value": "application/json"}],
            "body": json.dumps({
                "rfp_id": rfp_id,
                "product": product,
                "name": name,
                "email": email,
                "company_name": company_name,
                "results": "{{results.value}}",
                "remarks": "{{remarks.value}}",
            }),
            "style": "positive",
            "isPrimary": True,
        }
        actions = [submit_action, refresh_action]

    # Same card layout regardless of submission state
    card = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.0",
        "body": [
            {"type": "TextBlock", "text": f"Dear {name},",
             "wrap": True},
            {"type": "TextBlock", "text": f"Kindly advise us regarding the attached RFP file for **{product}**.",
             "wrap": True, "spacing": "Small"},
            {"type": "TextBlock", "text": "Please fill in your Results and Remarks using the interactive form below.",
             "wrap": True, "spacing": "Small"},
            {"type": "TextBlock", "text": "Team Assignment", "weight": "Bolder",
             "separator": True, "spacing": "Medium"},
            header_row,
            *data_rows,
            {"type": "TextBlock", "text": status_text,
             "isSubtle": True, "wrap": True, "spacing": "Medium"},
            {"type": "TextBlock", "text": "Best Regards,\nAutomation System",
             "wrap": True, "spacing": "Medium", "separator": True},
        ],
        "actions": actions,
        "padding": "None",
    }

    return card


@router.post("/response")
async def receive_card_response(request: Request):
    """
    Receive an Adaptive Card form submission from Outlook.
    Verifies the bearer token, extracts the response, and saves to Dataverse.
    When all team members have responded, sends a consolidated email.
    """
    # Step 1: Verify the bearer token from Microsoft
    auth_header = request.headers.get("Authorization", "")
    claims = _verify_actionable_message_token(auth_header)
    # Substrate token has the user email in 'sub' claim
    submitter_email = claims.get("sub") or claims.get("preferred_username") or claims.get("upn", "unknown")

    # Step 2: Parse the JSON body
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    rfp_id = body.get("rfp_id", "")
    product = body.get("product", "")
    name = body.get("name", "")
    expected_email = body.get("email", "")
    company_name = body.get("company_name", "")
    results = body.get("results", "")
    remarks = body.get("remarks", "")

    # Step 3: Verify that the submitter matches the expected email
    if expected_email and submitter_email.lower() != expected_email.lower():
        raise HTTPException(
            status_code=403,
            detail=f"Token email ({submitter_email}) does not match expected ({expected_email})",
        )

    # Step 4: Check for existing response (upsert logic)
    row_data = {
        "cr673_rfp_id": rfp_id,
        "cr673_product": product,
        "cr673_name": name,
        "cr673_email": expected_email or submitter_email,
        "cr673_results": results,
        "cr673_remarks": remarks,
        "cr673_submitted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "cr673_company_name": company_name,
    }

    try:
        existing = _DATAVERSE.query_rows(
            RFP_RESPONSE_TABLE_API,
            filter_expr=f"cr673_rfp_id eq '{rfp_id}' and cr673_email eq '{expected_email or submitter_email}'",
            top=1,
            table_logical_name=RFP_RESPONSE_TABLE_LOGICAL,
            use_display_names=True,
        )

        if existing and "value" in existing and len(existing["value"]) > 0:
            # Update existing response
            existing_row = existing["value"][0]
            pk_logical = f"{RFP_RESPONSE_TABLE_LOGICAL}id"
            try:
                colmap = _DATAVERSE.get_column_mapping(RFP_RESPONSE_TABLE_LOGICAL)
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
                    RFP_RESPONSE_TABLE_API,
                    record_id,
                    row_data,
                    table_logical_name=RFP_RESPONSE_TABLE_LOGICAL,
                    use_display_names=True,
                )
        else:
            # Insert new response
            _DATAVERSE.insert_row(
                RFP_RESPONSE_TABLE_API,
                row_data,
                table_logical_name=RFP_RESPONSE_TABLE_LOGICAL,
                use_display_names=True,
            )
    except Exception as e:
        print(f"❌ Failed to save response to Dataverse: {e}")
        raise HTTPException(status_code=500, detail="Failed to save response")

    # Step 5: Check if all team members have responded
    all_responses = _get_all_responses_for_rfp(rfp_id)
    responded_emails = {r.get("cr673_email", "").lower() for r in all_responses}
    team_emails = {m.get("email", "").lower() for m in RFP_TEAM_TABLE if m.get("email")}
    all_responded = team_emails.issubset(responded_emails)

    if all_responded and len(team_emails) > 0:
        # All team members have responded - send consolidated email with attachments + Decline button
        try:
            from helpers.email_helper import send_consolidated_response_email
            from config.config import RFP_ACTIVITY_LOG_TABLE_API, RFP_ACTIVITY_LOG_TABLE_LOGICAL

            responses_for_email = [
                {
                    "product": r.get("cr673_product", ""),
                    "name": r.get("cr673_name", ""),
                    "results": r.get("cr673_results", ""),
                    "remarks": r.get("cr673_remarks", ""),
                }
                for r in all_responses
            ]

            # Look up RFP end date from Dataverse activity log
            rfp_end_date = "-"
            try:
                activity = _DATAVERSE.query_rows(
                    RFP_ACTIVITY_LOG_TABLE_API,
                    filter_expr=f"cr673_name eq '{rfp_id}'",
                    top=1,
                    table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL,
                    use_display_names=True,
                )
                if activity and "value" in activity and len(activity["value"]) > 0:
                    rfp_end_date = activity["value"][0].get("RFP_End_Date", "-") or "-"
            except Exception:
                pass

            send_consolidated_response_email(rfp_id, responses_for_email, company_name, rfp_end_date)
        except Exception as e:
            print(f"⚠ Could not send consolidated email: {e}")

    # Step 6: Return updated card using shared builder
    response_lookup = {}
    for r in all_responses:
        r_email = r.get("cr673_email", "").lower()
        response_lookup[r_email] = {
            "results": r.get("cr673_results", ""),
            "remarks": r.get("cr673_remarks", ""),
        }
    # Ensure the current submission is in the lookup (in case query didn't return it yet)
    submitter_key = (expected_email or submitter_email).lower()
    if submitter_key not in response_lookup:
        response_lookup[submitter_key] = {"results": results, "remarks": remarks}

    refresh_card = _build_refresh_card(
        rfp_id=rfp_id,
        company_name=company_name,
        product=product,
        name=name,
        email=expected_email or submitter_email,
        response_lookup=response_lookup,
        user_has_submitted=True,
        responded_count=len(responded_emails & team_emails),
        total_count=len(team_emails),
        callback_url=ACTIONABLE_CARD_CALLBACK_URL,
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
    product = body.get("product", "")
    name = body.get("name", "")
    expected_email = body.get("email", "")
    company_name = body.get("company_name", "")

    # Step 3: Query Dataverse for latest responses
    all_responses = _get_all_responses_for_rfp(rfp_id)

    # Step 4: Build response lookup
    response_lookup = {}
    for r in all_responses:
        r_email = r.get("cr673_email", "").lower()
        response_lookup[r_email] = {
            "results": r.get("cr673_results", ""),
            "remarks": r.get("cr673_remarks", ""),
        }

    # Step 5: Check if current user has already submitted
    user_email_key = (expected_email or opener_email).lower()
    user_has_submitted = user_email_key in response_lookup

    team_emails = {m.get("email", "").lower() for m in RFP_TEAM_TABLE if m.get("email")}
    responded_count = len(set(response_lookup.keys()) & team_emails)

    print(f"🔄 Refresh: rfp={rfp_id}, user={user_email_key}, submitted={user_has_submitted}, {responded_count}/{len(team_emails)}")

    # Step 6: Build and return the updated card
    card = _build_refresh_card(
        rfp_id=rfp_id,
        company_name=company_name,
        product=product,
        name=name,
        email=expected_email or opener_email,
        response_lookup=response_lookup,
        user_has_submitted=user_has_submitted,
        responded_count=responded_count,
        total_count=len(team_emails),
        callback_url=ACTIONABLE_CARD_CALLBACK_URL,
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

    # Build response map: email -> response data
    response_map = {}
    for r in all_responses:
        email = r.get("cr673_email", "").lower()
        response_map[email] = {
            "name": r.get("cr673_name", ""),
            "product": r.get("cr673_product", ""),
            "results": r.get("cr673_results", ""),
            "remarks": r.get("cr673_remarks", ""),
            "submitted_at": r.get("cr673_submitted_at", ""),
        }

    # Build full team status
    team_status = []
    for member in RFP_TEAM_TABLE:
        email = member.get("email", "").lower()
        resp = response_map.get(email)
        team_status.append({
            "product": member["product"],
            "name": member["name"],
            "email": email,
            "responded": resp is not None,
            "results": resp["results"] if resp else "",
            "remarks": resp["remarks"] if resp else "",
            "submitted_at": resp["submitted_at"] if resp else "",
        })

    return JSONResponse(content={
        "ok": True,
        "rfp_id": rfp_id,
        "total_members": len(RFP_TEAM_TABLE),
        "responses_received": len(response_map),
        "team_status": team_status,
    })
