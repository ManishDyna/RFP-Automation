"""
Dashboard service - Core dashboard data fetching and caching logic.
Moved from Dashboard/backend/dashboard_backend.py
"""

from core.common_imports import *
from helpers.core_helper import DATAVERSE, get_rfp_activity_data_from_db
from fastapi import HTTPException
from datetime import datetime, timedelta, timezone
import time
from services.system_settings_service import get_setting

# IST offset: UTC+5:30
_IST_OFFSET = timedelta(hours=5, minutes=30)
_IST_TZ = timezone(_IST_OFFSET)


def _ist_to_utc_iso(dt_val) -> str:
    """
    Convert a naive datetime (assumed IST) to UTC ISO 8601 string with 'Z' suffix.
    This allows the frontend browser to correctly display it in the user's local timezone.
    Returns '-' for invalid/empty values.
    """
    if dt_val is None:
        return "-"
    if isinstance(dt_val, str):
        if not dt_val.strip() or dt_val.strip() == "-":
            return "-"
        try:
            dt_val = pd.to_datetime(dt_val, errors="coerce")
            if pd.isna(dt_val):
                return "-"
        except Exception:
            return "-"
    if hasattr(dt_val, 'tzinfo') and dt_val.tzinfo is not None:
        # Already timezone-aware — convert directly to UTC
        utc_dt = dt_val.astimezone(timezone.utc)
    else:
        # Naive datetime — assume IST
        ist_dt = dt_val.replace(tzinfo=_IST_TZ)
        utc_dt = ist_dt.astimezone(timezone.utc)
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

# ===== DASHBOARD DATA CACHE (TTL) =====
import threading
_DASHBOARD_CACHE = {"data": None, "ts": 0}
_DASHBOARD_TTL_SECONDS = get_setting('DASHBOARD_TTL_SECONDS', 300)
_DASHBOARD_CACHE_LOCK = threading.Lock()


def invalidate_dashboard_caches():
    """Invalidate all dashboard-related caches so next fetch gets fresh data."""
    _DASHBOARD_CACHE["data"] = None
    _DASHBOARD_CACHE["ts"] = 0
    _ALL_RFP_CACHE["data"] = None
    _ALL_RFP_CACHE["ts"] = 0


def format_publish_time(publish_time_str):
    """Format publish time string to UTC ISO 8601 (assumes IST input)."""
    if not publish_time_str or publish_time_str == "":
        return "-"

    try:
        if isinstance(publish_time_str, str):
            dt = pd.to_datetime(publish_time_str, errors="coerce")
            if pd.notna(dt):
                return _ist_to_utc_iso(dt)

        if hasattr(publish_time_str, 'strftime'):
            return _ist_to_utc_iso(publish_time_str)

    except Exception as e:
        print(f"Error formatting publish time '{publish_time_str}': {e}")

    return str(publish_time_str)


def get_dashboard_data_cached(force_refresh: bool = False):
    """
    Get dashboard data with caching and stampede prevention.
    Uses double-checked locking to prevent multiple concurrent refreshes.
    """
    from time import time as _now
    now = _now()

    # Quick check without lock (fast path for cache hits)
    if not force_refresh:
        if _DASHBOARD_CACHE["data"] is not None and (now - _DASHBOARD_CACHE["ts"]) < _DASHBOARD_TTL_SECONDS:
            return _DASHBOARD_CACHE["data"]

    # Acquire lock for refresh (prevents cache stampede)
    with _DASHBOARD_CACHE_LOCK:
        # Double-check after acquiring lock (another thread may have refreshed)
        now = _now()
        if not force_refresh:
            if _DASHBOARD_CACHE["data"] is not None and (now - _DASHBOARD_CACHE["ts"]) < _DASHBOARD_TTL_SECONDS:
                return _DASHBOARD_CACHE["data"]

        # Only ONE thread refreshes the cache
        data = get_dashboard_data()
        _DASHBOARD_CACHE["data"] = data
        _DASHBOARD_CACHE["ts"] = now
        return data


