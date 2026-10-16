# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 143 smoke - rate-limit detection (Pollinations 402)."""
from pathlib import Path
import ast, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 143: rate-limit detection ===")

lt = (SRC / "llm.py").read_text(encoding="utf-8")
check("has _is_rate_limit_error", "def _is_rate_limit_error" in lt)
check("has _parse_retry_after", "def _parse_retry_after" in lt)
check("detects 402", '"402" in e' in lt)
check("detects FREE_LIMIT", '"free_limit" in e' in lt)
check("detects 'retry after'", '"retry after" in e' in lt)
check("cooldown honors retry hint",
      "Part 143: honor provider-supplied retry hint" in lt)

sys.path.insert(0, str(SRC.parent))
from sunnyware import llm as L

check("429 detected", L._is_rate_limit_error("HTTP 429") is True)
check("rate limit detected", L._is_rate_limit_error("rate limit reached") is True)
check("tpd detected", L._is_rate_limit_error("exceeded TPD") is True)
check("402 detected", L._is_rate_limit_error("HTTP 402") is True)
check("FREE_LIMIT detected",
      L._is_rate_limit_error(
          '{"code":"FREE_LIMIT","message":"Free limit reached"}') is True)
check("retry after detected",
      L._is_rate_limit_error("Retry after 8s") is True)
check("clean error NOT rate-limit",
      L._is_rate_limit_error("syntax error in prompt") is False)
check("empty NOT rate-limit", L._is_rate_limit_error("") is False)

check("parse 'Retry after 8s' -> 8",
      L._parse_retry_after("Retry after 8s, or get unlimited") == 8)
check("parse 'retry_after: 30' -> 30",
      L._parse_retry_after("retry_after: 30") == 30)
check("parse 'Retry-After 5' -> 5",
      L._parse_retry_after("Retry-After 5") == 5)
check("parse 'retry after 8' -> 8",
      L._parse_retry_after("please retry after 8 seconds") == 8)
check("parse no-hint -> 0",
      L._parse_retry_after("rate limit exceeded") == 0)
check("parse empty -> 0", L._parse_retry_after("") == 0)
check("parse clamps high value -> 600",
      L._parse_retry_after("retry after 99999") == 600)

real = (
    '{"code":"FREE_LIMIT","message":"Free limit reached: 1 reply every '
    '30 seconds per IP. Retry after 8s, or get unlimited replies with '
    'a pollen key at https://enter.p..."}'
)
check("real Pollinations payload -> rate-limit",
      L._is_rate_limit_error(real) is True)
check("real Pollinations payload -> retry=8",
      L._parse_retry_after(real) == 8)

try:
    ast.parse(lt)
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
