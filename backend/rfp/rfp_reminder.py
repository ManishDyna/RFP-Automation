from core.common_imports import *
from helpers.email_helper import trigger_email
from helpers.core_helper import DATAVERSE
from config.config import RFP_ACTIVITY_LOG_TABLE_API, RFP_ACTIVITY_LOG_TABLE_LOGICAL


## Normalized constants used by the rest of the module
REMINDER_3DAY_COL = "Reminder_3Day_Sent"
REMINDER_1DAY_COL = "Reminder_1Day_Sent"

# Cached resolved column names (populated once per run)
_resolved_3day = None
_resolved_1day = None


def _discover_reminder_columns():
    """
    Fetch ONE row with ALL columns from Dataverse (no $select filter)
    and inspect the returned keys to find the actual reminder column names.
    This avoids any metadata-vs-OData mismatch for newly-created columns.
    Returns (col_3day_display_name, col_1day_display_name) — either can be None.
    """
    global _resolved_3day, _resolved_1day

    DATAVERSE.clear_column_mapping_cache(RFP_ACTIVITY_LOG_TABLE_LOGICAL)

    # Fetch 1 row with ALL columns (no select_columns → no $select param)
    sample = DATAVERSE.query_rows(
        RFP_ACTIVITY_LOG_TABLE_API,
        top=1,
        table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL,
        use_display_names=True,
    )

    col_3 = None
    col_1 = None
    if sample and "value" in sample and sample["value"]:
        actual_cols = list(sample["value"][0].keys())
        for col in actual_cols:
            cl = col.lower().replace(" ", "").replace("_", "")
            if "reminder" in cl and "3day" in cl:
                col_3 = col
            elif "reminder" in cl and "1day" in cl:
                col_1 = col
        # Debug: show what we found
        reminder_cols = [c for c in actual_cols if "remind" in c.lower()]
        print(f"📋 All reminder-like columns in data: {reminder_cols}")
        print(f"   Resolved 3-day col: {col_3}")
        print(f"   Resolved 1-day col: {col_1}")
    else:
        print("⚠ No rows in Dataverse table — cannot discover reminder columns.")

    _resolved_3day = col_3
    _resolved_1day = col_1
    return col_3, col_1


def _get_rfp_data_with_reminders():
    """
    Fetch RFP data including reminder tracking columns.
    Fetches ALL columns (no $select) to avoid display-name/trailing-space
    issues with newly-created columns, then normalises the keys we care about.
    The reminder endpoint runs infrequently so the extra payload is fine.
    """
    col_3day, col_1day = _discover_reminder_columns()

    # Fetch ALL columns — avoids $select mapping issues with trailing spaces
    data = DATAVERSE.get_all_rows(
        table_api_name=RFP_ACTIVITY_LOG_TABLE_API,
        table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL,
        use_display_names=True,
    )

    # Normalize: strip all keys and rename discovered reminder cols to our constants
    normalized = []
    for row in data:
        r = {k.strip(): v for k, v in row.items()}
        # Map actual reminder column names (stripped) to our constants
        if col_3day:
            stripped_3 = col_3day.strip()
            if stripped_3 in r and stripped_3 != REMINDER_3DAY_COL:
                r[REMINDER_3DAY_COL] = r.pop(stripped_3)
        if col_1day:
            stripped_1 = col_1day.strip()
            if stripped_1 in r and stripped_1 != REMINDER_1DAY_COL:
                r[REMINDER_1DAY_COL] = r.pop(stripped_1)
        normalized.append(r)
    return normalized


