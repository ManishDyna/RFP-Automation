"""
Helper module to unprotect Excel files (both .xls and .xlsx formats).
This module removes password protection and worksheet/workbook protection from Excel files.
"""

import os
import zipfile
import tempfile
import shutil
from xml.etree import ElementTree as ET

try:
    import win32com.client as win32  # pip install pywin32
except Exception:
    win32 = None


def detect_real_type(path: str) -> str:
    """
    Detect the actual file type by reading file headers.
    
    Args:
        path: Path to the file to check
        
    Returns:
        String indicating file type: 'xls', 'xlsx', 'zip', 'html', 'xml', 'csv', or 'unknown'
    """
    try:
        with open(path, 'rb') as f:
            header = f.read(8)
        if header[:4] == b'\xD0\xCF\x11\xE0':
            return 'xls'
        if header[:4] == b'PK\x03\x04':
            return 'xlsx'
        if header[:5] == b'<?xml':
            return 'xml'
        with open(path, 'rb') as f:
            chunk = f.read(2048).lower()
            if b'<html' in chunk or b'<table' in chunk:
                return 'html'
        # Naive CSV check
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            first = f.readline()
            if ',' in first or '\t' in first:
                return 'csv'
    except Exception:
        pass
    return 'unknown'


def unprotect_xlsx(xlsx_path: str, out_path: str) -> str:
    """
    Remove protection from .xlsx file by modifying its XML structure.
    
    Args:
        xlsx_path: Path to the protected .xlsx file
        out_path: Path where the unprotected file will be saved
        
    Returns:
        Path to the unprotected file
    """
    tmpdir = tempfile.mkdtemp()
    try:
        # Extract the .xlsx (which is a ZIP archive)
        with zipfile.ZipFile(xlsx_path, 'r') as zf:
            zf.extractall(tmpdir)

        ns = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

        # Remove worksheet protections
        ws_dir = os.path.join(tmpdir, 'xl', 'worksheets')
        if os.path.isdir(ws_dir):
            for name in os.listdir(ws_dir):
                if name.endswith('.xml'):
                    p = os.path.join(ws_dir, name)
                    try:
                        tree = ET.parse(p)
                        root = tree.getroot()
                        for sp in root.findall('m:sheetProtection', ns):
                            root.remove(sp)
                        tree.write(p, encoding='utf-8', xml_declaration=True)
                    except Exception:
                        pass

        # Remove workbook structure protection
        wb_xml = os.path.join(tmpdir, 'xl', 'workbook.xml')
        if os.path.exists(wb_xml):
            try:
                tree = ET.parse(wb_xml)
                root = tree.getroot()
                for wp in root.findall('m:workbookProtection', ns):
                    root.remove(wp)
                tree.write(wb_xml, encoding='utf-8', xml_declaration=True)
            except Exception:
                pass

        # Repackage as .xlsx
        with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for folder, _, files in os.walk(tmpdir):
                for f in files:
                    full = os.path.join(folder, f)
                    arc = os.path.relpath(full, tmpdir).replace('\\', '/')
                    zf.write(full, arc)
        return out_path
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def unprotect_xls_via_com(xls_path: str, out_path: str) -> str:
    """
    Remove protection from .xls file using Excel COM automation.
    Requires Microsoft Excel to be installed.

    Args:
        xls_path: Path to the protected .xls file
        out_path: Path where the unprotected file will be saved

    Returns:
        Path to the unprotected file

    Raises:
        RuntimeError: If Excel/pywin32 is not available
    """
    if win32 is None:
        raise RuntimeError("Excel/pywin32 required to handle .xls files")

    excel = win32.DispatchEx('Excel.Application')
    excel.DisplayAlerts = False
    try:
        wb = excel.Workbooks.Open(xls_path, False, False)
        # Try blank passwords; if protected with a password, this may fail silently
        try:
            wb.Unprotect()
        except Exception:
            pass
        try:
            for ws in wb.Worksheets:
                try:
                    ws.Unprotect()
                except Exception:
                    pass
        except Exception:
            pass
        wb.SaveAs(out_path, FileFormat=56)  # 56 = .xls format
        wb.Close(SaveChanges=False)
        return out_path
    finally:
        excel.Quit()


