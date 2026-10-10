#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Smoke: verify orchestrator tool-result truncation (Part 31E)."""

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sunnyware.orchestrator import _truncate_tool_result

PASS, FAIL = 0, 0

def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print("  [PASS]", name)
    else:
        FAIL += 1
        print("  [FAIL]", name, "->", detail)

print("=== orchestrator truncation smoke test ===")
print()

# 1. Base64 field stripped
big_b64 = "iVBORw0KGgo" + "A" * 20000
r = _truncate_tool_result({"image_base64": big_b64, "ok": True})
check("base64 replaced with marker", "[image:" in r["image_base64"], r.get("image_base64"))
check("ok field preserved", r.get("ok") is True, r.get("ok"))

# 2. Long stdout truncated
r = _truncate_tool_result({"stdout": "x" * 5000})
check("stdout truncated", "truncated" in r["stdout"], r["stdout"][:80])

# 3. Small result untouched
r = _truncate_tool_result({"ok": True, "result": "42", "elapsed_ms": 27})
check("small result unchanged", r.get("result") == "42", r)

# 4. Total JSON size bounded
big_dict = {
    "image_base64": "A" * 50000,
    "stdout": "y" * 10000,
    "result": "z" * 10000,
    "preview": "p" * 10000,
}
r = _truncate_tool_result(big_dict)
import json
serialized = json.dumps(r, default=str)
check("total size < 2500 chars", len(serialized) < 2500, "size=" + str(len(serialized)))

# 5. Non-dict input handled
r = _truncate_tool_result("just a string")
check("non-dict handled", isinstance(r, dict), type(r).__name__)

print()
print("=== Results:", PASS, "passed,", FAIL, "failed ===")
if FAIL > 0:
    sys.exit(1)
print("ALL TRUNCATION TESTS PASSED")
