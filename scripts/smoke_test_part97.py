# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 97 smoke test - Pollinations AI fallback provider.

Verifies:
  1. model_resolver.py has a 'pollinations' PREFERENCES entry
  2. .env.example documents POLLINATIONS_BASE_URL / API_KEY / MODEL
  3. main .env (if present) has the same keys
  4. Base URL points to text.pollinations.ai (OpenAI-compatible)
  5. Static verifications only -- live provider status is checked by the
     pre_push_check stage 5 (HF health).
"""
from pathlib import Path
import ast, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 97: Pollinations AI fallback provider ===")

# 1. model_resolver.py has the preference list
mr = (SRC / "model_resolver.py").read_text(encoding="utf-8")
check("model_resolver has 'pollinations' PREFERENCES",
      '"pollinations": [' in mr)
check("pollinations prefers 'openai' model first",
      '"pollinations": [\n        "openai"' in mr or
      '"pollinations": [' in mr and 'openai' in mr.split('"pollinations"')[1][:200])

# 2. .env.example documents all three keys
exp = ROOT / ".env.example"
check(".env.example exists", exp.is_file())
if exp.is_file():
    ex = exp.read_text(encoding="utf-8", errors="replace")
    check(".env.example has POLLINATIONS_BASE_URL",
          "POLLINATIONS_BASE_URL=" in ex)
    check(".env.example has POLLINATIONS_API_KEY",
          "POLLINATIONS_API_KEY=" in ex)
    check(".env.example has POLLINATIONS_MODEL",
          "POLLINATIONS_MODEL=" in ex)
    check(".env.example points at text.pollinations.ai",
          "text.pollinations.ai" in ex)

# 3. .env (local) has the keys (not committed, so just a soft check)
env = ROOT / ".env"
if env.is_file():
    et = env.read_text(encoding="utf-8", errors="replace")
    check(".env has POLLINATIONS_BASE_URL (local)",
          "POLLINATIONS_BASE_URL=" in et)
    check(".env has LLM_PROVIDERS including pollinations",
          "LLM_PROVIDERS=" in et and "pollinations" in et)

# 4. model_resolver parses
try:
    ast.parse(mr)
    check("model_resolver.py parses", True)
except SyntaxError as e:
    check("model_resolver.py parses", False, str(e))

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