def unprotect_xls_via_conversion(xls_path: str, out_path: str) -> str:
    """
    Fallback: Convert .xls to .xlsx without protection using xlrd + openpyxl.
    Used when pywin32/Microsoft Excel is not available.

    Args:
        xls_path: Path to the protected .xls file
        out_path: Path where the unprotected file will be saved (will be .xlsx)

    Returns:
        Path to the unprotected .xlsx file
    """
    import xlrd
    from openpyxl import Workbook
    from openpyxl.utils import get_column_letter

    rb = xlrd.open_workbook(xls_path, formatting_info=False)
    wb = Workbook()
    # Remove the default sheet created by openpyxl
    wb.remove(wb.active)

    for sheet_name in rb.sheet_names():
        rs = rb.sheet_by_name(sheet_name)
        ws = wb.create_sheet(title=sheet_name)

        for row_idx in range(rs.nrows):
            for col_idx in range(rs.ncols):
                cell = rs.cell(row_idx, col_idx)
                value = cell.value

                # Convert xlrd date floats to Python datetime
                if cell.ctype == xlrd.XL_CELL_DATE:
                    try:
                        value = xlrd.xldate_as_datetime(value, rb.datemode)
                    except Exception:
                        pass
                # Convert xlrd boolean
                elif cell.ctype == xlrd.XL_CELL_BOOLEAN:
                    value = bool(value)

                ws.cell(row=row_idx + 1, column=col_idx + 1, value=value)

        # Copy merged cells
        for merged_range in rs.merged_cells:
            rlo, rhi, clo, chi = merged_range
            ws.merge_cells(
                start_row=rlo + 1, start_column=clo + 1,
                end_row=rhi, end_column=chi
            )

    # Ensure output path has .xlsx extension
    base, ext = os.path.splitext(out_path)
    if ext.lower() == '.xls':
        out_path = base + '.xlsx'

    wb.save(out_path)
    print(f"Converted .xls to .xlsx (no protection): {out_path}")
    return out_path


def unprotect_xls_keep_xls(xls_path: str, out_path: str) -> str:
    """
    Remove protection from .xls file.
    Tries COM automation first, falls back to xlrd+openpyxl conversion.

    Args:
        xls_path: Path to the protected .xls file
        out_path: Path where the unprotected file will be saved

    Returns:
        Path to the unprotected file
    """
    # Try COM automation first (best quality, preserves formatting)
    if win32 is not None:
        try:
            return unprotect_xls_via_com(xls_path, out_path)
        except Exception as e:
            print(f"COM automation failed: {e}, falling back to conversion")

    # Fallback: convert .xls -> .xlsx using xlrd + openpyxl
    return unprotect_xls_via_conversion(xls_path, out_path)


def detect_real_type_from_bytes(data: bytes) -> str:
    """Detect the actual file type from raw bytes."""
    if data[:4] == b'\xD0\xCF\x11\xE0':
        return 'xls'
    if data[:4] == b'PK\x03\x04':
        return 'xlsx'
    if data[:5] == b'<?xml':
        return 'xml'
    chunk = data[:2048].lower()
    if b'<html' in chunk or b'<table' in chunk:
        return 'html'
    return 'unknown'


