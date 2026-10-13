#!/usr/bin/env python3
"""Part 75 smoke test - kpi_watch (log-only)."""
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
    print(" Part 75 - kpi_watch (log-only)")
    print("=" * 62)


    core = ROOT / "src/sunnyware/kpi_watch.py"
    check("kpi_watch.py exists", core.exists())
    check("migration 004 exists",
          (ROOT / "migrations/004_kpi_watches.sql").exists())

    if not core.exists():
        return 1

    src = core.read_text(encoding="utf-8")
    init_src = (ROOT / "src/sunnyware/tools/__init__.py").read_text(encoding="utf-8")

    check("add_watch defined", "async def add_watch" in src)
    check("list_watches defined", "async def list_watches" in src)
    check("run_watch defined", "async def run_watch" in src)
    check("run_all defined", "async def run_all" in src)
    check("parse number helper", "_parse_number" in src)
    check("compare helper", "_compare" in src)

    try:
        ast.parse(src); check("kpi_watch.py parses", True)
    except SyntaxError as e:
        check("kpi_watch.py parses", False, detail=str(e))

    for mod, cls in [
        ("kpi_watch_add", "KpiWatchAddTool"),
        ("kpi_watch_list", "KpiWatchListTool"),
        ("kpi_watch_run", "KpiWatchRunTool"),
    ]:
        f = ROOT / "src" / "sunnyware" / "tools" / (mod + ".py")
        check(mod + ".py exists", f.exists())
        if f.exists():
            s = f.read_text(encoding="utf-8")
            check(mod + " class", "class " + cls in s)
            try:
                ast.parse(s); check(mod + ".py parses", True)
            except SyntaxError as e:
                check(mod + ".py parses", False, detail=str(e))
        check(cls + " registered", cls + ".name: " + cls + "()" in init_src)

    # Unit: _parse_number
    from sunnyware.kpi_watch import _parse_number, _compare
    check("parse int", _parse_number("value is 42") == 42.0)
    check("parse negative", _parse_number("value -3.5") == -3.5)
    check("parse comma", _parse_number("burn is 12,500 per day") == 12500.0)
    check("parse missing -> None", _parse_number("no number here") is None)
    check("parse with pattern",
          _parse_number("KPI: 999 units", r"KPI:\s*(\d+)") == 999.0)

    # Unit: _compare
    check("lt breach", _compare(5, "lt", 10) is True)
    check("lt ok", _compare(15, "lt", 10) is False)
    check("gt breach", _compare(15, "gt", 10) is True)
    check("eq ok", _compare(10, "eq", 10) is True)
    check("ne breach", _compare(10, "ne", 10) is False)

    # Integration: all DB calls in ONE event loop
    async def run_db_checks():
        from sunnyware import state as _st
        from sunnyware.runtime import init_state
        init_state()
        await _st.init_pool()
        print("  [info] DB pool initialized")

        from sunnyware.kpi_watch import add_watch, list_watches

        r = await add_watch("smoke_test_p75", "return 42", "gt", 100,
                            interval_seconds=3600)
        check("add_watch succeeds", "error" not in r and r.get("ok") is True,
              detail=str(r)[:200] if r.get("error") else "")
        wid = r.get("id")

        r2 = await list_watches()
        check("list_watches succeeds", "error" not in r2)
        if "error" not in r2:
            names = [w["kpi_name"] for w in r2.get("watches", [])]
            check("smoke_test_p75 in list", "smoke_test_p75" in names)

        r3 = await add_watch("bad", "x", "INVALID", 0)
        check("bad comparison rejected", "error" in r3)

        r4 = await add_watch("bad2", "x", "gt", 0, interval_seconds=5)
        check("bad interval rejected", "error" in r4)

        # Cleanup
        if wid:
            try:
                import asyncpg
                url = [l.split("=",1)[1].strip().strip(chr(34)).strip(chr(39))
                       for l in (ROOT / ".env").read_text().splitlines()
                       if l.startswith("NEON_DATABASE_URL")][0]
                c = await asyncpg.connect(url)
                await c.execute("DELETE FROM kpi_watches WHERE kpi_name = $1",
                                "smoke_test_p75")
                await c.close()
                print("  [cleanup] removed smoke_test_p75")
            except Exception as e:
                print("  [cleanup warn] " + str(e))

    asyncio.run(run_db_checks())

    print()
    print("=" * 62)
    print(" RESULT: " + str(PASS) + " passed, " + str(FAIL) + " failed")
    print("=" * 62)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
