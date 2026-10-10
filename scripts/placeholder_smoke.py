#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Smoke: verify placeholder detection (Part 31F)."""

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sunnyware.orchestrator import _looks_like_placeholder

PASS, FAIL = 0, 0

def check(name, ok):
    global PASS, FAIL
    if ok:
        PASS += 1
        print("  [PASS]", name)
    else:
        FAIL += 1
        print("  [FAIL]", name)

print("=== placeholder detection smoke test ===")
print()

# Real answers -> NOT placeholder
check("numeric answer", not _looks_like_placeholder("The average is 24,666.67"))
check("long text answer", not _looks_like_placeholder(
    "Based on the retrieved document, the Marketing ad-spend variance was $2,000 unfavorable."
))
check("table answer", not _looks_like_placeholder(
    "| Dept | Total |\n|------|-------|\n| Sales | 54000 |"
))

# Placeholders -> detected
check("empty string", _looks_like_placeholder(""))
check("short ack", _looks_like_placeholder("Sure!"))
check("what next", _looks_like_placeholder("What would you like to do next?"))
check("how can i help", _looks_like_placeholder("How can I help you today?"))
check("let me know", _looks_like_placeholder("Let me know if you need anything else."))

print()
print("=== Results:", PASS, "passed,", FAIL, "failed ===")
if FAIL > 0:
    sys.exit(1)
print("ALL PLACEHOLDER TESTS PASSED")
