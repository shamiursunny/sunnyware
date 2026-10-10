#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Smoke test for the python_eval data workbench (Part 31D)."""

import asyncio
import os
import sys
from pathlib import Path

os.environ.setdefault("SUNNYWARE_CPU_THREADS", "2")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sunnyware.tools.python_eval import PythonEvalTool


tool = PythonEvalTool()
PASS, FAIL = 0, 0


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print("  [PASS]", name)
    else:
        FAIL += 1
        print("  [FAIL]", name, "->", detail)


async def run(code):
    return await tool.run({"code": code})


async def main():
    global PASS, FAIL
    print("=== python_eval workbench smoke test ===")
    print()

    # 1. numpy preloaded
    print("[1] numpy preloaded")
    r = await run("result = float(np.mean([1, 2, 3, 4]))")
    check("np.mean == 2.5", r.get("ok") and "2.5" in (r.get("result") or ""), r)

    # 2. pandas preloaded
    print("[2] pandas preloaded")
    r = await run(
        "df = pd.DataFrame({'a': [1,2,3], 'b': [4,5,6]})\n"
        "result = int((df['a'] * df['b']).sum())"
    )
    check("pandas series math == 32", r.get("ok") and "32" in (r.get("result") or ""), r)

    # 3. sqlite3 in-memory
    print("[3] sqlite3 in-memory")
    r = await run(
        "conn = sqlite3.connect(':memory:')\n"
        "conn.execute('CREATE TABLE t (x INT, y TEXT)')\n"
        "conn.executemany('INSERT INTO t VALUES (?,?)', [(1,'a'),(2,'b')])\n"
        "rows = list(conn.execute('SELECT SUM(x) FROM t'))\n"
        "result = rows[0][0]"
    )
    check("SQL SUM == 3", r.get("ok") and "3" in (r.get("result") or ""), r)

    # 4. duckdb via sql_on() helper (high-level convenience)
    print("[4] duckdb SQL over pandas (via sql_on)")
    r = await run(
        "df = pd.DataFrame({'dept': ['A','A','B'], 'amt': [10,20,30]})\n"
        "out = sql_on(df, 'SELECT dept, SUM(amt) AS s FROM df GROUP BY dept ORDER BY dept')\n"
        "result = out.to_dict('records')"
    )
    check(
        "sql_on groupby result",
        r.get("ok") and "dept" in (r.get("result") or ""),
        r,
    )

    # 4b. duckdb low-level connect() + register()
    print("[4b] duckdb low-level connect + register")
    r = await run(
        "df = pd.DataFrame({'x': [1,2,3]})\n"
        "conn = duckdb.connect()\n"
        "conn.register('df', df)\n"
        "out = conn.execute('SELECT SUM(x) AS s FROM df').fetchdf()\n"
        "conn.close()\n"
        "result = int(out['s'].iloc[0])"
    )
    check(
        "duckdb low-level SUM == 6",
        r.get("ok") and "6" in (r.get("result") or ""),
        r,
    )

    # 5. matplotlib chart capture
    print("[5] matplotlib chart -> base64 PNG")
    r = await run(
        "fig, ax = plt.subplots()\n"
        "ax.plot([1,2,3], [4,5,6])\n"
        "ax.set_title('test')\n"
        "result = 'chart_ok'"
    )
    check(
        "figure captured as base64",
        r.get("ok") and r.get("image_base64") and len(r["image_base64"]) > 100,
        str(r)[:200],
    )

    # 6. Jail: block 'import os'
    print("[6] reject 'import os'")
    r = await run("import os\nresult = 1")
    check(
        "import os rejected",
        (not r.get("ok")) and "rejected" in str(r.get("error", "")).lower(),
        r,
    )

    # 7. Jail: block open()
    print("[7] reject builtin open()")
    r = await run("f = open('/etc/passwd', 'r')\nresult = f.read()")
    check(
        "open() rejected",
        (not r.get("ok")) and "rejected" in str(r.get("error", "")).lower(),
        r,
    )

    # 8. Jail: block dunder access
    print("[8] reject dunder attribute")
    r = await run("result = (1).__class__")
    check(
        "dunder rejected",
        (not r.get("ok")) and "rejected" in str(r.get("error", "")).lower(),
        r,
    )

    # 9. Whitelisted import works
    print("[9] allow 'import scipy'")
    r = await run("import scipy\nresult = scipy.__name__")
    check(
        "scipy import OK",
        r.get("ok") and "scipy" in (r.get("result") or ""),
        r,
    )

    # 10. Blocked import
    print("[10] reject 'import subprocess'")
    r = await run("import subprocess\nresult = 1")
    check(
        "subprocess rejected",
        (not r.get("ok")) and "rejected" in str(r.get("error", "")).lower(),
        r,
    )

    # 11. ws_path jail helper
    print("[11] ws_path blocks traversal")
    r = await run(
        "try:\n"
        "    p = ws_path('../../etc/passwd')\n"
        "    result = 'ESCAPED:' + str(p)\n"
        "except PermissionError as e:\n"
        "    result = 'blocked'"
    )
    check(
        "ws_path traversal blocked",
        r.get("ok") and r.get("result") == "'blocked'",
        r,
    )

    # 12. ws_path works for safe path
    print("[12] ws_path writes+reads a file")
    r = await run(
        "p = ws_path('_smoke_test.txt')\n"
        "p.write_text('hello')\n"
        "result = p.read_text()\n"
        "p.unlink()"
    )
    check(
        "ws_path roundtrip",
        r.get("ok") and r.get("result") == "'hello'",
        r,
    )

    print()
    print("=== Results:", PASS, "passed,", FAIL, "failed ===")
    if FAIL > 0:
        sys.exit(1)
    print("ALL SANDBOX SMOKE TESTS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
