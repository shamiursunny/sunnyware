#!/usr/bin/env python3
"""Part 50 smoke test — csv_query tool."""
import ast, sys, asyncio, csv, os
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
    print(" Part 50 — csv_query tool")
    print("=" * 62)

    tool_file = ROOT / "src/sunnyware/tools/csv_query.py"
    init_file = ROOT / "src/sunnyware/tools/__init__.py"

    check("csv_query.py exists", tool_file.exists())
    check("tools/__init__.py exists", init_file.exists())
    if not (tool_file.exists() and init_file.exists()):
        return 1

    src = tool_file.read_text(encoding="utf-8")
    init_src = init_file.read_text(encoding="utf-8")

    check("class defined", "class CsvQueryTool" in src)
    check("name = csv_query", 'name = "csv_query"' in src)
    check("has file parameter", '"file"' in src)
    check("has sql parameter", '"sql"' in src)
    check("SELECT-only guard", "_ALLOWED_PREFIX" in src)
    check("workspace jail", "_workspace_root" in src)
    check("duckdb import guarded", "_HAS_DUCK" in src)
    check("registered in __init__",
          "CsvQueryTool.name: CsvQueryTool()" in init_src)

    try:
        ast.parse(src)
        check("csv_query.py parses", True)
    except SyntaxError as e:
        check("csv_query.py parses", False, detail=str(e))

    # duckdb availability
    try:
        import duckdb  # noqa
        check("duckdb importable", True)
    except Exception as e:
        check("duckdb importable", False, detail=str(e))
        return 1 if FAIL else 0

    # Integration test — write a small CSV and query it
    ws = Path(os.getenv("SUNNYWARE_WORKSPACE") or "/data/workspace").resolve()
    ws.mkdir(parents=True, exist_ok=True)
    test_csv = ws / "smoke_p50.csv"
    with test_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["region", "amount"])
        w.writerow(["APAC", 100])
        w.writerow(["APAC", 200])
        w.writerow(["EMEA", 150])
    check("wrote test CSV to workspace", test_csv.exists())

    async def run_tool():
        from sunnyware.tools.csv_query import CsvQueryTool
        t = CsvQueryTool()
        r1 = await t.run({
            "file": "smoke_p50.csv",
            "sql": "SELECT region, SUM(amount) AS total FROM smoke_p50 GROUP BY region ORDER BY total DESC",
        })
        r2 = await t.run({
            "file": "smoke_p50.csv",
            "sql": "DROP TABLE smoke_p50",  # should be rejected
        })
        r3 = await t.run({
            "file": "../etc/passwd",
            "sql": "SELECT 1",
        })  # should be rejected
        return r1, r2, r3

    r1, r2, r3 = asyncio.run(run_tool())

    check("query 1 succeeds", "error" not in r1 or not r1.get("error"),
          detail=str(r1)[:200] if r1.get("error") else "")
    if r1.get("rows"):
        check(f"query returns 2 groups (got {r1.get('row_count')})",
              r1.get("row_count") == 2)
        check("columns are correct",
              r1.get("columns") == ["region", "total"],
              detail=str(r1.get("columns")))
        # APAC = 300, EMEA = 150 (ORDER BY DESC)
        top = r1["rows"][0]
        check("APAC total = 300", top[0] == "APAC" and top[1] == 300,
              detail=str(top))
    else:
        check("query returns rows", False, detail=str(r1)[:200])

    check("non-SELECT rejected",
          "only SELECT" in str(r2.get("error", "")),
          detail=str(r2)[:120])
    check("workspace escape rejected",
          "workspace" in str(r3.get("error", "")).lower(),
          detail=str(r3)[:120])

    # cleanup
    try:
        test_csv.unlink()
    except Exception:
        pass

    print()
    print("=" * 62)
    print(f" RESULT: {PASS} passed, {FAIL} failed")
    print("=" * 62)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
