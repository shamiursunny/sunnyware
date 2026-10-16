# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 165 smoke - Neon DB + CI/CD status cards."""
from pathlib import Path
import ast, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" +
          (f"  ({detail})" if detail else ""))

print("=== Part 165: Neon + CI/CD status cards ===")

mt = (SRC / "routes" / "meta.py").read_text(encoding="utf-8")
check("meta.py: neon_health defined", "async def neon_health(" in mt)
check("meta.py: github_ci_status defined", "async def github_ci_status(" in mt)
check("meta.py: _dur_s helper", "def _dur_s(" in mt)
check("meta.py: _CI_CACHE present", "_CI_CACHE" in mt)
check("meta.py: summary wires neon", 'await _safe("neon", neon_health)' in mt)
check("meta.py: summary wires ci", 'await _safe("ci", github_ci_status)' in mt)
check("meta.py: hits correct repo",
      "shamiursunny/sunnyware" in mt and "actions/runs" in mt)
check("meta.py: caches GitHub responses", "90" in mt and "_CI_CACHE" in mt)

html = (ROOT / "static" / "status.html").read_text(encoding="utf-8")
check("status.html: neon card", 'id:"neon"' in html and 'key:"neon"' in html)
check("status.html: ci card", 'id:"ci"' in html and 'key:"ci"' in html)
check("status.html: renderNeon defined", "function renderNeon(" in html)
check("status.html: renderCI defined", "function renderCI(" in html)
check("status.html: neon card renders status badge",
      "renderNeon" in html and "latency_ms" in html)
check("status.html: ci card renders runs table",
      "runs.forEach" in html and "duration_s" in html)
check("status.html: no CDN introduced",
      "cdn." not in html and "googleapis" not in html
      and "unpkg" not in html and "jsdelivr" not in html)

for fp in [SRC / "routes" / "meta.py"]:
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
