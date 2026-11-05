# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Read BI and Office files from sandbox/workspace (BI tool for agents)."""
from pathlib import Path


def _safe_path(kind: str, rel: str) -> Path:
    from .. import paths
    base = paths.workspace() if kind == "workspace" else paths.sandbox()
    base.mkdir(parents=True, exist_ok=True)
    name = Path(rel).name
    target = (base / name).resolve()
    if not str(target).startswith(str(base)):
        raise ValueError(f"path escapes {kind}: {rel}")
    return target


class ReadBiFileTool:
    name = "read_bi_file"
    category = "Data"
    description = (
        "Read and inspect any Office or BI file in the workspace or sandbox. "
        "Supports: .xlsx/.xls/.xlsm (returns sheets as table data), "
        ".docx/.doc (paragraphs + tables), .pptx/.ppt (slide text), "
        ".pbix (Power BI metadata + report pages), "
        ".twb/.twbx (Tableau datasources + worksheets + calculated fields). "
        "Use this to answer questions like 'what's in this Excel file?', "
        "'summarize the Power BI report', 'list Tableau calculated fields'. "
        "Do NOT use for user-uploaded attachments (use rag_search for those)."
    )
    parameters = {
        "file": {
            "type": "string",
            "description": "Filename (e.g. 'sales.xlsx', 'report.pbix', 'dashboard.twbx')",
            "required": True,
        },
        "kind": {
            "type": "string",
            "description": "'workspace' (default) or 'sandbox'",
            "required": False,
        },
        "include_rows": {
            "type": "boolean",
            "description": "Include actual row data for tabular files (default true). False returns only headers + counts.",
            "required": False,
        },
        "max_rows_per_sheet": {
            "type": "integer",
            "description": "Max rows per sheet for Excel (default 100, max 500).",
            "required": False,
        },
    }

    async def run(self, args: dict) -> dict:
        rel = (args.get("file") or "").strip()
        if not rel:
            return {"error": "file is required"}
        kind = (args.get("kind") or "workspace").strip().lower()
        if kind not in ("workspace", "sandbox"):
            kind = "workspace"
        include_rows = args.get("include_rows", True)
        try:
            max_rows = int(args.get("max_rows_per_sheet") or 100)
        except (TypeError, ValueError):
            max_rows = 100
        max_rows = max(1, min(max_rows, 500))

        try:
            target = _safe_path(kind, rel)
        except ValueError as e:
            return {"error": str(e)}

        if not target.exists():
            return {"error": f"file not found in {kind}: {rel}"}

        ext = target.suffix.lower()

        try:
            from .. import office_preview
        except Exception as e:
            return {"error": f"office_preview unavailable: {e}"}

        try:
            if ext == ".xlsx":
                result = office_preview._extract_sheets_from_xlsx(target)
                return self._format_tabular(result, target, include_rows, max_rows, "xlsx")
            elif ext in (".xls", ".xlsm"):
                result = office_preview.parse_xls(target)
                if result.get("error"):
                    return result
                return self._format_tabular(result.get("sheets", {}), target, include_rows, max_rows, result.get("engine", "xls"))
            elif ext == ".docx":
                result = office_preview.parse_docx(target)
                return self._format_docx(result, target)
            elif ext == ".doc":
                result = office_preview.parse_doc(target)
                return self._format_docx(result, target)
            elif ext == ".pptx":
                result = office_preview.parse_pptx(target)
                return self._format_pptx(result, target)
            elif ext == ".ppt":
                result = office_preview.parse_ppt(target)
                return self._format_pptx(result, target)
            elif ext == ".pbix":
                result = office_preview.parse_pbix(target)
                return self._format_pbix(result, target)
            elif ext in (".twb", ".twbx"):
                result = office_preview.parse_twb(target) if ext == ".twb" else office_preview.parse_twbx(target)
                return self._format_twb(result, target)
            else:
                return {"error": f"unsupported file type: {ext} (supported: .xlsx .xls .xlsm .docx .doc .pptx .ppt .pbix .twb .twbx)"}
        except Exception as e:
            return {"error": f"read failed: {type(e).__name__}: {e}"}

    def _format_tabular(self, sheets: dict, target: Path, include_rows: bool, max_rows: int, engine: str) -> dict:
        out_sheets = {}
        for sname, sdata in (sheets or {}).items():
            headers = sdata.get("headers", [])
            rows = sdata.get("rows", [])
            entry = {"headers": headers, "row_count": len(rows)}
            if include_rows:
                entry["rows"] = rows[:max_rows]
                if len(rows) > max_rows:
                    entry["truncated"] = True
                    entry["total_rows"] = len(rows)
            out_sheets[sname] = entry
        return {"ok": True, "file": target.name, "engine": engine, "type": "tabular", "sheets": out_sheets, "size": target.stat().st_size}

    def _format_docx(self, result: dict, target: Path) -> dict:
        if result.get("error"):
            return result
        return {
            "ok": True, "file": target.name, "type": "docx",
            "engine": result.get("engine", "python-docx"),
            "paragraph_count": result.get("paragraph_count", 0),
            "paragraphs": result.get("paragraphs", [])[:200],
            "tables": result.get("tables", []),
            "size": target.stat().st_size,
        }

    def _format_pptx(self, result: dict, target: Path) -> dict:
        if result.get("error"):
            return result
        return {
            "ok": True, "file": target.name, "type": "pptx",
            "engine": result.get("engine", "python-pptx"),
            "slide_count": result.get("slide_count", 0),
            "slides": result.get("slides", [])[:200],
            "size": target.stat().st_size,
        }

    def _format_pbix(self, result: dict, target: Path) -> dict:
        if result.get("error"):
            return result
        return {
            "ok": True, "file": target.name, "type": "pbix",
            "version": result.get("version", ""),
            "has_report": result.get("has_report", False),
            "has_datamodel": result.get("has_datamodel", False),
            "pages": result.get("pages", []),
            "page_count": result.get("page_count", 0),
            "total_files": result.get("total_files", 0),
            "contents_sample": result.get("contents", [])[:20],
            "size": target.stat().st_size,
            "note": "Power BI .pbix is proprietary - cannot edit. Use export_table to save extracted data as CSV.",
        }

    def _format_twb(self, result: dict, target: Path) -> dict:
        if result.get("error"):
            return result
        return {
            "ok": True, "file": target.name, "type": "twb",
            "datasources": result.get("datasources", []),
            "worksheets": result.get("worksheets", []),
            "dashboards": result.get("dashboards", []),
            "calc_fields": result.get("calc_fields", []),
            "parameters": result.get("parameters", []),
            "filters": result.get("filters", []),
            "size": target.stat().st_size,
            "note": "Tableau .twb/.twbx is XML-based - cannot edit via AI. Use export_table to save datasource data as CSV.",
        }
