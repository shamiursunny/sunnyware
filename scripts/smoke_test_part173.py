# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 173 smoke - per-tool rate limits."""
from pathlib import Path
import ast, os, sys, time

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" +
          (f"  ({detail})" if detail else ""))

print("=== Part 173: per-tool rate limits ===")

# Code wiring
ct = (SRC / "circuit_breaker.py").read_text(encoding="utf-8")
check("circuit_breaker: rpm_limit()", "def rpm_limit()" in ct)
check("circuit_breaker: rate_limited reason", '"rate_limited"' in ct)
check("circuit_breaker: tracks recent_calls", "recent_calls" in ct)
check("circuit_breaker: snapshot exposes rpm",
      "rpm_limit" in ct and "rpm_current" in ct)
check("circuit_breaker: snapshot exposes cooldown",
      "rate_cooldown_s" in ct)

ot = (SRC / "orchestrator.py").read_text(encoding="utf-8")
check("orchestrator: handles rate_limited",
      'reason = decision.get("reason"' in ot
      and 'reason = decision.get("reason", "circuit_open")' in ot
      or "rate_limited" in ot)
check("orchestrator: dynamic reason", 'reason = decision.get("reason"' in ot)

ht = (SRC / "tools_health.py").read_text(encoding="utf-8")
check("tools_health: integrates rate_cool", "rate_cool" in ht)
check("tools_health: exposes rpm fields",
      '"rpm_limit"' in ht and '"rpm_current"' in ht)
check("tools_health: rate_limited reason",
      "rate limited" in ht.lower() or "rate_limited" in ht)

th = (ROOT / "static" / "tools.html").read_text(encoding="utf-8")
check("tools.html: rate_limited filter",
      'data-filter="rate_limited"' in th)
check("tools.html: filter logic handles rate_limited",
      'currentFilter === "rate_limited"' in th)
check("tools.html: meta shows rpm/cooldown",
      "rpm" in th and "cool " in th)
check("tools.html: detail shows rate limit",
      "rate limit" in th and "rate cooldown" in th)

# Functional test
sys.path.insert(0, str(SRC.parent))
os.environ["SUNNYWARE_TOOL_BREAKER_ENABLED"] = "1"
os.environ["SUNNYWARE_TOOL_RATE_LIMIT_PER_MINUTE"] = "5"
from sunnyware import circuit_breaker as CB

CB.reset()

# Initial allow
d = CB.check("test_tool")
check("initially allowed", d["allow"] is True)

# Record 5 calls within the minute
for i in range(5):
    CB.record("test_tool", True)

# 6th call must be rate-limited
d = CB.check("test_tool")
check("6th call rate_limited", d["allow"] is False)
check("reason is rate_limited", d.get("reason") == "rate_limited")
check("retry_after set", d.get("retry_after", 0) > 0)

# Snapshot reflects state
snap = CB.snapshot()
tool = next((t for t in snap["tools"] if t["name"] == "test_tool"), None)
check("snapshot rpm_limit=5", tool and tool["rpm_limit"] == 5)
check("snapshot rpm_current=5", tool and tool["rpm_current"] == 5)
check("snapshot rate_cooldown active",
      tool and tool["rate_cooldown_s"] > 0)

# Disabled bypasses
os.environ["SUNNYWARE_TOOL_RATE_LIMIT_PER_MINUTE"] = "0"
d = CB.check("test_tool")
check("disabled rate limit allows", d["allow"] is True)

# Reset for next test
os.environ.pop("SUNNYWARE_TOOL_RATE_LIMIT_PER_MINUTE", None)

# Files parse
for fp in [SRC / "circuit_breaker.py", SRC / "orchestrator.py",
           SRC / "tools_health.py"]:
    try:
        ast.parse(fp.read_text(encoding="utf-8"))
        check(f"{fp.name} parses", True)
    except SyntaxError as e:
        check(f"{fp.name} parses", False, str(e))

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
