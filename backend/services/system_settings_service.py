"""
System Settings Service - CRUD operations for dynamic system configuration.
Settings are stored in cr673_bahra_system_settings Dataverse table.
Provides an in-memory cache with TTL and fallback to config.py values.
"""

import time
import json
import threading
import logging
from typing import Optional, Dict, List, Any

from config.config import (
    SYSTEM_SETTINGS_TABLE_API,
    SYSTEM_SETTINGS_TABLE_LOGICAL,
)

logger = logging.getLogger(__name__)


def _get_dataverse():
    """Lazy import to avoid circular dependency with core_helper."""
    from helpers.core_helper import DATAVERSE
    return DATAVERSE

# ==================== CACHE ====================

_SETTINGS_CACHE: Dict[str, Dict] = {}
_CACHE_TS: float = 0
_CACHE_LOCK = threading.Lock()
SETTINGS_CACHE_TTL = 300  # 5 minutes


def _load_all_settings() -> Dict[str, Dict]:
    """Fetch all rows from Dataverse and return {key: row_dict}."""
    try:
        rows = _get_dataverse().get_all_rows(
            SYSTEM_SETTINGS_TABLE_API,
            table_logical_name=SYSTEM_SETTINGS_TABLE_LOGICAL,
            use_display_names=True,
        )
        result = {}
        for row in rows:
            key = row.get("Key", row.get("cr673_key", ""))
            if key:
                result[key] = {
                    "key": key,
                    "value": row.get("Value", row.get("cr673_value", "")),
                    "label": row.get("Label", row.get("cr673_label", key)),
                    "section": row.get("Section", row.get("cr673_section", "")),
                    "sub_section": row.get("Sub Section", row.get("cr6db_sub_section", "")),
                    "data_type": row.get("Data Type", row.get("cr673_data_type", "string")),
                    "description": row.get("Description", row.get("cr673_description", "")),
                    "is_editable": _parse_bool(row.get("Is Editable", row.get("cr673_is_editable", True))),
                    "is_sensitive": _parse_bool(row.get("Is Sensitive", row.get("cr673_is_sensitive", False))),
                    "id": row.get("Bahra System Settings", row.get("cr673_bahra_system_settingsid", "")),
                }
        return result
    except Exception as e:
        logger.error(f"Failed to load settings from Dataverse: {e}")
        return {}


