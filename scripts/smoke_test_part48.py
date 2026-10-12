#!/usr/bin/env python3
"""Part 48 smoke test — tool audit trail."""
import ast, sys, asyncio
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

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
    print(" Part 48 — tool audit trail")
    print("=" * 62)

    # Files
    check("migrations/003_tool_invocations.sql exists",
          (ROOT / "migrations/003_tool_invocations.sql").exists())
    check("src/sunnyware/audit.py exists",
          (ROOT / "src/sunnyware/audit.py").exists())

    # audit.py contents
    audit_src = (ROOT / "src/sunnyware/audit.py").read_text(encoding="utf-8")
    check("audit.py has log_tool_call", "def log_tool_call" in audit_src)
    check("audit.py has _write", "async def _write" in audit_src)
    check("audit.py uses app_state.get_pool",
          "app_state.get_pool()" in audit_src)
    try:
        ast.parse(audit_src)
        check("audit.py parses", True)
    except SyntaxError as e:
        check("audit.py parses", False, detail=str(e))

    # orchestrator hook
    orch = (ROOT / "src/sunnyware/orchestrator.py").read_text(encoding="utf-8")
    check("orchestrator imports audit",
          "from . import audit as _audit" in orch)
    check("orchestrator calls log_tool_call",
          "_audit.log_tool_call" in orch)

    # Neon table
    try:
        import asyncpg
        url = [l.split("=",1)[1].strip().strip('"').strip("'")
               for l in (ROOT / ".env").read_text().splitlines()
               if l.startswith("NEON_DATABASE_URL")][0]
        async def check_table():
            c = await asyncpg.connect(url)
            try:
                n = await c.fetchval("SELECT count(*) FROM tool_invocations")
                return n
            finally:
                await c.close()
        n = asyncio.run(check_table())
        check(f"tool_invocations table queryable (rows={n})", True)
    except Exception as e:
        check("tool_invocations table queryable", False, detail=str(e))

    print()
    print("=" * 62)
    print(f" RESULT: {PASS} passed, {FAIL} failed")
    print("=" * 62)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
