import os
import json
import atexit
import sys
import traceback
from datetime import datetime

# Ensure a local logs directory exists
LOG_DIR = os.path.join(os.getcwd(), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOCAL_LOG_FILE = os.path.join(LOG_DIR, "events.jsonl")


def _utc_iso() -> str:
    """UTC timestamp in ISO format."""
    return datetime.utcnow().isoformat()


def write_local_event(category: str, action: str, status: str, message: str = "", rfp_id: str = "", extra: dict | None = None) -> None:
    """Append a single event to a local JSONL file (durable, no network)."""
    record = {
        "ts": _utc_iso(),
        "category": str(category or ""),
        "action": str(action or ""),
        "status": str(status or ""),
        "message": str(message or ""),
        "rfp_id": str(rfp_id or ""),
        "extra": extra or {},
    }
    try:
        with open(LOCAL_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        # Last-resort: don't raise here; logging must never break callers
        pass


def capture_uncaught() -> None:
    """Install a global hook to log uncaught exceptions locally."""
    def _hook(exc_type, exc, tb):
        write_local_event(
            "SYSTEM",
            "Uncaught",
            "Error",
            "".join(traceback.format_exception(exc_type, exc, tb)),
        )
        # Continue default behavior
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _hook


def _on_process_exit():
    """Note normal process termination."""
    write_local_event("SYSTEM", "ProcessExit", "Info", "Process terminated")


# Register exit note automatically
atexit.register(_on_process_exit)


