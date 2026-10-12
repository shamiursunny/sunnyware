#!/usr/bin/env python3
"""Part 49 smoke test — recall_history tool."""
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
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label}" + (f" — {detail}" if detail else ""))


def main():
    print("=" * 62)
    print(" Part 49 — recall_history tool")
    print("=" * 62)

    tool_file = ROOT / "src/sunnyware/tools/recall_history.py"
    init_file = ROOT / "src/sunnyware/tools/__init__.py"

    check("recall_history.py exists", tool_file.exists())
    check("tools/__init__.py exists", init_file.exists())
    if not (tool_file.exists() and init_file.exists()):
        return 1

    src = tool_file.read_text(encoding="utf-8")
    init_src = init_file.read_text(encoding="utf-8")

    check("class defined", "class RecallHistoryTool" in src)
    check("name = recall_history", 'name = "recall_history"' in src)
    check("has query parameter", '"query"' in src)
    check("has days parameter", '"days"' in src)
    check("has limit parameter", '"limit"' in src)
    check("uses app_state.get_pool", "app_state.get_pool()" in src)
    check("joins events + sessions", "JOIN sessions" in src)
    check("ILIKE search", "ILIKE" in src)

    check("registered in __init__ import",
          "from .recall_history import RecallHistoryTool" in init_src)
    check("registered in _TOOLS dict",
          "RecallHistoryTool.name: RecallHistoryTool()" in init_src)

    try:
        ast.parse(src)
        check("recall_history.py parses", True)
    except SyntaxError as e:
        check("recall_history.py parses", False, detail=str(e))

    # count events
    try:
        import asyncpg
        url = [l.split("=",1)[1].strip().strip('"').strip("'")
               for l in (ROOT / ".env").read_text().splitlines()
               if l.startswith("NEON_DATABASE_URL")][0]
        async def q():
            c = await asyncpg.connect(url)
            n = await c.fetchval("SELECT count(*) FROM events")
            await c.close()
            return n
        n = asyncio.run(q())
        check(f"events table has data (rows={n})", n > 0)
    except Exception as e:
        check("events table queryable", False, detail=str(e))

    # direct tool invocation
    try:
        from sunnyware import state as app_state
        async def run_tool():
            await app_state.init_pool()
            from sunnyware.tools.recall_history import RecallHistoryTool
            t = RecallHistoryTool()
            r = await t.run({"query": "the", "days": 30, "limit": 3})
            return r
        r = asyncio.run(run_tool())
        check("tool runs without error", "error" not in r or not r.get("error"),
              detail=str(r)[:200] if r.get("error") else "")
        check(f"tool returns count field (got {r.get('count')})",
              "count" in r)
    except Exception as e:
        check("tool invocation", False, detail=f"{type(e).__name__}: {e}")

    print()
    print("=" * 62)
    print(f" RESULT: {PASS} passed, {FAIL} failed")
    print("=" * 62)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
