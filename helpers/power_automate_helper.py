"""
Power Automate flow synchronization.

Patches the Recurrence trigger of a cloud flow whenever an operator saves a
new cron schedule from the portal. Cloud flows are stored as rows in the same
Dataverse environment's `workflow` table, so we reuse the existing
DataverseClient — no separate auth, no api.flow.microsoft.com (unsupported).

Reference: https://learn.microsoft.com/power-automate/manage-flows-with-code
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional, Tuple

import requests

from config import config
from helpers.core_helper import DATAVERSE

logger = logging.getLogger(__name__)

_GUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

# Cache of flow-name -> workflowid. Populated on first sync and reused.
# Cleared automatically if a subsequent PATCH returns 404 (flow replaced).
_workflowid_cache: dict[str, str] = {}

# Portal sends Windows zone IDs directly (matches PA Recurrence trigger).
# This map only exists to translate legacy IANA values saved before the dropdown
# was expanded to the full Power Automate time-zone list. Anything not in the
# map falls through unchanged via the .get(tz, tz) call below.
_IANA_TO_WINDOWS_TZ = {
    "Asia/Kolkata": "India Standard Time",
    "Asia/Riyadh": "Arab Standard Time",
    "Europe/London": "GMT Standard Time",
    "Europe/Berlin": "W. Europe Standard Time",
}

_VALID_FREQUENCIES = {"Second", "Minute", "Hour", "Day", "Week", "Month", "Year"}


def _read_workflow_clientdata(workflow_id: str) -> dict:
    url = f"{DATAVERSE.api_url}workflows({workflow_id})?$select=name,clientdata,statecode"
    resp = requests.get(url, headers=DATAVERSE._headers(), timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(
            f"GET workflows({workflow_id}) failed: {resp.status_code} {resp.text[:400]}"
        )
    return resp.json()


def _resolve_workflow_id_by_name(flow_name: str) -> str:
    """Look up the Dataverse primary-key workflowid for a cloud flow by display name."""
    safe_name = flow_name.replace("'", "''")
    url = (
        f"{DATAVERSE.api_url}workflows"
        f"?$filter=name eq '{safe_name}' and category eq 5"
        f"&$select=name,workflowid,statecode"
    )
    resp = requests.get(url, headers=DATAVERSE._headers(), timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(
            f"Name lookup failed: {resp.status_code} {resp.text[:400]}"
        )
    rows = resp.json().get("value", [])
    if not rows:
        raise RuntimeError(
            f"No cloud flow named '{flow_name}' found. Add it to a Power Platform Solution "
            f"in environment {DATAVERSE.resource_url} so the Dataverse API can see it."
        )
    if len(rows) > 1:
        raise RuntimeError(
            f"Multiple flows named '{flow_name}' found ({len(rows)}). "
            f"Set POWER_AUTOMATE_WORKFLOW_ID in config to disambiguate."
        )
    return rows[0]["workflowid"]


def _get_target_workflow_id() -> str:
    """Resolve the workflowid, preferring explicit config, falling back to name lookup + cache."""
    explicit = (getattr(config, "POWER_AUTOMATE_WORKFLOW_ID", "") or "").strip()
    if _GUID_RE.match(explicit):
        return explicit

    flow_name = (getattr(config, "POWER_AUTOMATE_FLOW_NAME", "") or "").strip()
    if not flow_name:
        raise RuntimeError(
            "Neither POWER_AUTOMATE_WORKFLOW_ID (valid GUID) nor POWER_AUTOMATE_FLOW_NAME is set in config."
        )

    cached = _workflowid_cache.get(flow_name)
    if cached:
        return cached
    resolved = _resolve_workflow_id_by_name(flow_name)
    _workflowid_cache[flow_name] = resolved
    logger.info("Resolved PA flow '%s' -> workflowid %s", flow_name, resolved)
    return resolved


def _invalidate_cache() -> None:
    _workflowid_cache.clear()


def sync_schedule_to_power_automate(
    interval: int,
    frequency: str,
    timezone: Optional[str] = None,
    start_time: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Patch the Recurrence trigger of the configured cron flow.

    Returns (ok, message). On failure, the caller keeps the Dataverse row and
    surfaces `message` as a warning — the schedule is still persisted, only
    the PA flow is out of sync.
    """
    if frequency not in _VALID_FREQUENCIES:
        return False, f"Unsupported frequency '{frequency}'."

    try:
        try:
            workflow_id = _get_target_workflow_id()
            row = _read_workflow_clientdata(workflow_id)
        except RuntimeError as e:
            # Cached GUID may be stale (flow was deleted/recreated). Clear and retry once.
            if "404" in str(e) and _workflowid_cache:
                _invalidate_cache()
                workflow_id = _get_target_workflow_id()
                row = _read_workflow_clientdata(workflow_id)
            else:
                raise
        client_data = json.loads(row.get("clientdata") or "{}")

        trigger_name = getattr(config, "POWER_AUTOMATE_RECURRENCE_TRIGGER_NAME", "Recurrence")
        triggers = (
            client_data.get("properties", {}).get("definition", {}).get("triggers", {})
        )
        trigger = triggers.get(trigger_name)
        if trigger is None:
            # Fall back: pick the first Recurrence-type trigger regardless of name.
            for name, t in triggers.items():
                if (t or {}).get("recurrence") is not None:
                    trigger = t
                    trigger_name = name
                    break
        if trigger is None or "recurrence" not in trigger:
            return False, (
                f"No Recurrence trigger found in flow '{row.get('name')}'. "
                f"Expected trigger name '{trigger_name}'."
            )

        recurrence = trigger["recurrence"]
        recurrence["interval"] = int(interval)
        recurrence["frequency"] = frequency

        if timezone:
            recurrence["timeZone"] = _IANA_TO_WINDOWS_TZ.get(timezone, timezone)

        if start_time:
            recurrence["startTime"] = start_time
        else:
            recurrence.pop("startTime", None)

        updated_clientdata = json.dumps(client_data, separators=(",", ":"))

        DATAVERSE.update_row(
            table_api_name="workflows",
            record_id=workflow_id,
            data={"clientdata": updated_clientdata},
            use_display_names=False,
        )
        return True, f"Flow '{row.get('name')}' recurrence updated."
    except Exception as e:
        logger.exception("sync_schedule_to_power_automate failed")
        return False, str(e)
