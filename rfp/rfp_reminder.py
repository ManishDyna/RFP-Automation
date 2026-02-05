from core.common_imports import *
from helpers.email_helper import trigger_email
from helpers.core_helper import get_rfp_activity_data_from_db

def send_rfp_deadline_reminders():
    """
    Finds RFPs ending in 3, 2, 1 days OR less than 10 hours and sends reminder emails.
    Styled table shows days or hours left dynamically.
    """
    data = get_rfp_activity_data_from_db()
    print("data:-", data)
    
    # Fix: Create DataFrame directly from list of dictionaries
    df = pd.DataFrame(data)
    
    df.columns = df.columns.str.strip()

    if "RFP_End_Date" not in df.columns:
        print("❌ Missing RFP_End_Date column.")
        return

    # 🔹 Normalize datetime
    df["RFP_End_Date"] = pd.to_datetime(df["RFP_End_Date"], errors="coerce")
    now = datetime.now()

    # 🔹 Compute time differences
    df["Time_Left"] = df["RFP_End_Date"] - now
    df["Days_Left"] = df["Time_Left"].dt.days
    df["Hours_Left"] = df["Time_Left"].dt.total_seconds() / 3600

    # 🔹 Keep only matched data
    if "Matched_Data" in df.columns:
        df = df[df["Matched_Data"].notna() & (df["Matched_Data"].str.strip() != "")]
    else:
        print("⚠ No Matched_Data column found; using all rows.")

    # 🔹 Filter RFPs
    reminder_df = df[(df["Days_Left"].isin([3, 2, 1])) | (df["Hours_Left"] < 24)].copy()
    if reminder_df.empty:
        print("✅ No reminders to send today.")
        return

    # 🔹 Sort: closest deadline first
    reminder_df = reminder_df.sort_values(by="Time_Left")

    # 🔹 Build Stylish Table (use to_dict for better performance)
    table_rows = ""
    for row in reminder_df.to_dict('records'):
        rfp_id = row.get("RFP_ID", "Unknown RFP")
        end_date = row["RFP_End_Date"].strftime("%Y-%m-%d %H:%M")
        hours_left = row["Hours_Left"]

        # 🔥 Determine time left text
        if hours_left < 1:
            time_left = "<b style='color:red;'>Less than 1 hour!</b>"
        elif hours_left < 24:
            time_left = f"<b style='color:red;'>{int(hours_left)} hour(s)</b>"
        else:
            time_left = f"<b>{row['Days_Left']} day(s)</b>"

        # 🔥 Row color: red if <24h
        row_color = "#FFCCCC" if hours_left < 24 or hours_left < 48  else "#FFFFFF"

        table_rows += f"""
        <tr style="background-color:{row_color}; text-align:center;border:2px solid #333030;">
            <td>{rfp_id}</td>
            <td>{end_date}</td>
            <td>{time_left}</td>
        </tr>
        """

    html_table = f"""
    <table style="border-collapse:collapse; width:100%; border:2px solid #333030; font-family:Arial, sans-serif;">
        <thead style="background-color:#0078D7; color:white;">
            <tr>
                <th style="padding:8px; border:2px solid #333030;">RFP ID</th>
                <th style="padding:8px; border:2px solid #333030;">End Date</th>
                <th style="padding:8px; border:2px solid #333030;">Time Left</th>
            </tr>
        </thead>
        <tbody>
            {table_rows}
        </tbody>
    </table>
    """

    subject = f"🔔 RFP Deadline Reminder - {datetime.now().strftime('%Y-%m-%d')}"
    body_html = f"""
    <p>Dear Team,</p>
    <p>The following RFP(s) are approaching their deadline:</p>
    {html_table}
    <p>Please review and take necessary action.</p>
    <p>Best Regards,<br>Automation System</p>
    """

    # 🔹 Send Email
    trigger_email(
        subject=subject,
        body_html=body_html,
        email_flag="reminder"
    )

    print(f"✅ Reminder email sent for {len(reminder_df)} RFP(s).")
