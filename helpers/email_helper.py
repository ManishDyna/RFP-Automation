from core.common_imports import *

def create_file_names_and_source_files(rfp_titles: list, company_name: str = None) -> dict:
    """
    Create FileNames and SourceFiles lists from a list of RFP titles.

    Args:
        rfp_titles: List of RFP titles like ['SEC RFP-c001983', 'SEC RFP-c89722']
        company_name: Company name for SharePoint path (e.g., 'SABIC')

    Returns:
        dict with keys:
            - "FileNames": List of filenames like ["SEC RFP-c001983.xls", "SEC RFP-c89722.xls"]
            - "SourceFiles": List of SharePoint paths like ["/Shared Documents/RFP-logs/ALLRFPs/CompanyName/SEC RFP-c001983/downloaded-rfp/SEC RFP-c001983.xls", ...]
    """
    from helpers.core_helper import clean_rfp_title, get_sharepoint_rfp_material_path
    from services.system_settings_service import get_setting

    # Use provided company_name or fallback to default
    target_company = company_name or get_setting("COMPANY_NAME", "Saudi Electricity Company")

    file_names = []
    source_files = []

    for rfp_title in rfp_titles:
        # Clean the title to match folder naming
        clean_title = clean_rfp_title(rfp_title)

        # Create filename (add .xls extension)
        filename = f"{clean_title}.xls"
        file_names.append(filename)

        # Create SharePoint path: /Shared Documents/RFP-logs/ALLRFPs/{CompanyName}/{RFP_title}/downloaded-rfp/{filename}
        sp_path = get_sharepoint_rfp_material_path(rfp_title, target_company, filename)
        full_sp_path = f"/Shared Documents/{sp_path}"
        source_files.append(full_sp_path)

    return {
        "FileNames": file_names,
        "SourceFiles": source_files
    }


def _build_input_widget(col_def: dict) -> dict:
    """Build an Adaptive Card input element based on column type."""
    key = col_def["column_key"]
    col_type = col_def.get("column_type", "text")

    if col_type == "dropdown":
        options_raw = col_def.get("dropdown_options", "") or ""
        try:
            options = json.loads(options_raw) if options_raw else []
        except (json.JSONDecodeError, TypeError):
            options = []
        choices = [{"title": opt, "value": opt} for opt in options]
        return {
            "type": "Input.ChoiceSet",
            "id": key,
            "placeholder": f"{col_def.get('column_label', key)}...",
            "choices": choices,
            "style": "compact",
            "height": "stretch",
        }
    elif col_type == "yes_no":
        return {
            "type": "Input.Toggle",
            "id": key,
            "title": col_def.get("column_label", key),
            "valueOn": "Yes",
            "valueOff": "No",
        }
    else:  # text
        return {
            "type": "Input.Text",
            "id": key,
            "placeholder": f"{col_def.get('column_label', key)}...",
        }


def _build_dynamic_html_table(columns: list, team_table: list, response_data: list = None) -> str:
    """
    Build an HTML <table> dynamically from column definitions.
    If response_data is provided, fills input columns with response values.
    Otherwise, input columns are left empty.
    """
    # Header row
    headers = "".join(
        f"<th style='border:1px solid #ccc;padding:6px 10px;'>{col.get('column_label', col['column_key'])}</th>"
        for col in columns
    )

    # Data rows
    data_source = response_data if response_data else team_table
    rows_html = ""
    for item in data_source:
        cells = ""
        for col in columns:
            key = col["column_key"]
            if response_data:
                # Showing filled responses
                value = item.get(key, "") or ""
            elif col.get("column_category") == "display":
                value = item.get(key, "") or ""
            else:
                value = ""  # Input columns are empty in initial email
            cells += f"<td style='border:1px solid #ccc;padding:6px 10px;'>{value}</td>"
        rows_html += f"<tr>{cells}</tr>"

    return f"""<table style='border-collapse:collapse;margin:10px 0;'>
      <tr style='background:#f0f0f0;'>{headers}</tr>
      {rows_html}
    </table>"""


def _build_rfp_notification_html(rfp_titles: list, rfp_end_dates: dict = None) -> tuple:
    """
    Build the standard RFP notification email subject and HTML body
    matching the reference email format:
      - Subject  : RFP title (single) or "New <N> RFP(s) Found" (multiple)
      - Body     : Greeting + Products/Name table + due-date note
    """
    from services.master_data_service import get_all_rfp_team_for_emails
    from services.rfp_team_columns_service import get_all_columns
    RFP_TEAM_TABLE = get_all_rfp_team_for_emails()
    columns = get_all_columns()

    rfp_end_dates = rfp_end_dates or {}

    # Subject
    if len(rfp_titles) == 1:
        subject = rfp_titles[0]
    else:
        subject = f"New {len(rfp_titles)} RFP(s) Received ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})"

    # Dynamic HTML table
    table_html = _build_dynamic_html_table(columns, RFP_TEAM_TABLE)

    # Due-date notes (one per RFP)
    due_date_lines = ""
    for title in rfp_titles:
        end_date = rfp_end_dates.get(title, "-")
        due_date_lines += (
            f"<p style='background-color:#FFFF00;display:inline-block;padding:4px 8px;margin:2px 0;'>"
            f"<b>Note: the due date for <u>{title}</u> is {end_date}</b></p><br>"
        )

    body_html = f"""
    <p>Dear's,</p>
    <p>Kindly advise us regarding to the attached file</p>
    {table_html}
    {due_date_lines}
    <br><p>Best Regards,<br>Automation System</p>
    """

    return subject, body_html


