import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from core.common_imports import *
from helpers.core_helper import DATAVERSE, get_rfp_activity_data_from_db
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta
import json
import time
from functools import lru_cache
from config.config import *

# ===== DASHBOARD DATA CACHE (TTL) =====
# Short-lived in-memory cache to speed up soft navigations
_DASHBOARD_CACHE = {"data": None, "ts": 0}
# Use globally configured TTL
_DASHBOARD_TTL_SECONDS = DASHBOARD_TTL_SECONDS

def format_publish_time(publish_time_str):
    """Format publish time string for display"""
    if not publish_time_str or publish_time_str == "":
        return "-"
    
    try:
        # Try to parse the publish time string
        if isinstance(publish_time_str, str):
            # Handle different possible formats
            if "/" in publish_time_str and ("AM" in publish_time_str or "PM" in publish_time_str):
                # Format like "10/23/2025 7:20 PM"
                dt = pd.to_datetime(publish_time_str, errors="coerce")
                if pd.notna(dt):
                    return dt.strftime("%Y-%m-%d %H:%M")
            elif "T" in publish_time_str:
                # ISO format
                dt = pd.to_datetime(publish_time_str, errors="coerce")
                if pd.notna(dt):
                    return dt.strftime("%Y-%m-%d %H:%M")
        
        # If it's already a datetime object
        if hasattr(publish_time_str, 'strftime'):
            return publish_time_str.strftime("%Y-%m-%d %H:%M")
            
    except Exception as e:
        print(f"Error formatting publish time '{publish_time_str}': {e}")
    
    # Return original string if formatting fails
    return str(publish_time_str)

def get_dashboard_data_cached(force_refresh: bool = False):
    from time import time as _now
    now = _now()
    if not force_refresh:
        if _DASHBOARD_CACHE["data"] is not None and (now - _DASHBOARD_CACHE["ts"]) < _DASHBOARD_TTL_SECONDS:
            return _DASHBOARD_CACHE["data"]
    # Miss or forced refresh → compute fresh
    data = get_dashboard_data()
    _DASHBOARD_CACHE["data"] = data
    _DASHBOARD_CACHE["ts"] = now
    return data

def _automation_fetch_from_dataverse(top=200):  # Reduced from 5000
    try:
        # Using display names so it's easy to work with
        select_cols = ["RunID", "Timestamp", "Category", "RFP_ID", "Action", "automation_status", "Message"]
        
        # Remove date filtering for now to avoid type mismatch errors
        # We'll filter in Python after fetching the data
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
        # Return empty list if query fails
        return []

