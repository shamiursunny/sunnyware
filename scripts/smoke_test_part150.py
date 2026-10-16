# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 150 smoke - forced JSON retry on extraction failure."""
from pathlib import Path
import ast, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 150: forced JSON retry ===")

at = (SRC / "routes" / "agent.py").read_text(encoding="utf-8")

check("agent.py has _auditor_verdict_with_retry",
      "async def _auditor_verdict_with_retry" in at)
check("agent.py uses await retry",
      "await _auditor_verdict_with_retry" in at)
# The function definition itself still exists; only the CALL
# sites should be gone. Count patterns like "= _auditor_verdict_or_none("
# (assignment/return contexts), not the def line.
check("agent.py removed sync call sites",
      ": _auditor_verdict_or_none(" not in at
      and "= _auditor_verdict_or_none(" not in at
      and "return _auditor_verdict_or_none(" not in at)
check("retry helper mentions 'ONLY the JSON'",
      "return ONLY the JSON verdict object" in at)
check("retry helper mentions no fences",
      "No markdown fences" in at)
check("retry helper mentions required keys",
      "Required keys: verdict, canonical_label" in at)
check("retry helper calls run_agent",
      "_orc.run_agent(" in at)
check("retry helper is awaited from route",
      at.count("await _auditor_verdict_with_retry") == 2)

try:
    ast.parse(at.replace("\r\n", "\n"))
    check("agent.py parses", True)
except SyntaxError as e:
    check("agent.py parses", False, str(e))

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
