"""
Dashboard service - Core dashboard data fetching and caching logic.
Moved from Dashboard/backend/dashboard_backend.py
"""

from core.common_imports import *
from helpers.core_helper import DATAVERSE, get_rfp_activity_data_from_db
from fastapi import HTTPException
from datetime import datetime, timedelta
import time
from config.config import (
    DASHBOARD_TTL_SECONDS,
    LOGS_TTL_SECONDS,
    AUTOMATION_LOG_TABLE_API,
    AUTOMATION_LOG_TABLE_LOGICAL,
    URL,
)

# ===== DASHBOARD DATA CACHE (TTL) =====
_DASHBOARD_CACHE = {"data": None, "ts": 0}
_DASHBOARD_TTL_SECONDS = DASHBOARD_TTL_SECONDS


def format_publish_time(publish_time_str):
    """Format publish time string for display"""
    if not publish_time_str or publish_time_str == "":
        return "-"

    try:
        if isinstance(publish_time_str, str):
            if "/" in publish_time_str and ("AM" in publish_time_str or "PM" in publish_time_str):
                dt = pd.to_datetime(publish_time_str, errors="coerce")
                if pd.notna(dt):
                    return dt.strftime("%Y-%m-%d %H:%M")
            elif "T" in publish_time_str:
                dt = pd.to_datetime(publish_time_str, errors="coerce")
                if pd.notna(dt):
                    return dt.strftime("%Y-%m-%d %H:%M")

        if hasattr(publish_time_str, 'strftime'):
            return publish_time_str.strftime("%Y-%m-%d %H:%M")

    except Exception as e:
        print(f"Error formatting publish time '{publish_time_str}': {e}")

    return str(publish_time_str)


def get_dashboard_data_cached(force_refresh: bool = False):
    from time import time as _now
    now = _now()
    if not force_refresh:
        if _DASHBOARD_CACHE["data"] is not None and (now - _DASHBOARD_CACHE["ts"]) < _DASHBOARD_TTL_SECONDS:
            return _DASHBOARD_CACHE["data"]
    data = get_dashboard_data()
    _DASHBOARD_CACHE["data"] = data
    _DASHBOARD_CACHE["ts"] = now
    return data


def _automation_fetch_from_dataverse(top=200):
    try:
        select_cols = ["RunID", "Timestamp", "Category", "RFP_ID", "Action", "automation_status", "Message"]
        rows = DATAVERSE.get_rows_from_dataverse(
            table_api_name=AUTOMATION_LOG_TABLE_API,
            select_columns=select_cols,
            top=top,
            table_logical_name=AUTOMATION_LOG_TABLE_LOGICAL,
            use_display_names=True
        )
        return rows
    except Exception as e:
        print(f"Error fetching automation data: {e}")
        return []


