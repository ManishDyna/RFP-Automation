"""
Settings helper - loads application configuration from Dataverse table
cr673_bahra_system_settings and patches the config module at runtime.

On startup, call load_settings_from_dataverse() to apply Dataverse values
over the defaults in config/config.py. Subsequent saves via save_settings_batch()
also re-patch the config module so changes take effect immediately.
"""

import json
import logging
import time
import sys

logger = logging.getLogger(__name__)

# Table names for the system settings Dataverse table
SETTINGS_TABLE_API = "cr673_bahra_system_settingses"
SETTINGS_TABLE_LOGICAL = "cr673_bahra_system_settings"

# Cache TTL in seconds (5 minutes)
SETTINGS_CACHE_TTL = 300

# Internal cache: dict of key -> row (full row from Dataverse)
_settings_cache: dict = {}
_cache_loaded_at: float = 0.0


def _get_dataverse():
    """Lazy import of DATAVERSE to avoid circular imports."""
    from helpers.core_helper import DATAVERSE
    return DATAVERSE


def _deserialize_value(data_type: str, raw_value: str):
    """Convert a stored string value to the correct Python type."""
    if raw_value is None:
        return None
    try:
        if data_type == "json_list":
            return json.loads(raw_value)
        elif data_type == "json_table":
            return json.loads(raw_value)
        elif data_type == "integer":
            return int(raw_value)
        elif data_type == "boolean":
            return raw_value.strip().lower() == "true"
        else:
            return raw_value
    except Exception as e:
        logger.warning(f"Could not deserialize value for type '{data_type}': {e}")
        return raw_value


def _serialize_value(value) -> str:
    """Convert a Python value to a string for storage in Dataverse."""
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def load_settings_from_dataverse(force: bool = False) -> dict:
    """
    Load all settings from Dataverse and patch the config module.

    Args:
        force: If True, bypass cache and always reload from Dataverse.

    Returns:
        dict mapping config key -> deserialized Python value
    """
    global _settings_cache, _cache_loaded_at

    now = time.time()
    if (
        not force
        and _cache_loaded_at > 0
        and (now - _cache_loaded_at) < SETTINGS_CACHE_TTL
        and _settings_cache
    ):
        return _settings_cache

    try:
        dv = _get_dataverse()
        rows = dv.get_all_rows(
            table_api_name=SETTINGS_TABLE_API,
            select_columns=["cr673_key", "cr673_value", "cr673_data_type",
                            "cr673_section", "cr673_is_sensitive", "cr673_is_editable",
                            "cr673_label", "cr673_description"],
            table_logical_name=SETTINGS_TABLE_LOGICAL,
            use_display_names=False,
        )
    except Exception as e:
        logger.error(f"Failed to load settings from Dataverse: {e}")
        return _settings_cache  # Return stale cache on failure

    new_cache: dict = {}
    for row in rows:
        key = row.get("cr673_key") or row.get("Key")
        raw_value = row.get("cr673_value") or row.get("Value", "")
        data_type = row.get("cr673_data_type") or row.get("Data Type", "string")
        if not key:
            continue
        new_cache[key] = {
            "value": _deserialize_value(data_type, raw_value),
            "raw_value": raw_value,
            "data_type": data_type,
            "section": row.get("cr673_section") or row.get("Section", ""),
            "is_sensitive": row.get("cr673_is_sensitive", False),
            "is_editable": row.get("cr673_is_editable", True),
            "label": row.get("cr673_label") or row.get("Label", key),
            "description": row.get("cr673_description") or row.get("Description", ""),
            "record_id": row.get(f"{SETTINGS_TABLE_LOGICAL}id"),
        }

    _settings_cache = new_cache
    _cache_loaded_at = now

    _patch_config_module(new_cache)
    logger.info(f"Loaded {len(new_cache)} settings from Dataverse.")
    return new_cache


def _patch_config_module(cache: dict) -> None:
    """Apply loaded settings to the config.config module."""
    import config.config as cfg
    for key, entry in cache.items():
        if hasattr(cfg, key):
            try:
                setattr(cfg, key, entry["value"])
            except Exception as e:
                logger.warning(f"Could not patch config.{key}: {e}")


def get_setting(key: str, default=None):
    """
    Get a single setting value (uses cache).

    Returns:
        The deserialized Python value, or `default` if not found.
    """
    cache = load_settings_from_dataverse()
    entry = cache.get(key)
    if entry is None:
        return default
    return entry["value"]


def get_all_settings() -> dict:
    """
    Return the full settings cache.

    Returns:
        dict mapping config key -> {value, raw_value, data_type, section,
                                     is_sensitive, label, description, record_id}
    """
    return load_settings_from_dataverse()


def save_settings_batch(updates: dict) -> dict:
    """
    Save a batch of setting updates to Dataverse.

    Args:
        updates: dict mapping config key -> new string value (raw).
                 Values should already be serialized (e.g., JSON strings for lists).

    Returns:
        dict with keys: saved (list), failed (list of {key, error})
    """
    dv = _get_dataverse()
    cache = load_settings_from_dataverse()
    saved = []
    failed = []

    for key, new_raw_value in updates.items():
        entry = cache.get(key)
        try:
            record_id = entry.get("record_id") if entry else None
            data_type = entry.get("data_type", "string") if entry else "string"
            if record_id:
                # Update existing row
                ok = dv.update_row(
                    table_api_name=SETTINGS_TABLE_API,
                    record_id=record_id,
                    data={"cr673_value": str(new_raw_value)},
                    table_logical_name=SETTINGS_TABLE_LOGICAL,
                )
                if ok:
                    saved.append(key)
                else:
                    failed.append({"key": key, "error": "Update returned False"})
            else:
                # Insert new row (key doesn't exist in Dataverse yet)
                ok = dv.insert_row(
                    table_api_name=SETTINGS_TABLE_API,
                    data={
                        "cr673_key": key,
                        "cr673_value": str(new_raw_value),
                        "cr673_data_type": "string",
                        "cr673_section": "",
                        "cr673_is_sensitive": False,
                        "cr673_is_editable": True,
                    },
                    table_logical_name=SETTINGS_TABLE_LOGICAL,
                )
                if ok:
                    saved.append(key)
                else:
                    failed.append({"key": key, "error": "Insert returned False"})
        except Exception as e:
            logger.error(f"Failed to save setting '{key}': {e}")
            failed.append({"key": key, "error": str(e)})

    # Reload cache to pick up saved values and re-patch config
    if saved:
        load_settings_from_dataverse(force=True)

    return {"saved": saved, "failed": failed}


def get_settings_grouped() -> dict:
    """
    Return settings grouped by section, suitable for the settings page API.

    Returns:
        dict mapping section name -> list of setting objects
    """
    cache = load_settings_from_dataverse()
    grouped: dict = {}
    for key, entry in cache.items():
        section = entry.get("section") or "general"
        if section not in grouped:
            grouped[section] = []
        grouped[section].append({
            "key": key,
            "label": entry.get("label", key),
            "description": entry.get("description", ""),
            "value": entry["raw_value"],
            "data_type": entry.get("data_type", "string"),
            "is_sensitive": entry.get("is_sensitive", False),
            "is_editable": entry.get("is_editable", True),
        })
    return grouped