def _build_input_widget_indexed(col_def: dict, index: int) -> dict:
    """Build an Adaptive Card input element with a product-index-suffixed ID.
    E.g., results_0, remarks_1 — so multiple product rows can have unique IDs."""
    key = f"{col_def['column_key']}_{index}"
    col_type = col_def.get("column_type", "text")

    if col_type == "dropdown":
        options_raw = col_def.get("dropdown_options", "") or ""
        try:
            options = json.loads(options_raw) if options_raw else []
        except (json.JSONDecodeError, TypeError):
            options = []
        choices = [{"title": opt, "value": opt} for opt in options]
        return {
            "type": "Input.ChoiceSet",
            "id": key,
            "placeholder": f"{col_def.get('column_label', col_def['column_key'])}...",
            "choices": choices,
            "style": "compact",
            "height": "stretch",
        }
    elif col_type == "yes_no":
        return {
            "type": "Input.Toggle",
            "id": key,
            "title": col_def.get("column_label", col_def["column_key"]),
            "valueOn": "Yes",
            "valueOff": "No",
        }
    else:  # text
        return {
            "type": "Input.Text",
            "id": key,
            "placeholder": f"{col_def.get('column_label', col_def['column_key'])}...",
        }


def _build_adaptive_card_json(rfp_id, products, name, email, due_date, company_name, callback_url, originator_id, matched_line=""):
    """
    Build an Adaptive Card JSON string for one person (grouped by email).
    Shows only the products assigned to this person with editable input fields
    for each product row. One Submit sends all product responses at once.

    Args:
        products: list of product names assigned to this person
                  (e.g., ["Cables", "TBS and BED"])
    """
    from services.rfp_team_columns_service import get_all_columns, get_input_columns
    columns = get_all_columns()
    input_columns = get_input_columns()

    # --- Build ColumnSet-based table (only this person's products) ---
    header_cols = []
    for col in columns:
        if col["column_key"] == "name":
            continue  # Skip name column — email is shown instead
        col_width = 2 if col["column_key"] == "email" else 1
        header_cols.append({
            "type": "Column", "width": col_width, "padding": "None",
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
    for idx, product in enumerate(products):
        row_columns = []
        for col in columns:
            key = col["column_key"]
            if key == "name":
                continue  # Skip name column — email is shown instead
            col_width = 2 if key == "email" else 1
            if col.get("column_category") == "input":
                # Editable widget with indexed ID (results_0, results_1, etc.)
                item = _build_input_widget_indexed(col, idx)
            else:
                # Display column
                value = product if key == "product" else (email if key == "email" else "")
                item = {"type": "TextBlock", "text": value, "wrap": True,
                        "size": "Small", "weight": "Bolder"}
            row_columns.append({
                "type": "Column", "width": col_width, "padding": "None",
                "items": [item],
            })
        data_rows.append({
            "type": "ColumnSet",
            "separator": True,
            "padding": "None",
            "columns": row_columns,
        })

    # --- Footer items (due date, matched note, sign-off) ---
    note_items = [
        {
            "type": "TextBlock",
            "text": f"**Note:** the due date for __{rfp_id}__ is **{due_date}**",
            "wrap": True,
            "color": "Attention",
            "size": "Small",
        },
    ]
    if matched_line:
        note_items.append({
            "type": "TextBlock",
            "text": f"**NOTE:** {matched_line}",
            "wrap": True,
            "spacing": "Small",
            "size": "Small",
        })
    footer_items = [
        {
            "type": "Container",
            "style": "warning",
            "spacing": "Medium",
            "items": note_items,
        },
        {
            "type": "TextBlock",
            "text": "Best Regards,",
            "wrap": True,
            "size": "Small",
            "spacing": "Medium",
            "separator": True,
        },
        {
            "type": "TextBlock",
            "text": "Automation System",
            "wrap": True,
            "size": "Small",
            "spacing": "None",
        },
    ]

    # --- Product list text ---
    products_text = ", ".join(f"**{p}**" for p in products)

    # --- Assemble full card body ---
    body_items = [
        {
            "type": "TextBlock",
            "text": f"Dear {name},",
            "wrap": True,
            "size": "Small",
        },
        {
            "type": "TextBlock",
            "text": f"Kindly advise us regarding the attached RFP file for {products_text}.",
            "wrap": True,
            "size": "Small",
            "spacing": "Small",
        },
        {
            "type": "TextBlock",
            "text": "Please fill in your Results and Remarks for each product below.",
            "wrap": True,
            "size": "Small",
            "spacing": "Small",
        },
        {
            "type": "TextBlock",
            "text": "Your Products",
            "weight": "Bolder",
            "separator": True,
            "spacing": "Medium",
        },
        header_row,
        *data_rows,
        *footer_items,
    ]

    # Build submit body with indexed input bindings per product
    submit_body = {
        "rfp_id": rfp_id,
        "products": products,
        "name": name,
        "email": email,
        "company_name": company_name,
    }
    # Add indexed input column bindings: results_0, remarks_0, results_1, remarks_1, etc.
    for idx in range(len(products)):
        for col in input_columns:
            field_id = f"{col['column_key']}_{idx}"
            submit_body[field_id] = "{{" + field_id + ".value}}"

    card = {
        "originator": originator_id,
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.0",
        "hideOriginalBody": True,
        "padding": "Default",
        "body": body_items,
        "actions": [
            {
                "type": "Action.Http",
                "title": "Submit All Responses",
                "method": "POST",
                "url": callback_url,
                "headers": [
                    {"name": "Content-Type", "value": "application/json"}
                ],
                "body": json.dumps(submit_body),
                "style": "positive",
                "isPrimary": True,
            },
            {
                "type": "Action.Http",
                "title": "Refresh Status",
                "method": "POST",
                "url": callback_url + "/refresh",
                "headers": [
                    {"name": "Content-Type", "value": "application/json"}
                ],
                "body": json.dumps({
                    "rfp_id": rfp_id,
                    "products": products,
                    "name": name,
                    "email": email,
                    "company_name": company_name,
                }),
            },
        ],
    }
    return json.dumps(card)


def _get_graph_mail_token():
    """Get a Graph API access token for sending mail via Mail.Send permission."""
    from services.system_settings_service import get_setting
    import msal

    app = msal.ConfidentialClientApplication(
        get_setting("CLIENT_ID", ""),
        authority=f"https://login.microsoftonline.com/{get_setting('TENANT_ID', '')}",
        client_credential=get_setting("CLIENT_SECRET", ""),
    )
    result = app.acquire_token_for_client(["https://graph.microsoft.com/.default"])
    if "access_token" not in result:
        raise RuntimeError(f"Failed to get Graph API token: {result.get('error_description', result)}")
    return result["access_token"]


def _download_sp_file_bytes(graph_client, sp_path: str) -> bytes:
    """Download a file from SharePoint and return its bytes (for email attachment)."""
    try:
        graph_client.ensure_token()
        url = (
            f"https://graph.microsoft.com/v1.0/sites/{graph_client.site_id}"
            f"/drives/{graph_client.drive_id}/root:/{sp_path}:/content"
        )
        resp = requests.get(url, headers=graph_client.headers)
        if resp.status_code == 200:
            return resp.content
        else:
            print(f"[WARN] SP download returned {resp.status_code} for {sp_path}")
    except Exception as e:
        print(f"[WARN] Could not download SP file {sp_path}: {e}")
    return None


def send_actionable_rfp_emails(
    rfp_id: str,
    company_name: str,
    rfp_end_date: str = "-",
    matched_csv_path: str = None,
    graph_client=None,
):
    """
    Send one personalized Adaptive Card email PER team member via Graph API MIME endpoint.
    Uses raw MIME format to preserve the <script type="application/adaptivecard+json"> tag
    (both Power Automate and Graph API JSON sendMail strip <script> tags).
    """
    import base64
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.base import MIMEBase
    from email import encoders as email_encoders
    from helpers.core_helper import clean_rfp_title
    from services.system_settings_service import get_setting
    _sp_base = get_setting("SP_BASE_FOLDER", "RFP-logs")
    _originator_id = get_setting("ACTIONABLE_CARD_ORIGINATOR_ID", "")
    _callback_url = get_setting("ACTIONABLE_CARD_CALLBACK_URL", "")
    _email_to_new_rfp = get_setting("EMAIL_TO_NEW_RFP", "")
    _email_mode = get_setting("EMAIL_MODE", "dev")
    _dev_email = get_setting("DEV_EMAIL", "KSAGov.tenders@bahra-cables.com")
    # Apply dev mode redirect to EMAIL_TO_NEW_RFP (same logic as master_data_service.py)
    if _email_mode != "prod" and _email_to_new_rfp:
        _email_to_new_rfp = _dev_email
    from services.master_data_service import get_all_rfp_team_for_emails
    RFP_TEAM_TABLE = get_all_rfp_team_for_emails()

    # Include EMAIL_TO_NEW_RFP config recipient if not already in team table
    team_emails_lower = {m.get("email", "").lower() for m in RFP_TEAM_TABLE if m.get("email")}
    if _email_to_new_rfp and _email_to_new_rfp.lower() not in team_emails_lower:
        RFP_TEAM_TABLE = RFP_TEAM_TABLE + [
            {"product": "All", "name": _email_to_new_rfp.split("@")[0].replace(".", " ").title(), "email": _email_to_new_rfp}
        ]
    from core.log_events import log_rfp_activity

    # Get Graph API token for sending mail
    mail_token = _get_graph_mail_token()

    # Build attachment file list (SharePoint paths)
    file_data = create_file_names_and_source_files([rfp_id], company_name)
    sp_file_names = file_data["FileNames"]
    sp_source_files = file_data["SourceFiles"]

    if matched_csv_path and os.path.exists(matched_csv_path):
        matched_file_name = os.path.basename(matched_csv_path)
        sp_file_names.append(matched_file_name)
        clean_title = clean_rfp_title(rfp_id)
        sp_source_files.append(
            f"/Shared Documents/{_sp_base}/ALLRFPs/{company_name}/{clean_title}/{matched_file_name}"
        )

    # Download attachment files from SharePoint (or local)
    attachment_files = []  # list of (filename, bytes)
    for fname, sp_path in zip(sp_file_names, sp_source_files):
        file_bytes = None
        # Try local file first (for matched CSV)
        if matched_csv_path and fname == os.path.basename(matched_csv_path):
            if os.path.exists(matched_csv_path):
                with open(matched_csv_path, "rb") as f:
                    file_bytes = f.read()
        # Try SharePoint download
        if file_bytes is None and graph_client:
            clean_sp_path = sp_path.replace("/Shared Documents/", "", 1)
            file_bytes = _download_sp_file_bytes(graph_client, clean_sp_path)

        if file_bytes:
            attachment_files.append((fname, file_bytes))
        else:
            print(f"[WARN] Could not load attachment: {fname}")

    # Matched materials note (passed into the Adaptive Card)
    if matched_csv_path and os.path.exists(matched_csv_path):
        matched_line = (
            "The matched materials file contains system suggested materials that match Bahra offerings. "
            "It is important that you verify the complete RFP file. Do not rely solely on the matched materials file."
        )
    else:
        matched_line = "No matched materials were found for this RFP."

    # Sender email (must match the registered sender in Actionable Message dashboard)
    sender_email = "D365FOadmin@bahra-electric.com"

    # Group team members by email -> one email per person with all their products
    from collections import OrderedDict
    grouped = OrderedDict()
    for member in RFP_TEAM_TABLE:
        em = member.get("email", "")
        if not em:
            print(f"[WARN] No email configured for {member.get('name', '?')}, skipping")
            continue
        em_lower = em.lower()
        if em_lower not in grouped:
            grouped[em_lower] = {"name": member["name"], "email": em, "products": []}
        grouped[em_lower]["products"].append(member["product"])

    for em_lower, info in grouped.items():
        person_name = info["name"]
        person_email = info["email"]
        person_products = info["products"]

        # Build adaptive card JSON with all products for this person
        card_json = _build_adaptive_card_json(
            rfp_id=rfp_id,
            products=person_products,
            name=person_name,
            email=person_email,
            due_date=rfp_end_date,
            company_name=company_name,
            callback_url=_callback_url,
            originator_id=_originator_id,
            matched_line=matched_line,
        )

        # Build email HTML with embedded adaptive card
        body_html = f"""<html>
<head>
  <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
  <script type="application/adaptivecard+json">
  {card_json}
  </script>
</head>
<body></body>
</html>"""

        # Build raw MIME message (preserves <script> tag — JSON sendMail strips it)
        msg = MIMEMultipart("mixed")
        msg["From"] = sender_email
        msg["To"] = person_email
        msg["Subject"] = rfp_id

        # HTML body with adaptive card
        html_part = MIMEText(body_html, "html", "utf-8")
        msg.attach(html_part)

        # Attach files
        for att_name, att_bytes in attachment_files:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(att_bytes)
            email_encoders.encode_base64(part)
            part.add_header("Content-Disposition", f'attachment; filename="{att_name}"')
            msg.attach(part)

        # Send via Graph API MIME endpoint (raw MIME preserves <script> tags)
        mime_bytes = msg.as_bytes()
        encoded_mime = base64.b64encode(mime_bytes).decode("utf-8")

        try:
            response = requests.post(
                f"https://graph.microsoft.com/v1.0/users/{sender_email}/sendMail",
                headers={
                    "Authorization": f"Bearer {mail_token}",
                    "Content-Type": "text/plain",
                },
                data=encoded_mime,
            )

            if response.status_code == 202:
                print(f"[OK] Actionable email sent for {rfp_id} to {person_name} ({person_email}) - {len(person_products)} products")
            else:
                print(f"[ERROR] Actionable email failed for {rfp_id} to {person_name}: {response.status_code} {response.text}")
        except Exception as e:
            print(f"[ERROR] Failed to send email to {person_name}: {e}")

    # Log activity once per RFP
    log_rfp_activity(
        rfp_id=rfp_id,
        Downloaded_At=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        email_sent_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        email_to=";".join(m.get("email", "") for m in RFP_TEAM_TABLE if m.get("email")),
        email_status="Sent (Actionable)",
        company_name=company_name,
    )

    return rfp_id


def send_consolidated_response_email(rfp_id: str, responses: list, company_name: str = "", rfp_end_date: str = "-"):
    """
    Send a consolidated Adaptive Card email with the filled Results/Remarks table
    + Decline button to all team members. Called when ALL team members have responded.
    Sent via Graph API MIME to preserve the Adaptive Card <script> tag.

    Args:
        rfp_id: The RFP identifier
        responses: List of dicts with keys: product, name, results, remarks
        company_name: Company name for context
        rfp_end_date: Due date string for the RFP
    """
    import base64
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.base import MIMEBase
    from email import encoders as email_encoders
    from helpers.core_helper import clean_rfp_title
    from helpers.sharepoint_helper import GraphClient
    from services.system_settings_service import get_setting
    _email_to_new_rfp = get_setting("EMAIL_TO_NEW_RFP", "")
    _sp_base = get_setting("SP_BASE_FOLDER", "RFP-logs")
    _originator_id = get_setting("ACTIONABLE_CARD_ORIGINATOR_ID", "")
    _callback_url = get_setting("ACTIONABLE_CARD_CALLBACK_URL", "")
    _client_id = get_setting("CLIENT_ID", "")
    _client_secret = get_setting("CLIENT_SECRET", "")
    _tenant_id = get_setting("TENANT_ID", "")
    _sp_hostname = get_setting("SHAREPOINT_HOSTNAME", "bahracables.sharepoint.com")
    _site_path = get_setting("SITE_PATH", "/sites/LiveSite/RFPAutomation")
    _drive_name = get_setting("DRIVE_NAME", "Documents")
    _decline_emails = get_setting("DECLINE_BUTTON_EMAILS", [])
    _email_mode = get_setting("EMAIL_MODE", "dev")
    _dev_email = get_setting("DEV_EMAIL", "KSAGov.tenders@bahra-cables.com")
    if _email_mode != "prod" and _email_to_new_rfp:
        _email_to_new_rfp = _dev_email
    from services.master_data_service import get_all_rfp_team_for_emails
    RFP_TEAM_TABLE = get_all_rfp_team_for_emails()

    # Get Graph API token for sending mail
    mail_token = _get_graph_mail_token()

    # --- Download RFP file + matched CSV from SharePoint ---
    graph_client = GraphClient(
        _client_id, _client_secret, _tenant_id,
        _sp_hostname, _site_path, _drive_name,
    )
    graph_client.auth()
    graph_client.resolve_site_and_drive()

    file_data = create_file_names_and_source_files([rfp_id], company_name)
    sp_file_names = file_data["FileNames"]
    sp_source_files = file_data["SourceFiles"]

    # Also try to find matched materials CSV on SharePoint (filename has timestamp)
    clean_title = clean_rfp_title(rfp_id)
    sp_rfp_folder = f"{_sp_base}/ALLRFPs/{company_name}/{clean_title}"
    matched_csv_name = None
    try:
        folder_files = graph_client.list_files_in_directory(sp_rfp_folder, file_extensions=[".csv"])
        for f in folder_files:
            if f["name"].startswith(f"matched_materials_{clean_title}"):
                matched_csv_name = f["name"]
                sp_file_names.append(matched_csv_name)
                sp_source_files.append(f"/Shared Documents/{sp_rfp_folder}/{matched_csv_name}")
                break
    except Exception as e:
        print(f"[WARN] Could not list SP folder for matched CSV: {e}")

    attachment_files = []  # list of (filename, bytes)
    matched_line = ""
    for fname, sp_path in zip(sp_file_names, sp_source_files):
        clean_sp_path = sp_path.replace("/Shared Documents/", "", 1)
        file_bytes = _download_sp_file_bytes(graph_client, clean_sp_path)
        if file_bytes:
            attachment_files.append((fname, file_bytes))
            if matched_csv_name and fname == matched_csv_name:
                matched_line = (
                    "The matched materials file contains system suggested materials that match Bahra offerings. "
                    "It is important that you verify the complete RFP file. Do not rely solely on the matched materials file."
                )
        else:
            if matched_csv_name and fname == matched_csv_name:
                matched_line = "No matched materials were found for this RFP."
            else:
                print(f"[WARN] Could not load attachment: {fname}")

    if not matched_csv_name:
        matched_line = "No matched materials were found for this RFP."

    # --- Build Adaptive Card with filled response table + Decline button ---
    from services.rfp_team_columns_service import get_all_columns as _get_all_cols
    columns = _get_all_cols()

    # --- Build ColumnSet-based table ---
    header_cols = []
    for col in columns:
        col_width = 2 if col["column_key"] == "email" else 1
        header_cols.append({
            "type": "Column", "width": col_width, "padding": "None",
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
    for resp in responses:
        row_cols = []
        for col in columns:
            key = col["column_key"]
            col_width = 2 if key == "email" else 1
            value = resp.get(key, "") or ""
            if not value and col.get("column_category") == "input":
                value = "-"
            color = "Good" if col.get("column_category") == "input" and value != "-" else None
            text_block = {"type": "TextBlock", "text": value, "wrap": True, "size": "Small"}
            if color:
                text_block["color"] = color
            row_cols.append({
                "type": "Column", "width": col_width, "padding": "None",
                "items": [text_block],
            })
        data_rows.append({
            "type": "ColumnSet",
            "separator": True,
            "padding": "None",
            "columns": row_cols,
        })

    # Footer items with yellow background for notes
    note_items = [
        {"type": "TextBlock", "text": f"**Note:** the due date for __{rfp_id}__ is **{rfp_end_date}**",
         "wrap": True, "color": "Attention", "size": "Small"},
    ]
    if matched_line:
        note_items.append({"type": "TextBlock", "text": f"**NOTE:** {matched_line}",
                           "wrap": True, "spacing": "Small", "size": "Small"})
    footer_items = [
        {"type": "Container", "style": "warning", "spacing": "Medium", "items": note_items},
        {"type": "TextBlock", "text": "Best Regards,",
         "wrap": True, "spacing": "Medium", "separator": True, "size": "Small"},
        {"type": "TextBlock", "text": "Automation System",
         "wrap": True, "spacing": "None", "size": "Small"},
    ]

    # Decline button URL (same origin as callback)
    decline_url = _callback_url.rsplit("/response", 1)[0] + "/decline"

    body_items = [
        {"type": "TextBlock", "text": "Dear Team,", "wrap": True, "size": "Small"},
        {"type": "TextBlock", "text": "Kindly advise us regarding the attached RFP file.",
         "wrap": True, "spacing": "Small", "size": "Small"},
        {"type": "TextBlock", "text": f"All team members have submitted their responses for **{rfp_id}**.",
         "wrap": True, "spacing": "Small", "weight": "Bolder", "color": "Good", "size": "Small"},
        {"type": "TextBlock", "text": "Team Assignment", "weight": "Bolder",
         "separator": True, "spacing": "Medium"},
        header_row,
        *data_rows,
        *footer_items,
    ]

    # Decline action (only shown to specific emails from config)
    decline_action = {
        "type": "Action.Http",
        "title": "Decline RFP",
        "method": "POST",
        "url": decline_url,
        "headers": [{"name": "Content-Type", "value": "application/json"}],
        "body": json.dumps({
            "rfp_id": rfp_id,
            "company_name": company_name,
        }),
        "style": "destructive",
    }

    # Normalise allowed emails to lowercase for comparison
    allowed_decline = {e.strip().lower() for e in (_decline_emails if isinstance(_decline_emails, list) else [])}

    # New condition: Decline button only shown when ALL results are "No"
    all_results_no = all(
        (resp.get("results") or "").strip().lower() == "no"
        for resp in responses
    ) if responses else False

    # --- Collect all recipient emails ---
    all_emails = set()
    all_emails.add(_email_to_new_rfp)
    for member in RFP_TEAM_TABLE:
        if member.get("email"):
            all_emails.add(member["email"])

    sender_email = "D365FOadmin@bahra-electric.com"

    # --- Send individual MIME email per recipient ---
    for recipient_email in all_emails:
        # Build card: include Decline button only for allowed emails AND all results are "No"
        show_decline = (
            recipient_email.strip().lower() in allowed_decline
            and all_results_no
        )
        card = {
            "originator": _originator_id,
            "type": "AdaptiveCard",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.0",
            "hideOriginalBody": True,
            "padding": "Default",
            "body": body_items,
            "actions": [decline_action] if show_decline else [],
        }
        card_json = json.dumps(card)

        body_html = f"""<html>
<head>
  <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
  <script type="application/adaptivecard+json">
  {card_json}
  </script>
</head>
<body></body>
</html>"""

        msg = MIMEMultipart("mixed")
        msg["From"] = sender_email
        msg["To"] = recipient_email
        msg["Subject"] = f"All Responses Received - {rfp_id}"

        html_part = MIMEText(body_html, "html", "utf-8")
        msg.attach(html_part)

        # Attach files
        for att_name, att_bytes in attachment_files:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(att_bytes)
            email_encoders.encode_base64(part)
            part.add_header("Content-Disposition", f'attachment; filename="{att_name}"')
            msg.attach(part)

        # Send via Graph API MIME endpoint
        mime_bytes = msg.as_bytes()
        encoded_mime = base64.b64encode(mime_bytes).decode("utf-8")

        try:
            response = requests.post(
                f"https://graph.microsoft.com/v1.0/users/{sender_email}/sendMail",
                headers={
                    "Authorization": f"Bearer {mail_token}",
                    "Content-Type": "text/plain",
                },
                data=encoded_mime,
            )
            if response.status_code == 202:
                decline_tag = " [+Decline]" if show_decline else ""
                print(f"[OK] Consolidated email sent for {rfp_id} to {recipient_email}{decline_tag}")
            else:
                print(f"[ERROR] Consolidated email failed for {rfp_id} to {recipient_email}: {response.status_code} {response.text}")
        except Exception as e:
            print(f"[ERROR] Failed to send consolidated email to {recipient_email}: {e}")


def send_per_rfp_email(
    rfp_id: str,
    company_name: str,
    rfp_end_date: str = "-",
    matched_csv_path: str = None,
    graph_client=None,
):
    """
    Send one email per RFP with:
      - Subject: RFP ID
      - Body: Team table + due date + matched materials note
      - Attachments: RFP .xls file + matched material CSV (if exists)
      - To: EMAIL_TO_NEW_RFP

    If Adaptive Card config is set (ACTIONABLE_CARD_ORIGINATOR_ID and
    ACTIONABLE_CARD_CALLBACK_URL), sends 5 personalized interactive emails
    instead of 1 shared email.
    """
    from helpers.core_helper import clean_rfp_title, get_sharepoint_rfp_material_path
    from services.system_settings_service import get_setting
    _email_to_new_rfp = get_setting("EMAIL_TO_NEW_RFP", "")
    _flow_url = get_setting("FLOW_URL", "")
    _sp_base = get_setting("SP_BASE_FOLDER", "RFP-logs")
    _originator_id = get_setting("ACTIONABLE_CARD_ORIGINATOR_ID", "")
    _callback_url = get_setting("ACTIONABLE_CARD_CALLBACK_URL", "")
    _email_mode = get_setting("EMAIL_MODE", "dev")
    _dev_email = get_setting("DEV_EMAIL", "KSAGov.tenders@bahra-cables.com")
    if _email_mode != "prod" and _email_to_new_rfp:
        _email_to_new_rfp = _dev_email
    from services.master_data_service import get_all_rfp_team_for_emails
    RFP_TEAM_TABLE = get_all_rfp_team_for_emails()
    from core.log_events import log_rfp_activity

    # === Use Adaptive Card emails if configured ===
    if _originator_id and _callback_url:
        return send_actionable_rfp_emails(
            rfp_id=rfp_id,
            company_name=company_name,
            rfp_end_date=rfp_end_date,
            matched_csv_path=matched_csv_path,
            graph_client=graph_client,
        )

    # === Fallback: original HTML table email ===
    subject = rfp_id

    # === Build dynamic team table ===
    from services.rfp_team_columns_service import get_all_columns as _get_cols_fallback
    _cols_fb = _get_cols_fallback()
    table_html = _build_dynamic_html_table(_cols_fb, RFP_TEAM_TABLE)

    # === Combined note section (due date + matched materials) ===
    if matched_csv_path and os.path.exists(matched_csv_path):
        matched_line = (
            "The matched materials file contains system suggested materials that match Bahra offerings. "
            "It is important that you verify the complete RFP file. Do not rely solely on the matched materials file."
        )
    else:
        matched_line = "No matched materials were found for this RFP."

    combined_note = (
        f"<div style='background-color:#FFFF00;display:inline-block;padding:8px 12px;margin:8px 0;'>"
        f"<b>Note: the due date for <u>{rfp_id}</u> is {rfp_end_date}</b><br><br>"
        f"<b>NOTE:</b> {matched_line}"
        f"</div>"
    )

    # === Build body ===
    body_html = f"""
    <p>Dear's,</p>
    <p>Kindly advise us regarding to the attached file</p>
    {table_html}
    {combined_note}
    <br><p>Best Regards,<br>Automation System</p>
    """

    # === Build attachments: RFP file + matched material CSV (if exists) ===
    file_data = create_file_names_and_source_files([rfp_id], company_name)
    file_names = file_data["FileNames"]
    source_files = file_data["SourceFiles"]
    material_file_name = ""

    if matched_csv_path and os.path.exists(matched_csv_path):
        matched_file_name = os.path.basename(matched_csv_path)
        material_file_name = matched_file_name
        file_names.append(matched_file_name)
        clean_title = clean_rfp_title(rfp_id)
        source_files.append(f"/Shared Documents/{_sp_base}/ALLRFPs/{company_name}/{clean_title}/{matched_file_name}")

    email_to = _email_to_new_rfp

    payload = {
        "files": {
            "MaterialFileName": material_file_name,
            "FileNames": file_names,
            "SourceFiles": source_files,
        },
        "emailMeta": {
            "to": email_to,
            "subject": subject,
            "body": body_html,
        },
    }

    # === Send request to Power Automate ===
    response = requests.post(_flow_url, headers={"Content-Type": "application/json"}, data=json.dumps(payload))

    if response.status_code in [200, 202]:
        print(f"[OK] Per-RFP email sent for: {rfp_id}")
        log_rfp_activity(
            rfp_id=rfp_id,
            Downloaded_At=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            email_sent_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            email_to=email_to,
            email_status="Sent",
            company_name=company_name,
        )
    else:
        print(f"[ERROR] Per-RFP email failed for {rfp_id}: {response.status_code} - {response.text}")

    return rfp_id


def trigger_email(
    csv_file=None,
    rfp_id=None,
    not_mateched_files=None,
    subject=None,
    body_html=None,
    graph_client=None,
    email_flag=None,
    rfp_link=None,
    attachments=None,
    company_name=None,
    rfp_titles=None,
    rfp_end_dates=None,
):
    """
    Send email via Power Automate (Flow). Supports:
      - Success with CSV attachment
      - No matched data
      - Reminder emails
      - Failure fallback
    """
    from services.system_settings_service import get_setting
    _flow_url = get_setting("FLOW_URL", "")
    _sp_base = get_setting("SP_BASE_FOLDER", "RFP-logs")
    _email_to_new_rfp = get_setting("EMAIL_TO_NEW_RFP", "")
    _email_to_new_rfp_no_match = get_setting("EMAIL_TO_NEW_RFP_NO_MATCH", "")
    _email_to_new_rfp_with_match = get_setting("EMAIL_TO_NEW_RFP_WITH_MATCH", "")
    _email_to_rfp_reminder = get_setting("EMAIL_TO_RFP_REMINDER", "")
    _email_to_rfp_saved_draft = get_setting("EMAIL_TO_RFP_SAVED_DRAFT", "")
    _email_to_rfp_error_in_submission = get_setting("EMAIL_TO_RFP_ERROR_IN_SUBMISSION", "")
    _email_to_rfp_declined = get_setting("EMAIL_TO_RFP_DECLINED", "")
    _email_to_rfp_error_in_decline = get_setting("EMAIL_TO_RFP_ERROR_IN_DECLINE", "")
    _email_to_no_new_rfp = get_setting("EMAIL_TO_NO_NEW_RFP", "")
    _email_to_automation_failure = get_setting("EMAIL_TO_AUTOMATION_FAILURE", "")
    _email_mode = get_setting("EMAIL_MODE", "dev")
    _dev_email  = get_setting("DEV_EMAIL", "KSAGov.tenders@bahra-cables.com")
    if _email_mode != "prod":
        def _dev(addr): return _dev_email if addr else ""
        _email_to_new_rfp               = _dev(_email_to_new_rfp)
        _email_to_new_rfp_no_match      = _dev(_email_to_new_rfp_no_match)
        _email_to_new_rfp_with_match    = _dev(_email_to_new_rfp_with_match)
        _email_to_rfp_reminder          = _dev(_email_to_rfp_reminder)
        _email_to_rfp_saved_draft       = _dev(_email_to_rfp_saved_draft)
        _email_to_rfp_error_in_submission = _dev(_email_to_rfp_error_in_submission)
        _email_to_rfp_declined          = _dev(_email_to_rfp_declined)
        _email_to_rfp_error_in_decline  = _dev(_email_to_rfp_error_in_decline)
        _email_to_no_new_rfp            = _dev(_email_to_no_new_rfp)
        _email_to_automation_failure    = _dev(_email_to_automation_failure)

    not_mateched_files = not_mateched_files or []
    attachments = attachments or []

    # Preserve the rfp_titles passed in as a parameter before local variables shadow it
    incoming_rfp_titles: list[str] = rfp_titles or []

    unique_emails: list[str] = []
    rfp_titles: list[str] = []
    file_names: list[str] = []
    source_files: list[str] = []
    material_file_name = ""
    email_to = ""

    # === Success email if CSV file provided ===
    if csv_file and os.path.exists(csv_file):
        df = pd.read_csv(csv_file)
        df.columns = df.columns.str.strip()

        # Collect emails
        emails = pd.concat(
            [df.get("Sales department Email"), df.get("Technical Department Email")],
            ignore_index=True
        )
        emails = emails.dropna() if emails is not None else pd.Series([], dtype=str)
        unique_emails = emails.unique().tolist()
        if _email_mode != "prod" and unique_emails:
            unique_emails = [_dev_email]

        # Collect source files
        source_files = df["SourceFile"].dropna().unique().tolist() if "SourceFile" in df.columns else []
        # Collect RFP titles
        rfp_titles = (
            [t.strip() for t in df["RFP_Title"].dropna().unique().tolist()]
            if "RFP_Title" in df.columns else []
        )

        # Build RFP info list with End Dates
        rfp_info = []
        if "RFP_Title" in df.columns:
            for rfp in df["RFP_Title"].dropna().unique().tolist():
                rfp_rows = df[df["RFP_Title"] == rfp]
                RFP_End_Date = "-"
                if "RFP_End_Date" in rfp_rows.columns and not rfp_rows["RFP_End_Date"].isna().all():
                    RFP_End_Date = rfp_rows["RFP_End_Date"].iloc[0]
                rfp_info.append(f"{rfp} (End-date: {RFP_End_Date})")

        # Build email body
        if not body_html:
            body_html = f"""
            <p>Dear Team,</p>
            <p>Please find attached the latest <b>Matched Materials Report</b>.</p>
            <p><b>Source Files:</b></p>
            <ul><li>{'</li><li>'.join(rfp_info)}</li></ul>
            <p>Best Regards,<br>Automation System</p>
            """

        if not subject:
            subject = f"Automation Successfully Run on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        # Final payload
        file_data = create_file_names_and_source_files(rfp_titles, company_name)
        file_names = file_data["FileNames"]
        source_files = file_data["SourceFiles"]
        if unique_emails:
            matched_material_file_name = os.path.basename(csv_file)
            material_file_name = matched_material_file_name
            email_to = ";".join(unique_emails)
            # Include the matched materials CSV itself in the attachment list
            # so Power Automate can find it in SharePoint and attach it to the email
            file_names.append(material_file_name)
            source_files.append(f"/Shared Documents/{_sp_base}/ALLRFPs/{material_file_name}")
        else:
            # Nothing to send
            return rfp_titles

    # === New RFP found but no material match — attach the RFP file(s) ===
    elif csv_file == "not_matched_data":
        unique_emails = [_email_to_new_rfp_no_match]
        rfp_titles = [Path(f).stem for f in not_mateched_files]
        auto_subject, auto_body = _build_rfp_notification_html(rfp_titles, rfp_end_dates)
        if not subject:
            subject = auto_subject
        if not body_html:
            body_html = auto_body
        file_data = create_file_names_and_source_files(rfp_titles, company_name)
        file_names = file_data["FileNames"]
        source_files = file_data["SourceFiles"]
        email_to = _email_to_new_rfp_no_match

    # === Reminder emails ===
    elif email_flag == "reminder":
        email_to = _email_to_rfp_reminder

    # elif email_flag == "rfp_submitted":
    #     subject=f"RFP {rfp_id} Processed Successfully"
    #     body_html=f"""
    #     <p>Dear Team,</p>
    #     <p>The RFP with ID <b>{rfp_id}</b> has been successfully processed and all automation steps completed.</p>
    #     <p>Best Regards,<br>Automation System</p>
    #     """
    #     payload = {
    #         "files": {"MaterialFileName": '', "SourceFiles": []},
    #         "emailMeta": {
    #             "to": EMAIL_TO_RFP_SUBMITTED,
    #             "subject": subject,
    #             "body": body_html
    #         }
    #     }
    
    elif email_flag == "rfp_saved_draft":
        subject=f"RFP {rfp_id} Saved as Draft Successfully"
        
        # Build email body with RFP link button if link is provided
        if rfp_link:
            link_html = f"""
            <p style="margin: 20px 0;">
                <a href="{rfp_link}" 
                   style="background-color: #007bff; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                    View RFP
                </a>
            </p>
            """
        else:
            link_html = ""
        
        body_html = f"""
        <p>Dear Team,</p>
        <p>The RFP with ID <b>{rfp_id}</b> has been successfully saved as a draft.</p>
        {link_html}
        <p>Best Regards,<br>Automation System</p>
        """
        
        email_to = _email_to_rfp_saved_draft

    elif email_flag == "error_in_rfp_submission":
        subject = subject or f"RFP {rfp_id} Processing Failed"
        if not body_html:
            body_html = f"""
            <p>Dear Team,</p>
            <p>The RFP with ID <b>{rfp_id}</b> encountered an error during processing.</p>
            <p>Please check the automation logs for details.</p>
            <p>Best Regards,<br>Automation System</p>
            """
        email_to = _email_to_rfp_error_in_submission
    
    elif email_flag == "rfp_decline":
        subject=f"RFP {rfp_id} Decline Successfully"
        body_html=f"""
        <p>Dear Team,</p>
        <p>The RFP with ID <b>{rfp_id}</b> has been successfully Decline and all automation steps completed.</p>
        <p>Best Regards,<br>Automation System</p>
        """
        email_to = _email_to_rfp_declined

    elif email_flag == "error_in_rfp_decline":
        subject = subject or f"RFP {rfp_id} Decline Failed"
        if not body_html:
            body_html = f"""
            <p>Dear Team,</p>
            <p>The RFP with ID <b>{rfp_id}</b> encountered an error during decline.</p>
            <p>Please check the automation logs for details.</p>
            <p>Best Regards,<br>Automation System</p>
            """
        email_to = _email_to_rfp_error_in_decline

    # === CASE 1: New RFP found (matched or not) — reference format email ===
    elif email_flag == "new_rfp_found":
        rfp_titles = incoming_rfp_titles
        auto_subject, auto_body = _build_rfp_notification_html(rfp_titles, rfp_end_dates)
        if not subject:
            subject = auto_subject
        if not body_html:
            body_html = auto_body
        file_data = create_file_names_and_source_files(rfp_titles, company_name)
        file_names = file_data["FileNames"]
        source_files = file_data["SourceFiles"]
        email_to = _email_to_new_rfp

    # === CASE 2: No new RFP found on portal ===
    elif email_flag == "no_new_rfp":
        email_to = _email_to_no_new_rfp

    # === New RFP found with matched materials — send RFP file to a separate recipient ===
    elif email_flag == "new_rfp_with_match":
        rfp_titles = incoming_rfp_titles
        auto_subject, auto_body = _build_rfp_notification_html(rfp_titles, rfp_end_dates)
        if not subject:
            subject = auto_subject
        if not body_html:
            body_html = auto_body
        file_data = create_file_names_and_source_files(rfp_titles, company_name)
        file_names = file_data["FileNames"]
        source_files = file_data["SourceFiles"]
        email_to = _email_to_new_rfp_with_match

    elif email_flag == "automation_failure":
        if not subject:
            subject = "[WARN] Automation Failure"
        if not body_html:
            body_html = """
            <p>Dear Team,</p>
            <p>The automation encountered an unexpected error. Please review the attached log for details.</p>
            <p>Best Regards,<br>Automation System</p>
            """
        email_to = _email_to_automation_failure

    # === Failure fallback ===
    else:
        if not subject:
            subject = "[WARN] Automation Failure"
        if not body_html:
            body_html = """
            <p>Dear Client,</p>
            <p>The scheduled automation <b>did not complete successfully</b>. Our team has been notified.</p>
            <p>Best Regards,<br>Automation System</p>
            """
        email_to = _email_to_automation_failure

    for attachment in attachments:
        name = (attachment or {}).get("name")
        path = (attachment or {}).get("path")
        if name and path:
            file_names.append(name)
            source_files.append(path)

    payload = {
        "files": {
            "MaterialFileName": material_file_name,
            "FileNames": file_names,
            "SourceFiles": source_files,
        },
        "emailMeta": {
            "to": email_to,
            "subject": subject,
            "body": body_html,
        },
    }

    # === Send request to Power Automate ===
    response = requests.post(_flow_url, headers={"Content-Type": "application/json"}, data=json.dumps(payload))

    if response.status_code in [200, 202]:
        print(f"[OK] Email sent: {subject}")
        if len(rfp_titles) > 0:
            for title in rfp_titles:
                print("title:-",title)
                log_rfp_activity(
                    rfp_id=title,
                    Downloaded_At=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    email_sent_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    email_to=";".join(unique_emails),
                    email_status="Sent",
                    company_name=company_name
                )
    else:
        print(f"[ERROR] Email sending failed: {response.status_code} - {response.text}")

    return rfp_titles
