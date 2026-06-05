"""
Dashboard service - Core dashboard data fetching and caching logic.
Moved from Dashboard/backend/dashboard_backend.py
"""

from core.common_imports import *
from helpers.core_helper import DATAVERSE, get_rfp_activity_data_from_db, get_rfp_activity_data_lightweight, get_matched_data_for_rfps
from fastapi import HTTPException
from datetime import datetime, timedelta, timezone
import time
from services.system_settings_service import get_setting

# IST offset: UTC+5:30
_IST_OFFSET = timedelta(hours=5, minutes=30)
_IST_TZ = timezone(_IST_OFFSET)


def _derive_match_flags(matched_data_str):
    """Derive Material_Matched, Keyword_Matched, and match percentage from Matched_Data JSON."""
    material_matched, keyword_matched = "No", "No"
    match_pct_data = None
    if matched_data_str and str(matched_data_str).strip():
        try:
            data = json.loads(str(matched_data_str))

            # New categorized format (dict with summary)
            if isinstance(data, dict) and "summary" in data:
                s = data["summary"]
                exact = s.get("exact_match_count", 0)
                keyword = s.get("keyword_match_count", 0)
                if exact + keyword > 0:
                    material_matched = "Yes"
                if keyword > 0:
                    keyword_matched = "Yes"
                match_pct_data = {
                    "match_percentage": s.get("match_percentage", 0),
                    "total_materials": data.get("total_items", 0),
                    "matched_count": exact + keyword,
                }

            # Old flat format (list) — backward compatibility
            elif isinstance(data, list):
                for item in data:
                    if item.get("is_matched"):
                        material_matched = "Yes"
                        if item.get("MatchMethod", "").lower() == "keyword":
                            keyword_matched = "Yes"
                if data and any("is_matched" in item for item in data):
                    total = len(data)
                    matched = sum(1 for item in data if bool(item.get("is_matched", True)))
                    match_pct_data = {
                        "match_percentage": round((matched / total * 100) if total > 0 else 0, 1),
                        "total_materials": total,
                        "matched_count": matched,
                    }
        except (json.JSONDecodeError, TypeError):
            pass
    return material_matched, keyword_matched, match_pct_data


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


