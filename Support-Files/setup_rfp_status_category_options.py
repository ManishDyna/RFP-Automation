"""
Setup script to ensure the `category` field on cr673_bhara_rfp_status has the
two choice options the system needs: 'submit' and 'decline'.

Context:
  cr673_bhara_rfp_status logs every status change. The `category` column
  (logical name: cr673_submissioncategory) is a Dataverse choice field.
  Originally it only had a 'submit' option, so all decline events were
  silently mislabeled as 'submit'. This script adds 'decline' if missing.

Usage:
    python Support-Files/setup_rfp_status_category_options.py

Safe to re-run (skips options that already exist).
"""

import sys
import io
import time
import requests
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from helpers.dataverse_helper import DataverseClient
from config.config import TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL

TABLE_LOGICAL = "cr673_bhara_rfp_status"
CATEGORY_ATTR_LOGICAL = "cr673_submissioncategory"
REQUIRED_LABELS = ["submit", "decline"]


def make_label(text: str) -> dict:
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.Label",
        "LocalizedLabels": [
            {
                "@odata.type": "Microsoft.Dynamics.CRM.LocalizedLabel",
                "Label": text,
                "LanguageCode": 1033,
            }
        ],
    }


def insert_option(dv: DataverseClient, label: str) -> bool:
    url = f"{dv.api_url}InsertOptionValue"
    body = {
        "EntityLogicalName": TABLE_LOGICAL,
        "AttributeLogicalName": CATEGORY_ATTR_LOGICAL,
        "Label": make_label(label),
    }
    resp = requests.post(url, json=body, headers=dv._headers())
    if resp.status_code in (200, 201, 204):
        try:
            data = resp.json()
            new_value = data.get("NewOptionValue", "?")
        except Exception:
            new_value = "?"
        print(f"  [OK] Added option '{label}' (value={new_value})")
        return True
    print(f"  [ERROR] Failed to add option '{label}': {resp.status_code} {resp.text}")
    return False


def publish_entity(dv: DataverseClient) -> None:
    url = f"{dv.api_url}PublishXml"
    body = {
        "ParameterXml": f"<importexportxml><entities><entity>{TABLE_LOGICAL}</entity></entities></importexportxml>"
    }
    resp = requests.post(url, json=body, headers=dv._headers())
    if resp.status_code in (200, 204):
        print(f"  [OK] Published changes to {TABLE_LOGICAL}")
    else:
        print(f"  [WARN] Publish returned {resp.status_code}: {resp.text}")


def main() -> int:
    print(f"\n{'=' * 70}")
    print(f"  Ensure choice options on {TABLE_LOGICAL}.{CATEGORY_ATTR_LOGICAL}")
    print(f"  Required labels: {REQUIRED_LABELS}")
    print(f"{'=' * 70}\n")

    dv = DataverseClient(
        tenant_id=TENANT_ID,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        resource_url=RESOURCE_URL,
    )

    try:
        current = dv.get_choice_options(TABLE_LOGICAL, CATEGORY_ATTR_LOGICAL)
    except Exception as e:
        print(f"[ERROR] Could not read existing choice options: {e}")
        return 1

    existing_labels = {k.lower(): k for k in current.get("label_to_value", {}).keys()}
    print(f"Existing options: {list(existing_labels.values()) or '(none)'}\n")

    added = 0
    for required in REQUIRED_LABELS:
        if required.lower() in existing_labels:
            print(f"  [SKIP] '{required}' already exists")
            continue
        print(f"  Adding '{required}'...")
        if insert_option(dv, required):
            added += 1

    if added > 0:
        print(f"\nWaiting 3s before publish...")
        time.sleep(3)
        publish_entity(dv)

        print("\nFinal options:")
        try:
            final = dv.get_choice_options(TABLE_LOGICAL, CATEGORY_ATTR_LOGICAL)
            for label, value in final.get("label_to_value", {}).items():
                print(f"  - '{label}' = {value}")
        except Exception as e:
            print(f"  [WARN] Could not re-read options: {e}")

    print(f"\n{'=' * 70}")
    print(f"  DONE. Added {added} option(s).")
    print(f"{'=' * 70}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
