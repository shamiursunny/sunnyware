# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 103 smoke test - provider health metrics dashboard endpoint."""
from pathlib import Path
import ast, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 103: provider health metrics dashboard ===")

meta = (SRC / "routes" / "meta.py").read_text(encoding="utf-8")

# 1. Endpoint definition
check("route decorator present",
      '@router.get("/api/providers/metrics")' in meta)
check("handler function defined",
      "async def providers_metrics():" in meta)
check("Part 103 marker present", "Part 103:" in meta)

# 2. Aggregation pieces
check("imports providers module", "from .. import providers as _prov" in meta)
check("imports provider_limits module",
      "from .. import provider_limits as _pl" in meta)
check("imports metrics module", "from .. import metrics as _m" in meta)

# 3. Prefix-sum helper
check("_sum_prefix helper defined", "def _sum_prefix(prefix):" in meta)
check("aggregates llm_provider_attempt",
      '_sum_prefix("llm_provider_attempt")' in meta)
check("aggregates empty responses",
      '_sum_prefix("llm_provider_empty_response")' in meta)
check("aggregates learned limits",
      '_sum_prefix("provider_limit_learned")' in meta)
check("aggregates retries",
      '_sum_prefix("llm_request_retried")' in meta)

# 4. Response shape
check("summary block present", '"summary":' in meta and "total_providers" in meta)
check("providers list present", '"providers": rows' in meta)
check("storage block present", '"storage":' in meta)
check("session stats per provider", '"session": {' in meta)
check("lifetime stats per provider", '"lifetime": {' in meta)
check("learned_limit per provider", '"learned_limit": learned.get(p.name)' in meta)
check("timestamp included", '"timestamp": _t.time()' in meta)

# 5. Summary fields
for key in ["ready", "cooling", "session_success_total",
            "session_fail_total", "session_success_rate",
            "lifetime_attempts_total", "lifetime_empty_total",
            "lifetime_learned_total", "retries_total"]:
    check(f"summary has '{key}'", f'"{key}"' in meta)

# 6. Error handling
check("wrapped in try/except", "except Exception as e:" in meta)
check("returns JSONResponse on error", "JSONResponse(" in meta)

# 7. Existing endpoints still intact
check("existing /api/providers/status still present",
      '@router.get("/api/providers/status")' in meta)
check("existing /api/providers/limits still present",
      '@router.get("/api/providers/limits")' in meta)

# 8. File parses
try:
    ast.parse(meta)
    check("meta.py parses", True)
except SyntaxError as e:
    check("meta.py parses", False, str(e))

# 9. Route count sanity
tree = ast.parse(meta)
top_level_async = [n for n in tree.body
                   if isinstance(n, ast.AsyncFunctionDef)]
check("meta.py has >= 15 async routes",
      len(top_level_async) >= 15,
      f"{len(top_level_async)} found")

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
