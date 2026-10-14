# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 104 smoke test - WebUI provider health panel."""
from pathlib import Path
import ast, sys

ROOT = Path(__file__).resolve().parent.parent
WUI = ROOT / "src" / "sunnyware" / "webui.py"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 104: WebUI provider health panel ===")

wui = WUI.read_text(encoding="utf-8")

# 1. Modal title updated
check("modal title updated",
      "Stats &amp; Provider Health" in wui)

# 2. renderProviderHealth function
check("renderProviderHealth() defined",
      "function renderProviderHealth(metrics)" in wui)
check("creates providerHealthSection id",
      "sec.id = 'providerHealthSection'" in wui)
check("has 'Provider Health' title",
      "h.textContent = 'Provider Health'" in wui)
check("renders summary line",
      "providers | " in wui and "cooling | session rate" in wui)
check("renders providers table",
      "tbl.className = 'ph-table'" in wui)
check("table has Provider/Model/Status/Rate columns",
      "'Provider', 'Model', 'Status', 'Rate'" in wui)
check("dot element for cooling/ready",
      ".ph-dot " in wui and "p.cooling ? 'cooling' : 'ready'" in wui)
check("shows storage path_source",
      "st.path_source" in wui)
check("shows learned limits",
      "learned: " in wui and "Object.keys(learned)" in wui)
check("shows lifetime counters",
      "Lifetime: " in wui and "attempts | " in wui)

# 3. openUsageModal fetches metrics
check("openUsageModal fetches /api/providers/metrics",
      "fetch('/api/providers/metrics')" in wui)
check("inserts PH section at top of body",
      "body.insertBefore(ph, body.firstChild)" in wui)

# 4. Auto-refresh
check("auto-refresh timer var",
      "var _phRefreshTimer = null" in wui)
check("_startPHRefresh defined",
      "function _startPHRefresh()" in wui)
check("_stopPHRefresh defined",
      "function _stopPHRefresh()" in wui)
check("refresh interval 10000ms",
      "}, 10000);" in wui)
check("closeUsageModal stops timer",
      "_stopPHRefresh();" in wui)
check("skips refresh when modal closed",
      "m.style.display === 'none'" in wui)

# 5. CSS
for cls in [".ph-section", ".ph-title", ".ph-summary", ".ph-table",
            ".ph-table th", ".ph-table td", ".ph-dot", ".ph-dot.ready",
            ".ph-dot.cooling", ".ph-foot", ".ph-empty"]:
    check(f"CSS has '{cls}'", cls in wui)

# 6. Existing functionality preserved
check("existing /api/usage still fetched",
      "fetch('/api/usage')" in wui)
check("existing /api/usage/pricing still fetched",
      "fetch('/api/usage/pricing')" in wui)
check("renderUsageDashboard still called",
      "renderUsageDashboard(usage, pricing)" in wui)
check("existing usageClose button present",
      'id="usageClose"' in wui)
check("existing usageBody id present",
      'id="usageBody"' in wui)

# 7. File parses
try:
    ast.parse(wui)
    check("webui.py parses", True)
except SyntaxError as e:
    check("webui.py parses", False, str(e))

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