def _get_system_action_sets():
    # Returns (submitted_ids, declined_ids).
    # Source of truth: the RFP status-history table cr673_bhara_rfp_statuses.
    # We read the `to_this` column — it records the status the RFP
    # transitioned INTO. Our automation writes `to_this='saved_draft'` when
    # it submits via the portal, and `to_this='declined'` when it declines.
    # We dedupe by rfp_id so each RFP is counted at most once even if it
    # went through multiple transitions.
    status_api = get_setting("RFP_STATUS_TABLE_API", "cr673_bhara_rfp_statuses")
    status_logical = get_setting("RFP_STATUS_TABLE_LOGICAL", "cr673_bhara_rfp_status")
    submitted, declined = set(), set()
    try:
        rows = DATAVERSE.get_all_rows(
            table_api_name=status_api,
            table_logical_name=status_logical,
            use_display_names=True,
        )
    except Exception as e:
        print(f"⚠ _get_system_action_sets: rfp_statuses read failed: {e}")
        return submitted, declined

    def _find_key(row, candidates):
        keys_lower = {k.lower().replace(" ", "").replace("_", ""): k for k in row.keys()}
        for c in candidates:
            norm = c.lower().replace(" ", "").replace("_", "")
            if norm in keys_lower:
                return keys_lower[norm]
        return None

    rfp_key = None
    to_key = None
    for r in rows or []:
        if rfp_key is None:
            rfp_key = _find_key(r, ["RFP_ID", "rfp_id", "rfpreference", "RFP Reference"])
        if to_key is None:
            to_key = _find_key(r, ["to_this", "tothis", "currentstatus", "CurrentStatus"])
        if rfp_key and to_key:
            break

    if not rfp_key or not to_key:
        print(f"⚠ _get_system_action_sets: could not resolve rfp_id or to_this columns (rfp_key={rfp_key}, to_key={to_key}). Sample row keys: {list((rows[0] if rows else {}).keys())}")
        return submitted, declined

    for r in rows or []:
        raw_rid = r.get(rfp_key)
        rid = (raw_rid.strip() if isinstance(raw_rid, str) else str(raw_rid or "").strip())
        if not rid:
            continue
        raw_to = r.get(to_key)
        to_val = (raw_to.strip().lower() if isinstance(raw_to, str) else str(raw_to or "").strip().lower())
        if to_val == "saved_draft":
            submitted.add(rid)
        elif to_val == "declined":
            declined.add(rid)

    print(f"_get_system_action_sets: rfp_statuses → submitted={len(submitted)}, declined={len(declined)} (from {len(rows or [])} status rows)")
    return submitted, declined


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

        # --- Parallel server-side counts + future RFP fetch ---
        _table_api = get_setting("RFP_ACTIVITY_LOG_TABLE_API", "cr673_bahra_rfps_v2s")
        _table_logical = get_setting("RFP_ACTIVITY_LOG_TABLE_LOGICAL", "cr673_bahra_rfps_v2")
        now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

        from concurrent.futures import ThreadPoolExecutor, as_completed

        def _count(label, filter_expr=None):
            c = DATAVERSE.count_rows(_table_api, filter_expr=filter_expr, table_logical_name=_table_logical, use_display_names=True)
            return label, c

        def _fetch_future():
            return DATAVERSE.get_all_rows(
                table_api_name=_table_api,
                select_columns=["RFP_ID", "Email_Status", "RFP_End_Date", "owner_name", "publish_time", "Company_Name", "participated", "Link"],
                filter_expr=f"RFP_End_Date ge {now_iso}",
                table_logical_name=_table_logical,
                use_display_names=True,
            )

        def _fetch_publish_timeline():
            """Pull only publish_time across all rows. publish_time is a TEXT
            column (e.g. '2/23/2026 8:10 PM'), so OData $orderby is unreliable
            — we parse every value with pd.to_datetime and take min/max in
            Python. We DO want publish_time (not createdon) because createdon
            reflects when each row was inserted into Dataverse, which is much
            more recent than the actual portal publish dates."""
            return DATAVERSE.get_all_rows(
                table_api_name=_table_api,
                select_columns=["publish_time"],
                table_logical_name=_table_logical,
                use_display_names=True,
            )

        total_all_rfps = 0
        total_submitted_rfps = 0
        total_declined_rfps = 0
        total_open_rfps = 0
        total_not_participated_rfps = 0
        rfp_rows = []
        publish_timeline_rows = []

        try:
            with ThreadPoolExecutor(max_workers=7) as executor:
                futures = {
                    executor.submit(_count, "total"): "total",
                    executor.submit(_count, "submitted", "participated eq 'submitted' or participated eq 'yes'"): "submitted",
                    executor.submit(_count, "declined", "participated eq 'declined'"): "declined",
                    executor.submit(_count, "open", f"RFP_End_Date ge {now_iso} and (participated eq '' or participated eq 'no' or participated eq null)"): "open",
                    executor.submit(_count, "not_participated", f"RFP_End_Date lt {now_iso} and (participated eq '' or participated eq 'no' or participated eq null)"): "not_participated",
                    executor.submit(_fetch_future): "future_rows",
                    executor.submit(_fetch_publish_timeline): "publish_timeline",
                }
                for future in as_completed(futures):
                    key = futures[future]
                    try:
                        result = future.result()
                        if key == "future_rows":
                            rfp_rows = result
                        elif key == "publish_timeline":
                            publish_timeline_rows = result
                        else:
                            label, count = result
                            if label == "total": total_all_rfps = count
                            elif label == "submitted": total_submitted_rfps = count
                            elif label == "declined": total_declined_rfps = count
                            elif label == "open": total_open_rfps = count
                            elif label == "not_participated": total_not_participated_rfps = count
                    except Exception as e:
                        print(f"  Parallel task {key} failed: {e}")

            print(f"Parallel fetch done: total={total_all_rfps}, submitted={total_submitted_rfps}, declined={total_declined_rfps}, open={total_open_rfps}, not_participated={total_not_participated_rfps}, future_rows={len(rfp_rows)}")
        except Exception as e:
            print(f"Parallel fetch failed, falling back to full fetch: {e}")
            rfp_rows = get_rfp_activity_data_lightweight()
            total_all_rfps = len(rfp_rows)

        print(f"Future RFPs fetched: {len(rfp_rows)} rows")

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

        if not rfp_df.empty:
            # Parse dates (now ISO format from Dataverse datetime column)
            if "RFP_End_Date" in rfp_df.columns:
                try:
                    rfp_df["_RFP_End_Date_dt"] = pd.to_datetime(rfp_df["RFP_End_Date"], errors="coerce")
                    if rfp_df["_RFP_End_Date_dt"].dt.tz is not None:
                        rfp_df["_RFP_End_Date_dt"] = rfp_df["_RFP_End_Date_dt"].dt.tz_localize(None)
                except Exception as e:
                    print(f"Error parsing RFP_End_Date: {e}")
                    rfp_df["_RFP_End_Date_dt"] = pd.NaT

                rfp_df = rfp_df.drop_duplicates(subset=["RFP_ID"], keep="first")
                print(f"Future RFPs after dedup: {len(rfp_df)}")

                # Fallback: if server-side counts failed, compute from full data
                if total_all_rfps == 0:
                    all_rfp_rows = get_rfp_activity_data_lightweight()
                    all_df = pd.DataFrame(all_rfp_rows).fillna("")
                    all_df = all_df.drop_duplicates(subset=["RFP_ID"], keep="first")
                    total_all_rfps = len(all_df)
                    participated_lower = all_df["participated"].fillna("").str.strip().str.lower()
                    total_submitted_rfps = int(((participated_lower == "submitted") | (participated_lower == "yes")).sum())
                    total_declined_rfps = int((participated_lower == "declined").sum())
                    all_df["_dt"] = pd.to_datetime(all_df["RFP_End_Date"], errors="coerce")
                    now_dt = datetime.now()
                    open_mask = participated_lower.isin(["", "no", "open", "not participated"])
                    total_open_rfps = int((open_mask & (all_df["_dt"].notna() & (all_df["_dt"] >= now_dt))).sum())
                    total_not_participated_rfps = int((open_mask & (all_df["_dt"].notna() & (all_df["_dt"] < now_dt))).sum())

                # Fetch Matched_Data only for future RFPs
                future_rfp_ids = rfp_df["RFP_ID"].tolist()
                matched_data_map = get_matched_data_for_rfps(future_rfp_ids)

                # Companies
                rfp_df["Company_Name"] = rfp_df["Company_Name"].fillna("Saudi Energy").replace("", "Saudi Energy")
                unique_companies = set(rfp_df["Company_Name"].unique())
                for cn in unique_companies:
                    companies_rfps[cn] = {"open": [], "submitted": [], "saved_draft": [], "declined": []}

                for row in rfp_df.to_dict('records'):
                    end_str = str(row.get("RFP_End_Date", "") or "")

                    rfp_link = row.get("Link", "") or row.get("link", "")
                    if not rfp_link:
                        rfp_link = get_setting('URL', 'https://service.ariba.com/Sourcing.aw/109582016/aw?awh=r&awssk=u9fNiSxN&dard=1#b0')

                    company_name = row.get("Company_Name", "") or "Saudi Energy"

                    # Derive Material_Matched / Keyword_Matched / match percentage from Matched_Data
                    md_str = matched_data_map.get(row.get("RFP_ID", ""), "")
                    mat_flag, kw_flag, match_pct = _derive_match_flags(md_str)

                    rfp_data = {
                        "RFP_ID": row.get("RFP_ID", ""),
                        "RFP_End_Date": end_str,
                        "Company_Name": company_name,
                        "Owner_Name": row.get("owner_name", ""),
                        "Publish_Time": str(row.get("publish_time", "") or ""),
                        "participated": row.get("participated", ""),
                        "Link": rfp_link,
                        "Material_Matched": mat_flag,
                        "Keyword_Matched": kw_flag,
                        "match_percentage_data": match_pct,
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

        # Always include every configured company on the dashboard, even when
        # no open RFP exists for it yet — empty buckets let the frontend render
        # a zero-count card instead of hiding the company entirely.
        configured_companies = get_setting("COMPANY_OPTIONS", []) or []
        for cn in configured_companies:
            if cn and cn not in companies_rfps:
                companies_rfps[cn] = {"open": [], "submitted": [], "saved_draft": [], "declined": []}
                unique_companies.add(cn)

        saved_rfps = total_all_rfps if total_all_rfps > 0 else int(len(rfp_df))
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

        # Data timeline sourced from `publish_time` (TEXT column with KSA-local
        # values like '2/23/2026 8:10 PM'). OData $orderby on text is unreliable,
        # so we parse every value with pd.to_datetime and take min/max here.
        # publish_time reflects the actual portal publish date, which goes back
        # years — unlike `createdon` which only tracks when we inserted the row.
        first_publish_iso = "-"
        last_publish_iso = "-"
        parsed_count = 0
        try:
            if publish_timeline_rows:
                pt_series = pd.to_datetime(
                    pd.Series([r.get("publish_time", "") for r in publish_timeline_rows]),
                    errors="coerce",
                )
                parsed_count = int(pt_series.notna().sum())
                pt_series = pt_series.dropna()
                if not pt_series.empty:
                    if pt_series.dt.tz is not None:
                        pt_series = pt_series.dt.tz_localize(None)
                    first_publish_iso = _ist_to_utc_iso(pt_series.min())
                    last_publish_iso = _ist_to_utc_iso(pt_series.max())
        except Exception as e:
            print(f"Error computing publish timeline: {e}")

        data_timeline = {
            "first_rfp_date": first_publish_iso,
            "last_rfp_date": last_publish_iso,
        }
        print(
            f"Timeline (publish_time): rows={len(publish_timeline_rows)}, "
            f"parsed={parsed_count}, first={first_publish_iso}, last={last_publish_iso}"
        )

        # ── System-action counts from cr673_bhara_rfp_statuses ──
        # DISTINCT RFP_IDs with `from_this = 'saved_draft'` → Submitted by System.
        # DISTINCT RFP_IDs with `from_this = 'declined'`    → Declined by System.
        submitted_ids, declined_ids = _get_system_action_sets()
        system_breakdown_by_company = {}
        submitted_by_system_rfps = []
        declined_by_system_rfps = []
        if submitted_ids or declined_ids:
            try:
                all_rfp_rows_for_index = get_rfp_activity_data_lightweight()
            except Exception as e:
                print(f"⚠ Could not build full RFP index for system breakdowns: {e}")
                all_rfp_rows_for_index = []
            rfp_index = {}
            for r in all_rfp_rows_for_index or []:
                rid = (r.get("RFP_ID") or "").strip()
                if rid:
                    rfp_index[rid] = r

            for rid in sorted(submitted_ids):
                row = rfp_index.get(rid) or {}
                co = (row.get("Company_Name") or "").strip() or "Unknown"
                submitted_by_system_rfps.append({"RFP_ID": rid, "Company_Name": co})
                system_breakdown_by_company.setdefault(co, {"submitted": 0, "declined": 0})["submitted"] += 1

            for rid in sorted(declined_ids):
                row = rfp_index.get(rid) or {}
                co = (row.get("Company_Name") or "").strip() or "Unknown"
                declined_by_system_rfps.append({"RFP_ID": rid, "Company_Name": co})
                system_breakdown_by_company.setdefault(co, {"submitted": 0, "declined": 0})["declined"] += 1

        total_submitted_by_system = len(submitted_ids)
        total_declined_by_system = len(declined_ids)
        print(
            f"System action counts: submitted={total_submitted_by_system}, "
            f"declined={total_declined_by_system}, companies_in_breakdown={len(system_breakdown_by_company)}"
        )

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
            "total_open_rfps": total_open_rfps,
            "total_not_participated_rfps": total_not_participated_rfps,
            "total_submitted_by_system": total_submitted_by_system,
            "total_declined_by_system": total_declined_by_system,
            "submitted_by_system_rfps": submitted_by_system_rfps,
            "declined_by_system_rfps": declined_by_system_rfps,
            "system_breakdown_by_company": system_breakdown_by_company,
            "companies_rfps": companies_rfps,
            "unique_companies": unique_companies_list,
            "data_timeline": data_timeline,
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
    """Get all RFP data from database without date filtering.
    Runs two parallel queries:
    1. Lightweight: all columns EXCEPT Matched_Data (fast, small payload)
    2. Flags-only: RFP_ID + Matched_Data (parsed to derive flags, then discarded)
    This avoids carrying the heavy Matched_Data JSON through the entire pipeline.
    """
    try:
        print(f"Starting all RFP data fetch at {datetime.now()}")
        start_time = time.time()

        from concurrent.futures import ThreadPoolExecutor

        _table_api = get_setting("RFP_ACTIVITY_LOG_TABLE_API", "cr673_bahra_rfps_v2s")
        _table_logical = get_setting("RFP_ACTIVITY_LOG_TABLE_LOGICAL", "cr673_bahra_rfps_v2")

        def _fetch_lightweight():
            return get_rfp_activity_data_lightweight()

        def _fetch_match_flags():
            """Fetch Matched_Data, parse to flags immediately, discard the heavy JSON."""
            rows = DATAVERSE.get_all_rows(
                table_api_name=_table_api,
                select_columns=["RFP_ID", "Matched_Data"],
                table_logical_name=_table_logical,
                use_display_names=True,
            )
            flags_map = {}
            for r in rows:
                rfp_id = r.get("RFP_ID", "")
                if rfp_id:
                    mat_flag, kw_flag, match_pct = _derive_match_flags(r.get("Matched_Data", ""))
                    flags_map[rfp_id] = (mat_flag, kw_flag)
            return flags_map

        # Run both queries in parallel
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_rows = executor.submit(_fetch_lightweight)
            future_flags = executor.submit(_fetch_match_flags)
            rfp_rows = future_rows.result()
            flags_map = future_flags.result()

        print(f"RFP data fetched: {len(rfp_rows)} rows (lightweight) + {len(flags_map)} flag entries")

        if not rfp_rows:
            rfp_df = pd.DataFrame()
        else:
            rfp_df = pd.DataFrame(rfp_rows).fillna("")

        # DEBUG: Check raw data right after fetch
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

                # Derive Material_Matched / Keyword_Matched from pre-parsed flags_map
                rfp_df["Material_Matched"] = rfp_df["RFP_ID"].map(lambda rid: flags_map.get(rid, ("No", "No"))[0])
                rfp_df["Keyword_Matched"] = rfp_df["RFP_ID"].map(lambda rid: flags_map.get(rid, ("No", "No"))[1])

                # Aggregate at RFP level: if ANY row has "Yes", propagate to all rows for that RFP
                for col in ["Material_Matched", "Keyword_Matched"]:
                    yes_rfps = set(rfp_df.loc[rfp_df[col].astype(str).str.strip().str.lower() == "yes", "RFP_ID"])
                    rfp_df.loc[rfp_df["RFP_ID"].isin(yes_rfps), col] = "Yes"

                # Deduplicate: Count each RFP_ID only once (keep first occurrence)
                rfp_df = rfp_df.drop_duplicates(subset=["RFP_ID"], keep="first")
                print(f"All RFP data after deduplication: {len(rfp_df)} unique RFPs")

                # Normalize Company_Name in dataframe (fix empty/null values)
                rfp_df["Company_Name"] = rfp_df["Company_Name"].fillna("Saudi Energy").replace("", "Saudi Energy")

                # Vectorized: Count submitted and declined (faster than iterrows)
                participated_lower = rfp_df["participated"].fillna("").str.strip().str.lower()
                total_submitted_rfps = int(((participated_lower == "submitted") | (participated_lower == "yes")).sum())
                total_declined_rfps = int((participated_lower == "declined").sum())

                # Use to_dict('records') for building list (faster than iterrows, safer than itertuples)
                for row in rfp_df.to_dict('records'):
                    end_str = str(row.get("RFP_End_Date", "") or "")

                    rfp_link = row.get("Link", "") or row.get("link", "")
                    if not rfp_link:
                        rfp_link = get_setting('URL', 'https://service.ariba.com/Sourcing.aw/109582016/aw?awh=r&awssk=u9fNiSxN&dard=1#b0')

                    # Material_Matched / Keyword_Matched derived from Matched_Data JSON above
                    material_matched_raw = str(row.get("Material_Matched", "") or "").strip()
                    keyword_matched_raw = str(row.get("Keyword_Matched", "") or "").strip()

                    rfp_data = {
                        "RFP_ID": row.get("RFP_ID", ""),
                        "RFP_End_Date": end_str,
                        "Company_Name": row.get("Company_Name", "") or "Saudi Energy",
                        "Owner_Name": row.get("owner_name", ""),
                        "Publish_Time": str(row.get("publish_time", "") or ""),
                        "participated": row.get("participated", ""),
                        "Link": rfp_link,
                        "Material_Matched": material_matched_raw,
                        "Keyword_Matched": keyword_matched_raw,
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
        company = row.get("Company_Name", "") or "Saudi Energy"
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


def _add_to_material_group(material_groups, material_code, material_desc, rfp_id, company, rfp_end_date, participated, match_method, extracted="", bahra_item_code=""):
    """Helper: add a material entry to material_groups dict."""
    if not material_code:
        return
    if material_code not in material_groups:
        material_groups[material_code] = {
            "material_code": material_code,
            "bahra_item_code": bahra_item_code,
            "material_description": material_desc,
            "rfp_count": 0,
            "rfps": [],
            "companies": set(),
            "submitted_count": 0,
        }
    group = material_groups[material_code]
    if bahra_item_code and not group.get("bahra_item_code"):
        group["bahra_item_code"] = bahra_item_code
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


def _add_to_keyword_group(keyword_groups, kw, rfp_id, company, rfp_end_date, participated, material_code, material_desc, bahra_item_code=""):
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
            "bahra_item_codes": set(),
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
            "bahra_item_code": bahra_item_code,
            "material_description": material_desc,
        })
        kw_group["rfp_count"] += 1
        if company:
            kw_group["companies"].add(company)
        if participated in ("submitted", "yes"):
            kw_group["submitted_count"] += 1
    if material_code:
        kw_group["material_codes"].add(material_code)
    if bahra_item_code:
        kw_group["bahra_item_codes"].add(bahra_item_code)


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

    from services.master_data_service import get_material_code_to_bahra_code_map
    bahra_map = get_material_code_to_bahra_code_map()

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

            direct_bahra_code = bahra_map.get(direct_material_code, "")

            # Material grouping
            _add_to_material_group(
                material_groups, direct_material_code, direct_material_desc,
                rfp_id, company, rfp_end_date, participated, match_method,
                bahra_item_code=direct_bahra_code,
            )

            # Keyword grouping from Matched_Keywords column (comma-separated)
            if direct_matched_keywords:
                for kw in direct_matched_keywords.split(","):
                    _add_to_keyword_group(
                        keyword_groups, kw, rfp_id, company, rfp_end_date,
                        participated, direct_material_code, direct_material_desc,
                        bahra_item_code=direct_bahra_code,
                    )

        else:
            # FALLBACK PATH: parse Matched_Data JSON
            matched_data_str = row.get("Matched_Data", "") or ""
            if not matched_data_str.strip():
                continue

            try:
                parsed = _json.loads(matched_data_str)
            except (ValueError, TypeError):
                continue

            # Build a unified list of matched items from either format
            matched_items_for_insights = []

            # New categorized format (dict with summary)
            if isinstance(parsed, dict) and "summary" in parsed:
                for item in parsed.get("exact_matches", []):
                    matched_items_for_insights.append({
                        "material_code": item.get("material_code", ""),
                        "material_desc": item.get("material_description", ""),
                        "match_method": "exact",
                        "matched_keyword": "",
                    })
                for item in parsed.get("keyword_matches", []):
                    matched_items_for_insights.append({
                        "material_code": item.get("material_code", ""),
                        "material_desc": item.get("material_description", ""),
                        "match_method": "keyword",
                        "matched_keyword": item.get("matched_keyword", ""),
                    })

            # Old flat format (list) — backward compatibility
            elif isinstance(parsed, list):
                for item in parsed:
                    if item.get("is_matched") is False:
                        continue
                    matched_items_for_insights.append({
                        "material_code": str(item.get("Material", "") or "").strip(),
                        "material_desc": str(item.get("Material Description", "") or "").strip(),
                        "match_method": str(item.get("MatchMethod", "exact") or "exact").lower(),
                        "matched_keyword": "",
                    })
            else:
                continue

            if not matched_items_for_insights:
                continue

            all_rfp_ids_with_matches.add(rfp_id)

            for mi in matched_items_for_insights:
                material_code = mi["material_code"]
                material_desc = mi["material_desc"]
                match_method = mi["match_method"]
                item_bahra_code = bahra_map.get(material_code, "")

                # Material grouping
                _add_to_material_group(
                    material_groups, material_code, material_desc,
                    rfp_id, company, rfp_end_date, participated, match_method, material_code,
                    bahra_item_code=item_bahra_code,
                )

                # Keyword grouping
                if match_method == "keyword":
                    # New format stores matched_keyword directly
                    if mi["matched_keyword"]:
                        _add_to_keyword_group(
                            keyword_groups, mi["matched_keyword"], rfp_id, company,
                            rfp_end_date, participated, material_code, material_desc,
                            bahra_item_code=item_bahra_code,
                        )
                    else:
                        # Old format: cross-reference with keywords list
                        search_text = (material_desc + " " + material_code).upper()
                        for kw in keywords_list:
                            if kw.upper() in search_text:
                                _add_to_keyword_group(
                                    keyword_groups, kw, rfp_id, company, rfp_end_date,
                                    participated, material_code, material_desc,
                                    bahra_item_code=item_bahra_code,
                                )

    # Convert sets to sorted lists for JSON serialization
    materials_list = sorted(material_groups.values(), key=lambda x: x["rfp_count"], reverse=True)
    for m in materials_list:
        m["companies"] = sorted(list(m["companies"]))

    keywords_list_result = sorted(keyword_groups.values(), key=lambda x: x["rfp_count"], reverse=True)
    for k in keywords_list_result:
        k["companies"] = sorted(list(k["companies"]))
        k["material_codes"] = sorted(list(k["material_codes"]))
        k["bahra_item_codes"] = sorted(list(k.get("bahra_item_codes", [])))

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
