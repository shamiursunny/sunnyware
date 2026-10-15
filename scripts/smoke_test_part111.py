# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 111 smoke test - actuarial / insurance / risk libraries."""
from pathlib import Path
import ast, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 111: actuarial / insurance / risk libraries ===")

# 1. requirements.txt has the 3 libraries
req = (ROOT / "requirements.txt").read_text(encoding="utf-8")
check("chainladder in requirements", "chainladder" in req)
check("lifelib in requirements", "lifelib" in req)
check("solvency2-data in requirements", "solvency2-data" in req)
check("haute NOT in requirements (Py3.11 only)", "haute" not in req)

# 2. Sandbox allowlist
sandbox = (SRC / "tools" / "_sandbox.py").read_text(encoding="utf-8")
check("chainladder in ALLOWED_MODULES", '"chainladder"' in sandbox)
check("lifelib in ALLOWED_MODULES", '"lifelib"' in sandbox)
check("solvency2_data in ALLOWED_MODULES", '"solvency2_data"' in sandbox)
check("sparse in allowlist (chainladder dep)", '"sparse"' in sandbox)
check("modelx in allowlist (lifelib dep)", '"modelx"' in sandbox)

# 3. Sandbox validates imports
sys.path.insert(0, str(SRC.parent))
from sunnyware.tools import _sandbox
code = """
import chainladder as cl
import lifelib
import solvency2_data
result = "ok"
"""
errors = _sandbox.validate(code)
check("sandbox accepts all 3 imports", not errors, str(errors[:3]) if errors else "")

# 4. Sandbox file parses
try:
    ast.parse(sandbox)
    check("_sandbox.py parses", True)
except SyntaxError as e:
    check("_sandbox.py parses", False, str(e))

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
