"""
Progress tracking helper for long-running operations.
This module provides a shared progress state that can be accessed by both
the automation logic and API routes without circular imports.
"""

# Shared progress state for all operations
_PROGRESS = {
    "download": {"current": 0, "total": 0, "current_item": "", "message": ""},
    "submit": {"current": 0, "total": 0, "current_item": "", "message": ""},
    "decline": {"current": 0, "total": 0, "current_item": "", "message": ""},
    "sync": {"current": 0, "total": 0, "current_item": "", "message": ""},
}


def update_progress(operation: str, current: int = None, total: int = None, current_item: str = None, message: str = None):
    """
    Update progress for an operation. Only updates provided fields.

    Args:
        operation: One of 'download', 'submit', 'decline', 'sync'
        current: Current item number being processed
        total: Total number of items to process
        current_item: Name/description of current item
        message: Status message
    """
    if operation not in _PROGRESS:
        return
    if current is not None:
        _PROGRESS[operation]["current"] = current
    if total is not None:
        _PROGRESS[operation]["total"] = total
    if current_item is not None:
        _PROGRESS[operation]["current_item"] = current_item
    if message is not None:
        _PROGRESS[operation]["message"] = message


def get_progress(operation: str) -> dict:
    """
    Get progress for an operation with calculated percentage.

    Returns:
        Dict with current, total, percentage, current_item, message
    """
    prog = _PROGRESS.get(operation, {})
    total = prog.get("total", 0)
    current = prog.get("current", 0)
    percentage = int((current / total * 100) if total > 0 else 0)
    return {
        "current": current,
        "total": total,
        "percentage": percentage,
        "current_item": prog.get("current_item", ""),
        "message": prog.get("message", ""),
    }


def reset_progress(operation: str):
    """Reset progress for an operation."""
    if operation in _PROGRESS:
        _PROGRESS[operation] = {"current": 0, "total": 0, "current_item": "", "message": ""}
