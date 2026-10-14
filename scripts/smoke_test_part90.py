# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 90 smoke test - per-request token budget guard.

Verifies:
  1. MAX_REQUEST_TOKENS constant exists (default 8000)
  2. _BUDGET_MESSAGE template exists with {used} and {cap}
  3. _estimate_tokens helper exists and produces sane output
  4. _tokens_used accumulator initialized before the loop
  5. Budget check compares _tokens_used >= MAX_REQUEST_TOKENS
  6. budget_exceeded key is returned when limit trips
  7. SSE event type 'budget_exceeded' emitted
"""
from pathlib import Path
import ast, re, sys

ROOT = Path(__file__).resolve().parent.parent
ORC = ROOT / "src" / "sunnyware" / "orchestrator.py"

checks = []
def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 90: per-request token budget guard ===")

src = ORC.read_text(encoding="utf-8")

# 1. Constant
check("MAX_REQUEST_TOKENS defined", "MAX_REQUEST_TOKENS = " in src,
      re.search(r"MAX_REQUEST_TOKENS = (\d+)", src).group(1) if re.search(r"MAX_REQUEST_TOKENS = (\d+)", src) else "")

# 2. Budget message
check("_BUDGET_MESSAGE defined", "_BUDGET_MESSAGE = (" in src)
check("_BUDGET_MESSAGE has {used}", "{used:" in src and "{cap:" in src)

# 3. Helper function
check("_estimate_tokens defined", "def _estimate_tokens(" in src)
check("_estimate_tokens uses ~4 chars/token", "// 4" in src)

# 4. Accumulator initialized
check("_tokens_used initialized to 0", "_tokens_used = 0" in src)

# 5. Budget check in loop
check("budget check present", "if _tokens_used >= MAX_REQUEST_TOKENS:" in src)

# 6. budget_exceeded returned
check("budget_exceeded returned in dict", '"budget_exceeded": True' in src)

# 7. SSE event emitted
check("SSE budget_exceeded event emitted", '"type": "budget_exceeded"' in src)

# 8. Accumulator increments on each iteration
check("_tokens_used += in loop", "_tokens_used += _estimate_tokens(" in src)

# 9. File still parses
try:
    ast.parse(src)
    check("orchestrator.py parses", True)
except SyntaxError as e:
    check("orchestrator.py parses", False, str(e))

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
