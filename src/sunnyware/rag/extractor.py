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


def extract_xlsx(path: Path) -> List[Dict]:
    from openpyxl import load_workbook
    wb = load_workbook(str(path), read_only=True, data_only=True)
    out = []
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        it = ws.iter_rows(values_only=True)
        try:
            headers = [str(h) if h is not None else "" for h in next(it)]
        except StopIteration:
            continue
        rows = []
        for row in it:
            d = {headers[i]: row[i] for i in range(min(len(headers), len(row)))}
            rows.append(d)
        if rows:
            out.append({"source": f"{path.name} [{sheet_name}]", "rows": rows})
    return out


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
