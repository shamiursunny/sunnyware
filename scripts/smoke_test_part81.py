#!/usr/bin/env python3
"""Part 81 smoke test - dynamic schedules."""
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
    print(" Part 81 - dynamic schedules")
    print("=" * 62)

    core = ROOT / "src/sunnyware/dynamic_schedule.py"
    check("dynamic_schedule.py exists", core.exists())
    check("migration 007 exists",
          (ROOT / "migrations/007_dynamic_schedules.sql").exists())
    if not core.exists(): return 1

    src = core.read_text(encoding="utf-8")
    check("add() defined", "async def add(" in src)
    check("list_all() defined", "async def list_all(" in src)
    check("delete() defined", "async def delete(" in src)
    check("run_now() defined", "async def run_now(" in src)
    check("bootstrap() defined", "async def bootstrap(" in src)
    check("uses scheduler.register_job", "register_job" in src)

    try:
        ast.parse(src); check("dynamic_schedule parses", True)
    except SyntaxError as e:
        check("dynamic_schedule parses", False, detail=str(e))

    init_src = (ROOT / "src/sunnyware/tools/__init__.py").read_text(encoding="utf-8")
    for mod, cls in [
        ("schedule_add", "ScheduleAddTool"),
        ("schedule_list", "ScheduleListTool"),
        ("schedule_delete", "ScheduleDeleteTool"),
        ("schedule_run_now", "ScheduleRunNowTool"),
    ]:
        f = ROOT / "src" / "sunnyware" / "tools" / (mod + ".py")
        check(mod + ".py exists", f.exists())
        if f.exists():
            s = f.read_text(encoding="utf-8")
            check(mod + " class", "class " + cls in s)
        check(cls + " registered", cls + ".name: " + cls + "()" in init_src)

    main_src = (ROOT / "src/sunnyware/main.py").read_text(encoding="utf-8")
    check("lifespan hooks bootstrap", "dynamic_schedule" in main_src)

    # Integration (needs DB pool)
    async def run_db():
        from sunnyware import state as _st
        from sunnyware.runtime import init_state
        init_state()
        await _st.init_pool()

        from sunnyware.dynamic_schedule import (
            add, list_all, delete, run_now,
        )

        r = await add(
            name="smoke_p81",
            prompt="Reply with the single word OK",
            interval_seconds=3600,
        )
        check("add succeeds", "error" not in r and r.get("ok") is True,
              detail=str(r)[:200] if r.get("error") else "")
        check("registered as scheduler job",
              "dyn:smoke_p81" in __import__("sunnyware.scheduler", fromlist=["_jobs"])._jobs)

        r2 = await list_all()
        check("list succeeds", "error" not in r2)
        if "error" not in r2:
            names = [s["name"] for s in r2.get("schedules", [])]
            check("smoke_p81 in list", "smoke_p81" in names)

        r3 = await delete("smoke_p81")
        check("delete succeeds", "error" not in r3 and r3.get("ok") is True)

        r4 = await list_all()
        if "error" not in r4:
            names = [s["name"] for s in r4.get("schedules", [])]
            check("smoke_p81 gone from list", "smoke_p81" not in names)

        r5 = await add("bad", "x", 5)
        check("bad interval rejected", "error" in r5)

        r6 = await add("", "x", 3600)
        check("empty name rejected", "error" in r6)

        r7 = await run_now("does-not-exist-xyz")
        check("missing schedule rejected", "error" in r7)

    try:
        asyncio.run(run_db())
    except Exception as e:
        check("DB integration", False, detail=type(e).__name__ + ": " + str(e)[:120])

    print()
    print("=" * 62)
    print(" RESULT: " + str(PASS) + " passed, " + str(FAIL) + " failed")
    print("=" * 62)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
