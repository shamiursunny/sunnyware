# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 138 smoke test - cost attribution admin surface."""
from pathlib import Path
import ast, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 138: cost attribution admin surface ===")

ut = (SRC / "usage.py").read_text(encoding="utf-8")
mt = (SRC / "routes" / "meta.py").read_text(encoding="utf-8")

check("usage.py has gemini-2.0-flash", "gemini-2.0-flash" in ut)
check("usage.py has gemini-1.5-pro", "gemini-1.5-pro" in ut)
check("_get_tenant falls back", "get_rate_limit_key" in ut)
check("has all_tenants_summary", "async def all_tenants_summary" in ut)
check("has trends", "async def trends" in ut)
check("has reset", "async def reset" in ut)
check("has export_rows", "async def export_rows" in ut)

check("GET /api/usage/all", '"/api/usage/all"' in mt)
check("GET /api/usage/tenant/{key}",
      '"/api/usage/tenant/{tenant_key}"' in mt)
check("GET /api/usage/trends", '"/api/usage/trends"' in mt)
check("POST /api/usage/reset", '"/api/usage/reset"' in mt)
check("GET /api/usage/export.csv", '"/api/usage/export.csv"' in mt)
check("admin guard used >= 5 times",
      mt.count("_check_admin()") >= 5,
      f"count={mt.count('_check_admin()')}")

for fp in [SRC / "usage.py", SRC / "routes" / "meta.py"]:
    try:
        ast.parse(fp.read_text(encoding="utf-8"))
        check(f"{fp.name} parses", True)
    except SyntaxError as e:
        check(f"{fp.name} parses", False, str(e))

passed = sum(1 for _, ok, _ in checks if ok)
total = len(checks)
print(f"\n{passed}/{total} checks passed")
if passed < total:
    for name, ok, detail in checks:
        if not ok:
            print(f"  - {name} {detail}")
    sys.exit(1)
print("ALL PASS")