def _automation_fetch_from_dataverse(top=200):
    try:
        select_cols = ["RunID", "Timestamp", "Category", "RFP_ID", "Action", "automation_status", "Message"]
        rows = DATAVERSE.get_rows_from_dataverse(
            table_api_name=get_setting('AUTOMATION_LOG_TABLE_API', 'cr673_bahra_automation_log1s'),
            select_columns=select_cols,
            top=top,
            order_by="Timestamp desc",
            table_logical_name=get_setting('AUTOMATION_LOG_TABLE_LOGICAL', 'cr673_bahra_automation_log1'),
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

                # Aggregate Material_Matched / Keyword_Matched at RFP level before dedup
                # If ANY row for an RFP has "Yes", propagate "Yes" to all rows for that RFP
                for col in ["Material_Matched", "Keyword_Matched"]:
                    if col in rfp_df.columns:
                        yes_rfps = set(rfp_df.loc[rfp_df[col].astype(str).str.strip().str.lower() == "yes", "RFP_ID"])
                        rfp_df.loc[rfp_df["RFP_ID"].isin(yes_rfps), col] = "Yes"

                # Deduplicate: Count each RFP_ID only once (keep first occurrence)
                rfp_df = rfp_df.drop_duplicates(subset=["RFP_ID"], keep="first")
                print(f"RFP data after deduplication: {len(rfp_df)} unique RFPs")

                # Vectorized: Normalize Company_Name in dataframe (fix empty/null values)
                rfp_df["Company_Name"] = rfp_df["Company_Name"].fillna("Saudi Electricity Company").replace("", "Saudi Electricity Company")
                unique_companies = set(rfp_df["Company_Name"].unique())
                for company_name in unique_companies:
                    companies_rfps[company_name] = {
                        "open": [],
                        "submitted": [],
                        "saved_draft": [],
                        "declined": []
                    }

                # Vectorized: Count submitted and declined (faster than iterrows)
                participated_lower = rfp_df["participated"].fillna("").str.strip().str.lower()
                total_submitted_rfps = int(((participated_lower == "submitted") | (participated_lower == "yes")).sum())
                total_declined_rfps = int((participated_lower == "declined").sum())

                # Use to_dict('records') for remaining logic (faster than iterrows, safer than itertuples)
                # Use current datetime to hide RFPs where deadline has passed
                now_dt = datetime.now()
                future_count = 0
                past_count = 0
                invalid_date_count = 0

                for row in rfp_df.to_dict('records'):
                    end_dt = row.get("_RFP_End_Date_dt")
                    end_str = _ist_to_utc_iso(end_dt) if pd.notna(end_dt) else str(row.get("RFP_End_Date", ""))

                    # Debug: Track date distribution
                    if pd.isna(end_dt):
                        invalid_date_count += 1
                    elif end_dt >= now_dt:
                        future_count += 1
                    else:
                        past_count += 1

                    # Show only RFPs where deadline has not passed (end date >= current time)
                    if pd.notna(end_dt) and end_dt >= now_dt:
                        rfp_link = row.get("Link", "") or row.get("link", "")
                        if not rfp_link:
                            rfp_link = get_setting('URL', 'https://service.ariba.com/Sourcing.aw/109582016/aw?awh=r&awssk=u9fNiSxN&dard=1#b0')

                        company_name = row.get("Company_Name", "") or "Saudi Electricity Company"

                        # Use Material_Matched / Keyword_Matched directly from Dataverse
                        material_matched_raw = str(row.get("Material_Matched", "") or "").strip()
                        keyword_matched_raw = str(row.get("Keyword_Matched", "") or "").strip()

                        rfp_data = {
                            "RFP_ID": row.get("RFP_ID", ""),
                            "RFP_End_Date": end_str,
                            "Company_Name": company_name,
                            "Owner_Name": row.get("owner_name", ""),
                            "Publish_Time": format_publish_time(row.get("publish_time", "")),
                            "participated": row.get("participated", ""),
                            "Link": rfp_link,
                            "Material_Matched": material_matched_raw,
                            "Keyword_Matched": keyword_matched_raw,
                        }

                        downloaded_rfp_list.append(rfp_data)

                        participation_status = (row.get("participated", "") or "").lower().strip()
                        if participation_status == "no" or participation_status == "":
                            rfp_data["status"] = "open"
                            open_rfp_list.append(rfp_data)
                            companies_rfps[company_name]["open"].append(rfp_data)
                        elif participation_status == "submitted" or participation_status == "yes":
                            rfp_data["status"] = "submitted"
                            submitted_rfp_list.append(rfp_data)
                            companies_rfps[company_name]["submitted"].append(rfp_data)
                        elif participation_status == "declined":
                            rfp_data["status"] = "declined"
                            declined_rfp_list.append(rfp_data)
                            companies_rfps[company_name]["declined"].append(rfp_data)
                        elif participation_status == "saved_draft":
                            rfp_data["status"] = "saved draft"
                            saved_draft_rfp_list.append(rfp_data)
                            companies_rfps[company_name]["saved_draft"].append(rfp_data)

                # Debug: Print date distribution
                print(f"DEBUG: RFP Date Distribution - Future: {future_count}, Past: {past_count}, Invalid: {invalid_date_count}")
                print(f"DEBUG: Current datetime: {now_dt}")
                if not rfp_df.empty and "_RFP_End_Date_dt" in rfp_df.columns:
                    sample_dates = rfp_df["_RFP_End_Date_dt"].head(3).tolist()
                    print(f"DEBUG: Sample end dates: {sample_dates}")

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

        # Get last step details (auto_df is sorted by RunDate descending)
        last_run_id = "-"
        last_run_time = "-"
        last_run_action = "-"
        if not auto_df.empty and "RunDate" in auto_df.columns and auto_df["RunDate"].notna().any():
            last_row = auto_df.iloc[0]
            last_run_time = _ist_to_utc_iso(last_row["RunDate"])
            last_run_id = str(last_row.get("RunID", "-")) if last_row.get("RunID", "") else "-"
            last_run_action = str(last_row.get("Action", "-")) if last_row.get("Action", "") else "-"

        automation_stats = {
            "total_runs": int(len(auto_df)),
            "successful_runs": int((auto_df.get("automation_status", pd.Series(dtype=str)).astype(str).str.lower() == "success").sum()) if not auto_df.empty else 0,
            "failed_runs": int((auto_df.get("automation_status", pd.Series(dtype=str)).astype(str).str.lower() == "failed").sum()) if not auto_df.empty else 0,
            "last_run_time": last_run_time,
            "last_run_id": last_run_id,
            "last_run_action": last_run_action,
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
        import traceback
        traceback.print_exc()
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

        # DEBUG: Check raw data right after fetch
        if not rfp_df.empty and "Material_Matched" in rfp_df.columns:
            raw_yes = rfp_df["Material_Matched"].astype(str).str.strip().str.lower().eq("yes").sum()
            raw_unique_vals = rfp_df["Material_Matched"].astype(str).str.strip().unique().tolist()[:10]
            raw_yes_rfps = rfp_df.loc[rfp_df["Material_Matched"].astype(str).str.strip().str.lower() == "yes", "RFP_ID"].unique().tolist()
            print(f"DEBUG RAW: Material_Matched column exists. Rows with 'Yes': {raw_yes}")
            print(f"DEBUG RAW: Unique Material_Matched values (first 10): {raw_unique_vals}")
            print(f"DEBUG RAW: RFP_IDs with Material_Matched=Yes ({len(raw_yes_rfps)}): {raw_yes_rfps}")
        else:
            print(f"DEBUG RAW: Material_Matched column {'NOT FOUND' if not rfp_df.empty else 'empty df'}. Columns: {list(rfp_df.columns) if not rfp_df.empty else 'N/A'}")

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

                # Aggregate Material_Matched / Keyword_Matched at RFP level before dedup
                # If ANY row for an RFP has "Yes", propagate "Yes" to all rows for that RFP
                for col in ["Material_Matched", "Keyword_Matched"]:
                    if col in rfp_df.columns:
                        yes_rfps = set(rfp_df.loc[rfp_df[col].astype(str).str.strip().str.lower() == "yes", "RFP_ID"])
                        rfp_df.loc[rfp_df["RFP_ID"].isin(yes_rfps), col] = "Yes"

                # Deduplicate: Count each RFP_ID only once (keep first occurrence)
                rfp_df = rfp_df.drop_duplicates(subset=["RFP_ID"], keep="first")
                print(f"All RFP data after deduplication: {len(rfp_df)} unique RFPs")

                # Normalize Company_Name in dataframe (fix empty/null values)
                rfp_df["Company_Name"] = rfp_df["Company_Name"].fillna("Saudi Electricity Company").replace("", "Saudi Electricity Company")

                # Vectorized: Count submitted and declined (faster than iterrows)
                participated_lower = rfp_df["participated"].fillna("").str.strip().str.lower()
                total_submitted_rfps = int(((participated_lower == "submitted") | (participated_lower == "yes")).sum())
                total_declined_rfps = int((participated_lower == "declined").sum())

                # Use to_dict('records') for building list (faster than iterrows, safer than itertuples)
                for row in rfp_df.to_dict('records'):
                    end_dt = row.get("_RFP_End_Date_dt")
                    end_str = _ist_to_utc_iso(end_dt) if pd.notna(end_dt) else str(row.get("RFP_End_Date", ""))

                    rfp_link = row.get("Link", "") or row.get("link", "")
                    if not rfp_link:
                        rfp_link = get_setting('URL', 'https://service.ariba.com/Sourcing.aw/109582016/aw?awh=r&awssk=u9fNiSxN&dard=1#b0')

                    # Use Material_Matched / Keyword_Matched directly from Dataverse
                    material_matched_raw = str(row.get("Material_Matched", "") or "").strip()
                    keyword_matched_raw = str(row.get("Keyword_Matched", "") or "").strip()

                    rfp_data = {
                        "RFP_ID": row.get("RFP_ID", ""),
                        "RFP_End_Date": end_str,
                        "Company_Name": row.get("Company_Name", "") or "Saudi Electricity Company",
                        "Owner_Name": row.get("owner_name", ""),
                        "Publish_Time": format_publish_time(row.get("publish_time", "")),
                        "participated": row.get("participated", ""),
                        "Link": rfp_link,
                        "Material_Matched": material_matched_raw,
                        "Keyword_Matched": keyword_matched_raw,
                    }

                    all_rfp_list.append(rfp_data)

        # Debug: Log Material_Matched / Keyword_Matched value distribution
        mat_yes = sum(1 for r in all_rfp_list if r.get("Material_Matched", "").lower() == "yes")
        mat_no = sum(1 for r in all_rfp_list if r.get("Material_Matched", "").lower() == "no")
        mat_empty = sum(1 for r in all_rfp_list if r.get("Material_Matched", "").strip() == "")
        kw_yes = sum(1 for r in all_rfp_list if r.get("Keyword_Matched", "").lower() == "yes")
        kw_no = sum(1 for r in all_rfp_list if r.get("Keyword_Matched", "").lower() == "no")
        kw_empty = sum(1 for r in all_rfp_list if r.get("Keyword_Matched", "").strip() == "")
        print(f"DEBUG Material_Matched: Yes={mat_yes}, No={mat_no}, Empty={mat_empty}, Total={len(all_rfp_list)}")
        print(f"DEBUG Keyword_Matched: Yes={kw_yes}, No={kw_no}, Empty={kw_empty}, Total={len(all_rfp_list)}")
        # Print sample of first 3 Material_Matched values to check format
        sample_vals = [(r.get("RFP_ID", ""), repr(r.get("Material_Matched", ""))) for r in all_rfp_list[:3]]
        print(f"DEBUG Sample Material_Matched values: {sample_vals}")

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
_ALL_RFP_TTL_SECONDS = get_setting('DASHBOARD_TTL_SECONDS', 300)


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


def get_material_insights_data():
    """
    Build material insights from the existing bahra_rfps table data.
    Uses the same data as RFP Insights (get_all_rfp_data_cached) which already
    has Material_Matched, Keyword_Matched columns populated.
    Calculates all analytics from Material_Matched/Keyword_Matched flags and participated status.
    """
    all_rfp_data = get_all_rfp_data_cached(force_refresh=False)
    downloaded_rfps = all_rfp_data.get("downloaded_rfps") or []

    if not downloaded_rfps:
        return {"materials": [], "stats": {}, "unique_rfps": {}, "item_stats": {}}

    materials_list = []
    company_rfps = {}
    material_matched_count = 0
    keyword_matched_count = 0

    # RFP-level accumulators (calculated from existing Yes/No flags)
    rfps_with_keyword_match = 0
    rfps_with_material_match = 0
    rfps_with_any_match = 0
    submitted_rfp_count = 0
    submitted_with_material_match = 0
    submitted_with_keyword_match = 0

    # Company-wise breakdown for charts
    company_breakdown = {}

    for row in downloaded_rfps:
        rfp_id = row.get("RFP_ID", "")
        company = row.get("Company_Name", "") or "Saudi Electricity Company"
        material_matched = (row.get("Material_Matched") or "No").strip()
        keyword_matched = (row.get("Keyword_Matched") or "No").strip()
        participated = (row.get("participated") or "").strip().lower()

        if company not in company_rfps:
            company_rfps[company] = set()
        company_rfps[company].add(rfp_id)

        # Init company breakdown
        if company not in company_breakdown:
            company_breakdown[company] = {
                "total": 0, "material_matched": 0, "keyword_matched": 0,
                "not_matched": 0, "submitted": 0, "declined": 0, "open": 0,
            }
        company_breakdown[company]["total"] += 1

        is_material = material_matched.lower() == "yes"
        is_keyword = keyword_matched.lower() == "yes"

        if is_material:
            material_matched_count += 1
            rfps_with_material_match += 1
            company_breakdown[company]["material_matched"] += 1
        if is_keyword:
            keyword_matched_count += 1
            rfps_with_keyword_match += 1
            company_breakdown[company]["keyword_matched"] += 1
        if is_material or is_keyword:
            rfps_with_any_match += 1
        if not is_material and not is_keyword:
            company_breakdown[company]["not_matched"] += 1

        # Count submitted/bid RFPs
        is_submitted = participated in ("submitted", "yes")
        if is_submitted:
            submitted_rfp_count += 1
            company_breakdown[company]["submitted"] += 1
            if is_material:
                submitted_with_material_match += 1
            if is_keyword:
                submitted_with_keyword_match += 1
        elif participated == "declined":
            company_breakdown[company]["declined"] += 1
        else:
            company_breakdown[company]["open"] += 1

        materials_list.append({
            "rfp_id": rfp_id,
            "company": company,
            "material_matched": material_matched,
            "keyword_matched": keyword_matched,
            "participated": participated,
        })

    # Build unique RFPs grouped by company for filter dropdown
    unique_rfps = {}
    for comp, rfp_ids in company_rfps.items():
        unique_rfps[comp] = sorted(list(rfp_ids))

    total_rfps = len(materials_list)
    not_matched_count = total_rfps - material_matched_count - keyword_matched_count \
        + len([m for m in materials_list if m["material_matched"].lower() == "yes" and m["keyword_matched"].lower() == "yes"])

    stats = {
        "total_rfps": total_rfps,
        "material_matched_count": material_matched_count,
        "keyword_matched_count": keyword_matched_count,
        "not_matched_count": not_matched_count,
    }

    # Build company chart data (sorted by total descending)
    company_chart_data = sorted(
        [{"company": comp, **counts} for comp, counts in company_breakdown.items()],
        key=lambda x: x["total"],
        reverse=True
    )

    # RFP-level analysis stats (calculated in code from existing flags)
    item_stats = {
        "total_rfps": total_rfps,
        "rfps_with_material_match": rfps_with_material_match,
        "rfps_with_keyword_match": rfps_with_keyword_match,
        "rfps_with_any_match": rfps_with_any_match,
        "rfps_not_matched": not_matched_count,
        "submitted_rfp_count": submitted_rfp_count,
        "submitted_with_material_match": submitted_with_material_match,
        "submitted_with_keyword_match": submitted_with_keyword_match,
        "company_chart_data": company_chart_data,
    }

    return {
        "materials": materials_list,
        "stats": stats,
        "unique_rfps": unique_rfps,
        "item_stats": item_stats,
    }


# ===== MATERIAL INSIGHTS CACHE =====
_MATERIAL_CACHE = {"data": None, "ts": 0}
_MATERIAL_TTL_SECONDS = get_setting('DASHBOARD_TTL_SECONDS', 300)


def get_material_insights_cached(force_refresh: bool = False):
    from time import time as _now
    now = _now()
    if not force_refresh:
        if _MATERIAL_CACHE["data"] is not None and (now - _MATERIAL_CACHE["ts"]) < _MATERIAL_TTL_SECONDS:
            return _MATERIAL_CACHE["data"]
    data = get_material_insights_data()
    _MATERIAL_CACHE["data"] = data
    _MATERIAL_CACHE["ts"] = now
    return data


# ===== RAW RFP DATA CACHE (with Matched_Data) =====
_RAW_RFP_CACHE = {"data": None, "ts": 0}


def get_raw_rfp_data_cached(force_refresh=False):
    """Cache raw Dataverse rows (with Matched_Data) for material insights."""
    from time import time as _now
    now = _now()
    if not force_refresh:
        if _RAW_RFP_CACHE["data"] is not None and (now - _RAW_RFP_CACHE["ts"]) < _MATERIAL_TTL_SECONDS:
            return _RAW_RFP_CACHE["data"]
    data = get_rfp_activity_data_from_db()
    _RAW_RFP_CACHE["data"] = data
    _RAW_RFP_CACHE["ts"] = now
    return data


def _get_keywords_list():
    """Load the unique keywords from the master CSV file."""
    import csv as _csv
    import os as _os
    keywords_path = _os.path.join("ALLRFPs", "unique_keywords.csv")
    keywords = []
    try:
        with open(keywords_path, 'r') as f:
            reader = _csv.reader(f)
            next(reader, None)  # skip header
            for row in reader:
                if row and row[0].strip():
                    keywords.append(row[0].strip())
    except Exception as e:
        print(f"Error loading keywords CSV: {e}")
    return keywords


_KEYWORDS_CACHE = {"data": None}


def _get_keywords_list_cached():
    if _KEYWORDS_CACHE["data"] is not None:
        return _KEYWORDS_CACHE["data"]
    _KEYWORDS_CACHE["data"] = _get_keywords_list()
    return _KEYWORDS_CACHE["data"]


def _add_to_material_group(material_groups, material_code, material_desc, rfp_id, company, rfp_end_date, participated, match_method, extracted=""):
    """Helper: add a material entry to material_groups dict."""
    if not material_code:
        return
    if material_code not in material_groups:
        material_groups[material_code] = {
            "material_code": material_code,
            "material_description": material_desc,
            "rfp_count": 0,
            "rfps": [],
            "companies": set(),
            "submitted_count": 0,
        }
    group = material_groups[material_code]
    existing_rfp_ids = {r["rfp_id"] for r in group["rfps"]}
    if rfp_id not in existing_rfp_ids:
        group["rfps"].append({
            "rfp_id": rfp_id,
            "company": company,
            "rfp_end_date": str(rfp_end_date),
            "participated": participated,
            "match_method": match_method,
            "extracted_material": extracted,
        })
        group["rfp_count"] += 1
        if company:
            group["companies"].add(company)
        if participated in ("submitted", "yes"):
            group["submitted_count"] += 1


def _add_to_keyword_group(keyword_groups, kw, rfp_id, company, rfp_end_date, participated, material_code, material_desc):
    """Helper: add a keyword entry to keyword_groups dict."""
    kw = kw.strip()
    if not kw:
        return
    if kw not in keyword_groups:
        keyword_groups[kw] = {
            "keyword": kw,
            "rfp_count": 0,
            "rfps": [],
            "companies": set(),
            "submitted_count": 0,
            "material_codes": set(),
        }
    kw_group = keyword_groups[kw]
    existing_kw_rfps = {r["rfp_id"] for r in kw_group["rfps"]}
    if rfp_id not in existing_kw_rfps:
        kw_group["rfps"].append({
            "rfp_id": rfp_id,
            "company": company,
            "rfp_end_date": str(rfp_end_date),
            "participated": participated,
            "material_code": material_code,
            "material_description": material_desc,
        })
        kw_group["rfp_count"] += 1
        if company:
            kw_group["companies"].add(company)
        if participated in ("submitted", "yes"):
            kw_group["submitted_count"] += 1
    if material_code:
        kw_group["material_codes"].add(material_code)


def get_material_insights_grouped_data():
    """
    Build material-code-centric and keyword-centric views.

    Primary path: uses direct columns (Material_Code, Material_Description,
    Matched_Keywords) from the Dataverse table.
    Fallback path: parses Matched_Data JSON + CSV keyword cross-reference
    for rows that don't have the direct columns populated.
    """
    import json as _json

    raw_rows = get_raw_rfp_data_cached()
    if not raw_rows:
        return {"materials": [], "keywords": [], "stats": {}, "top_materials_chart": [], "keyword_chart": []}

    keywords_list = _get_keywords_list_cached()

    material_groups = {}  # material_code -> group dict
    keyword_groups = {}   # keyword -> group dict
    all_rfp_ids_with_matches = set()

    for row in raw_rows:
        rfp_id = row.get("RFP_ID", "")
        company = (row.get("Company_Name", "") or "").strip()
        participated = (row.get("participated") or "").strip().lower()
        rfp_end_date = row.get("RFP_End_Date", "")

        # --- Direct columns (primary path) ---
        direct_material_code = (row.get("Material_Code", "") or "").strip()
        direct_material_desc = (row.get("Material_Description", "") or "").strip()
        direct_matched_keywords = (row.get("Matched_Keywords", "") or "").strip()
        material_matched_flag = (row.get("Material_Matched", "") or "").strip().lower()
        keyword_matched_flag = (row.get("Keyword_Matched", "") or "").strip().lower()

        if direct_material_code:
            # PRIMARY PATH: use direct columns
            all_rfp_ids_with_matches.add(rfp_id)

            # Determine match method from flags
            if keyword_matched_flag == "yes":
                match_method = "keyword"
            else:
                match_method = "exact"

            # Material grouping
            _add_to_material_group(
                material_groups, direct_material_code, direct_material_desc,
                rfp_id, company, rfp_end_date, participated, match_method
            )

            # Keyword grouping from Matched_Keywords column (comma-separated)
            if direct_matched_keywords:
                for kw in direct_matched_keywords.split(","):
                    _add_to_keyword_group(
                        keyword_groups, kw, rfp_id, company, rfp_end_date,
                        participated, direct_material_code, direct_material_desc
                    )

        else:
            # FALLBACK PATH: parse Matched_Data JSON
            matched_data_str = row.get("Matched_Data", "") or ""
            if not matched_data_str.strip():
                continue

            try:
                matched_items = _json.loads(matched_data_str)
            except (ValueError, TypeError):
                continue

            if not isinstance(matched_items, list):
                continue

            all_rfp_ids_with_matches.add(rfp_id)

            for item in matched_items:
                # Skip unmatched materials (new format has is_matched field)
                if item.get("is_matched") is False:
                    continue
                material_code = str(item.get("Material", "") or "").strip()
                material_desc = str(item.get("Material Description", "") or "").strip()
                match_method = str(item.get("MatchMethod", "exact") or "exact").lower()
                extracted = str(item.get("ExtractedMaterial", "") or "").strip()

                # Material grouping
                _add_to_material_group(
                    material_groups, material_code, material_desc,
                    rfp_id, company, rfp_end_date, participated, match_method, extracted
                )

                # Keyword grouping via CSV cross-reference
                if match_method == "keyword":
                    desc_upper = material_desc.upper()
                    name_upper = str(item.get("ColumnName", "") or "").upper()
                    search_text = desc_upper + " " + name_upper + " " + extracted.upper()

                    for kw in keywords_list:
                        if kw.upper() in search_text:
                            _add_to_keyword_group(
                                keyword_groups, kw, rfp_id, company, rfp_end_date,
                                participated, material_code, material_desc
                            )

    # Convert sets to sorted lists for JSON serialization
    materials_list = sorted(material_groups.values(), key=lambda x: x["rfp_count"], reverse=True)
    for m in materials_list:
        m["companies"] = sorted(list(m["companies"]))

    keywords_list_result = sorted(keyword_groups.values(), key=lambda x: x["rfp_count"], reverse=True)
    for k in keywords_list_result:
        k["companies"] = sorted(list(k["companies"]))
        k["material_codes"] = sorted(list(k["material_codes"]))

    # Count submitted RFPs across all matched
    submitted_count = sum(
        1 for row in raw_rows
        if (row.get("participated") or "").strip().lower() in ("submitted", "yes")
        and row.get("RFP_ID", "") in all_rfp_ids_with_matches
    )

    stats = {
        "total_unique_materials": len(materials_list),
        "total_unique_keywords": len(keywords_list_result),
        "total_rfps_with_matches": len(all_rfp_ids_with_matches),
        "total_material_rfp_links": sum(m["rfp_count"] for m in materials_list),
        "total_keyword_rfp_links": sum(k["rfp_count"] for k in keywords_list_result),
        "submitted_rfp_count": submitted_count,
    }

    # Chart data: top 10 materials by RFP count
    top_materials_chart = [
        {"material": m["material_code"], "description": m["material_description"][:40], "rfp_count": m["rfp_count"]}
        for m in materials_list[:10]
    ]

    # Chart data: keyword frequency
    keyword_chart = [
        {"keyword": k["keyword"], "rfp_count": k["rfp_count"]}
        for k in keywords_list_result
    ]

    return {
        "materials": materials_list,
        "keywords": keywords_list_result,
        "stats": stats,
        "top_materials_chart": top_materials_chart,
        "keyword_chart": keyword_chart,
    }


# ===== MATERIAL INSIGHTS GROUPED CACHE =====
_MATERIAL_GROUPED_CACHE = {"data": None, "ts": 0}


def get_material_insights_grouped_cached(force_refresh=False):
    from time import time as _now
    now = _now()
    if not force_refresh:
        if _MATERIAL_GROUPED_CACHE["data"] is not None and (now - _MATERIAL_GROUPED_CACHE["ts"]) < _MATERIAL_TTL_SECONDS:
            return _MATERIAL_GROUPED_CACHE["data"]
    data = get_material_insights_grouped_data()
    _MATERIAL_GROUPED_CACHE["data"] = data
    _MATERIAL_GROUPED_CACHE["ts"] = now
    return data


def get_logs_data(top: int = 5000):
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
            # Sort logs by timestamp, newest first. None timestamps go to the end.
            from datetime import datetime as dt_type
            min_dt = dt_type.min.replace(tzinfo=None)
            def sort_key(x):
                ts = x.get('_parsed_ts')
                if ts is None:
                    return (0, min_dt)  # None timestamps sorted last
                # Make datetime naive for comparison if it has timezone
                if hasattr(ts, 'tzinfo') and ts.tzinfo is not None:
                    ts = ts.replace(tzinfo=None)
                return (1, ts)  # Valid timestamps sorted by date
            logs.sort(key=sort_key, reverse=True)
        except Exception as e:
            print(f"Error sorting logs: {e}")

        return logs
    except Exception as e:
        print(f"Error fetching logs data: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching logs data: {str(e)}")


# Short-lived cache for logs page
_LOGS_CACHE = {"data": None, "ts": 0, "top": None}
_LOGS_TTL_SECONDS = get_setting('LOGS_TTL_SECONDS', 300)


def get_logs_data_cached(force_refresh: bool = False, top: int = 5000):
    from time import time as _now
    now = _now()
    if not force_refresh and _LOGS_CACHE["data"] is not None and _LOGS_CACHE["top"] == top and (now - _LOGS_CACHE["ts"]) < _LOGS_TTL_SECONDS:
        return _LOGS_CACHE["data"]
    data = get_logs_data(top=top)
    _LOGS_CACHE["data"] = data
    _LOGS_CACHE["ts"] = now
    _LOGS_CACHE["top"] = top
    return data
