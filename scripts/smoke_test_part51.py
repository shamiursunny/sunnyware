#!/usr/bin/env python3
"""Part 51 smoke test — chart_from_data tool."""
import ast, sys, asyncio, base64
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
    print(" Part 51 — chart_from_data tool")
    print("=" * 62)

    tool_file = ROOT / "src/sunnyware/tools/chart_from_data.py"
    init_file = ROOT / "src/sunnyware/tools/__init__.py"

    check("chart_from_data.py exists", tool_file.exists())
    check("tools/__init__.py exists", init_file.exists())
    if not (tool_file.exists() and init_file.exists()):
        return 1

    src = tool_file.read_text(encoding="utf-8")
    init_src = init_file.read_text(encoding="utf-8")

    check("class defined", "class ChartFromDataTool" in src)
    check("name = chart_from_data", 'name = "chart_from_data"' in src)
    check("supports inline data", '"data"' in src)
    check("supports file input", '"file"' in src)
    check("supported chart types",
          all(t in src for t in ('"bar"', '"line"', '"scatter"', '"pie"', '"hist"', '"box"')) or
          all(t in src for t in ("bar", "line", "scatter", "pie", "hist", "box")))
    check("matplotlib Agg backend", 'matplotlib.use("Agg"' in src)
    check("workspace jail", "_workspace_root" in src)
    check("returns image_base64", '"image_base64"' in src)
    check("registered in __init__",
          "ChartFromDataTool.name: ChartFromDataTool()" in init_src)

    try:
        ast.parse(src)
        check("chart_from_data.py parses", True)
    except SyntaxError as e:
        check("chart_from_data.py parses", False, detail=str(e))

    try:
        import matplotlib  # noqa
        check("matplotlib importable", True)
    except Exception as e:
        check("matplotlib importable", False, detail=str(e))
        return 1 if FAIL else 0

    # Integration tests
    from sunnyware.tools.chart_from_data import ChartFromDataTool
    t = ChartFromDataTool()

    sample = [
        {"region": "APAC", "amount": 100},
        {"region": "EMEA", "amount": 150},
        {"region": "AMER", "amount": 200},
    ]

    async def run(**kw):
        return await t.run(kw)

    r1 = asyncio.run(run(data=sample, chart_type="bar", x="region", y="amount",
                          title="Revenue by Region"))
    check("bar chart succeeds", "error" not in r1, detail=str(r1)[:200])
    if r1.get("image_base64"):
        try:
            raw = base64.b64decode(r1["image_base64"])
            check(f"bar decoded PNG ({len(raw)} bytes)",
                  raw[:8] == b"\x89PNG\r\n\x1a\n")
        except Exception as e:
            check("bar decoded PNG", False, detail=str(e))

    r2 = asyncio.run(run(data=sample, chart_type="line", x="region", y="amount"))
    check("line chart succeeds", "error" not in r2, detail=str(r2)[:200])

    r3 = asyncio.run(run(data=sample, chart_type="pie", x="region", y="amount"))
    check("pie chart succeeds", "error" not in r3, detail=str(r3)[:200])

    r4 = asyncio.run(run(data=sample, chart_type="hist", y="amount"))
    check("hist chart succeeds", "error" not in r4, detail=str(r4)[:200])

    r5 = asyncio.run(run(data=sample, chart_type="bar"))
    check("bar without x rejected", "error" in r5,
          detail=str(r5)[:120] if "error" not in r5 else "ok")

    r6 = asyncio.run(run(data=sample, chart_type="unknown", x="region", y="amount"))
    check("invalid chart_type rejected", "error" in r6)

    r7 = asyncio.run(run(file="../../etc/passwd", chart_type="bar", x="a", y="b"))
    check("workspace escape rejected", "error" in r7)

    r8 = asyncio.run(run(file="nonexistent.csv", chart_type="bar", x="a", y="b"))
    check("missing file rejected", "error" in r8)

    print()
    print("=" * 62)
    print(f" RESULT: {PASS} passed, {FAIL} failed")
    print("=" * 62)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
