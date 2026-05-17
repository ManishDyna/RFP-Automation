"""
Export per-RFP, per-material quantities (with name + description) to a single
flat Excel sheet.

Walks the local ALLRFPs/{Company}/{RFP}/downloaded-rfp/ folder structure,
reads the "Other Content" sheet from each RFP Excel, and writes one row per
material code with: Company | RFP Title | Material Code | Name | Description |
Quantity | Source File.

Usage (from project root):
    python -m Support-Files.export_rfp_quantities

Output:
    Support-Files/exports/RFP_Materials_Quantity_<YYYYMMDD_HHMMSS>.xlsx
"""

import os
import sys
from datetime import datetime

import pandas as pd

# Allow running as a plain script from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


OUTPUT_COLUMNS = [
    "Company",
    "RFP Title",
    "Material Code",
    "Name",
    "Description",
    "Quantity",
    "Source File",
]


def find_rfp_excels(allrfps_root: str):
    """
    Yield (company, rfp_title, excel_path) for every Excel found under
    ALLRFPs/{Company}/{RFP}/downloaded-rfp/. Falls back to RFP folder root
    if no downloaded-rfp/ subfolder exists (legacy layout).
    """
    if not os.path.isdir(allrfps_root):
        return

    for company in sorted(os.listdir(allrfps_root)):
        company_path = os.path.join(allrfps_root, company)
        if not os.path.isdir(company_path):
            continue

        for rfp_title in sorted(os.listdir(company_path)):
            rfp_path = os.path.join(company_path, rfp_title)
            if not os.path.isdir(rfp_path):
                continue

            downloaded = os.path.join(rfp_path, "downloaded-rfp")
            search_dir = downloaded if os.path.isdir(downloaded) else rfp_path

            for fname in os.listdir(search_dir):
                if fname.lower().endswith((".xls", ".xlsx")) and not fname.startswith("~$"):
                    yield company, rfp_title, os.path.join(search_dir, fname)


def main():
    # Bootstrap project imports in the right order to avoid circular imports
    # (services.__init__ pulls in core_helper which we import next)
    import core.common_imports  # noqa: F401
    from helpers.core_helper import extract_materials_from_excel

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    allrfps_root = os.path.join(project_root, "ALLRFPs")

    print(f"Scanning: {allrfps_root}")

    rows = []
    rfp_count = 0
    skipped = 0

    for company, rfp_title, excel_path in find_rfp_excels(allrfps_root):
        rfp_count += 1
        rel = os.path.relpath(excel_path, project_root)
        print(f"  [{rfp_count}] {company} / {rfp_title} -> {os.path.basename(excel_path)}")

        try:
            materials = extract_materials_from_excel(
                excel_path,
                include_details=True,
                filter_by_intent=False,
            )
        except Exception as e:
            print(f"      [SKIP] read error: {e}")
            skipped += 1
            continue

        if not materials:
            print(f"      [SKIP] no materials extracted")
            skipped += 1
            continue

        for m in materials:
            rows.append({
                "Company": company,
                "RFP Title": rfp_title,
                "Material Code": m.get("material_code", ""),
                "Name": m.get("name", ""),
                "Description": m.get("description", ""),
                "Quantity": m.get("quantity", ""),
                "Source File": rel,
            })

    if not rows:
        print("\nNo material rows produced. Nothing written.")
        return

    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exports")
    os.makedirs(out_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(out_dir, f"RFP_Materials_Quantity_{stamp}.xlsx")

    df = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    df.to_excel(out_path, index=False)

    print(
        f"\nDone. RFPs scanned: {rfp_count}, skipped: {skipped}, "
        f"rows written: {len(rows)}\nOutput: {out_path}"
    )


if __name__ == "__main__":
    main()
