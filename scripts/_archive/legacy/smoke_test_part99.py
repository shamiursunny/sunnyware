# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 99 smoke test - long-prompt routing (provider size filter)."""
from pathlib import Path
import ast, sys, os

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 99: long-prompt routing ===")

prov = (SRC / "providers.py").read_text(encoding="utf-8")
llm = (SRC / "llm.py").read_text(encoding="utf-8")

# 1. Provider dataclass
check("Provider has max_prompt_tokens field",
      "max_prompt_tokens: int = 0" in prov)
check("max_prompt_tokens default = 0 (unlimited)",
      "max_prompt_tokens: int = 0   # Part 99" in prov)

# 2. status() exposes it
check("status() exposes max_prompt_tokens",
      '"max_prompt_tokens": self.max_prompt_tokens' in prov)

# 3. load_providers defaults
check("groq default 7500", '"groq": 7500' in prov)
check("gemini default 1M", '"gemini": 1000000' in prov)
check("openrouter default 32k", '"openrouter": 32000' in prov)
check("pollinations default 32k", '"pollinations": 32000' in prov)
check("env override supported",
      "_MAX_PROMPT_TOKENS" in prov or "MAX_PROMPT_TOKENS" in prov)

# 4. llm.py helper
check("_estimate_prompt_tokens helper defined",
      "def _estimate_prompt_tokens(" in llm)
check("counts prompt + system + history",
      "isinstance(prompt, str)" in llm and "isinstance(system, str)" in llm)

# 5. Skip logic
check("pre-filter computes prompt tokens",
      "_prompt_tokens = _estimate_prompt_tokens(" in llm)
check("fallback: tries all if none eligible",
      "_any_eligible" in llm)
check("skips oversized providers",
      "_prompt_tokens > p.max_prompt_tokens" in llm)

# 6. Files parse
for name, src in [("providers.py", prov), ("llm.py", llm)]:
    try:
        ast.parse(src)
        check(f"{name} parses", True)
    except SyntaxError as e:
        check(f"{name} parses", False, str(e))

# 7. Live import + sanity
sys.path.insert(0, str(SRC.parent))
try:
    from sunnyware import providers as p
    provs = p.load_providers(reload=True)
    check("load_providers() runs", isinstance(provs, list))
    # Each provider has the attr (even if 0 in legacy mode)
    check("all providers have max_prompt_tokens attr",
          all(hasattr(x, "max_prompt_tokens") for x in provs))
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
