# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 102 smoke test - retry policy for full failover cycle."""
from pathlib import Path
import ast, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 102: retry policy for full failover cycle ===")

llm = (SRC / "llm.py").read_text(encoding="utf-8")

# 1. Retry block exists
check("Part 102 comment present", "Part 102: if every provider failed" in llm)
check("checks _retry_depth == 0", "if _retry_depth == 0:" in llm)

# 2. Reloads providers to see fresh cooldown state
check("reloads providers (fresh cooldown)",
      "load_providers(reload=True)" in llm)

# 3. Cooldown-based heuristic
check("computes min cooldown remaining",
      "_min_cool = min(" in llm)
check("20s threshold present", "_min_cool <= 20.0" in llm)
check("only when no ready providers", "and not _ready" in llm)

# 4. Wait cap
check("wait capped at 8s", "min(_min_cool + 0.5, 8.0)" in llm)

# 5. Recursion with _retry_depth=1 (prevents infinite loops)
check("recurses with _retry_depth=1",
      "_retry_depth=1," in llm)
check("passes prompt to recursive call",
      "return await chat(" in llm and "prompt," in llm)

# 6. Diagnostics
check("logs 'all providers failed' diagnostic",
      "[llm.chat] all providers failed" in llm)
check("logs 'retrying once' message",
      "retrying once after" in llm)

# 7. Metric
check("metric llm_request_retried emitted",
      'llm_request_retried' in llm)

# 8. Final return still present (fallback if retry also fails)
check("final return still present",
      '"error": "all providers failed; last: "' in llm)

# 9. Signature still has _retry_depth param
check("_retry_depth in chat() signature",
      "_retry_depth: int = 0," in llm)

# 10. File parses
try:
    ast.parse(llm)
    check("llm.py parses", True)
except SyntaxError as e:
    check("llm.py parses", False, str(e))

# 11. Live: chat() is a coroutine function
sys.path.insert(0, str(SRC.parent))
try:
    from sunnyware import llm as _l
    import inspect
    check("chat() is coroutine", inspect.iscoroutinefunction(_l.chat))
    sig = inspect.signature(_l.chat)
    check("chat() accepts _retry_depth",
          "_retry_depth" in sig.parameters)
    check("chat() _retry_depth default 0",
          sig.parameters["_retry_depth"].default == 0)
except Exception as e:
    check("live import works", False, f"{type(e).__name__}: {e}")

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
