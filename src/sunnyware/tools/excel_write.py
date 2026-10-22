# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Excel writer tool (Part 61).

Write .xlsx files with real formatting: multiple sheets, bold headers,
freeze panes, column widths, number formats, formulas, conditional fills.

openpyxl is already present in the sandbox — zero new deps.
"""
import base64
import os
import re
from pathlib import Path
from typing import Optional

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    _HAS_OPENPYXL = True
except Exception:
    _HAS_OPENPYXL = False


_MAX_SHEETS = 20
_MAX_ROWS = 10000
_MAX_COLS = 100
_MAX_RETURN_BYTES = 200 * 1024  # base64 return cap

# Common number format shortcuts
_NUMFMT = {
    "int": "#,##0",
    "float": "#,##0.00",
    "money": "$#,##0",
    "money_cents": "$#,##0.00",
    "percent": "0.0%",
    "percent2": "0.00%",
    "date": "yyyy-mm-dd",
    "datetime": "yyyy-mm-dd hh:mm",
}


def _workspace_root() -> Path:
    p = os.getenv("SUNNYWARE_WORKSPACE") or os.getenv("WORKSPACE_PATH")
    if p:
        return Path(p).resolve()
    return Path("/data/workspace").resolve()


def _safe_name(name: str) -> str:
    name = (name or "workbook.xlsx").strip()
    cleaned = "".join(c if (c.isalnum() or c in "._-") else "_" for c in name)
    if not cleaned.lower().endswith(".xlsx"):
        cleaned += ".xlsx"
    return cleaned[:120]


def _safe_sheet_name(name: str, idx: int) -> str:
    name = (name or f"Sheet{idx + 1}").strip()
    # Excel forbids : \ / ? * [ ]
    name = re.sub(r"[:\\/\?\*\[\]]", "_", name)
    return name[:31] or f"Sheet{idx + 1}"


def _coerce_cell(v):
    """If v is a dict with 'formula', return it as a formula string."""
    if isinstance(v, dict):
        f = v.get("formula")
        if isinstance(f, str) and f.startswith("="):
            return f
    return v


class ExcelWriteTool:
    name = "excel_write"
    description = "Write data to an Excel .xlsx file. Triggers: write Excel, save to Excel, create spreadsheet. Input: filepath and data array. Returns confirmation."
    parameters = {
        "filename": {
            "type": "string",
            "description": "Output filename (default workbook.xlsx)",
            "required": False,
        },
        "sheets": {
            "type": "array",
            "description": "Array of sheet specs (see description).",
            "required": True,
        },
        "include_base64": {
            "type": "boolean",
            "description": "Return base64 of file if under 200 KB (default true)",
            "required": False,
        },
    }

    async def run(self, args: dict) -> dict:
        if not _HAS_OPENPYXL:
            return {"error": "openpyxl not installed in this environment"}

        sheets = args.get("sheets")
        if not isinstance(sheets, list) or not sheets:
            return {"error": "sheets must be a non-empty array"}
        if len(sheets) > _MAX_SHEETS:
            return {"error": f"too many sheets (max {_MAX_SHEETS})"}

        fname = _safe_name(args.get("filename") or "workbook.xlsx")
        root = _workspace_root()
        try:
            root.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return {"error": f"workspace not writable: {e}"}
        out_path = (root / fname).resolve()
        try:
            out_path.relative_to(root)
        except ValueError:
            return {"error": "filename escapes workspace"}

        wb = Workbook()
        # Remove the default sheet — we'll add our own
        wb.remove(wb.active)

        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill("solid", fgColor="1D2026")
        header_align = Alignment(horizontal="left", vertical="center")
        thin = Side(style="thin", color="D0D0D0")
        border = Border(left=thin, right=thin, top=thin, bottom=thin)

        sheets_written = 0
        rows_written = 0

        try:
            for idx, spec in enumerate(sheets):
                if not isinstance(spec, dict):
                    continue
                name = _safe_sheet_name(spec.get("name"), idx)
                ws = wb.create_sheet(title=name)

                tab_color = spec.get("tab_color")
                if isinstance(tab_color, str) and re.match(r"^[0-9A-Fa-f]{6}$", tab_color):
                    ws.sheet_properties.tabColor = tab_color

                headers = spec.get("headers") or []
                rows = spec.get("rows") or []
                if not isinstance(rows, list):
                    rows = []
                if len(rows) > _MAX_ROWS:
                    rows = rows[:_MAX_ROWS]

                # Write headers
                if headers:
                    if len(headers) > _MAX_COLS:
                        headers = headers[:_MAX_COLS]
                    for c, h in enumerate(headers, start=1):
                        cell = ws.cell(row=1, column=c, value=str(h))
                        cell.font = header_font
                        cell.fill = header_fill
                        cell.alignment = header_align
                        cell.border = border

                # Write rows
                for r, row in enumerate(rows, start=2):
                    if not isinstance(row, list):
                        continue
                    for c, v in enumerate(row, start=1):
                        if c > _MAX_COLS:
                            break
                        cell = ws.cell(row=r, column=c, value=_coerce_cell(v))
                        cell.border = border
                    rows_written += 1

                # Column widths
                widths = spec.get("column_widths") or []
                for i, w in enumerate(widths, start=1):
                    try:
                        ws.column_dimensions[get_column_letter(i)].width = float(w)
                    except Exception:
                        pass
                # Auto-width heuristic if no explicit widths and we have headers
                if not widths and headers:
                    for c, h in enumerate(headers, start=1):
                        try:
                            maxlen = len(str(h))
                            for row in rows[:50]:  # sample first 50 rows
                                if isinstance(row, list) and c - 1 < len(row):
                                    v = row[c - 1]
                                    if isinstance(v, dict):
                                        v = v.get("formula", "")
                                    maxlen = max(maxlen, len(str(v)))
                            ws.column_dimensions[get_column_letter(c)].width = min(
                                max(maxlen + 2, 8), 50)
                        except Exception:
                            pass

                # Number formats: {"1": "money", "3": "percent"}
                nfmt = spec.get("number_formats") or {}
                if isinstance(nfmt, dict):
                    for col_key, fmt_key in nfmt.items():
                        try:
                            col_idx = int(col_key)
                        except (TypeError, ValueError):
                            continue
                        fmt = _NUMFMT.get(str(fmt_key).lower())
                        if not fmt:
                            continue
                        for r in range(1, len(rows) + 2):
                            try:
                                ws.cell(row=r, column=col_idx).number_format = fmt
                            except Exception:
                                pass

                # Freeze panes (headers row by default)
                if spec.get("freeze", True) and headers:
                    ws.freeze_panes = "A2"

                sheets_written += 1
        except Exception as e:
            return {"error": f"workbook build failed: {type(e).__name__}: {e}"}

        try:
            wb.save(str(out_path))
        except Exception as e:
            return {"error": f"save failed: {type(e).__name__}: {e}"}

        try:
            size = out_path.stat().st_size
        except Exception:
            size = 0

        result = {
            "filename": fname,
            "path": str(out_path),
            "sheets_written": sheets_written,
            "rows_written": rows_written,
            "size_bytes": size,
        }

        if args.get("include_base64", True) and size <= _MAX_RETURN_BYTES:
            try:
                result["base64"] = base64.b64encode(
                    out_path.read_bytes()).decode("ascii")
                result["returned_base64"] = True
            except Exception:
                result["returned_base64"] = False
        else:
            result["returned_base64"] = False
            if size > _MAX_RETURN_BYTES:
                result["note"] = (
                    f"file is {size} bytes, exceeds {_MAX_RETURN_BYTES} "
                    f"base64 return cap. Use the path instead."
                )

        return result
