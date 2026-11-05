# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Export tabular data to CSV/JSON/TSV in workspace OR sandbox."""
import json
from pathlib import Path


class ExportTableTool:
    name = "export_table"
    category = "Data"
    description = (
        "Export tabular data to a CSV, TSV, or JSON file. "
        "Works on BOTH workspace and sandbox (controlled by 'target_kind'). "
        "Provide EITHER 'rows' (JSON array of objects) OR 'source_file' (an .xlsx/.xls/.xlsm/.csv). "
        "Use this to save extracted Power BI / Tableau / Excel data as CSV so users can download it. "
        "Default target is sandbox (for AI-generated intermediate files). "
        "Set target_kind='workspace' to save into the user's workspace instead. "
        "Example: after read_bi_file returns Excel sheet rows, call export_table with rows=... to save as CSV."
    )
    parameters = {
        "filename": {
            "type": "string",
            "description": "Output filename (e.g. 'sales_export.csv', 'tableau_data.json')",
            "required": True,
        },
        "rows": {
            "type": "string",
            "description": "JSON array of row objects (e.g. '[{\"name\":\"Alice\",\"age\":30}]'). Alternative to source_file.",
            "required": False,
        },
        "source_file": {
            "type": "string",
            "description": "Source file to read (e.g. 'sales.xlsx'). Alternative to rows.",
            "required": False,
        },
        "source_kind": {
            "type": "string",
            "description": "Where source_file lives: 'workspace' (default) or 'sandbox'",
            "required": False,
        },
        "target_kind": {
            "type": "string",
            "description": "Where to save output: 'sandbox' (default) or 'workspace'",
            "required": False,
        },
        "sheet": {
            "type": "string",
            "description": "Optional sheet name when using source_file",
            "required": False,
        },
        "columns": {
            "type": "string",
            "description": "Optional comma-separated list of columns to keep (e.g. 'name,age')",
            "required": False,
        },
    }

    async def run(self, args: dict) -> dict:
        from .. import paths
        fname = (args.get("filename") or "").strip()
        if not fname:
            return {"error": "filename is required"}
        fname = Path(fname).name
        ext = Path(fname).suffix.lower()
        if ext not in (".csv", ".json", ".tsv"):
            return {"error": f"only .csv/.json/.tsv supported, got: {ext}"}

        # Where to write
        target_kind = (args.get("target_kind") or "sandbox").strip().lower()
        if target_kind not in ("workspace", "sandbox"):
            target_kind = "sandbox"
        target_base = paths.workspace() if target_kind == "workspace" else paths.sandbox()

        source_file = (args.get("source_file") or "").strip()
        rows_arg = args.get("rows")

        rows = []
        if source_file:
            src_kind = (args.get("source_kind") or "workspace").strip().lower()
            if src_kind not in ("workspace", "sandbox"):
                src_kind = "workspace"
            src_base = paths.workspace() if src_kind == "workspace" else paths.sandbox()
            target = src_base / Path(source_file).name
            if not target.exists():
                return {"error": f"source file not found in {src_kind}: {target}"}
            try:
                from .. import office_preview
                src_ext = target.suffix.lower()
                if src_ext == ".xlsx":
                    sheets = office_preview._extract_sheets_from_xlsx(target)
                elif src_ext in (".xls", ".xlsm"):
                    r = office_preview.parse_xls(target)
                    if r.get("error"): return r
                    sheets = r.get("sheets", {})
                elif src_ext == ".csv":
                    import csv as _csv
                    with open(str(target), "r", encoding="utf-8", errors="replace") as f:
                        reader = _csv.DictReader(f)
                        rows = list(reader)
                    sheets = {"CSV": {"rows": rows}}
                else:
                    return {"error": f"unsupported source: {src_ext}"}
                wanted_sheet = (args.get("sheet") or "").strip()
                if wanted_sheet and wanted_sheet in sheets:
                    sheet_data = sheets[wanted_sheet]
                else:
                    first = next(iter(sheets.values()), None)
                    if not first:
                        return {"error": "no sheet data found"}
                    sheet_data = first
                rows = sheet_data.get("rows", [])
            except Exception as e:
                return {"error": f"source load failed: {type(e).__name__}: {e}"}
        elif rows_arg:
            try:
                parsed = json.loads(rows_arg) if isinstance(rows_arg, str) else rows_arg
                if isinstance(parsed, dict) and "rows" in parsed:
                    parsed = parsed["rows"]
                if not isinstance(parsed, list):
                    return {"error": "rows must be a JSON array"}
                rows = parsed
            except json.JSONDecodeError as e:
                return {"error": f"rows JSON invalid: {e}"}
        else:
            return {"error": "provide either 'rows' or 'source_file'"}

        # Column filter
        columns_arg = (args.get("columns") or "").strip()
        if columns_arg:
            wanted = [c.strip() for c in columns_arg.split(",") if c.strip()]
            rows = [{k: r.get(k) for k in wanted if k in r} for r in rows]

        # Write output
        target_base.mkdir(parents=True, exist_ok=True)
        out_path = target_base / fname

        try:
            if ext == ".csv":
                if not rows:
                    out_path.write_text("", encoding="utf-8")
                else:
                    headers = list(rows[0].keys())
                    lines = [",".join(headers)]
                    for r in rows:
                        line = ",".join('"' + str(r.get(h, "")).replace('"', '""') + '"' for h in headers)
                        lines.append(line)
                    out_path.write_text("\n".join(lines), encoding="utf-8")
            elif ext == ".tsv":
                if not rows:
                    out_path.write_text("", encoding="utf-8")
                else:
                    headers = list(rows[0].keys())
                    lines = ["\t".join(headers)]
                    for r in rows:
                        line = "\t".join(str(r.get(h, "")).replace("\t", " ") for h in headers)
                        lines.append(line)
                    out_path.write_text("\n".join(lines), encoding="utf-8")
            elif ext == ".json":
                out_path.write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")

            return {
                "ok": True,
                "file": fname,
                "target_kind": target_kind,
                "path": str(out_path),
                "row_count": len(rows),
                "size": out_path.stat().st_size,
            }
        except Exception as e:
            return {"error": f"write failed: {type(e).__name__}: {e}"}
