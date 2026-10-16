# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 163 smoke - unified status dashboard."""
from pathlib import Path
import ast, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 163: unified status dashboard ===")

hp = ROOT / "static" / "status.html"
check("static/status.html exists", hp.exists())
html = hp.read_text(encoding="utf-8") if hp.exists() else ""

check("has doctype", "<!doctype html>" in html.lower())
check("has <title>", "<title>" in html)
check("has viewport meta", 'name="viewport"' in html)
check("has auto-refresh setInterval", "setInterval" in html)
check("has refresh button", 'id="refresh-now"' in html)
check("has overall health badge", 'id="badge-health"' in html)
check("no jQuery/CDN hostnames",
      "cdn." not in html and "googleapis" not in html
      and "unpkg" not in html and "jsdelivr" not in html)

endpoints = [
    "/health/ready",
    "/api/usage/budget",
    "/api/golden/latest",
    "/api/evals/trends",
    "/api/tools/circuits",
    "/api/recon/stats",
    "/api/audit/verify",
]
for ep in endpoints:
    check(f"refs {ep}", ep in html)

for fn in ["renderHealth", "renderBudget", "renderGolden", "renderEvals",
           "renderCircuits", "renderRecon", "renderAudit",
           "renderProviders"]:
    check(f"has {fn}", fn in html)

check("no JS backtick templates", "`" not in html)

mt = (SRC / "routes" / "meta.py").read_text(encoding="utf-8")
check("meta.py has /status route", '"/status"' in mt)
check("meta.py imports HTMLResponse", "HTMLResponse" in mt)

check("html size reasonable (>=5KB, <=80KB)",
      5_000 <= len(html) <= 80_000,
      f"{len(html)} bytes")

try:
    ast.parse(mt)
    check("meta.py parses", True)
except SyntaxError as e:
    check("meta.py parses", False, str(e))

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