def _get_record_id(rfp_id: str):
    """Query Dataverse for a single RFP and return its primary-key record ID."""
    result = DATAVERSE.query_rows(
        RFP_ACTIVITY_LOG_TABLE_API,
        filter_expr=f"RFP_ID eq '{rfp_id}'",
        top=1,
        table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL,
        use_display_names=True,
    )
    if result and "value" in result and len(result["value"]) > 0:
        row = result["value"][0]
        # Resolve primary key — may be under display name or logical name
        try:
            colmap = DATAVERSE.get_column_mapping(RFP_ACTIVITY_LOG_TABLE_LOGICAL)
            logical_to_display = {v: k for k, v in colmap.items()}
        except Exception:
            logical_to_display = {}
        pk_logical = f"{RFP_ACTIVITY_LOG_TABLE_LOGICAL}id"
        pk_display = logical_to_display.get(pk_logical)
        return (row.get(pk_display) if pk_display else None) or row.get(pk_logical)
    return None


def _mark_reminder_sent(rfp_id: str, field_name: str):
    """Update a single RFP record in Dataverse to mark a reminder as sent.
    field_name is our constant (REMINDER_3DAY_COL / REMINDER_1DAY_COL);
    we use the already-discovered actual Dataverse column name."""
    # Use the column names discovered earlier by _discover_reminder_columns()
    actual_col = None
    if field_name == REMINDER_3DAY_COL:
        actual_col = _resolved_3day
    elif field_name == REMINDER_1DAY_COL:
        actual_col = _resolved_1day

    if not actual_col:
        print(f"⚠ Reminder column '{field_name}' not found in Dataverse — cannot update.")
        return False

    record_id = _get_record_id(rfp_id)
    if not record_id:
        print(f"⚠ Could not find record for RFP '{rfp_id}' to update {actual_col}")
        return False
    try:
        DATAVERSE.update_row(
            RFP_ACTIVITY_LOG_TABLE_API,
            record_id,
            {actual_col: "Yes"},
            table_logical_name=RFP_ACTIVITY_LOG_TABLE_LOGICAL,
            use_display_names=True,
        )
        print(f"✅ Marked {actual_col}=Yes for RFP: {rfp_id}")
        return True
    except Exception as e:
        print(f"⚠ Failed to update {actual_col} for RFP '{rfp_id}': {e}")
        return False


