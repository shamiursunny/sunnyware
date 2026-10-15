# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 137 smoke test - continuous evals framework."""
from pathlib import Path
import ast, asyncio, json, os, sys, tempfile

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 137: continuous evals framework ===")

ep = SRC / "evals.py"
check("evals.py exists", ep.exists())
et = ep.read_text(encoding="utf-8") if ep.exists() else ""
check("has load_cases", "def load_cases" in et)
check("has run_case", "async def run_case" in et)
check("has run_suite", "async def run_suite" in et)
check("has status", "def status()" in et)
check("has trends", "def trends" in et)
check("has prune_history", "def prune_history" in et)
check("has default_call_fn", "async def default_call_fn" in et)
check("has dry_run_call_fn", "async def dry_run_call_fn" in et)

tmpdir = tempfile.mkdtemp()
os.environ["SUNNYWARE_EVAL_STORAGE"] = os.path.join(tmpdir, "evals_test.json")
os.environ["SUNNYWARE_EVAL_KEEP_RUNS"] = "5"

sys.path.insert(0, str(SRC.parent))
from sunnyware import evals as E

cases = E.load_cases()
check("default cases present", len(cases) >= 5, f"n={len(cases)}")
check("has safety case", any("safety" in (c.get("tags") or []) for c in cases))
check("has plumbing case", any("plumbing" in (c.get("tags") or []) for c in cases))
check("all cases have id+input",
      all(c.get("id") and c.get("input") for c in cases))

asserts = [
    {"kind": "contains", "value": "pong"},
    {"kind": "not_contains", "value": "ERROR"},
    {"kind": "min_length", "value": 3},
]
ok, res = E._check_all("pong", asserts)
check("contains pass", res[0]["ok"] is True)
check("not_contains pass", res[1]["ok"] is True)
check("min_length pass", res[2]["ok"] is True)
check("all-pass -> ok=True", ok is True)

ok2, res2 = E._check_all("nope", asserts)
check("contains fail -> ok=False", ok2 is False)
check("contains fail detail", res2[0]["ok"] is False)

r = E._check_one("hello", {"kind": "regex", "pattern": "^h"})
check("regex pass", r["ok"] is True)
r = E._check_one("hello", {"kind": "equals", "value": "hello"})
check("equals pass", r["ok"] is True)
r = E._check_one("hello", {"kind": "unknown_xyz"})
check("unknown kind -> fail-safe", r["ok"] is False)

async def fake_ok(text): return "pong"
async def fake_timeout(text):
    await asyncio.sleep(10)
    return "x"

async def run_tests():
    r = await E.run_case(
        {"id": "t1", "input": "x",
         "assertions": [{"kind": "contains", "value": "pong"}]},
        fake_ok,
    )
    check("run_case pass", r["status"] == "pass")
    check("run_case duration_ms", isinstance(r["duration_ms"], int))
    check("run_case excerpt", r["response_excerpt"] == "pong")

    r2 = await E.run_case(
        {"id": "t2", "input": "x",
         "assertions": [{"kind": "contains", "value": "missing"}]},
        fake_ok,
    )
    check("run_case fail", r2["status"] == "fail")
    check("run_case fail lists assertion",
          len(r2["assertions"]) == 1 and r2["assertions"][0]["ok"] is False)

    async def raise_err(text):
        raise RuntimeError("boom")
    r3 = await E.run_case(
        {"id": "t3", "input": "x", "assertions": []},
        raise_err,
    )
    check("run_case error captured", r3["status"] == "error")
    check("run_case error contains msg", "boom" in (r3.get("error") or ""))

    r4 = await E.run_case(
        {"id": "t4", "input": "x", "assertions": [],
         "timeout_sec": 0.2},
        fake_timeout,
    )
    check("run_case timeout -> error", r4["status"] == "error")
    check("timeout mentions timeout", "timeout" in (r4.get("error") or "").lower())

asyncio.run(run_tests())

async def run_suites():
    run = await E.run_suite(E.dry_run_call_fn, triggered_by="smoke")
    check("run_suite returned run_id", bool(run.get("run_id")))
    check("run_suite has cases", len(run.get("cases") or []) >= 5)
    s = run["summary"]
    check("summary total matches cases",
          s["total"] == len(run["cases"]))
    check("summary has score", 0.0 <= s["score"] <= 1.0)
    check("dry_run flagged", run.get("dry_run") is False)

    run2 = await E.run_suite(E.dry_run_call_fn, tags=["plumbing"],
                             triggered_by="smoke", dry_run=True)
    check("tag filter works", len(run2["cases"]) >= 1)
    check("tag filter smaller", len(run2["cases"]) < len(run["cases"]))
    check("dry_run flagged true", run2.get("dry_run") is True)

    h = E.load_history()
    check("history has runs", len(h.get("runs") or []) >= 2)
    check("history version", h.get("version") == E.VERSION)

    latest = E.latest_run()
    check("latest_run returns dict", isinstance(latest, dict))
    check("latest run is the most recent",
          latest.get("run_id") == run2.get("run_id"))

asyncio.run(run_suites())

tr = E.trends(n=10)
check("trends returns list", isinstance(tr, list))
check("trends has entries", len(tr) >= 2)
check("trend entry has summary", "summary" in tr[0])

async def many_runs():
    for i in range(8):
        await E.run_suite(E.dry_run_call_fn, triggered_by="prune",
                          dry_run=True)
asyncio.run(many_runs())
h = E.load_history()
check("prune keeps <= KEEP_RUNS (5)",
      len(h["runs"]) <= 5, f"n={len(h['runs'])}")

st = E.status()
check("status has case_count", st.get("case_count", 0) >= 5)
check("status has stored_runs", "stored_runs" in st)
check("status has storage_path", "storage_path" in st)
check("status last_run populated", isinstance(st.get("last_run"), dict))
check("status last_run summary",
      isinstance(st["last_run"].get("summary"), dict))

bad_file = os.path.join(tmpdir, "bad_cases.json")
with open(bad_file, "w", encoding="utf-8") as f:
    f.write("not json {{{")
os.environ["SUNNYWARE_EVAL_CASES_FILE"] = bad_file
check("malformed cases file -> defaults", len(E.load_cases()) >= 5)

good_file = os.path.join(tmpdir, "good_cases.json")
with open(good_file, "w", encoding="utf-8") as f:
    json.dump({"cases": [
        {"id": "custom1", "input": "hello"},
    ]}, f)
os.environ["SUNNYWARE_EVAL_CASES_FILE"] = good_file
custom = E.load_cases()
check("custom cases file loaded", len(custom) == 1)
check("custom case id preserved", custom[0]["id"] == "custom1")
check("custom case defaults filled", custom[0]["weight"] == 1.0)

del os.environ["SUNNYWARE_EVAL_CASES_FILE"]
del os.environ["SUNNYWARE_EVAL_STORAGE"]
del os.environ["SUNNYWARE_EVAL_KEEP_RUNS"]

try:
    ast.parse(ep.read_text(encoding="utf-8"))
    check("evals.py parses", True)
except SyntaxError as e:
    check("evals.py parses", False, str(e))

passed = sum(1 for _, ok, _ in checks if ok)
total = len(checks)
print(f"\n{passed}/{total} checks passed")
if passed < total:
    print("\nFAILED CHECKS:")
    for name, ok, detail in checks:
        if not ok:
            print(f"  - {name} {detail}")
    sys.exit(1)
print("ALL PASS")
