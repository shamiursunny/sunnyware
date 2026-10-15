# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 134 smoke test - per-tenant rate limiting."""
from pathlib import Path
import ast, os, sys, time

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 134: per-tenant rate limiting ===")

# 1. auth.py has new helpers
at = (SRC / "auth.py").read_text(encoding="utf-8")
check("auth.py has evict_stale", "def evict_stale" in at)
check("auth.py has reset_tenant", "def reset_tenant" in at)
check("auth.py has per_tenant_snapshot", "def per_tenant_snapshot" in at)
check("auth.py has tenant_status", "def tenant_status" in at)
check("auth.py still has check_rate_limit",
      "def check_rate_limit" in at)

# 2. main.py wires tenant discriminator
mt = (SRC / "main.py").read_text(encoding="utf-8")
check("main.py has Part 134 marker",
      "Part 134: richer tenant discriminator" in mt)
check("main.py calls evict_stale", "_auth.evict_stale()" in mt)
check("main.py uses x-session-id header",
      "x-session-id" in mt)
check("main.py uses x-forwarded-for header",
      "x-forwarded-for" in mt)
ANON = 'anonymous'
check("main.py has _eff_key fallback",
      ('_eff_key = "' + ANON + '"') in mt)

# 3. routes wired
rt = (SRC / "routes" / "meta.py").read_text(encoding="utf-8")
check("GET /api/rate_limit/status",
      '@router.get("/api/rate_limit/status")' in rt)
check("GET /api/rate_limit/tenants",
      '@router.get("/api/rate_limit/tenants")' in rt)
check("POST /api/rate_limit/reset",
      '@router.post("/api/rate_limit/reset")' in rt)
check("POST /api/rate_limit/evict",
      '@router.post("/api/rate_limit/evict")' in rt)

# 4. Functional tests
sys.path.insert(0, str(SRC.parent))
from sunnyware import auth as A

# Force-enable a small limit
os.environ["SUNNYWARE_RATE_LIMIT_PER_MINUTE"] = "5"
A.reset_rate_limits()
check("rate_limit_enabled with env=5", A.rate_limit_enabled())
check("rate_limit_per_minute == 5", A.rate_limit_per_minute() == 5)

# 5 requests OK, 6th blocked
tk = "test-tenant-1"
allowed = 0
blocked = 0
retry_after = None
for i in range(6):
    r = A.check_rate_limit(tk)
    if r["ok"]:
        allowed += 1
    else:
        blocked += 1
        retry_after = r.get("retry_after")
check("first 5 allowed", allowed == 5, f"n={allowed}")
check("6th blocked", blocked == 1)
check("retry_after is int",
      isinstance(retry_after, int) and retry_after > 0,
      f"retry_after={retry_after}")

# 6. Another tenant unaffected
r_other = A.check_rate_limit("test-tenant-2")
check("tenant-2 unaffected", r_other["ok"] is True)
check("tenant-2 remaining == 4", r_other["remaining"] == 4,
      f"rem={r_other['remaining']}")

# 7. tenant_status
st = A.tenant_status("test-tenant-1")
check("tenant_status used=5", st["used_in_window"] == 5,
      str(st["used_in_window"]))
check("tenant_status remaining=0", st["remaining_in_window"] == 0)
check("tenant_status enabled", st["rate_limit_enabled"] is True)

# 8. per_tenant_snapshot
snap = A.per_tenant_snapshot()
check("snapshot has test-tenant-1", "test-tenant-1" in snap)
check("snapshot has test-tenant-2", "test-tenant-2" in snap)

# 9. reset_tenant
ok = A.reset_tenant("test-tenant-1")
check("reset_tenant returns True", ok is True)
st2 = A.tenant_status("test-tenant-1")
check("after reset used=0", st2["used_in_window"] == 0)

# 10. reset_tenant on missing
ok2 = A.reset_tenant("never-seen")
check("reset_tenant missing -> False", ok2 is False)

# 11. reset_rate_limits clears everything
A.reset_rate_limits()
snap2 = A.per_tenant_snapshot()
check("reset_rate_limits clears all", len(snap2) == 0)

# 12. evict_stale - simulate old bucket
A.reset_rate_limits()
A.check_rate_limit("stale-tenant")
A._buckets["stale-tenant"].clear()
A._buckets["stale-tenant"].append(time.time() - 300)  # 5 min old
n = A.evict_stale()
check("evict_stale removes old bucket", n == 1, f"n={n}")
check("stale-tenant gone", "stale-tenant" not in A._buckets)

# 13. Disabled mode -> always ok
os.environ["SUNNYWARE_RATE_LIMIT_PER_MINUTE"] = "0"
A.reset_rate_limits()
r_dis = A.check_rate_limit("any")
check("disabled -> ok=True", r_dis["ok"] is True)
check("disabled -> limit=0", r_dis["limit"] == 0)
check("disabled -> remaining=-1", r_dis["remaining"] == -1)

# Restore env
os.environ["SUNNYWARE_RATE_LIMIT_PER_MINUTE"] = "60"

# 14. Files parse
for fp in [SRC / "auth.py", SRC / "main.py",
           SRC / "routes" / "meta.py"]:
    try:
        ast.parse(fp.read_text(encoding="utf-8"))
        check(f"{fp.name} parses", True)
    except SyntaxError as e:
        check(f"{fp.name} parses", False, str(e))

# 15. Part 134d: bypass path helpers
check("auth.py has is_bypass_path", "def is_bypass_path" in at)
check("auth.py has rate_limit_bypass_prefixes",
      "def rate_limit_bypass_prefixes" in at)
check("bypass: /api/rate_limit/status",
      A.is_bypass_path("/api/rate_limit/status") is True)
check("bypass: /api/rate_limit/tenants",
      A.is_bypass_path("/api/rate_limit/tenants") is True)
check("bypass: /api/rate_limit/reset",
      A.is_bypass_path("/api/rate_limit/reset") is True)
check("bypass: /api/rate_limit/evict",
      A.is_bypass_path("/api/rate_limit/evict") is True)
check("no bypass: /api/agent/run",
      A.is_bypass_path("/api/agent/run") is False)
check("no bypass: empty path",
      A.is_bypass_path("") is False)
check("bypass: prefix match /api/rate_limit/status/extra",
      A.is_bypass_path("/api/rate_limit/status/extra") is True)
check("main.py has Part 134d marker",
      "Part 134d: admin/status endpoints" in mt)
# env override
os.environ["SUNNYWARE_RATE_LIMIT_BYPASS"] = "/custom/path"
check("env override: /custom/path bypassed",
      A.is_bypass_path("/custom/path") is True)
check("env override: default path NOT bypassed",
      A.is_bypass_path("/api/rate_limit/status") is False)
check("env override: /custom/path/sub bypassed",
      A.is_bypass_path("/custom/path/sub") is True)
del os.environ["SUNNYWARE_RATE_LIMIT_BYPASS"]
check("default restored: /api/rate_limit/status bypassed",
      A.is_bypass_path("/api/rate_limit/status") is True)
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
