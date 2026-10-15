# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 113D smoke test - insurance data sources (Socrata state DOI)."""
from pathlib import Path
import ast, asyncio, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 113D: insurance data sources ===")

# 1. File exists + parses
f = SRC / "tools" / "insurance_data.py"
check("insurance_data.py exists", f.exists())
try:
    ast.parse(f.read_text(encoding="utf-8"))
    check("insurance_data.py parses", True)
except SyntaxError as e:
    check("insurance_data.py parses", False, str(e))

# 2. Registry wiring
init = (SRC / "tools" / "__init__.py").read_text(encoding="utf-8")
check("tools/__init__.py imports InsuranceDataTool",
      "from .insurance_data import InsuranceDataTool" in init)
check("tools/__init__.py registers in _TOOLS",
      "InsuranceDataTool.name: InsuranceDataTool()" in init)

# 3. Tool appears in list_tools
sys.path.insert(0, str(SRC.parent))
from sunnyware import tools as tools_registry
names = tools_registry.tool_names()
check("insurance_data in tool registry", "insurance_data" in names)
check("registry size >= 68 (was 67)", len(names) >= 68, f"n={len(names)}")

# 4. Class API surface
from sunnyware.tools.insurance_data import InsuranceDataTool
inst = InsuranceDataTool()
check("name == insurance_data", inst.name == "insurance_data")
check("description mentions Socrata", "Socrata" in inst.description)
check("parameters has action + state + query + dataset_id + limit",
      {"action", "state", "query", "dataset_id", "limit"} <= set(inst.parameters))

# 5. Live-ish behavior (no network needed for these)
async def probe():
    r1 = await inst.run({})                                    # no action
    r2 = await inst.run({"action": "bogus"})                   # unknown
    r3 = await inst.run({"action": "states"})                  # catalog
    r4 = await inst.run({"action": "discover", "state": "XX"}) # unknown state
    r5 = await inst.run({"action": "fetch", "state": "TX"})    # missing dataset_id
    r6 = await inst.run({"action": "inspect", "state": "TX"})  # missing dataset_id
    return r1, r2, r3, r4, r5, r6

r1, r2, r3, r4, r5, r6 = asyncio.run(probe())
check("no action -> error", "error" in r1)
check("unknown action -> error", "error" in r2 and "available" in r2)
check("states -> returns 8 portals",
      isinstance(r3.get("states"), list) and len(r3["states"]) == 8)
check("states includes TX + NY",
      {s["code"] for s in r3["states"]} >= {"TX", "NY"})
check("unknown state -> error with available",
      "error" in r4 and "available" in r4)
check("fetch without dataset_id -> error", "error" in r5)
check("inspect without dataset_id -> error", "error" in r6)

# 6. roles.py — actuary has insurance_ prefix + prompt mention
rt = (SRC / "roles.py").read_text(encoding="utf-8")
check("actuary tool_prefixes has insurance_",
      '"edgar_", "fred_", "insurance_"' in rt)
check("actuary addon mentions insurance_data",
      "insurance_data for US state DOI datasets" in rt)

# 7. active_tool_names includes insurance_data for actuary
from sunnyware import roles as _roles
actuary_tools = _roles.active_tool_names("actuary") or []
check("actuary active tools include insurance_data",
      "insurance_data" in actuary_tools)
check("actuary subset still < 67 (proper filtering)",
      len(actuary_tools) < 67, f"n={len(actuary_tools)}")

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