def _parse_bool(value) -> bool:
    """Parse various boolean representations."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "yes", "1")
    return bool(value)


def _ensure_cache():
    """Load cache if empty or expired."""
    global _SETTINGS_CACHE, _CACHE_TS
    with _CACHE_LOCK:
        if _SETTINGS_CACHE and (time.time() - _CACHE_TS) < SETTINGS_CACHE_TTL:
            return
    # Load outside lock to avoid blocking
    settings = _load_all_settings()
    with _CACHE_LOCK:
        _SETTINGS_CACHE = settings
        _CACHE_TS = time.time()


def invalidate_settings_cache():
    """Force cache reload on next access."""
    global _SETTINGS_CACHE, _CACHE_TS
    with _CACHE_LOCK:
        _SETTINGS_CACHE = {}
        _CACHE_TS = 0


def _cast_value(raw_value: str, data_type: str) -> Any:
    """Cast a string value to the appropriate Python type based on data_type."""
    if not raw_value and raw_value != "":
        return raw_value

    try:
        if data_type == "number":
            if "." in str(raw_value):
                return float(raw_value)
            return int(raw_value)
        elif data_type == "boolean":
            return str(raw_value).lower() in ("true", "yes", "1")
        elif data_type == "json":
            return json.loads(raw_value)
        else:
            return str(raw_value)
    except (ValueError, json.JSONDecodeError):
        return raw_value


# ==================== PUBLIC API ====================

def get_setting(key: str, fallback=None, cast_type: bool = True) -> Any:
    """
    Get a setting value.
    Priority: cache → Dataverse → config.py attribute → fallback.
    If cast_type=True, auto-cast based on data_type.
    """
    _ensure_cache()

    with _CACHE_LOCK:
        entry = _SETTINGS_CACHE.get(key)

    if entry:
        value = entry["value"]
        if cast_type:
            return _cast_value(value, entry.get("data_type", "string"))
        return value

    # Fallback to config.py
    try:
        import config.config as cfg
        config_value = getattr(cfg, key, None)
        if config_value is not None:
            return config_value
    except Exception:
        pass

    return fallback


def get_all_settings() -> List[Dict]:
    """Return all settings for the admin UI. Masks sensitive values."""
    _ensure_cache()

    with _CACHE_LOCK:
        settings = list(_SETTINGS_CACHE.values())

    result = []
    for s in settings:
        entry = {**s}
        if entry.get("is_sensitive"):
            entry["value"] = "••••••••"
        result.append(entry)

    # Sort by section then label
    result.sort(key=lambda x: (x.get("section", ""), x.get("label", "")))
    return result


def get_sections() -> List[str]:
    """Return distinct section names."""
    _ensure_cache()
    with _CACHE_LOCK:
        sections = sorted(set(s.get("section", "") for s in _SETTINGS_CACHE.values() if s.get("section")))
    return sections


def reveal_setting(key: str, actor_email: str = "") -> Optional[str]:
    """Return the unmasked value for a setting (used for eye-toggle on sensitive settings).
    Logs an audit event when a sensitive value is revealed."""
    _ensure_cache()
    with _CACHE_LOCK:
        entry = _SETTINGS_CACHE.get(key)
    if entry:
        # Audit log for sensitive value reveals
        if entry.get("is_sensitive") and actor_email:
            try:
                from services.audit_service import log_event, AuditCategory, AuditAction
                log_event(
                    action=AuditAction.SETTING_REVEALED,
                    category=AuditCategory.SYSTEM,
                    actor_email=actor_email,
                    target_type="system_setting",
                    target_id=key,
                    details=json.dumps({"key": key, "section": entry.get("section", "")}),
                )
            except Exception as e:
                logger.warning(f"Audit log failed for setting reveal: {e}")
        return entry["value"]
    return None


def get_setting_entry(key: str) -> Optional[Dict]:
    """Get the full setting entry dict."""
    _ensure_cache()
    with _CACHE_LOCK:
        return _SETTINGS_CACHE.get(key)


def update_setting(key: str, new_value: str, actor_email: str = "") -> Dict:
    """
    Update a single setting in Dataverse.
    Returns {"ok": True} on success or {"ok": False, "error": "..."} on failure.
    """
    _ensure_cache()

    with _CACHE_LOCK:
        entry = _SETTINGS_CACHE.get(key)

    if not entry:
        return {"ok": False, "error": f"Setting '{key}' not found"}

    if not entry.get("is_editable"):
        return {"ok": False, "error": f"Setting '{key}' is not editable"}

    # Validate JSON if data_type is json
    data_type = entry.get("data_type", "string")
    if data_type == "json":
        try:
            json.loads(new_value)
        except json.JSONDecodeError as e:
            return {"ok": False, "error": f"Invalid JSON: {e}"}

    # Validate number
    if data_type == "number":
        try:
            float(new_value)
        except ValueError:
            return {"ok": False, "error": f"Invalid number: {new_value}"}

    # Validate boolean
    if data_type == "boolean":
        if new_value.lower() not in ("true", "false", "yes", "no", "1", "0"):
            return {"ok": False, "error": f"Invalid boolean: {new_value}. Use 'true' or 'false'"}

    record_id = entry.get("id")
    if not record_id:
        return {"ok": False, "error": f"No record ID found for setting '{key}'"}

    # Update in Dataverse
    try:
        old_value = entry["value"]
        success = _get_dataverse().update_row(
            SYSTEM_SETTINGS_TABLE_API,
            record_id,
            {"Value": new_value},
            table_logical_name=SYSTEM_SETTINGS_TABLE_LOGICAL,
            use_display_names=True,
        )
        if not success:
            return {"ok": False, "error": "Dataverse update failed"}

        # Invalidate cache
        invalidate_settings_cache()

        # Log audit event
        try:
            from services.audit_service import log_event, AuditCategory, AuditAction
            masked_old = "••••••••" if entry.get("is_sensitive") else old_value
            masked_new = "••••••••" if entry.get("is_sensitive") else new_value
            log_event(
                action=AuditAction.SETTING_UPDATED,
                category=AuditCategory.SYSTEM,
                actor_email=actor_email,
                target_type="system_setting",
                target_id=key,
                details=json.dumps({
                    "key": key,
                    "old_value": masked_old,
                    "new_value": masked_new,
                    "section": entry.get("section", ""),
                }),
            )
        except Exception as e:
            logger.warning(f"Audit log failed for setting update: {e}")

        return {"ok": True}

    except Exception as e:
        logger.error(f"Failed to update setting '{key}': {e}")
        return {"ok": False, "error": str(e)}
