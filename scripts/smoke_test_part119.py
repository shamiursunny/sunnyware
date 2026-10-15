# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 119 smoke test - per-role agent monitoring metrics."""
from pathlib import Path
import ast, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 119: agent monitoring metrics ===")

# 1. Orchestrator instrumentation present
orch = (SRC / "orchestrator.py").read_text(encoding="utf-8")
check("orchestrator has Part 119 marker",
      "Part 119: metric instrumentation" in orch)
check("orchestrator increments agent_runs_total",
      '"agent_runs_total"' in orch)
check("orchestrator increments agent_success_total",
      '"agent_success_total"' in orch)
check("orchestrator increments agent_failure_total",
      '"agent_failure_total"' in orch)
check("orchestrator tracks latency_ms_total",
      '"agent_latency_ms_total"' in orch)
check("orchestrator tracks iterations_total",
      '"agent_iterations_total"' in orch)
check("orchestrator still returns _result_119",
      "return _result_119" in orch)
check("orchestrator still calls _run_agent_body",
      "_result_119 = await _run_agent_body(" in orch)
check("orchestrator resets context token on failure path",
      "_CURRENT_ROLE.reset(_role_token)\n        raise" in orch
      or "_CURRENT_ROLE.reset(_role_token)\n            raise" in orch)

# 2. Routes endpoint present
routes = (SRC / "routes" / "meta.py").read_text(encoding="utf-8")
check("route /api/agents/metrics present",
      '@router.get("/api/agents/metrics")' in routes)
check("route reads runs bucket",
      '"agent_runs_total"' in routes)
check("route reads success bucket",
      '"agent_success_total"' in routes)
check("route reads failure bucket",
      '"agent_failure_total"' in routes)
check("route reads latency",
      '"agent_latency_ms_total"' in routes)
check("route returns known_roles",
      '"known_roles"' in routes)

# 3. Metrics API compatibility (live in-process test)
sys.path.insert(0, str(SRC.parent))
from sunnyware import metrics as M

M.reset()
M.incr_labeled("agent_runs_total", "actuary")
M.incr_labeled("agent_runs_total", "actuary")
M.incr_labeled("agent_success_total", "actuary")
snap = M.snapshot()
check("metrics.incr_labeled works",
      isinstance(snap.get("agent_runs_total"), dict))
check("counter increment works",
      snap.get("agent_runs_total", {}).get("actuary") == 2)
check("snapshot returns labeled buckets",
      snap.get("agent_success_total", {}).get("actuary") == 1)
M.reset()

# 4. Files parse
for fp in [SRC / "orchestrator.py", SRC / "routes" / "meta.py"]:
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