def unprotect_xlsx_bytes(data: bytes) -> bytes:
    """Remove protection from .xlsx bytes in memory. Returns unprotected .xlsx bytes."""
    from io import BytesIO
    tmpdir = tempfile.mkdtemp()
    try:
        with zipfile.ZipFile(BytesIO(data), 'r') as zf:
            zf.extractall(tmpdir)

        ns = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

        ws_dir = os.path.join(tmpdir, 'xl', 'worksheets')
        if os.path.isdir(ws_dir):
            for name in os.listdir(ws_dir):
                if name.endswith('.xml'):
                    p = os.path.join(ws_dir, name)
                    try:
                        tree = ET.parse(p)
                        root = tree.getroot()
                        for sp in root.findall('m:sheetProtection', ns):
                            root.remove(sp)
                        tree.write(p, encoding='utf-8', xml_declaration=True)
                    except Exception:
                        pass

        wb_xml = os.path.join(tmpdir, 'xl', 'workbook.xml')
        if os.path.exists(wb_xml):
            try:
                tree = ET.parse(wb_xml)
                root = tree.getroot()
                for wp in root.findall('m:workbookProtection', ns):
                    root.remove(wp)
                tree.write(wb_xml, encoding='utf-8', xml_declaration=True)
            except Exception:
                pass

        out_buf = BytesIO()
        with zipfile.ZipFile(out_buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            for folder, _, files in os.walk(tmpdir):
                for f in files:
                    full = os.path.join(folder, f)
                    arc = os.path.relpath(full, tmpdir).replace('\\', '/')
                    zf.write(full, arc)
        return out_buf.getvalue()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def unprotect_xls_bytes_to_xlsx(data: bytes) -> bytes:
    """Convert .xls bytes to unprotected .xlsx bytes using xlrd + openpyxl (in memory)."""
    import xlrd
    from openpyxl import Workbook
    from io import BytesIO

    rb = xlrd.open_workbook(file_contents=data, formatting_info=False)
    wb = Workbook()
    wb.remove(wb.active)

    for sheet_name in rb.sheet_names():
        rs = rb.sheet_by_name(sheet_name)
        ws = wb.create_sheet(title=sheet_name)

        for row_idx in range(rs.nrows):
            for col_idx in range(rs.ncols):
                cell = rs.cell(row_idx, col_idx)
                value = cell.value

                if cell.ctype == xlrd.XL_CELL_DATE:
                    try:
                        value = xlrd.xldate_as_datetime(value, rb.datemode)
                    except Exception:
                        pass
                elif cell.ctype == xlrd.XL_CELL_BOOLEAN:
                    value = bool(value)

                ws.cell(row=row_idx + 1, column=col_idx + 1, value=value)

        for merged_range in rs.merged_cells:
            rlo, rhi, clo, chi = merged_range
            ws.merge_cells(
                start_row=rlo + 1, start_column=clo + 1,
                end_row=rhi, end_column=chi
            )

    out_buf = BytesIO()
    wb.save(out_buf)
    return out_buf.getvalue()


def unprotect_excel_bytes(data: bytes, filename: str = "") -> tuple[bytes, str]:
    """
    Unprotect Excel file from raw bytes (in memory, no disk I/O).

    Args:
        data: Raw Excel file bytes
        filename: Original filename (used for extension hint)

    Returns:
        Tuple of (unprotected_bytes, output_filename)
    """
    real_type = detect_real_type_from_bytes(data)
    base, ext = os.path.splitext(filename)

    if real_type == 'xlsx':
        out_bytes = unprotect_xlsx_bytes(data)
        return out_bytes, f"{base}_unprotected.xlsx"
    elif real_type == 'xls':
        out_bytes = unprotect_xls_bytes_to_xlsx(data)
        return out_bytes, f"{base}_unprotected.xlsx"
    else:
        # Return as-is if not a recognized Excel format
        return data, filename


def unprotect_excel_file(file_path: str, output_path: str = None) -> str:
    """
    Unprotect an Excel file (auto-detects format and applies appropriate method).
    
    Args:
        file_path: Path to the Excel file to unprotect
        output_path: Optional path for the output file. If None, creates a file with 
                    '_unprotected' suffix in the same directory
        
    Returns:
        Path to the unprotected file, or None if file couldn't be processed
        
    Raises:
        FileNotFoundError: If the input file doesn't exist
        RuntimeError: If Excel is required but not available
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    base, ext = os.path.splitext(os.path.basename(file_path))
    
    # Check if already unprotected
    if base.endswith('_unprotected'):
        print(f"File already unprotected: {file_path}")
        return file_path
    
    # Determine output path
    if output_path is None:
        output_path = os.path.join(os.path.dirname(file_path), f"{base}_unprotected{ext}")
    
    # Detect actual file type
    real_type = detect_real_type(file_path)
    
    if real_type == 'xlsx':
        return unprotect_xlsx(file_path, output_path)
    elif real_type == 'xls':
        return unprotect_xls_keep_xls(file_path, output_path)
    else:
        print(f"Skip non-Excel or unsupported file ({real_type}): {file_path}")
        return None

