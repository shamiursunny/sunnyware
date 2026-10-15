# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 117 smoke test - insurance_research tool (EDGAR + FRED)."""
from pathlib import Path
import ast, asyncio, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 117: insurance_research tool ===")

# 1. File exists + parses
f = SRC / "tools" / "insurance_research.py"
check("insurance_research.py exists", f.exists())
try:
    ast.parse(f.read_text(encoding="utf-8"))
    check("insurance_research.py parses", True)
except SyntaxError as e:
    check("insurance_research.py parses", False, str(e))

# 2. Registration
init = (SRC / "tools" / "__init__.py").read_text(encoding="utf-8")
check("tools/__init__.py imports InsuranceResearchTool",
      "from .insurance_research import InsuranceResearchTool" in init)
check("tools/__init__.py registers in _TOOLS",
      "InsuranceResearchTool.name: InsuranceResearchTool()" in init)

# 3. Tool appears in registry
sys.path.insert(0, str(SRC.parent))
from sunnyware import tools as tools_registry
names = tools_registry.tool_names()
check("insurance_research in tool registry",
      "insurance_research" in names)
check("registry size >= 70", len(names) >= 70, f"n={len(names)}")

# 4. Class API surface
from sunnyware.tools.insurance_research import InsuranceResearchTool
inst = InsuranceResearchTool()
check("name == insurance_research", inst.name == "insurance_research")
check("description mentions EDGAR", "EDGAR" in inst.description)
check("description mentions FRED",  "FRED"  in inst.description)
check("parameters have action+query+forms+cik+series_id",
      {"action", "query", "forms", "cik", "series_id"} <= set(inst.parameters))

# 5. Behavior tests (no network)
async def probe():
    r1 = await inst.run({})
    r2 = await inst.run({"action": "bogus"})
    r3 = await inst.run({"action": "search_filings"})
    r4 = await inst.run({"action": "company_filings"})
    r5 = await inst.run({"action": "company_filings", "cik": "abc"})
    r6 = await inst.run({"action": "fred_search"})
    r7 = await inst.run({"action": "fred_series"})
    return r1, r2, r3, r4, r5, r6, r7

r1, r2, r3, r4, r5, r6, r7 = asyncio.run(probe())
check("no action -> error", "error" in r1)
check("unknown action -> error+available", "error" in r2 and "available" in r2)
check("search_filings w/o query -> error", "error" in r3)
check("company_filings w/o cik -> error", "error" in r4)
check("company_filings w/ non-digit cik -> error", "error" in r5)
check("fred_search w/o query -> error", "error" in r6)
check("fred_series w/o series_id -> error", "error" in r7)

# 6. roles.py actuary has insurance_research
rt = (SRC / "roles.py").read_text(encoding="utf-8")
check("actuary tool_prefixes has insurance_research",
      '"insurance_research"' in rt)

from sunnyware import roles as _roles
actuary_tools = _roles.active_tool_names("actuary") or []
check("actuary active tools include insurance_research",
      "insurance_research" in actuary_tools)
check("actuary subset still < 67", len(actuary_tools) < 67, f"n={len(actuary_tools)}")

# 7. Files parse
for fp in [SRC / "tools" / "insurance_research.py",
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
