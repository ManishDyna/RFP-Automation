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
    from config.config import COMPANY_NAME

    # Use provided company_name or fallback to default
    target_company = company_name or COMPANY_NAME

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
):
    """
    Send email via Power Automate (Flow). Supports:
      - Success with CSV attachment
      - No matched data
      - Reminder emails
      - Failure fallback
    """
    not_mateched_files = not_mateched_files or []
    attachments = attachments or []

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
        else:
            # Nothing to send
            return rfp_titles

    # === No matched data ===
    elif csv_file == "not_matched_data":
        unique_emails = [EMAIL_TO_NO_MATCHED_DATA]
        rfp_titles = [Path(f).stem for f in not_mateched_files]
        if not subject:
            subject = f"Automation Run - No Matched Data ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})"
        if not body_html:
            body_html = """
            <p>Dear Team,</p>
            <p>The automation completed successfully, but <b>no new materials</b> were matched.</p>
            <p>No action required. The system will continue monitoring and notify you of updates.</p>
            <p>Best Regards,<br>Automation System</p>
            """
        file_data = create_file_names_and_source_files(rfp_titles, company_name)
        file_names = file_data["FileNames"]
        source_files = file_data["SourceFiles"]
        email_to = EMAIL_TO_NO_MATCHED_DATA

    # === Reminder emails ===
    elif email_flag == "reminder":
        email_to = EMAIL_TO_RFP_REMINDER

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
        
        email_to = EMAIL_TO_RFP_SAVED_DRAFT

    elif email_flag == "error_in_rfp_submission":
        subject = subject or f"RFP {rfp_id} Processing Failed"
        # Check if attachments are provided
        has_attachments = attachments and len(attachments) > 0
        attachment_note = ""
        if has_attachments:
            attachment_note = "<p><b>Error details are included in the attached log file.</b></p>"
        body_html = f"""
        <p>Dear Team,</p>
        <p>The RFP with ID <b>{rfp_id}</b> encountered an error during processing.</p>
        {attachment_note}
        <p>Please check the automation logs for details.</p>
        <p>Best Regards,<br>Automation System</p>
        """
        email_to = EMAIL_TO_RFP_ERROR_IN_SUBMISSION
    
    elif email_flag == "rfp_decline":
        subject=f"RFP {rfp_id} Decline Successfully"
        body_html=f"""
        <p>Dear Team,</p>
        <p>The RFP with ID <b>{rfp_id}</b> has been successfully Decline and all automation steps completed.</p>
        <p>Best Regards,<br>Automation System</p>
        """
        email_to = EMAIL_TO_RFP_DECLINED

    elif email_flag == "error_in_rfp_decline":
        subject = subject or f"RFP {rfp_id} Decline Failed"
        # Check if attachments are provided
        has_attachments = attachments and len(attachments) > 0
        attachment_note = ""
        if has_attachments:
            attachment_note = "<p><b>Error details are included in the attached log file.</b></p>"
        body_html = f"""
        <p>Dear Team,</p>
        <p>The RFP with ID <b>{rfp_id}</b> encountered an error during processing.</p>
        {attachment_note}
        <p>Please check the automation logs for details.</p>
        <p>Best Regards,<br>Automation System</p>
        """
        email_to = EMAIL_TO_RFP_ERROR_IN_DECLINE

    elif email_flag == "automation_failure":
        if not subject:
            subject = "⚠ Automation Failure"
        if not body_html:
            body_html = """
            <p>Dear Team,</p>
            <p>The automation encountered an unexpected error. Please review the attached log for details.</p>
            <p>Best Regards,<br>Automation System</p>
            """
        email_to = EMAIL_TO_AUTOMATION_FAILURE

    # === Failure fallback ===
    else:
        if not subject:
            subject = "⚠ Automation Failure"
        if not body_html:
            body_html = """
            <p>Dear Client,</p>
            <p>The scheduled automation <b>did not complete successfully</b>. Our team has been notified.</p>
            <p>Best Regards,<br>Automation System</p>
            """
        email_to = EMAIL_TO_AUTOMATION_FAILURE

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
    response = requests.post(FLOW_URL, headers={"Content-Type": "application/json"}, data=json.dumps(payload))

    if response.status_code in [200, 202]:
        print(f"✅ Email sent: {subject}")
        if len(rfp_titles) > 0:
            for title in rfp_titles:
                print("title:-",title)
                log_rfp_activity(
                    rfp_id=title,
                    Downloaded_At=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    email_sent_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    email_to=";".join(unique_emails),
                    email_status="Sent"
                )
    else:
        print(f"❌ Email sending failed: {response.status_code} - {response.text}")

    return rfp_titles
