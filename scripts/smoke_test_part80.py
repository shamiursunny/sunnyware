#!/usr/bin/env python3
"""Part 80 smoke test - data_quality_report."""
import ast, csv, os, sys, asyncio
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
        PASS += 1; print("  [PASS] " + label)
    else:
        FAIL += 1; print("  [FAIL] " + label + (" - " + detail if detail else ""))


def main():
    print("=" * 62)
    print(" Part 80 - data_quality_report")
    print("=" * 62)

    f = ROOT / "src/sunnyware/tools/data_quality_report.py"
    check("data_quality_report.py exists", f.exists())
    if not f.exists():
        return 1

    src = f.read_text(encoding="utf-8")
    init_src = (ROOT / "src/sunnyware/tools/__init__.py").read_text(encoding="utf-8")

    check("class defined", "class DataQualityReportTool" in src)
    check("name = data_quality_report", 'name = "data_quality_report"' in src)
    check("uses pandas", "import pandas as pd" in src)
    check("per-column report", "_col_report" in src)
    check("IQR outliers", "outliers_iqr" in src)
    check("duplicate hints", "duplicate_key_hints" in src)
    check("workspace jail", "_workspace_root" in src)
    check("registered", "DataQualityReportTool.name: DataQualityReportTool()" in init_src)

    try:
        ast.parse(src); check("parses", True)
    except SyntaxError as e:
        check("parses", False, detail=str(e))

    # Integration - write a small CSV with known issues
    ws = Path(os.getenv("SUNNYWARE_WORKSPACE") or "/data/workspace").resolve()
    ws.mkdir(parents=True, exist_ok=True)
    csv_path = ws / "smoke_p80.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "name", "amount", "score"])
        w.writerow(["A1", "Alice", 100, 8.5])
        w.writerow(["A2", "Bob", 200, 9.1])
        w.writerow(["A3", "", 150, None])          # missing
        w.writerow(["A4", "  Dan  ", 300, 7.2])    # whitespace
        w.writerow(["A1", "Eve", 100, 6.5])        # dup id
        w.writerow(["A5", "Frank", 999999, 5.0])   # outlier

    async def run(**kw):
        from sunnyware.tools.data_quality_report import DataQualityReportTool
        return await DataQualityReportTool().run(kw)

    r = asyncio.run(run(file="smoke_p80.csv"))
    check("read succeeds", "error" not in r,
          detail=str(r)[:200] if r.get("error") else "")

    if "error" not in r:
        check("rows_analyzed == 6", r.get("rows_analyzed") == 6,
              detail=str(r.get("rows_analyzed")))
        check("columns == 4", r.get("columns") == 4)
        check("duplicate_rows == 0 (all rows differ)", r.get("duplicate_rows") == 0)
        cr = r.get("column_reports", {})

        check("id column has dup hint",
              any(h["column"] == "id" for h in r.get("duplicate_key_hints", [])))
        check("name column has null detected",
              cr.get("name", {}).get("nulls") == 1)
        check("name col has whitespace flag",
              cr.get("name", {}).get("has_whitespace") is True)
        check("score col has null detected",
              cr.get("score", {}).get("nulls") == 1)
        check("amount col has min/max",
              "min" in cr.get("amount", {}) and "max" in cr.get("amount", {}))
        check("amount col outlier detected",
              cr.get("amount", {}).get("outliers_iqr", 0) >= 1)
        check("amount mean present",
              "mean" in cr.get("amount", {}))

    # Rejections
    check("missing file rejected",
          "error" in asyncio.run(run(file="nope.csv")))
    check("escape rejected",
          "error" in asyncio.run(run(file="../../etc/passwd")))
    check("no args rejected", "error" in asyncio.run(run()))

    try: csv_path.unlink()
    except Exception: pass

    print()
    print("=" * 62)
    print(" RESULT: " + str(PASS) + " passed, " + str(FAIL) + " failed")
    print("=" * 62)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
