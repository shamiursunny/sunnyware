# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Multi-format file extraction. Returns list of {source, text} blocks."""

from pathlib import Path
from typing import List, Dict
import csv


def extract_pdf(path: Path) -> List[Dict]:
    from pypdf import PdfReader
    out = []
    reader = PdfReader(str(path))
    for i, page in enumerate(reader.pages):
        try:
            txt = page.extract_text() or ""
        except Exception:
            txt = ""
        if txt.strip():
            out.append({"source": f"{path.name} (page {i+1})", "text": txt})
    return out


def extract_docx(path: Path) -> List[Dict]:
    from docx import Document
    doc = Document(str(path))
    parts = [p.text for p in doc.paragraphs if p.text.strip()]
    if not parts:
        return []
    return [{"source": path.name, "text": "\n".join(parts)}]


def extract_text(path: Path) -> List[Dict]:
    txt = path.read_text(encoding="utf-8", errors="ignore")
    return [{"source": path.name, "text": txt}] if txt.strip() else []


def extract_csv(path: Path) -> List[Dict]:
    rows = []
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(dict(row))
    return [{"source": path.name, "rows": rows}]


def _xlsx_extract_with_mode(path: Path, data_only: bool) -> List[Dict]:
    """Extract with a specific data_only mode. Returns list of blocks."""
    from openpyxl import load_workbook
    from openpyxl.utils import get_column_letter
    try:
        wb = load_workbook(str(path), read_only=True, data_only=data_only)
    except Exception:
        return []
    out = []
    for sheet_name in wb.sheetnames:
        try:
            ws = wb[sheet_name]
            it = ws.iter_rows(values_only=True)

            # Scan up to 10 rows to find the first row that has at least one
            # non-empty cell — treat that as the header row.
            header_row = None
            buffered = []
            for _ in range(10):
                try:
                    row = next(it)
                except StopIteration:
                    break
                buffered.append(row)
                if any(c is not None and str(c).strip() for c in row):
                    header_row = row
                    break

            if header_row is None:
                # No non-empty row in first 10 — sheet is essentially blank
                continue

            # Build (index, header) pairs, falling back to column letters
            headers = []
            for idx, h in enumerate(header_row):
                hs = str(h).strip() if h is not None else ""
                if not hs:
                    hs = "col_" + get_column_letter(idx + 1)
                headers.append((idx, hs))

            rows = []
            # Consume remaining buffered rows (after header_row index) + iterator
            start_idx = buffered.index(header_row) + 1
            for row in buffered[start_idx:]:
                d = {}
                for idx, hname in headers:
                    if idx < len(row):
                        val = row[idx]
                        if val is not None and str(val).strip():
                            d[hname] = val
                if d:
                    rows.append(d)
            for row in it:
                d = {}
                for idx, hname in headers:
                    if idx < len(row):
                        val = row[idx]
                        if val is not None and str(val).strip():
                            d[hname] = val
                if d:
                    rows.append(d)

            if rows:
                out.append({"source": f"{path.name} [{sheet_name}]", "rows": rows})
        except Exception:
            continue
    return out


def extract_xlsx(path: Path) -> List[Dict]:
    """Extract XLSX/XLS.

    Strategy:
      1. Try cached values (data_only=True), scan up to 10 rows for headers.
      2. If nothing, retry with data_only=False to capture formula strings.
      3. If still nothing, dump every non-empty cell as a text block
         (last-resort fallback so the file is never entirely invisible).
    """
    out = _xlsx_extract_with_mode(path, data_only=True)
    if out:
        return out
    out = _xlsx_extract_with_mode(path, data_only=False)
    if out:
        return out
    # Last-resort: dump every non-empty cell as text
    try:
        from openpyxl import load_workbook
        wb = load_workbook(str(path), read_only=True, data_only=False)
        chunks = []
        for sheet_name in wb.sheetnames:
            try:
                ws = wb[sheet_name]
                for row in ws.iter_rows(values_only=True):
                    cells = [str(c).strip() for c in row if c is not None and str(c).strip()]
                    if cells:
                        chunks.append(" | ".join(cells))
            except Exception:
                continue
        text = "\n".join(chunks)
        if text.strip():
            return [{"source": f"{path.name} [raw cells]", "text": text}]
    except Exception:
        pass
    return []


EXTRACTORS = {
    ".pdf": extract_pdf,
    ".docx": extract_docx,
    ".txt": extract_text,
    ".md": extract_text,
    ".csv": extract_csv,
    ".xlsx": extract_xlsx,
    ".xls": extract_xlsx,
}


def extract(path: Path) -> List[Dict]:
    ext = path.suffix.lower()
    fn = EXTRACTORS.get(ext)
    if not fn:
        raise ValueError(f"unsupported extension: {ext}")
    return fn(path)


def supported_extensions() -> list:
    return sorted(EXTRACTORS.keys())
