# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 105 smoke test - per-message provider badge."""
from pathlib import Path
import ast, sys

ROOT = Path(__file__).resolve().parent.parent
WUI = ROOT / "src" / "sunnyware" / "webui.py"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 105: per-message provider badge ===")

wui = WUI.read_text(encoding="utf-8")

# 1. lastProvider declaration
check("lastProvider declared",
      "let lastProvider = '';" in wui)
check("Part 105 comment on declaration",
      "// Part 105: track provider for the trailing chip" in wui)

# 2. final handler sets lastProvider
check("final handler sets lastProvider",
      "lastProvider = data.provider;  // Part 105" in wui)
check("lastProvider set at least twice (final + done)",
      wui.count("lastProvider = data.provider;  // Part 105") >= 2,
      f"{wui.count('lastProvider = data.provider;  // Part 105')} occurrences")

# 3. Chip append after stream
check("chip appended after stream end",
      "append provider chip under the assistant bubble" in wui)
check("chip uses insertAdjacentElement",
      "agentBubble.insertAdjacentElement('afterend', _chip)" in wui)
check("chip textContent includes 'via '",
      "'via ' + lastProvider" in wui)
check("chip shows seconds",
      "(ms / 1000).toFixed(1) + 's'" in wui)
check("chip guarded by agentBubble && lastProvider",
      "if (agentBubble && lastProvider) {" in wui)
check("chip wrapped in try/catch",
      "} catch (e) { /* silent */ }" in wui)

# 4. CSS
check("CSS rule .provider-chip present",
      ".provider-chip {" in wui)
check("CSS uses --text-mute",
      "color: var(--text-mute);" in wui)
check("CSS alignment padding",
      "padding-left: calc(var(--sp-3) + 3px)" in wui)
check("CSS opacity muted",
      "opacity: 0.7;" in wui)
check("CSS user-select none",
      "user-select: none;" in wui)

# 5. Existing functionality preserved
check("existing providerBadge still updated",
      "pb.textContent = 'via ' + data.provider" in wui)
check("existing latEl still set",
      "latEl.textContent = ms + ' ms'" in wui)

# 6. File parses
try:
    ast.parse(wui)
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