def get_dashboard_data():
    try:
        print(f"Starting dashboard data fetch at {datetime.now()}")
        start_time = time.time()
        
        # --- Automation (Dataverse) with caching ---
        auto_rows = _automation_fetch_from_dataverse()
        print(f"Automation data fetched: {len(auto_rows)} rows")
        
        # Handle empty data gracefully
        if not auto_rows:
            auto_df = pd.DataFrame()
        else:
            auto_df = pd.DataFrame(auto_rows).fillna("")
        # Normalize Timestamp -> RunDate
        if "Timestamp" in auto_df.columns:
            try:
                auto_df["RunDate"] = pd.to_datetime(auto_df["Timestamp"], errors="coerce")
            except Exception as e:
                print(f"Error converting Timestamp to datetime: {e}")
                auto_df["RunDate"] = pd.NaT
        else:
            auto_df["RunDate"] = pd.NaT
        
        # Filter to last 30 days in Python to avoid Dataverse query issues
        if not auto_df.empty and "RunDate" in auto_df.columns:
            try:
                # Convert timezone-aware datetimes to timezone-naive for comparison
                if auto_df["RunDate"].dt.tz is not None:
                    auto_df["RunDate"] = auto_df["RunDate"].dt.tz_localize(None)
                
                thirty_days_ago = datetime.now() - timedelta(days=30)
                auto_df = auto_df[auto_df["RunDate"] >= thirty_days_ago]
                auto_df = auto_df.dropna(subset=["RunDate"]).sort_values("RunDate", ascending=False)
            except Exception as e:
                print(f"Error filtering automation data by date: {e}")
                # Continue with unfiltered data
        
        print(f"Automation data after filtering: {len(auto_df)} rows")

        # --- RFP Activity (Dataverse) with caching ---
        rfp_rows = get_rfp_activity_data_from_db()

        print(f"RFP data fetched: {len(rfp_rows)} rows")

        # Handle empty data gracefully
        if not rfp_rows:
            rfp_df = pd.DataFrame()
        else:
            rfp_df = pd.DataFrame(rfp_rows).fillna("")

        # Prepare RFPs grouped by company
        downloaded_rfp_list = []
        open_rfp_list = []
        submitted_rfp_list = []
        saved_draft_rfp_list = []
        declined_rfp_list = []
        
        # Group RFPs by company
        companies_rfps = {}  # {company_name: {"open": [], "submitted": [], "saved_draft": [], "declined": []}}
        unique_companies = set()
        total_submitted_rfps = 0
        total_declined_rfps = 0
        
        if not rfp_df.empty:
            # Normalize/parse end date
            if "RFP_End_Date" in rfp_df.columns:
                try:
                    rfp_df["_RFP_End_Date_dt"] = pd.to_datetime(rfp_df["RFP_End_Date"], errors="coerce")
                    # Convert tz-aware to naive for safe sort/format
                    if rfp_df["_RFP_End_Date_dt"].dt.tz is not None:
                        rfp_df["_RFP_End_Date_dt"] = rfp_df["_RFP_End_Date_dt"].dt.tz_localize(None)
                except Exception as e:
                    print(f"Error parsing RFP_End_Date: {e}")
                    rfp_df["_RFP_End_Date_dt"] = pd.NaT

                # Sort ascending by end date
                try:
                    rfp_df = rfp_df.sort_values(["_RFP_End_Date_dt", "RFP_ID"], ascending=[True, True])
                except Exception:
                    pass

                # First pass: Extract ALL unique companies from database (regardless of end date)
                for _, row in rfp_df.iterrows():
                    company_name = row.get("Company_Name", "") if row.get("Company_Name", "") else "Saudi Electricity Company"
                    unique_companies.add(company_name)
                    # Initialize company structure for all companies
                    if company_name not in companies_rfps:
                        companies_rfps[company_name] = {
                            "open": [],
                            "submitted": [],
                            "saved_draft": [],
                            "declined": []
                        }
                
                # Second pass: Build lightweight list for UI grouped by company (only future RFPs)
                for _, row in rfp_df.iterrows():
                    end_dt = row.get("_RFP_End_Date_dt")
                    end_str = end_dt.strftime("%Y-%m-%d %H:%M") if pd.notna(end_dt) else str(row.get("RFP_End_Date", ""))
                    
                    if row.get("participated", "").strip().lower() == "submitted" or row.get("participated", "").strip().lower() == "yes":
                        total_submitted_rfps += 1
                    if row.get("participated", "").strip().lower() == "declined":
                        total_declined_rfps += 1
                    # Only show RFPs where end date is today or in the future
                    # Skip if end_dt is NaT or past date
                    if pd.notna(end_dt) and end_dt >= datetime.now():
                        # Get RFP link, use base Ariba URL as fallback if not available
                        rfp_link = row.get("Link", "") or row.get("link", "")
                        if not rfp_link:
                            # Fallback to base Ariba portal URL if link is not stored
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
                            # "Email_Status": row.get("Email_Status", "")
                        }
                        
                        # Add to main list
                        downloaded_rfp_list.append(rfp_data)
                        
                        # Categorize by participation status and add to company group
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


        # Fallback: no date available → no month split
        saved_rfps = int(len(rfp_df))
        prev_saved_rfps = 0
        downloaded_rfps = saved_rfps
        prev_downloaded_rfps = 0

       # RFP stats in the format expected by frontend
        rfp_stats = {
            "total_rfps": saved_rfps,
            "downloaded_rfps": downloaded_rfps,
            "prev_total_rfps": prev_saved_rfps,
            "prev_downloaded_rfps": prev_downloaded_rfps,
        }

        # Automation summary snapshot for UI cards
        automation_stats = {
            "total_runs": int(len(auto_df)),
            "successful_runs": int((auto_df.get("automation_status", pd.Series(dtype=str)).astype(str).str.lower() == "success").sum()) if not auto_df.empty else 0,
            "failed_runs": int((auto_df.get("automation_status", pd.Series(dtype=str)).astype(str).str.lower() == "failed").sum()) if not auto_df.empty else 0,
            "last_run_time": auto_df["RunDate"].max().strftime("%Y-%m-%d %H:%M") if ("RunDate" in auto_df.columns and auto_df["RunDate"].notna().any()) else "-"
        }

        # Get unique companies list (sorted)
        unique_companies_list = sorted(list(unique_companies))
        
        # Unified payload
        data = {
            "rfp": rfp_stats,
            "automation": automation_stats,
            # "events": events,
            # "logs": all_logs
            "downloaded_rfps": downloaded_rfp_list,
            "open_rfps": open_rfp_list,
            "submitted_rfps": submitted_rfp_list,
            "declined_rfps": declined_rfp_list,
            "saved_draft_rfps": saved_draft_rfp_list,
            "total_submitted_rfps": total_submitted_rfps,
            "total_declined_rfps": total_declined_rfps,
            "companies_rfps": companies_rfps,  # RFPs grouped by company
            "unique_companies": unique_companies_list  # List of unique company names
        }
        
        end_time = time.time()
        print(f"Dashboard data processed in {end_time - start_time:.2f} seconds")
        
        return data

    except Exception as e:
        print(f"Error building dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error building dashboard: {str(e)}")

