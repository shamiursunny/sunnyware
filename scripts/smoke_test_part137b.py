# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 137b smoke test - evals endpoints wired."""
from pathlib import Path
import ast, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 137b: evals endpoints wired ===")

rt = (SRC / "routes" / "meta.py").read_text(encoding="utf-8")
check("GET  /api/evals/status",  '"/api/evals/status"' in rt)
check("GET  /api/evals/latest",  '"/api/evals/latest"' in rt)
check("GET  /api/evals/trends",  '"/api/evals/trends"' in rt)
check("POST /api/evals/run",     '"/api/evals/run"' in rt)
check("evals_status imports evals", "from .. import evals as _evals" in rt)
check("evals_run is admin-guarded", "_check_admin()" in rt)
check("evals_run supports dry_run", "dry_run" in rt)
check("evals_run supports tags", "tags" in rt)
check("only one evals/run handler",
      rt.count('@router.post("/api/evals/run")') == 1)

try:
    ast.parse(rt)
    check("meta.py parses", True)
except SyntaxError as e:
    check("meta.py parses", False, str(e))

passed = sum(1 for _, ok, _ in checks if ok)
total = len(checks)
print(f"\n{passed}/{total} checks passed")
if passed < total:
    for name, ok, detail in checks:
        if not ok:
            print(f"  - {name} {detail}")
    sys.exit(1)
print("ALL PASS")
