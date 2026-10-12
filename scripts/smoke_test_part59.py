#!/usr/bin/env python3
"""Part 59 smoke test — pdf_report tool."""
import ast, base64, os, sys, asyncio
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

PASS, FAIL = 0, 0


def check(label, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label}" + (f" — {detail}" if detail else ""))


def main():
    print("=" * 62)
    print(" Part 59 — pdf_report tool")
    print("=" * 62)

    tool_file = ROOT / "src/sunnyware/tools/pdf_report.py"
    init_file = ROOT / "src/sunnyware/tools/__init__.py"

    check("pdf_report.py exists", tool_file.exists())
    if not tool_file.exists():
        return 1

    src = tool_file.read_text(encoding="utf-8")
    init_src = init_file.read_text(encoding="utf-8")

    check("class defined", "class PdfReportTool" in src)
    check("name = pdf_report", 'name = "pdf_report"' in src)
    check("PdfPages used", "PdfPages" in src)
    check("text page helper", "_text_page" in src)
    check("table page helper", "_table_page" in src)
    check("chart page helper", "_chart_page" in src)
    check("workspace jail", "_workspace_root" in src)
    check("safe filename", "_safe_name" in src)
    check("max pages cap", "_MAX_PAGES" in src)
    check("registered in __init__",
          "PdfReportTool.name: PdfReportTool()" in init_src)

    try:
        ast.parse(src)
        check("pdf_report.py parses", True)
    except SyntaxError as e:
        check("pdf_report.py parses", False, detail=str(e))

    try:
        import matplotlib  # noqa
        check("matplotlib importable", True)
    except Exception as e:
        check("matplotlib importable", False, detail=str(e))
        return 1 if FAIL else 0

    # Integration — build a 3-page PDF (text, table, chart)
    async def run(**kw):
        from sunnyware.tools.pdf_report import PdfReportTool
        return await PdfReportTool().run(kw)

    # Generate a small chart first via chart_from_data
    async def mkchart():
        from sunnyware.tools.chart_from_data import ChartFromDataTool
        r = await ChartFromDataTool().run({
            "data": [{"x": "APAC", "y": 100}, {"x": "EMEA", "y": 150},
                     {"x": "AMER", "y": 200}],
            "chart_type": "bar", "x": "x", "y": "y",
            "title": "Regional Revenue",
        })
        return r.get("image_base64")

    chart_b64 = asyncio.run(mkchart())
    check("chart_from_data produced png", bool(chart_b64))

    pages = [
        {"type": "text", "title": "Executive Summary",
         "body": "Revenue grew 12% QoQ.\n\nHighlights:\n- APAC up 15%\n- EMEA up 8%\n- AMER up 11%"},
        {"type": "table", "title": "Regional Breakdown",
         "headers": ["Region", "Revenue", "QoQ %"],
         "rows": [["APAC", "$100M", "+15%"],
                  ["EMEA", "$150M", "+8%"],
                  ["AMER", "$200M", "+11%"]]},
    ]
    if chart_b64:
        pages.append({"type": "chart", "title": "Regional Chart",
                      "image_base64": chart_b64, "caption": "Revenue by region"})

    r = asyncio.run(run(
        filename="smoke_p59.pdf",
        title="Q3 FP&A Report",
        pages=pages,
    ))
    check("pdf generation succeeds", "error" not in r,
          detail=str(r)[:200] if r.get("error") else "")
    if "error" not in r:
        check("3 pages rendered", r.get("pages_rendered") == 3,
              detail=f"got {r.get('pages_rendered')}")
        check("PDF file exists on disk", Path(r["path"]).exists())
        check("PDF size > 5 KB", r.get("size_bytes", 0) > 5000,
              detail=f"got {r.get('size_bytes')}")
        check("preview_image_base64 returned",
              bool(r.get("preview_image_base64")))

    # Rejections
    r2 = asyncio.run(run(pages=[]))
    check("empty pages rejected", "error" in r2)

    r3 = asyncio.run(run(pages=[{"type": "text", "title": "x", "body": "y"}],
                          filename="../escape.pdf"))
    check("filename escape rejected OR sanitized",
          "error" in r3 or "/" not in r3.get("filename", ""))

    # Cleanup
    try:
        Path(r.get("path", "")).unlink()
    except Exception:
        pass

    print()
    print("=" * 62)
    print(f" RESULT: {PASS} passed, {FAIL} failed")
    print("=" * 62)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
