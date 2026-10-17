# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 172 smoke - per-tool health + versions cards."""
from pathlib import Path
import ast, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" +
          (f"  ({detail})" if detail else ""))

print("=== Part 172: per-tool health + versions ===")

# ─── tools_health.py module ───
tp = SRC / "tools_health.py"
check("tools_health.py exists", tp.exists())
tt = tp.read_text(encoding="utf-8") if tp.exists() else ""
for fn in ("def snapshot(", "def get_tool_health(",
           "def _tool_health(", "def _get_all_tools("):
    check(f"has {fn}", fn in tt)
check("uses circuit_breaker", "circuit_breaker as cb" in tt)
check("composite status has all 5",
      all(s in tt for s in ("broken", "degraded",
                            "working", "never_used")))

# ─── meta.py wiring ───
mt = (SRC / "routes" / "meta.py").read_text(encoding="utf-8")
check("meta.py: tools_health_snapshot helper",
      "async def tools_health_snapshot(" in mt)
check("meta.py: summary wires tools_health",
      'await _safe("tools_health", tools_health_snapshot)' in mt)
check("meta.py: github_ci_status returns successful",
      '"successful": successful' in mt)
check("meta.py: github_ci_status returns current_version",
      '"current_version": current_version' in mt)
check("meta.py: fetches per_page=10",
      'actions/runs?per_page=10' in mt)

# ─── status.html ───
html = (ROOT / "static" / "status.html").read_text(encoding="utf-8")
check("status.html: tools card in CARDS",
      'id:"tools"' in html and 'key:"tools_health"' in html)
check("status.html: versions card in CARDS",
      'id:"versions"' in html and 'key:"ci"' in html)
check("status.html: renderToolsHealth defined",
      "function renderToolsHealth(" in html)
check("status.html: renderVersions defined",
      "function renderVersions(" in html)
check("versions renderer reads successful",
      "d.successful" in html)
check("versions renderer shows current_version",
      "current_version" in html)
check("versions renderer shows rollback hint",
      "rollback:" in html or "git revert" in html)

# ─── Functional test ───
sys.path.insert(0, str(SRC.parent))
try:
    from sunnyware import tools_health as TH
    snap = TH.snapshot()
    check("snapshot returns dict", isinstance(snap, dict))
    check("has summary", "summary" in snap)
    check("has tools", "tools" in snap)
    check("has groups", "groups" in snap)
    s = snap.get("summary", {})
    state_sum = (s.get("working", 0) + s.get("degraded", 0)
                 + s.get("broken", 0) + s.get("never_used", 0))
    check("states sum to total",
          state_sum == s.get("total", 0),
          f"{state_sum} vs {s.get('total')}")
    tools = snap.get("tools", [])
    if tools:
        all_have = all(
            all(k in t for k in ("name", "status", "reason", "category"))
            for t in tools
        )
        check("all tools have required keys", all_have)
        check("get_tool_health works",
              TH.get_tool_health(tools[0]["name"]) is not None)
        check("total matches tool count",
              s.get("total") == len(tools))
except Exception as e:
    check("snapshot executes cleanly", False, str(e))

# ─── Files parse ───
for fp in [tp, SRC / "routes" / "meta.py"]:
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
