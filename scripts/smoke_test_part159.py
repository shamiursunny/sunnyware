# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 159 smoke - budget + rollup + alerts."""
from pathlib import Path
import ast, asyncio, os, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 159: budget + rollup + alerts ===")

ut = (SRC / "usage.py").read_text(encoding="utf-8")
mt = (SRC / "routes" / "meta.py").read_text(encoding="utf-8")

check("usage.py has budget_status", "async def budget_status" in ut)
check("usage.py has check_budget", "async def check_budget" in ut)
check("usage.py has fire_alerts", "def fire_alerts" in ut)
check("usage.py has rollup", "async def rollup" in ut)
check("usage.py has reset_alerts", "def reset_alerts" in ut)
check("usage.py imports datetime",
      "from datetime import datetime, timezone" in ut)

check("GET /api/usage/budget", '"/api/usage/budget"' in mt)
check("GET /api/usage/rollup", '"/api/usage/rollup"' in mt)
check("POST /api/usage/alerts/reset",
      '"/api/usage/alerts/reset"' in mt)

sys.path.insert(0, str(SRC.parent))
from sunnyware import usage as U

os.environ.pop("SUNNYWARE_BUDGET_USD_DAILY", None)
os.environ.pop("SUNNYWARE_BUDGET_USD_MONTHLY", None)
os.environ.pop("SUNNYWARE_BUDGET_ALERT_PCT", None)

check("default daily cap 0", U._budget_daily() == 0.0)
check("default monthly cap 0", U._budget_monthly() == 0.0)
check("default alert [80]", U._alert_thresholds() == [80])

os.environ["SUNNYWARE_BUDGET_USD_DAILY"] = "5.50"
os.environ["SUNNYWARE_BUDGET_USD_MONTHLY"] = "100"
os.environ["SUNNYWARE_BUDGET_ALERT_PCT"] = "50, 80, 95"
check("daily cap parses", U._budget_daily() == 5.5)
check("monthly cap parses", U._budget_monthly() == 100.0)
check("alert thresholds parse", U._alert_thresholds() == [50, 80, 95])

os.environ["SUNNYWARE_BUDGET_ALERT_PCT"] = "bogus,0,101,50"
check("alert thresholds filter bad", U._alert_thresholds() == [50])

U.reset_alerts()
status = {
    "daily": {"enabled": True, "pct": 85.0, "used_usd": 4.25, "cap_usd": 5.0},
    "monthly": {"enabled": True, "pct": 55.0, "used_usd": 55.0, "cap_usd": 100.0},
}
os.environ["SUNNYWARE_BUDGET_ALERT_PCT"] = "50,80,95"
alerts1 = U.fire_alerts("tenantA", status)
check("alerts fire (50,80 daily + 50 monthly)",
      len(alerts1) == 3, "n=%d" % len(alerts1))
alerts2 = U.fire_alerts("tenantA", status)
check("alerts deduped on second call", len(alerts2) == 0)

alerts3 = U.fire_alerts("tenantB", status)
check("tenant B independent", len(alerts3) == 3)

n = U.reset_alerts("tenantA")
check("reset_alerts(A) -> 1", n == 1)
n = U.reset_alerts("never")
check("reset_alerts(missing) -> 0", n == 0)

n = U.reset_alerts()
check("reset_alerts() clears others", n >= 1)

async def test_budget_no_pool():
    os.environ.pop("SUNNYWARE_PERSIST_USAGE", None)
    return await U.budget_status("tenantX")

s = asyncio.run(test_budget_no_pool())
check("budget_status has daily", "daily" in s)
check("budget_status has monthly", "monthly" in s)
check("budget_status daily.enabled", s["daily"]["enabled"] is True)
check("budget_status daily.cap 5.5", s["daily"]["cap_usd"] == 5.5)

async def test_rollup():
    return await U.rollup("tenantX", days=7, bucket="day")

r = asyncio.run(test_rollup())
check("rollup returns series key", "series" in r)
check("rollup empty ok", isinstance(r["series"], list))
check("rollup echoes bucket", r["bucket"] == "day")

r = asyncio.run(U.rollup("t", bucket="bogus"))
check("bad bucket -> day", r["bucket"] == "day")

for k in ("SUNNYWARE_BUDGET_USD_DAILY", "SUNNYWARE_BUDGET_USD_MONTHLY",
          "SUNNYWARE_BUDGET_ALERT_PCT"):
    os.environ.pop(k, None)

for fp in [SRC / "usage.py", SRC / "routes" / "meta.py"]:
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
