#!/usr/bin/env python3
"""Part 84 smoke test - SQL sandbox."""
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
    print(" Part 84 - sql_sandbox")
    print("=" * 62)

    core = ROOT / "src/sunnyware/sql_sandbox.py"
    check("sql_sandbox.py exists", core.exists())
    check("migration 009 exists",
          (ROOT / "migrations/009_sql_sandbox.sql").exists())
    if not core.exists(): return 1

    src = core.read_text(encoding="utf-8")
    check("create() defined", "async def create(" in src)
    check("execute() defined", "async def execute(" in src)
    check("list_all() defined", "async def list_all(" in src)
    check("load_csv() defined", "async def load_csv(" in src)
    check("drop() defined", "async def drop(" in src)
    check("blocked keywords list", "_BLOCKED_KEYWORDS" in src)
    check("blocked identifiers list", "_BLOCKED_IDENTS" in src)
    check("search_path set", "search_path" in src)
    check("statement_timeout", "statement_timeout" in src)

    try:
        ast.parse(src); check("parses", True)
    except SyntaxError as e:
        check("parses", False, detail=str(e))

    init_src = (ROOT / "src/sunnyware/tools/__init__.py").read_text(encoding="utf-8")
    for mod, cls in [
        ("sql_sandbox_create", "SqlSandboxCreateTool"),
        ("sql_sandbox_execute", "SqlSandboxExecuteTool"),
        ("sql_sandbox_list", "SqlSandboxListTool"),
        ("sql_sandbox_load_csv", "SqlSandboxLoadCsvTool"),
    ]:
        f = ROOT / "src" / "sunnyware" / "tools" / (mod + ".py")
        check(mod + ".py exists", f.exists())
        if f.exists():
            s = f.read_text(encoding="utf-8")
            check(mod + " class", "class " + cls in s)
        check(cls + " registered", cls + ".name: " + cls + "()" in init_src)

    # Unit tests: _check_sql blockers (no DB needed)
    from sunnyware.sql_sandbox import _check_sql, _validate_name

    check("DROP SCHEMA blocked", _check_sql("DROP SCHEMA sb_x CASCADE") is not None)
    check("DROP DATABASE blocked", _check_sql("DROP DATABASE x") is not None)
    check("pg_read_file blocked", _check_sql("SELECT pg_read_file('/etc/passwd')") is not None)
    check("CREATE EXTENSION blocked", _check_sql("CREATE EXTENSION x") is not None)
    check("public.sessions blocked", _check_sql("SELECT * FROM public.sessions") is not None)
    check("bare sessions blocked", _check_sql("SELECT * FROM sessions") is not None)
    check("events blocked", _check_sql("SELECT * FROM events") is not None)
    check("clean SELECT allowed", _check_sql("SELECT a, b FROM t1 WHERE a > $1") is None)
    check("CREATE TABLE allowed", _check_sql("CREATE TABLE t1 (a TEXT)") is None)
    check("INSERT allowed", _check_sql("INSERT INTO t1 VALUES ($1)") is None)

    check("bad name rejected", _validate_name("BAD-Name")[0] is None)
    check("good name ok", _validate_name("my_sandbox")[0] == "my_sandbox")

    # Integration
    async def run_db():
        from sunnyware import state as _st
        from sunnyware.runtime import init_state
        init_state()
        await _st.init_pool()
        from sunnyware.sql_sandbox import (
            create, execute, list_all, load_csv, drop,
        )

        r = await create("smoke_p84", "test sandbox")
        check("create succeeds", "error" not in r and r.get("ok") is True,
              detail=str(r)[:200] if r.get("error") else "")

        r2 = await execute("smoke_p84", "CREATE TABLE t (a TEXT, b TEXT)")
        check("CREATE TABLE ok", "error" not in r2)

        r3 = await execute("smoke_p84",
                           "INSERT INTO t (a, b) VALUES ($1, $2)",
                           params=["hello", "42"])
        check("INSERT ok", "error" not in r3)

        r4 = await execute("smoke_p84",
                           "SELECT a, b::int AS bnum FROM t WHERE a = $1",
                           params=["hello"])
        check("SELECT ok", "error" not in r4 and r4.get("row_count") == 1,
              detail=str(r4)[:200])
        if "error" not in r4 and r4.get("rows"):
            check("SELECT row correct", r4["rows"][0].get("bnum") == 42)

        # Blocked query
        r5 = await execute("smoke_p84", "SELECT * FROM public.sessions")
        check("cross-schema query blocked", "error" in r5)

        r6 = await execute("smoke_p84", "DROP SCHEMA sb_smoke_p84 CASCADE")
        check("DROP SCHEMA blocked", "error" in r6)

        # CSV load
        ws = Path(os.getenv("SUNNYWARE_WORKSPACE") or "/data/workspace").resolve()
        ws.mkdir(parents=True, exist_ok=True)
        csv_path = ws / "smoke_p84.csv"
        with csv_path.open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["name", "amount"])
            w.writerow(["Alice", "100"])
            w.writerow(["Bob", "200"])
        r7 = await load_csv("smoke_p84", "smoke_p84.csv", "people")
        check("load_csv ok", "error" not in r7 and r7.get("rows_loaded") == 2,
              detail=str(r7)[:200])

        r8 = await execute("smoke_p84",
                           "SELECT count(*) AS n, sum(amount::numeric) AS total FROM people")
        if "error" not in r8 and r8.get("rows"):
            row = r8["rows"][0]
            check("aggregation correct", row.get("n") == 2)

        # list
        r9 = await list_all()
        check("list_all ok", "error" not in r9)
        if "error" not in r9:
            names = [s["name"] for s in r9.get("sandboxes", [])]
            check("smoke_p84 in list", "smoke_p84" in names)

        # Cleanup
        r10 = await drop("smoke_p84")
        check("drop ok", "error" not in r10 and r10.get("ok") is True)

        try: csv_path.unlink()
        except Exception: pass

    try:
        asyncio.run(run_db())
    except Exception as e:
        check("DB integration", False, detail=type(e).__name__ + ": " + str(e)[:150])

    print()
    print("=" * 62)
    print(" RESULT: " + str(PASS) + " passed, " + str(FAIL) + " failed")
    print("=" * 62)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