def get_dashboard_data():
    try:
        print(f"Starting dashboard data fetch at {datetime.now()}")
        start_time = time.time()

        auto_rows = _automation_fetch_from_dataverse()
        print(f"Automation data fetched: {len(auto_rows)} rows")

        if not auto_rows:
            auto_df = pd.DataFrame()
        else:
            auto_df = pd.DataFrame(auto_rows).fillna("")

        if "Timestamp" in auto_df.columns:
            try:
                auto_df["RunDate"] = pd.to_datetime(auto_df["Timestamp"], errors="coerce")
            except Exception as e:
                print(f"Error converting Timestamp to datetime: {e}")
                auto_df["RunDate"] = pd.NaT
        else:
            auto_df["RunDate"] = pd.NaT

        if not auto_df.empty and "RunDate" in auto_df.columns:
            try:
                if auto_df["RunDate"].dt.tz is not None:
                    auto_df["RunDate"] = auto_df["RunDate"].dt.tz_localize(None)

                thirty_days_ago = datetime.now() - timedelta(days=30)
                auto_df = auto_df[auto_df["RunDate"] >= thirty_days_ago]
                auto_df = auto_df.dropna(subset=["RunDate"]).sort_values("RunDate", ascending=False)
            except Exception as e:
                print(f"Error filtering automation data by date: {e}")

        print(f"Automation data after filtering: {len(auto_df)} rows")

        rfp_rows = get_rfp_activity_data_from_db()
        print(f"RFP data fetched: {len(rfp_rows)} rows")

        if not rfp_rows:
            rfp_df = pd.DataFrame()
        else:
            rfp_df = pd.DataFrame(rfp_rows).fillna("")

        downloaded_rfp_list = []
        open_rfp_list = []
        submitted_rfp_list = []
        saved_draft_rfp_list = []
        declined_rfp_list = []

        companies_rfps = {}
        unique_companies = set()
        total_submitted_rfps = 0
        total_declined_rfps = 0

        if not rfp_df.empty:
            if "RFP_End_Date" in rfp_df.columns:
                try:
                    rfp_df["_RFP_End_Date_dt"] = pd.to_datetime(rfp_df["RFP_End_Date"], errors="coerce")
                    if rfp_df["_RFP_End_Date_dt"].dt.tz is not None:
                        rfp_df["_RFP_End_Date_dt"] = rfp_df["_RFP_End_Date_dt"].dt.tz_localize(None)
                except Exception as e:
                    print(f"Error parsing RFP_End_Date: {e}")
                    rfp_df["_RFP_End_Date_dt"] = pd.NaT

                try:
                    rfp_df = rfp_df.sort_values(["_RFP_End_Date_dt", "RFP_ID"], ascending=[True, True])
                except Exception:
                    pass

                for _, row in rfp_df.iterrows():
                    company_name = row.get("Company_Name", "") if row.get("Company_Name", "") else "Saudi Electricity Company"
                    unique_companies.add(company_name)
                    if company_name not in companies_rfps:
                        companies_rfps[company_name] = {
                            "open": [],
                            "submitted": [],
                            "saved_draft": [],
                            "declined": []
                        }

                for _, row in rfp_df.iterrows():
                    end_dt = row.get("_RFP_End_Date_dt")
                    end_str = end_dt.strftime("%Y-%m-%d %H:%M") if pd.notna(end_dt) else str(row.get("RFP_End_Date", ""))

                    if row.get("participated", "").strip().lower() == "submitted" or row.get("participated", "").strip().lower() == "yes":
                        total_submitted_rfps += 1
                    if row.get("participated", "").strip().lower() == "declined":
                        total_declined_rfps += 1

                    if pd.notna(end_dt) and end_dt >= datetime.now():
                        rfp_link = row.get("Link", "") or row.get("link", "")
                        if not rfp_link:
                            rfp_link = URL

                        company_name = row.get("Company_Name", "") if row.get("Company_Name", "") else "Saudi Electricity Company"

                        rfp_data = {
                            "RFP_ID": row.get("RFP_ID", ""),
                            "RFP_End_Date": end_str,
                            "Company_Name": company_name,
                            "Owner_Name": row.get("owner_name", ""),
                            "Publish_Time": format_publish_time(row.get("publish_time", "")),
                            "participated": row.get("participated", ""),
                            "Link": rfp_link,
                        }

                        downloaded_rfp_list.append(rfp_data)

                        participation_status = (row.get("participated", "") or "").lower()
                        if participation_status == "no" or participation_status == "":
                            open_rfp_list.append(rfp_data)
                            companies_rfps[company_name]["open"].append(rfp_data)
                        elif participation_status == "submitted" or participation_status == "yes":
                            submitted_rfp_list.append(rfp_data)
                            companies_rfps[company_name]["submitted"].append(rfp_data)
                        elif participation_status == "declined":
                            declined_rfp_list.append(rfp_data)
                            companies_rfps[company_name]["declined"].append(rfp_data)
                        elif participation_status == "saved_draft":
                            saved_draft_rfp_list.append(rfp_data)
                            companies_rfps[company_name]["saved_draft"].append(rfp_data)

        saved_rfps = int(len(rfp_df))
        prev_saved_rfps = 0
        downloaded_rfps = saved_rfps
        prev_downloaded_rfps = 0

        rfp_stats = {
            "total_rfps": saved_rfps,
            "downloaded_rfps": downloaded_rfps,
            "prev_total_rfps": prev_saved_rfps,
            "prev_downloaded_rfps": prev_downloaded_rfps,
        }

        automation_stats = {
            "total_runs": int(len(auto_df)),
            "successful_runs": int((auto_df.get("automation_status", pd.Series(dtype=str)).astype(str).str.lower() == "success").sum()) if not auto_df.empty else 0,
            "failed_runs": int((auto_df.get("automation_status", pd.Series(dtype=str)).astype(str).str.lower() == "failed").sum()) if not auto_df.empty else 0,
            "last_run_time": auto_df["RunDate"].max().strftime("%Y-%m-%d %H:%M") if ("RunDate" in auto_df.columns and auto_df["RunDate"].notna().any()) else "-"
        }

        unique_companies_list = sorted(list(unique_companies))

        data = {
            "rfp": rfp_stats,
            "automation": automation_stats,
            "downloaded_rfps": downloaded_rfp_list,
            "open_rfps": open_rfp_list,
            "submitted_rfps": submitted_rfp_list,
            "declined_rfps": declined_rfp_list,
            "saved_draft_rfps": saved_draft_rfp_list,
            "total_submitted_rfps": total_submitted_rfps,
            "total_declined_rfps": total_declined_rfps,
            "companies_rfps": companies_rfps,
            "unique_companies": unique_companies_list
        }

        end_time = time.time()
        print(f"Dashboard data processed in {end_time - start_time:.2f} seconds")

        return data

    except Exception as e:
        print(f"Error building dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error building dashboard: {str(e)}")


