# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 149 smoke - mandatory tool-use rules in auditor prompt."""
from pathlib import Path
import ast, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 149: mandatory tool-use rules ===")

rt = (SRC / "roles.py").read_text(encoding="utf-8")

check("MANDATORY calculator rule present",
      "MANDATORY: ALWAYS call calculator" in rt)
check("calculator rule has example",
      "you MUST call calculator('240 * 0.15')" in rt)
check("SIDECAR TRIGGERS block present",
      "SIDECAR TRIGGERS:" in rt)
check("trigger word: layers", "'layers'" in rt)
check("trigger word: end-to-end", "'end-to-end'" in rt)
check("trigger word: all sources of error",
      "'all sources of error'" in rt)
check("trigger word: multi-layer", "'multi-layer'" in rt)
check("trigger word: benchmark", "'benchmark'" in rt)
check("trigger word: evaluator", "'evaluator'" in rt)
check("trigger word: rubric", "'rubric'" in rt)
check("trigger word: evidence hierarchy", "'evidence hierarchy'" in rt)
check("skipping is a defect marker",
      "Skipping this when trigger words are present is a defect" in rt)

sys.path.insert(0, str(SRC.parent))
from sunnyware import roles as R

p = R.prompt_addon("auditor") or ""
check("prompt has MANDATORY", "MANDATORY" in p)
check("prompt has SIDECAR TRIGGERS", "SIDECAR TRIGGERS" in p)
check("prompt has call-once hint still",
      "Call calculator ONCE per unique expression" in p)
check("prompt has auditor_full_spec ONCE",
      "auditor_full_spec ONCE" in p)
check("prompt length <= 4500", len(p) <= 4500, "len=%d" % len(p))
check("prompt length >= 2800", len(p) >= 2800, "len=%d" % len(p))

try:
    ast.parse(rt)
    check("roles.py parses", True)
except SyntaxError as e:
    check("roles.py parses", False, str(e))

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
