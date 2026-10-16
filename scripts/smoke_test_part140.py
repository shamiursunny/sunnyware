# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 140 smoke - Sunnyware identity clause in system prompts."""
from pathlib import Path
import ast, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 140: Sunnyware identity clause ===")

pt = (SRC / "prompts.py").read_text(encoding="utf-8")

check("has _IDENTITY_CLAUSE constant", "_IDENTITY_CLAUSE" in pt)
check("clause forbids Gemini claim", "Gemini" in pt and "never claim" in pt)
check("clause mentions Sunnyware name", "Your name is Sunnyware" in pt)

needle = '_IDENTITY_CLAUSE + " "'
clause_count = pt.count(needle)
check("compact_prompt uses clause", needle in pt)
check("both prompts prepend clause", clause_count >= 2,
      "count=%d" % clause_count)

sys.path.insert(0, str(SRC.parent))
from sunnyware import prompts as P

c = P.compact_prompt()
n = P.native_prompt()
check("compact_prompt has clause", isinstance(c, str) and "never claim" in c)
check("native_prompt has clause", isinstance(n, str) and "never claim" in n)
check("clause forbids LFM", "LFM" in c)
check("clause forbids GPT", "GPT" in c)
check("clause forbids Llama", "Llama" in c)
check("compact still has tools list", "Available tools:" in c)
check("native still has CORE RULES", "CORE RULES" in n)

try:
    ast.parse(pt)
    check("prompts.py parses", True)
except SyntaxError as e:
    check("prompts.py parses", False, str(e))

passed = sum(1 for _, ok, _ in checks if ok)
total = len(checks)
print(f"\n{passed}/{total} checks passed")
if passed < total:
    for name, ok, detail in checks:
        if not ok:
            print(f"  - {name} {detail}")
    sys.exit(1)
print("ALL PASS")
