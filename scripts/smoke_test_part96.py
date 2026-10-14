# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 96 smoke test - real token counts from provider usage."""
from pathlib import Path
import ast, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 96: real token counts from provider usage ===")

llm = (SRC / "llm.py").read_text(encoding="utf-8")
orc = (SRC / "orchestrator.py").read_text(encoding="utf-8")

# 1. llm.py returns the three token keys
check("llm.py returns 'tokens_in'", '"tokens_in":' in llm)
check("llm.py returns 'tokens_out'", '"tokens_out":' in llm)
check("llm.py returns 'tokens_total'", '"tokens_total":' in llm)
check("tokens_total = in + out", '"tokens_total": in_tok + out_tok' in llm)
check("in_tok initialized before try", "in_tok = 0\n            out_tok = 0" in llm)

# 2. orchestrator uses real tokens with fallback
check("_tools_overhead initialized", "_tools_overhead = 0" in orc)
check("_tools_overhead computed from tools_schema",
      "_tools_overhead = _estimate_tokens(str(tools_schema))" in orc)
check("reads tokens_total from result",
      '_real = int(result.get("tokens_total", 0) or 0)' in orc)
check("uses real tokens (subtracting overhead)",
      "_tokens_used += max(0, _real - _tools_overhead)" in orc)
check("falls back to heuristic when no real tokens",
      "_estimate_tokens(\n                system_prompt, content," in orc)

# 3. Double-counting fixed: prompt no longer passed to fallback heuristic
# (prompt is inside messages, so passing it separately double-counted)
_has_double_count = "_estimate_tokens(\n            prompt, system_prompt, content," in orc
check("no double-count of prompt in fallback", not _has_double_count)

# 4. Both files parse
for name, src in [("llm.py", llm), ("orchestrator.py", orc)]:
    try:
        ast.parse(src)
        check(f"{name} parses", True)
    except SyntaxError as e:
        check(f"{name} parses", False, str(e))

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
