# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 113C smoke test - per-action cache TTL + cache diagnostics."""
from pathlib import Path
import ast, sys, time

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 113C: per-action cache TTL + diagnostics ===")

sys.path.insert(0, str(SRC.parent))

# 1. _financial_http.py — cache_stats + cache_clear exist
from sunnyware.tools import _financial_http as fh
check("cache_stats exists", callable(getattr(fh, "cache_stats", None)))
check("cache_clear exists", callable(getattr(fh, "cache_clear", None)))

# 2. cache round-trip via helpers
fh.cache_clear()
check("cache_clear returns int", isinstance(fh.cache_clear(), int))
fh.cache_set("test:key", {"v": 42}, ttl=10.0)
check("cache_get returns stored value", fh.cache_get("test:key") == {"v": 42})
fh.cache_set("test:expired", {"v": 1}, ttl=-1.0)
check("cache_get drops expired", fh.cache_get("test:expired") is None)
stats = fh.cache_stats()
check("cache_stats shape", isinstance(stats, dict) and "total_keys" in stats
      and "live_keys" in stats and "expired_keys" in stats)
check("cache_stats live_keys >= 1", stats["live_keys"] >= 1)

# 3. eulerpool_data — per-action TTL table
sys.path.insert(0, str(SRC.parent))
import importlib
ed = importlib.import_module("sunnyware.tools.eulerpool_data")
check("_ttl_for exists", callable(getattr(ed, "_ttl_for", None)))
check("options_greeks -> 60s", ed._ttl_for("options_greeks") == 60.0)
check("options_chain  -> 60s", ed._ttl_for("options_chain") == 60.0)
check("profile        -> 24h", ed._ttl_for("profile") == 86400.0)
check("candles        -> 300s", ed._ttl_for("candles") == 300.0)
check("unknown action -> default (3600)",
      ed._ttl_for("totally_unknown_action") == ed._TTL)

# 4. Metrics counters wired
et = (SRC / "tools" / "eulerpool_data.py").read_text(encoding="utf-8")
check("hit metric present", 'eulerpool_cache_hit' in et)
check("miss metric present", 'eulerpool_cache_miss' in et)
check("api call counter present", 'eulerpool_api_calls_total' in et)
check("cache_set uses _ttl_for", "cache_set(ck, out, _ttl_for(action))" in et)

# 5. Routes endpoint
mt = (SRC / "routes" / "meta.py").read_text(encoding="utf-8")
check("GET /api/cache/stats route exists",
      '@router.get("/api/cache/stats")' in mt)
check("POST /api/cache/clear route exists",
      '@router.post("/api/cache/clear")' in mt)
check("stats endpoint reads cache_stats",
      "_fh.cache_stats()" in mt)
check("stats endpoint reads metrics",
      "_m.snapshot()" in mt)

# 6. Files parse
for f in [SRC / "tools" / "_financial_http.py",
          SRC / "tools" / "eulerpool_data.py",
          SRC / "routes" / "meta.py"]:
    try:
        ast.parse(f.read_text(encoding="utf-8"))
        check(f"{f.name} parses", True)
    except SyntaxError as e:
        check(f"{f.name} parses", False, str(e))

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
