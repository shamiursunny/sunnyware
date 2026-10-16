# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 139 smoke - resolved_model propagation."""
from pathlib import Path
import ast, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 139: resolved_model propagation ===")

ot = (SRC / "orchestrator.py").read_text(encoding="utf-8")
at = (SRC / "routes" / "agent.py").read_text(encoding="utf-8")

check("orchestrator init _last_model", "    _last_model = None" in ot)
check("orchestrator captures resolved_model",
      '_last_model = result.get("resolved_model")' in ot)
cnt = ot.count('"resolved_model": _last_model,')
check("orchestrator returns resolved_model (>=6 times)",
      cnt >= 6, f"count={cnt}")
check("route uses agent_result.get(resolved_model)",
      'agent_result.get("resolved_model")' in at)

for fp in [SRC / "orchestrator.py", SRC / "routes" / "agent.py"]:
    try:
        ast.parse(fp.read_text(encoding="utf-8"))
        check(f"{fp.name} parses", True)
    except SyntaxError as e:
        check(f"{fp.name} parses", False, str(e))

passed = sum(1 for _, ok, _ in checks if ok)
total = len(checks)
print(f"\n{passed}/{total} checks passed")
if passed < total:
    for name, ok, detail in checks:
        if not ok:
            print(f"  - {name} {detail}")
    sys.exit(1)
print("ALL PASS")
