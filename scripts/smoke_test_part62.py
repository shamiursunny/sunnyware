#!/usr/bin/env python3
"""Part 62 smoke test — excel_read tool."""
import ast, os, sys, asyncio
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
    print(" Part 62 — excel_read tool")
    print("=" * 62)

    tool_file = ROOT / "src/sunnyware/tools/excel_read.py"
    init_file = ROOT / "src/sunnyware/tools/__init__.py"

    check("excel_read.py exists", tool_file.exists())
    if not tool_file.exists():
        return 1

    src = tool_file.read_text(encoding="utf-8")
    init_src = init_file.read_text(encoding="utf-8")

    check("class defined", "class ExcelReadTool" in src)
    check("name = excel_read", 'name = "excel_read"' in src)
    check("uses load_workbook", "load_workbook" in src)
    check("workspace jail", "_workspace_root" in src)
    check("row cap", "_MAX_ROWS_PER_SHEET" in src)
    check("col cap", "_MAX_COLS" in src)
    check("formula support", "include_formulas" in src)
    check("list_only mode", "list_only" in src)
    check("registered in __init__",
          "ExcelReadTool.name: ExcelReadTool()" in init_src)

    try:
        ast.parse(src)
        check("excel_read.py parses", True)
    except SyntaxError as e:
        check("excel_read.py parses", False, detail=str(e))

    try:
        import openpyxl  # noqa
        check("openpyxl importable", True)
    except Exception as e:
        check("openpyxl importable", False, detail=str(e))
        return 1 if FAIL else 0

    # Integration: write an xlsx with excel_write, then read it back
    async def write_wb():
        from sunnyware.tools.excel_write import ExcelWriteTool
        return await ExcelWriteTool().run({
            "filename": "smoke_p62.xlsx",
            "include_base64": False,
            "sheets": [
                {
                    "name": "P&L",
                    "headers": ["Line", "FY24", "FY25E"],
                    "rows": [
                        ["Revenue", 12000000, 15600000],
                        ["COGS", 7200000, 9100000],
                        ["Gross Profit",
                         {"formula": "=B2-B3"},
                         {"formula": "=C2-C3"}],
                    ],
                    "number_formats": {"2": "money", "3": "money"},
                },
                {
                    "name": "Assumptions",
                    "headers": ["Key", "Value"],
                    "rows": [["Growth", 0.30], ["Churn", 0.05]],
                },
            ],
        })

    wr = asyncio.run(write_wb())
    check("write succeeded", "error" not in wr,
          detail=str(wr)[:120] if wr.get("error") else "")

    async def read_wb(**kw):
        from sunnyware.tools.excel_read import ExcelReadTool
        return await ExcelReadTool().run(kw)

    # Read all sheets
    r = asyncio.run(read_wb(file="smoke_p62.xlsx"))
    check("read succeeds", "error" not in r,
          detail=str(r)[:200] if r.get("error") else "")
    if "error" not in r:
        check("2 sheets listed", r.get("sheet_count") == 2)
        check("sheet names correct",
              r.get("sheet_names") == ["P&L", "Assumptions"],
              detail=str(r.get("sheet_names")))
        check("sheets array has 2 entries", len(r.get("sheets", [])) == 2)
        pl = r["sheets"][0]
        check("P&L headers correct",
              pl.get("headers") == ["Line", "FY24", "FY25E"],
              detail=str(pl.get("headers")))
        check("P&L has 3 rows", len(pl.get("rows", [])) == 3)
        # Row 1: Revenue
        row1 = pl["rows"][0]
        check("row 1 is Revenue", row1.get("Line") == "Revenue")
        check("Revenue FY24 = 12000000", row1.get("FY24") == 12000000)
        # Row 3: formula preserved
        row3 = pl["rows"][2]
        gp = row3.get("Gross Profit")
        check("formula preserved as dict", isinstance(gp, dict) and
              gp.get("formula") == "=B2-B3", detail=str(gp))

    # list_only mode
    r2 = asyncio.run(read_wb(file="smoke_p62.xlsx", list_only=True))
    check("list_only succeeds", "error" not in r2)
    if "error" not in r2:
        check("list_only has no rows",
              all("rows" not in s for s in r2["sheets"]))
        check("list_only keeps max_row",
              all("max_row" in s for s in r2["sheets"]))

    # Specific sheet
    r3 = asyncio.run(read_wb(file="smoke_p62.xlsx", sheet="Assumptions"))
    check("single sheet succeeds", "error" not in r3)
    if "error" not in r3:
        check("only 1 sheet returned", len(r3["sheets"]) == 1)
        check("correct sheet name", r3["sheets"][0]["name"] == "Assumptions")

    # include_formulas=True should keep raw '=...' string
    r4 = asyncio.run(read_wb(file="smoke_p62.xlsx",
                             sheet="P&L", include_formulas=True))
    check("include_formulas mode succeeds", "error" not in r4)
    if "error" not in r4:
        row3 = r4["sheets"][0]["rows"][2]
        gp = row3.get("Gross Profit")
        check("formula kept as string with include_formulas=True",
              gp == "=B2-B3", detail=repr(gp))

    # Rejections
    r5 = asyncio.run(read_wb(file="nonexistent.xlsx"))
    check("missing file rejected", "error" in r5)

    r6 = asyncio.run(read_wb(file="../../etc/passwd"))
    check("workspace escape rejected", "error" in r6)

    r7 = asyncio.run(read_wb(file="smoke_p62.xlsx", sheet="NopeSheet"))
    check("bad sheet name rejected", "error" in r7)

    r8 = asyncio.run(read_wb(file="notexcel.txt"))
    check("non-xlsx rejected", "error" in r8)

    # Cleanup
    ws = Path(os.getenv("SUNNYWARE_WORKSPACE") or "/data/workspace").resolve()
    try: (ws / "smoke_p62.xlsx").unlink()
    except Exception: pass

    print()
    print("=" * 62)
    print(f" RESULT: {PASS} passed, {FAIL} failed")
    print("=" * 62)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
