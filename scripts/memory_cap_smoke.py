#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Smoke: verify memory payload caps stop token blowup (Part 31E)."""

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sunnyware.memory import (
    _sanitize_content, MAX_LOG_CONTENT_CHARS,
    MAX_HISTORY_CONTENT_CHARS, MAX_CONTEXT_CONTENT_CHARS,
)

PASS, FAIL = 0, 0

def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print("  [PASS]", name)
    else:
        FAIL += 1
        print("  [FAIL]", name, "->", detail)

print("=== memory cap smoke test ===")
print()

# 1. Short text passes through
r = _sanitize_content("hello world", 100)
check("short text unchanged", r == "hello world", r)

# 2. Long text truncated
long_text = "x" * 5000
r = _sanitize_content(long_text, 100)
check("long text truncated", len(r) < 200 and "truncated" in r, repr(r[:100]))

# 3. Base64 blob redacted
# Realistic base64: uppercase + lowercase + digits
fake_b64 = ("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAA" * 40) + "=="
r = _sanitize_content("before " + fake_b64 + " after", 5000)
check("base64 blob redacted",
      "redacted" in r and "before " in r and " after" in r,
      repr(r[:200]))

# 4. Realistic chart-response scenario
chart_msg = "Here is the chart:\n\n" + ("iVBORw0KGgo" + "A" * 15000) + "\n\nEnd."
r = _sanitize_content(chart_msg, MAX_LOG_CONTENT_CHARS)
check("chart message capped", len(r) < MAX_LOG_CONTENT_CHARS + 200, "len=" + str(len(r)))
check("chart base64 redacted", "iVBORw0KGgoAAA" not in r, "base64 marker still present")

# 5. Simulate 10 x 15 KB messages replayed -> total should be tiny
total_before = 10 * 15000
total_after = sum(len(_sanitize_content("y" * 15000, MAX_HISTORY_CONTENT_CHARS)) for _ in range(10))
check("10x15KB replay capped", total_after < 10000,
      "before=" + str(total_before) + " after=" + str(total_after))

# 6. Cap constants sensible
check("log cap <= 2500", MAX_LOG_CONTENT_CHARS <= 2500, str(MAX_LOG_CONTENT_CHARS))
check("history cap <= 1000", MAX_HISTORY_CONTENT_CHARS <= 1000, str(MAX_HISTORY_CONTENT_CHARS))
check("context cap <= 300", MAX_CONTEXT_CONTENT_CHARS <= 300, str(MAX_CONTEXT_CONTENT_CHARS))

print()
print("=== Results:", PASS, "passed,", FAIL, "failed ===")
if FAIL > 0:
    sys.exit(1)
print("ALL MEMORY CAP TESTS PASSED")
