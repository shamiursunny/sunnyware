# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 158 smoke - golden dataset regressions."""
from pathlib import Path
import ast, asyncio, os, sys, tempfile

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 158: golden dataset ===")

gp = SRC / "golden.py"
dp = SRC / "static" / "golden_dataset.json"
check("golden.py exists", gp.exists())
check("golden_dataset.json exists", dp.exists())
gt = gp.read_text(encoding="utf-8")
check("has load_cases", "def load_cases" in gt)
check("has run_suite", "async def run_suite" in gt)
check("has promote", "def promote" in gt)
check("has delete_case", "def delete_case" in gt)

mt = (SRC / "routes" / "meta.py").read_text(encoding="utf-8")
check("GET /api/golden/status", '"/api/golden/status"' in mt)
check("GET /api/golden/latest", '"/api/golden/latest"' in mt)
check("GET /api/golden/trends", '"/api/golden/trends"' in mt)
check("POST /api/golden/run", '"/api/golden/run"' in mt)
check("POST /api/golden/promote", '"/api/golden/promote"' in mt)
check("POST /api/golden/delete", '"/api/golden/delete"' in mt)

tmpdir = tempfile.mkdtemp()
os.environ["SUNNYWARE_GOLDEN_STORAGE"] = os.path.join(tmpdir, "g.json")
os.environ["SUNNYWARE_GOLDEN_KEEP_RUNS"] = "5"

sys.path.insert(0, str(SRC.parent))
from sunnyware import golden as G

cases = G.load_cases()
check("5 default cases", len(cases) == 5, f"n={len(cases)}")
ids = [c["id"] for c in cases]
check("has echo_ping", "echo_ping" in ids)
check("has no_prompt_injection", "no_prompt_injection" in ids)

r = G.compare("pong", ["pong"], "contains")
check("contains pass", r["ok"] is True)
r = G.compare("nothing", ["pong"], "contains")
check("contains fail", r["ok"] is False)
r = G.compare("hello there", ["LEAKED"], "not_contains")
check("not_contains pass", r["ok"] is True)
r = G.compare("LEAKED here", ["LEAKED"], "not_contains")
check("not_contains fail", r["ok"] is False)
r = G.compare("hello", "^h", "regex")
check("regex pass", r["ok"] is True)
r = G.compare("hello there", "hello there", "exact")
check("exact pass", r["ok"] is True)
r = G.compare("hello", ["hello"], "bogus")
check("unknown match -> fail", r["ok"] is False)

async def fake_ok(text): return "pong"
r = asyncio.run(G.run_case(
    {"id": "t1", "input": "x", "expected": ["pong"], "match": "contains"},
    fake_ok,
))
check("run_case pass", r["status"] == "pass")
check("run_case has duration_ms", isinstance(r["duration_ms"], int))

async def raise_err(text): raise RuntimeError("boom")
r = asyncio.run(G.run_case(
    {"id": "t2", "input": "x", "expected": [], "match": "contains"},
    raise_err,
))
check("run_case error captured", r["status"] == "error")
check("run_case error contains msg", "boom" in (r.get("match_detail") or ""))

run = asyncio.run(G.run_suite(G.dry_run_call_fn, triggered_by="smoke"))
check("run_suite returned run_id", bool(run.get("run_id")))
check("run_suite has cases", len(run.get("cases") or []) == 5)
check("run_suite summary total", run["summary"]["total"] == 5)

h = G.load_history()
check("history has runs", len(h.get("runs") or []) >= 1)
latest = G.latest_run()
check("latest_run works", isinstance(latest, dict))
check("latest is our run", latest.get("run_id") == run.get("run_id"))

r = G.promote({"id": "custom1", "input": "hi",
               "expected": ["hi"], "match": "contains"})
check("promote created", r.get("ok") and r.get("action") == "created")
check("case count now 6", len(G.load_cases()) == 6)

r = G.promote({"id": "custom1", "input": "hi",
               "expected": ["hi"], "match": "contains"})
check("promote updated", r.get("ok") and r.get("action") == "updated")

r = G.delete_case("custom1")
check("delete ok", r.get("ok") is True)
check("case count back to 5", len(G.load_cases()) == 5)

r = G.delete_case("never-seen")
check("delete missing -> not_found", r.get("ok") is False)

bad = os.path.join(tmpdir, "bad.json")
with open(bad, "w", encoding="utf-8") as f:
    f.write("{{{ not json")
os.environ["SUNNYWARE_GOLDEN_FILE"] = bad
check("malformed dataset -> 0 cases", len(G.load_cases()) == 0)
del os.environ["SUNNYWARE_GOLDEN_FILE"]

del os.environ["SUNNYWARE_GOLDEN_STORAGE"]
del os.environ["SUNNYWARE_GOLDEN_KEEP_RUNS"]

for fp in [gp, SRC / "routes" / "meta.py"]:
    try:
        ast.parse(fp.read_text(encoding="utf-8"))
        check(f"{fp.name} parses", True)
    except SyntaxError as e:
        check(f"{fp.name} parses", False, str(e))

passed = sum(1 for _, ok, _ in checks if ok)
total = len(checks)
print("")
print(f"{passed}/{total} checks passed")
if passed < total:
    for name, ok, detail in checks:
        if not ok:
            print(f"  - {name} {detail}")
    sys.exit(1)
print("ALL PASS")