def get_all_rfp_data():
    """Get all RFP data from database without date filtering."""
    try:
        print(f"Starting all RFP data fetch at {datetime.now()}")
        start_time = time.time()

        rfp_rows = get_rfp_activity_data_from_db()
        print(f"RFP data fetched: {len(rfp_rows)} rows")

        if not rfp_rows:
            rfp_df = pd.DataFrame()
        else:
            rfp_df = pd.DataFrame(rfp_rows).fillna("")

        all_rfp_list = []
        total_submitted_rfps = 0
        total_declined_rfps = 0

        if not rfp_df.empty:
            if "RFP_End_Date" in rfp_df.columns:
                try:
                    rfp_df["_RFP_End_Date_dt"] = pd.to_datetime(rfp_df["RFP_End_Date"], errors="coerce")
                    if rfp_df["_RFP_End_Date_dt"].dt.tz is not None:
                        rfp_df["_RFP_End_Date_dt"] = rfp_df["_RFP_End_Date_dt"].dt.tz_localize(None)
                except Exception as e:
                    print(f"Error parsing RFP_End_Date: {e}")
                    rfp_df["_RFP_End_Date_dt"] = pd.NaT

                try:
                    rfp_df = rfp_df.sort_values(["_RFP_End_Date_dt", "RFP_ID"], ascending=[True, True])
                except Exception:
                    pass

                for _, row in rfp_df.iterrows():
                    end_dt = row.get("_RFP_End_Date_dt")
                    end_str = end_dt.strftime("%Y-%m-%d %H:%M") if pd.notna(end_dt) else str(row.get("RFP_End_Date", ""))

                    if row.get("participated", "").strip().lower() == "submitted" or row.get("participated", "").strip().lower() == "yes":
                        total_submitted_rfps += 1
                    if row.get("participated", "").strip().lower() == "declined":
                        total_declined_rfps += 1

                    rfp_link = row.get("Link", "") or row.get("link", "")
                    if not rfp_link:
                        rfp_link = URL

                    rfp_data = {
                        "RFP_ID": row.get("RFP_ID", ""),
                        "RFP_End_Date": end_str,
                        "Company_Name": row.get("Company_Name", "") if row.get("Company_Name", "") else "Saudi Electricity Company",
                        "Owner_Name": row.get("owner_name", ""),
                        "Publish_Time": format_publish_time(row.get("publish_time", "")),
                        "participated": row.get("participated", ""),
                        "Link": rfp_link,
                    }

                    all_rfp_list.append(rfp_data)

        end_time = time.time()
        print(f"All RFP data processed in {end_time - start_time:.2f} seconds")

        return {
            "downloaded_rfps": all_rfp_list,
            "total_submitted_rfps": total_submitted_rfps,
            "total_declined_rfps": total_declined_rfps
        }

    except Exception as e:
        print(f"Error fetching all RFP data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching all RFP data: {str(e)}")


# ===== ALL RFP DATA CACHE (TTL) =====
_ALL_RFP_CACHE = {"data": None, "ts": 0}
_ALL_RFP_TTL_SECONDS = DASHBOARD_TTL_SECONDS


def get_all_rfp_data_cached(force_refresh: bool = False):
    from time import time as _now
    now = _now()
    if not force_refresh:
        if _ALL_RFP_CACHE["data"] is not None and (now - _ALL_RFP_CACHE["ts"]) < _ALL_RFP_TTL_SECONDS:
            return _ALL_RFP_CACHE["data"]
    data = get_all_rfp_data()
    _ALL_RFP_CACHE["data"] = data
    _ALL_RFP_CACHE["ts"] = now
    return data


def get_logs_data(top: int = 200):
    try:
        print(f"Starting logs data fetch at {datetime.now()}")
        start_time = time.time()
        logs = _automation_fetch_from_dataverse(top=top)
        print(f"Logs data fetched: {len(logs)} rows")

        for log in logs:
            if log.get('Timestamp'):
                try:
                    timestamp = log['Timestamp']
                    if isinstance(timestamp, str):
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    else:
                        dt = timestamp

                    log['formatted_timestamp'] = dt.strftime('%Y-%m-%d %H:%M:%S')
                    log['_parsed_ts'] = dt
                except Exception as e:
                    print(f"Error formatting timestamp {log.get('Timestamp')}: {e}")
                    log['formatted_timestamp'] = str(log.get('Timestamp', '-'))
                    log['_parsed_ts'] = None
            else:
                log['formatted_timestamp'] = '-'
                log['_parsed_ts'] = None

        try:
            logs.sort(key=lambda x: (x.get('_parsed_ts') is None, x.get('_parsed_ts')), reverse=True)
        except Exception:
            pass

        return logs
    except Exception as e:
        print(f"Error fetching logs data: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching logs data: {str(e)}")


# Short-lived cache for logs page
_LOGS_CACHE = {"data": None, "ts": 0, "top": None}
_LOGS_TTL_SECONDS = LOGS_TTL_SECONDS


def get_logs_data_cached(force_refresh: bool = False, top: int = 200):
    from time import time as _now
    now = _now()
    if not force_refresh and _LOGS_CACHE["data"] is not None and _LOGS_CACHE["top"] == top and (now - _LOGS_CACHE["ts"]) < _LOGS_TTL_SECONDS:
        return _LOGS_CACHE["data"]
    data = get_logs_data(top=top)
    _LOGS_CACHE["data"] = data
    _LOGS_CACHE["ts"] = now
    _LOGS_CACHE["top"] = top
    return data
