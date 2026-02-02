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


def unprotect_xls_keep_xls(xls_path: str, out_path: str) -> str:
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

