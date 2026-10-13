#!/usr/bin/env python3
"""Part 74 smoke test - report_batch tool."""
import ast, sys, asyncio
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
    print(" Part 74 - report_batch tool")
    print("=" * 62)

    f = ROOT / "src/sunnyware/tools/report_batch.py"
    check("report_batch.py exists", f.exists())
    if not f.exists():
        return 1

    src = f.read_text(encoding="utf-8")
    init_src = (ROOT / "src/sunnyware/tools/__init__.py").read_text(encoding="utf-8")

    check("class defined", "class ReportBatchTool" in src)
    check("name = report_batch", 'name = "report_batch"' in src)
    check("asyncio.gather used", "asyncio.gather" in src)
    check("timeout guard", "asyncio.wait_for" in src)
    check("prompt cap", "_MAX_PROMPTS" in src)
    check("registered", "ReportBatchTool.name: ReportBatchTool()" in init_src)

    try:
        ast.parse(src); check("report_batch.py parses", True)
    except SyntaxError as e:
        check("report_batch.py parses", False, detail=str(e))

    # Rejections (no LLM call needed)
    async def run(**kw):
        from sunnyware.tools.report_batch import ReportBatchTool
        return await ReportBatchTool().run(kw)

    r1 = asyncio.run(run(prompts=[]))
    check("empty prompts rejected", "error" in r1)

    r2 = asyncio.run(run(prompts=["ok", 123]))
    check("non-string prompt rejected", "error" in r2)

    r3 = asyncio.run(run(prompts=["x" * 5000]))
    check("oversized prompt rejected", "error" in r3)

    r4 = asyncio.run(run(prompts=["a"] * 11))
    check("too many prompts rejected", "error" in r4)

    r5 = asyncio.run(run())
    check("no args rejected", "error" in r5)

    print()
    print("=" * 62)
    print(" RESULT: " + str(PASS) + " passed, " + str(FAIL) + " failed")
    print("=" * 62)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
