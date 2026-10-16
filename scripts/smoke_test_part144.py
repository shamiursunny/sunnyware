# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 144 smoke - tool-aware eligibility + provider test endpoint."""
from pathlib import Path
import ast, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 144: tool-aware eligibility + provider test ===")

lt = (SRC / "llm.py").read_text(encoding="utf-8")
mt = (SRC / "routes" / "meta.py").read_text(encoding="utf-8")

check("llm.py has _estimate_tools_tokens",
      "def _estimate_tools_tokens" in lt)
check("llm.py uses _tools_tokens in eligibility",
      "_tools_tokens = _estimate_tools_tokens" in lt)
check("llm.py has _required_tokens",
      "_required_tokens = _prompt_tokens + _tools_tokens" in lt)
check("llm.py loop skip uses _required_tokens",
      "Part 99 + 144: skip provider that can't fit prompt+tools" in lt)

check("meta.py has /api/providers/test/{name}",
      '"/api/providers/test/{name}"' in mt)
check("test endpoint is admin-guarded",
      "_check_admin()" in mt)

sys.path.insert(0, str(SRC.parent))
from sunnyware import llm as L

check("None tools -> 0", L._estimate_tools_tokens(None) == 0)
check("empty list -> 0", L._estimate_tools_tokens([]) == 0)
small = [{"type": "function", "function": {"name": "x",
          "description": "y", "parameters": {}}}]
n = L._estimate_tools_tokens(small)
check("small tool -> positive int", isinstance(n, int) and n > 0,
      "n=%d" % n)
big = [{"type": "function", "function": {
    "name": "tool_%d" % i, "description": "x" * 200,
    "parameters": {"type": "object"}}} for i in range(50)]
n_big = L._estimate_tools_tokens(big)
check("50 tools -> larger", n_big > n, "n=%d" % n_big)
# Real Sunnyware schema (58 tools, full descriptions) = ~8,700 tokens.
# The synthetic 50-tool fixture is ~3,800. Assert the estimator scales
# proportionally rather than hardcoding the real-schema threshold.
check("50 tools estimator scales", n_big > 3000,
      "n=%d" % n_big)

p_tok = L._estimate_prompt_tokens("hi", None, None)
check("_estimate_prompt_tokens still works",
      isinstance(p_tok, int) and p_tok > 0)

for fp in [SRC / "llm.py", SRC / "routes" / "meta.py"]:
    try:
        ast.parse(fp.read_text(encoding="utf-8"))
        check(f"{fp.name} parses", True)
    except SyntaxError as e:
        check(f"{fp.name} parses", False, str(e))

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
