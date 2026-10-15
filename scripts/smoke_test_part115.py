# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 115 smoke test - role-specific content styling."""
from pathlib import Path
import ast, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 115: role-specific content styling ===")

t = (SRC / "webui.py").read_text(encoding="utf-8")

check("Part 115 marker present", "Part 115: role-specific content" in t)

# FP&A
check("FPA table border", '#chat[data-role="fpa"] .msg.agent table' in t)
check("FPA table th bg", '#chat[data-role="fpa"] .msg.agent th' in t)
check("FPA h1/h2 color", '#chat[data-role="fpa"] .msg.agent h1' in t)

# Quant
check("Quant pre border-left", '#chat[data-role="quant"] .msg.agent pre' in t)
check("Quant code color", '#chat[data-role="quant"] .msg.agent code' in t)
check("Quant h1/h2 color", '#chat[data-role="quant"] .msg.agent h1' in t)

# Actuary
check("Actuary table border", '#chat[data-role="actuary"] .msg.agent table' in t)
check("Actuary blockquote", '#chat[data-role="actuary"] .msg.agent blockquote' in t)
check("Actuary h1/h2 color", '#chat[data-role="actuary"] .msg.agent h1' in t)

# Tax
check("Tax ol marker", '#chat[data-role="tax"] .msg.agent ol li::marker' in t)
check("Tax ul marker", '#chat[data-role="tax"] .msg.agent ul li::marker' in t)
check("Tax h1/h2 color", '#chat[data-role="tax"] .msg.agent h1' in t)

# CFO
check("CFO padding+background", '#chat[data-role="cfo"] .msg.agent' in t and 'rgba(139,92,246,0.04)' in t)
check("CFO h1/h2 color", '#chat[data-role="cfo"] .msg.agent h1' in t)
check("CFO table border", '#chat[data-role="cfo"] .msg.agent table' in t)

# CDO
check("CDO task-list style", 'rgba(6,182,212,0.04)' in t)
check("CDO h1/h2 color", '#chat[data-role="cdo"] .msg.agent h1' in t)

# Regression guards from 113B (must still be present)
check("113B fpa border intact", '#chat[data-role="fpa"] .msg.agent     { border-left-color: #4a90e2; }' in t)
check("113B cfo border intact", '#chat[data-role="cfo"] .msg.agent     { border-left-color: #8b5cf6; }' in t)
check("113B cdo border intact", '#chat[data-role="cdo"] .msg.agent     { border-left-color: #06b6d4; }' in t)

try:
    ast.parse(t)
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
