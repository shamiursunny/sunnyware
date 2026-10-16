# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 154 smoke - retry-wait threshold + cap raised."""
from pathlib import Path
import ast, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 154: retry-wait threshold + cap ===")

lt = (SRC / "llm.py").read_text(encoding="utf-8")

check("Part 154 marker present", "Part 154: raised from 20s to 40s" in lt)
check("env var SUNNYWARE_RETRY_WAIT_MAX_S present",
      "SUNNYWARE_RETRY_WAIT_MAX_S" in lt)
check("default = 40", 'getenv("SUNNYWARE_RETRY_WAIT_MAX_S", "40")' in lt)
check("threshold raised: no <= 20.0",
      "_min_cool <= 20.0" not in lt)
check("threshold now uses _retry_wait_max",
      "_min_cool <= _retry_wait_max" in lt)
check("wait cap raised: no 8.0 hard cap",
      "min(_min_cool + 0.5, 8.0)" not in lt)
check("new wait cap uses _retry_wait_max",
      "min(_min_cool + 1.0, _retry_wait_max + 5.0)" in lt)

try:
    ast.parse(lt.replace("\r\n", "\n"))
    check("llm.py parses", True)
except SyntaxError as e:
    check("llm.py parses", False, str(e))

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
