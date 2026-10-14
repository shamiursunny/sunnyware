# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 91 smoke test - WebUI budget_exceeded styling.

Verifies the WebUI:
  1. Declares a budgetExceeded flag
  2. Handles the 'budget_exceeded' SSE event type
  3. Reads data.budget_exceeded from the 'final' event
  4. Applies class 'budget' to the assistant bubble
  5. Has .msg.agent.budget CSS rule
  6. Has BUDGET LIMIT ::before prefix (ASCII-safe)
  7. webui.py parses
"""
from pathlib import Path
import ast, sys

ROOT = Path(__file__).resolve().parent.parent
WUI = ROOT / "src" / "sunnyware" / "webui.py"

checks = []
def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 91: WebUI budget_exceeded styling ===")

src = WUI.read_text(encoding="utf-8")

check("budgetExceeded flag declared", "let budgetExceeded = false" in src)
check("SSE 'budget_exceeded' case present", "type === 'budget_exceeded'" in src)
check("reads data.budget_exceeded in final", "data.budget_exceeded" in src)
check("adds 'budget' class to bubble", "classList.add('budget')" in src)
check("CSS rule .msg.agent.budget present", ".msg.agent.budget {" in src)
check("::before prefix 'BUDGET LIMIT:' present", "BUDGET LIMIT:" in src)
check("no unicode escapes leaked in CSS", "\\u" not in src.split(".msg.agent.budget")[1][:200] if ".msg.agent.budget" in src else False)

try:
    ast.parse(src)
    check("webui.py parses", True)
except SyntaxError as e:
    check("webui.py parses", False, str(e))

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
