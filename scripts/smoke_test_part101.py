# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 101 smoke test - empty-response fallback in multi-provider chain."""
from pathlib import Path
import ast, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 101: empty-response fallback ===")

llm = (SRC / "llm.py").read_text(encoding="utf-8")

# 1. Helper exists and is correct
check("_is_empty_response() defined", "def _is_empty_response(" in llm)
check("helper takes a dict", "def _is_empty_response(r: dict)" in llm)
check("helper checks ok status", 'not r.get("ok")' in llm)
check("helper checks content strip", 'content = (r.get("content") or "").strip()' in llm)
check("helper checks tool_calls", 'tool_calls = r.get("tool_calls") or []' in llm)
check("helper returns both-empty condition",
      "return (not content) and (not tool_calls)" in llm)

# 2. HTTP path patched
check("HTTP path: empty-check before ok-check",
      "empty responses as failures so we try the" in llm)
check("HTTP path: uses helper", "r.get(\"ok\") and _is_empty_response(r)" in llm)
check("HTTP path: 15s cooldown on empty",
      'p.mark_cooldown(15.0)' in llm)
check("HTTP path: continues to next provider",
      "p.record_failure(_err)" in llm)

# 3. Local path patched
check("Local path: empty check present",
      "empty response from local model" in llm)
check("Local path: 10s cooldown on empty",
      # ensure the local-path cooldown is present, both use mark_cooldown
      'p.mark_cooldown(10.0)' in llm)

# 4. Metric emitted
check("Metric emitted (both paths)",
      llm.count("llm_provider_empty_response") >= 2,
      f"{llm.count('llm_provider_empty_response')} occurrences")

# 5. Backward compat: _chat_single still returns ok=True on empty
#    (chain-level handling lives in chat(), not in _chat_single)
check("_chat_single unchanged (returns ok=True with empty)",
      '"ok": True,\n                "content": content,\n                "tool_calls": tool_calls,' in llm)

# 6. File parses
try:
    ast.parse(llm)
    check("llm.py parses", True)
except SyntaxError as e:
    check("llm.py parses", False, str(e))

# 7. Live behavior test: _is_empty_response returns correct values
sys.path.insert(0, str(SRC.parent))
try:
    from sunnyware import llm as _l
    # Empty content, no tools -> True
    r1 = {"ok": True, "content": "", "tool_calls": None}
    check("empty content + no tools -> True", _l._is_empty_response(r1) is True)
    # Whitespace only -> True
    r2 = {"ok": True, "content": "   \n  ", "tool_calls": []}
    check("whitespace + empty list -> True", _l._is_empty_response(r2) is True)
    # Real content -> False
    r3 = {"ok": True, "content": "Hello!", "tool_calls": None}
    check("real content -> False", _l._is_empty_response(r3) is False)
    # Content with tool calls -> False
    r4 = {"ok": True, "content": "", "tool_calls": [{"id": "x"}]}
    check("tool calls but no content -> False", _l._is_empty_response(r4) is False)
    # Not ok -> False
    r5 = {"ok": False, "error": "boom"}
    check("not ok -> False", _l._is_empty_response(r5) is False)
    # Non-dict -> False
    check("non-dict -> False", _l._is_empty_response("nope") is False)
    check("None -> False", _l._is_empty_response(None) is False)
except Exception as e:
    check("live module test", False, f"{type(e).__name__}: {e}")

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
