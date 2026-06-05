"""
Rebuild .master_rfp_sync_progress.json from an existing preview CSV.

Use this when the progress file got out of sync with a partial preview CSV
(e.g. a second --reset run wiped progress mid-flow).

Usage:
  python Support-Files\rebuild_progress_from_preview.py <preview_csv_path>
"""

import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROGRESS_FILE = HERE / ".master_rfp_sync_progress.json"


def clean_id(rfp_id: str) -> str:
    return re.sub(r"\s+", " ", str(rfp_id or "")).strip()


def main():
    if len(sys.argv) != 2:
        print("Usage: python rebuild_progress_from_preview.py <preview_csv_path>")
        sys.exit(1)

    preview_path = Path(sys.argv[1])
    if not preview_path.exists():
        print(f"[ERROR] Preview file not found: {preview_path}")
        sys.exit(1)

    completed = set()
    errored = {}
    with open(preview_path, "r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            rfp_id = clean_id(row.get("rfp_id", ""))
            if not rfp_id:
                continue
            status = (row.get("status") or "").strip().upper()
            if status == "ERROR":
                prev = errored.get(rfp_id, {})
                errored[rfp_id] = {
                    "attempts": prev.get("attempts", 0) + 1,
                    "last_error": (row.get("notes") or "").strip() or "scrape error",
                }
            else:
                # OK / MISSING / WRONG / SKIPPED_NO_LINK / INFO all mean this RFP
                # was visited; don't re-scrape it on resume.
                completed.add(rfp_id)

    # Don't list a RFP as both completed and errored — completed wins
    for rid in completed:
        errored.pop(rid, None)

    # Backup existing progress if any
    if PROGRESS_FILE.exists():
        backup = PROGRESS_FILE.with_suffix(".json.bak")
        PROGRESS_FILE.rename(backup)
        print(f"[INFO] Existing progress backed up to: {backup.name}")

    payload = {
        "started_at": datetime.now().isoformat(),
        "completed": sorted(completed),
        "errored": errored,
        "rebuilt_from": str(preview_path),
    }
    with open(PROGRESS_FILE, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)

    print(f"\n  Rebuilt progress file: {PROGRESS_FILE}")
    print(f"  RFPs marked completed : {len(completed)}")
    print(f"  RFPs marked errored   : {len(errored)}")
    print(f"\n  You can now resume safely:")
    print(f"  python Support-Files\\master_rfp_sync.py --company \"Saudi Energy\" --links-file \"...\" --username ... --password ...")


if __name__ == "__main__":
    main()
