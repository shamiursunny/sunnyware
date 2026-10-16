# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 137c smoke test - evals scheduler job."""
from pathlib import Path
import ast, asyncio, os, sys, tempfile

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 137c: evals scheduler job ===")

# 1. jobs/evals.py exists and has correct shape
jp = SRC / "jobs" / "evals.py"
check("jobs/evals.py exists", jp.exists())
jt = jp.read_text(encoding="utf-8") if jp.exists() else ""
check("has async run()", "async def run()" in jt)
check("calls evals.run_suite", "E.run_suite" in jt)
check("uses default_call_fn", "E.default_call_fn" in jt)
check("uses structured logger", "from ..runtime import log" in jt)
check("tags triggered_by=scheduler", 'triggered_by="scheduler"' in jt)

# 2. jobs/__init__.py imports evals + conditional registration
ip = SRC / "jobs" / "__init__.py"
it = ip.read_text(encoding="utf-8")
check("imports evals module", "from . import cleanup, heartbeat, evals" in it)
check("has SUNNYWARE_EVAL_INTERVAL_HOURS read",
      "SUNNYWARE_EVAL_INTERVAL_HOURS" in it)
check("registers evals_suite job", '"evals_suite"' in it)
check("evals_suite uses evals.run handler", "handler=evals.run" in it)

# 3. Existing jobs still registered
check("heartbeat still registered", '"heartbeat"' in it)
check("session_cleanup still registered", '"session_cleanup"' in it)

# 4. Structural: registration guarded by env > 0
check("conditional registration present", "if _ivl > 0:" in it)

# 5. Functional: run the job handler in isolation
os.environ["SUNNYWARE_EVAL_STORAGE"] = os.path.join(
    tempfile.mkdtemp(), "ev.json"
)
os.environ["SUNNYWARE_EVAL_KEEP_RUNS"] = "5"
# Point scheduler off for the test (we don't need it running)
os.environ["SUNNYWARE_SCHEDULE_ENABLED"] = "false"

sys.path.insert(0, str(SRC.parent))
from sunnyware.jobs import evals as eval_job

r = asyncio.run(eval_job.run())
check("job run returns dict", isinstance(r, dict))
check("job run has run_id", bool(r.get("run_id")))
check("job run has summary", isinstance(r.get("summary"), dict))
s = r.get("summary") or {}
check("summary has total", isinstance(s.get("total"), int))
check("summary total >= 5", (s.get("total") or 0) >= 5)

# Cleanup
del os.environ["SUNNYWARE_EVAL_STORAGE"]
del os.environ["SUNNYWARE_EVAL_KEEP_RUNS"]
del os.environ["SUNNYWARE_SCHEDULE_ENABLED"]

# 6. Registration check with env var UNset (should NOT register)
import importlib
# Fresh scheduler module to isolate
for m in list(sys.modules):
    if m.startswith("sunnyware.jobs") or m.startswith("sunnyware.scheduler"):
        del sys.modules[m]
os.environ.pop("SUNNYWARE_EVAL_INTERVAL_HOURS", None)
from sunnyware import scheduler as sched_mod
from sunnyware.jobs import register_all
register_all()
jobs_unset = [j["name"] for j in sched_mod.list_jobs()]
check("env unset: evals_suite NOT registered",
      "evals_suite" not in jobs_unset, f"jobs={jobs_unset}")
check("env unset: heartbeat IS registered",
      "heartbeat" in jobs_unset)

# 7. Registration with env=6 → SHOULD register
for m in list(sys.modules):
    if m.startswith("sunnyware.jobs") or m.startswith("sunnyware.scheduler"):
        del sys.modules[m]
os.environ["SUNNYWARE_EVAL_INTERVAL_HOURS"] = "6"
from sunnyware import scheduler as sched_mod2
from sunnyware.jobs import register_all as register_all2
register_all2()
jobs_set = [j["name"] for j in sched_mod2.list_jobs()]
check("env=6: evals_suite registered",
      "evals_suite" in jobs_set, f"jobs={jobs_set}")

# Check interval is 6h = 21600s
evals_job = next((j for j in sched_mod2.list_jobs() if j["name"] == "evals_suite"), None)
check("evals_suite interval == 21600s",
      evals_job and evals_job["interval_seconds"] == 21600,
      f"interval={evals_job and evals_job['interval_seconds']}")

del os.environ["SUNNYWARE_EVAL_INTERVAL_HOURS"]

# 8. Files parse
for fp in [jp, ip]:
    try:
        ast.parse(fp.read_text(encoding="utf-8"))
        check(f"{fp.name} parses", True)
    except SyntaxError as e:
        check(f"{fp.name} parses", False, str(e))

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