def _build_reminder_table(rfp_rows: list) -> str:
    """Build an HTML table for the reminder email from a list of RFP dicts."""
    table_rows = ""
    for row in rfp_rows:
        rfp_id = row["rfp_id"]
        end_date = row["end_date_str"]
        hours_left = row["hours_left"]

        if hours_left < 1:
            time_left = "<b style='color:red;'>Less than 1 hour!</b>"
        elif hours_left < 24:
            time_left = f"<b style='color:red;'>{int(hours_left)} hour(s)</b>"
        else:
            days = int(hours_left // 24)
            time_left = f"<b>{days} day(s)</b>"

        row_color = "#FFCCCC" if hours_left < 48 else "#FFFFFF"

        table_rows += f"""
        <tr style="background-color:{row_color}; text-align:center;border:2px solid #333030;">
            <td style="padding:8px; border:2px solid #333030;">{rfp_id}</td>
            <td style="padding:8px; border:2px solid #333030;">{end_date}</td>
            <td style="padding:8px; border:2px solid #333030;">{time_left}</td>
        </tr>
        """

    return f"""
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


def send_rfp_deadline_reminders():
    """
    Send RFP deadline reminders for 3-day and 1-day windows.
    Each reminder is sent only ONCE per RFP — tracked via
    Reminder_3Day_Sent / Reminder_1Day_Sent columns in Dataverse (Bahra_rfps table).
    """
    data = _get_rfp_data_with_reminders()
    if not data:
        print("✅ No RFP data found.")
        return

    df = pd.DataFrame(data)
    df.columns = df.columns.str.strip()

    if "RFP_End_Date" not in df.columns:
        print("❌ Missing RFP_End_Date column.")
        return

    # Parse dates and compute time remaining.
    # Dataverse now returns RFP_End_Date as ISO 8601 UTC (tz-aware) after the
    # string→datetime column migration. Normalise via utc=True, then strip the
    # tz so arithmetic with naive datetime.now() works.
    df["RFP_End_Date"] = pd.to_datetime(df["RFP_End_Date"], errors="coerce", utc=True).dt.tz_localize(None)
    now = datetime.now()
    df["Hours_Left"] = (df["RFP_End_Date"] - now).dt.total_seconds() / 3600

    # Only consider RFPs that are still in the future
    df = df[df["Hours_Left"] > 0].copy()

    # Normalize reminder tracking columns (may be missing or NaN)
    for col in ("Reminder_3Day_Sent", "Reminder_1Day_Sent"):
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].fillna("").astype(str).str.strip().str.lower()

    # ── Collect RFPs needing 3-day reminder ──
    # Deadline is within 3 days (≤72 hours) AND 3-day reminder not yet sent
    three_day_mask = (
        (df["Hours_Left"] <= 72) &
        (df["Reminder_3Day_Sent"] != "yes")
    )
    three_day_rfps = []
    for _, row in df[three_day_mask].iterrows():
        three_day_rfps.append({
            "rfp_id": row.get("RFP_ID", "Unknown"),
            "end_date_str": row["RFP_End_Date"].strftime("%Y-%m-%d %H:%M") if pd.notna(row["RFP_End_Date"]) else "-",
            "hours_left": row["Hours_Left"],
        })

    # ── Collect RFPs needing 1-day reminder ──
    # Deadline is within 1 day (≤24 hours) AND 1-day reminder not yet sent
    one_day_mask = (
        (df["Hours_Left"] <= 24) &
        (df["Reminder_1Day_Sent"] != "yes")
    )
    one_day_rfps = []
    for _, row in df[one_day_mask].iterrows():
        one_day_rfps.append({
            "rfp_id": row.get("RFP_ID", "Unknown"),
            "end_date_str": row["RFP_End_Date"].strftime("%Y-%m-%d %H:%M") if pd.notna(row["RFP_End_Date"]) else "-",
            "hours_left": row["Hours_Left"],
        })

    # ── Send 3-day reminder email ──
    if three_day_rfps:
        html_table = _build_reminder_table(three_day_rfps)
        subject = f"🔔 RFP Deadline Reminder (3 Days) - {now.strftime('%Y-%m-%d')}"
        body_html = f"""
        <p>Dear Team,</p>
        <p>The following RFP(s) have their deadline within <b>3 days</b>:</p>
        {html_table}
        <p>Please review and take necessary action.</p>
        <p>Best Regards,<br>Automation System</p>
        """
        trigger_email(subject=subject, body_html=body_html, email_flag="reminder")
        print(f"✅ 3-day reminder email sent for {len(three_day_rfps)} RFP(s).")

        # Mark each RFP as 3-day reminder sent in Dataverse
        for rfp in three_day_rfps:
            _mark_reminder_sent(rfp["rfp_id"], "Reminder_3Day_Sent")
    else:
        print("✅ No 3-day reminders to send.")

    # ── Send 1-day reminder email ──
    if one_day_rfps:
        html_table = _build_reminder_table(one_day_rfps)
        subject = f"🚨 URGENT: RFP Deadline Tomorrow (1 Day) - {now.strftime('%Y-%m-%d')}"
        body_html = f"""
        <p>Dear Team,</p>
        <p>The following RFP(s) have their deadline within <b>1 day</b>. <b style="color:red;">Immediate action required!</b></p>
        {html_table}
        <p>Please review and take necessary action urgently.</p>
        <p>Best Regards,<br>Automation System</p>
        """
        trigger_email(subject=subject, body_html=body_html, email_flag="reminder")
        print(f"✅ 1-day reminder email sent for {len(one_day_rfps)} RFP(s).")

        # Mark each RFP as 1-day reminder sent in Dataverse
        for rfp in one_day_rfps:
            _mark_reminder_sent(rfp["rfp_id"], "Reminder_1Day_Sent")
    else:
        print("✅ No 1-day reminders to send.")

    total = len(three_day_rfps) + len(one_day_rfps)
    if total == 0:
        print("✅ All reminders already sent. Nothing to do.")
    else:
        print(f"✅ Reminder process complete. Sent reminders for {total} RFP(s).")
