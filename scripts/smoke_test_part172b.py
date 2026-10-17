# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 172b smoke - tools page + health endpoint."""
from pathlib import Path
import ast, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" +
          (f"  ({detail})" if detail else ""))

print("=== Part 172b: tools page + health endpoint ===")

tp = ROOT / "static" / "tools.html"
check("tools.html exists", tp.exists())
th = tp.read_text(encoding="utf-8") if tp.exists() else ""
check("has renderGroup", "function renderGroup(" in th)
check("has render", "function render(" in th)
check("has poll", "async function poll(" in th)
check("has filter buttons", 'data-filter="broken"' in th)
check("has search box", 'id="search"' in th)
check("has back to status", 'href="/status"' in th)
check("fetches /api/tools/health", "/api/tools/health" in th)
check("has category grouping", "byCat" in th)
check("has expand details", "detail" in th and "expanded" in th)
check("no CDN", "cdn." not in th and "googleapis" not in th)

mt = (SRC / "routes" / "meta.py").read_text(encoding="utf-8")
check("meta.py: /api/tools/health endpoint", '"/api/tools/health"' in mt)
check("meta.py: /tools HTML route",
      '@router.get("/tools", response_class=HTMLResponse)' in mt)
check("meta.py: /tools serves tools.html", '"tools.html"' in mt)

sh = (ROOT / "static" / "status.html").read_text(encoding="utf-8")
check("status.html: renders total tools as headline",
      'big.textContent = String(total)' in sh)
check("status.html: subtext tools registered",
      "tools registered" in sh)
check("status.html: subtext calls this session",
      "calls this session" in sh)

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