# I want to add a function to get the logs data
def get_all_rfp_data():
    """
    Get all RFP data from database without date filtering (includes past, present, and future RFPs).
    This is used for the RFP Details page where users need to see all historical data.
    """
    try:
        print(f"Starting all RFP data fetch at {datetime.now()}")
        start_time = time.time()
        
        # --- RFP Activity (Dataverse) ---
        rfp_rows = get_rfp_activity_data_from_db()
        print(f"RFP data fetched: {len(rfp_rows)} rows")

        # Handle empty data gracefully
        if not rfp_rows:
            rfp_df = pd.DataFrame()
        else:
            rfp_df = pd.DataFrame(rfp_rows).fillna("")

        # Prepare all RFPs list (no date filtering)
        all_rfp_list = []
        total_submitted_rfps = 0
        total_declined_rfps = 0
        
        if not rfp_df.empty:
            # Normalize/parse end date
            if "RFP_End_Date" in rfp_df.columns:
                try:
                    rfp_df["_RFP_End_Date_dt"] = pd.to_datetime(rfp_df["RFP_End_Date"], errors="coerce")
                    # Convert tz-aware to naive for safe sort/format
                    if rfp_df["_RFP_End_Date_dt"].dt.tz is not None:
                        rfp_df["_RFP_End_Date_dt"] = rfp_df["_RFP_End_Date_dt"].dt.tz_localize(None)
                except Exception as e:
                    print(f"Error parsing RFP_End_Date: {e}")
                    rfp_df["_RFP_End_Date_dt"] = pd.NaT

                # Sort ascending by end date
                try:
                    rfp_df = rfp_df.sort_values(["_RFP_End_Date_dt", "RFP_ID"], ascending=[True, True])
                except Exception:
                    pass

                # Build list for all RFPs (no date filter - includes past, present, and future)
                for _, row in rfp_df.iterrows():
                    end_dt = row.get("_RFP_End_Date_dt")
                    end_str = end_dt.strftime("%Y-%m-%d %H:%M") if pd.notna(end_dt) else str(row.get("RFP_End_Date", ""))
                    
                    if row.get("participated", "").strip().lower() == "submitted" or row.get("participated", "").strip().lower() == "yes":
                        total_submitted_rfps += 1
                    if row.get("participated", "").strip().lower() == "declined":
                        total_declined_rfps += 1
                    
                    # Include all RFPs regardless of date (past, present, future)
                    # Get RFP link, use base Ariba URL as fallback if not available
                    rfp_link = row.get("Link", "") or row.get("link", "")
                    if not rfp_link:
                        # Fallback to base Ariba portal URL if link is not stored
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
                    
                    # Add to main list (no date filtering)
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
# Cache for all RFP data (including past dates) used in RFP Details page
_ALL_RFP_CACHE = {"data": None, "ts": 0}
# Use globally configured TTL
_ALL_RFP_TTL_SECONDS = DASHBOARD_TTL_SECONDS

def get_all_rfp_data_cached(force_refresh: bool = False):
    from time import time as _now
    now = _now()
    if not force_refresh:
        if _ALL_RFP_CACHE["data"] is not None and (now - _ALL_RFP_CACHE["ts"]) < _ALL_RFP_TTL_SECONDS:
            return _ALL_RFP_CACHE["data"]
    # Miss or forced refresh → compute fresh
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
        
        # Format timestamps for display
        for log in logs:
            if log.get('Timestamp'):
                try:
                    # Convert timestamp to datetime and format as string
                    timestamp = log['Timestamp']
                    if isinstance(timestamp, str):
                        # Try to parse string timestamp
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

        # Sort logs by timestamp descending (latest first)
        try:
            logs.sort(key=lambda x: (x.get('_parsed_ts') is None, x.get('_parsed_ts')), reverse=True)
        except Exception as _:
            pass
        
        return logs
    except Exception as e:
        print(f"Error fetching logs data: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching logs data: {str(e)}")

# Short-lived cache for logs page
_LOGS_CACHE = {"data": None, "ts": 0, "top": None}
# Use globally configured TTL
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