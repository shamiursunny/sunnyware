# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 118 smoke test - govcon_data tool (USAspending v2, keyless)."""
from pathlib import Path
import ast, asyncio, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 118: govcon_data tool ===")

# 1. File exists + parses
f = SRC / "tools" / "govcon_data.py"
check("govcon_data.py exists", f.exists())
try:
    ast.parse(f.read_text(encoding="utf-8"))
    check("govcon_data.py parses", True)
except SyntaxError as e:
    check("govcon_data.py parses", False, str(e))

# 2. Registration
init = (SRC / "tools" / "__init__.py").read_text(encoding="utf-8")
check("tools/__init__.py imports GovconDataTool",
      "from .govcon_data import GovconDataTool" in init)
check("tools/__init__.py registers GovconDataTool",
      "GovconDataTool.name: GovconDataTool()" in init)

# 3. Registry
sys.path.insert(0, str(SRC.parent))
from sunnyware import tools as tools_registry
names = tools_registry.tool_names()
check("govcon_data in tool registry", "govcon_data" in names)
check("registry size >= 71", len(names) >= 71, f"n={len(names)}")

# 4. Class API surface
from sunnyware.tools.govcon_data import GovconDataTool
inst = GovconDataTool()
check("name == govcon_data", inst.name == "govcon_data")
check("description mentions USAspending", "USAspending" in inst.description)
check("description mentions NAICS 524126",
      "524126" in inst.description)
check("parameters have action+keyword+naics+state+category",
      {"action", "keyword", "naics", "state", "category"} <= set(inst.parameters))

# 5. Behavior tests (no network)
async def probe():
    r1 = await inst.run({})
    r2 = await inst.run({"action": "bogus"})
    r3 = await inst.run({"action": "award_search"})   # no filters
    r4 = await inst.run({"action": "recipient_search"})  # no keyword
    r5 = await inst.run({"action": "spending_by_category",
                         "category": "bogus"})
    return r1, r2, r3, r4, r5

r1, r2, r3, r4, r5 = asyncio.run(probe())
check("no action -> error", "error" in r1)
check("unknown action -> error + available",
      "error" in r2 and "available" in r2)
check("award_search w/o filters -> error", "error" in r3)
check("recipient_search w/o keyword -> error", "error" in r4)
check("spending_by_category bogus category -> error + available",
      "error" in r5 and "available" in r5)

# 6. roles.py wiring
rt = (SRC / "roles.py").read_text(encoding="utf-8")
check("roles.py has govcon_data", '"govcon_data"' in rt)

from sunnyware import roles as _roles
cfo = _roles.active_tool_names("cfo") or []
check("govcon_data in cfo subset", "govcon_data" in cfo)

# 7. Files parse
for fp in [SRC / "tools" / "govcon_data.py",
           SRC / "tools" / "__init__.py",
           SRC / "roles.py"]:
    try:
        ast.parse(fp.read_text(encoding="utf-8"))
        check(f"{fp.name} parses", True)
    except SyntaxError as e:
        check(f"{fp.name} parses", False, str(e))

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
