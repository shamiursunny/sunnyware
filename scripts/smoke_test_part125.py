# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 125 smoke test - research_search (edgar+fred+govcon)."""
from pathlib import Path
import ast, asyncio, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 125: multi-source research_search ===")

f = SRC / "tools" / "research_search.py"
check("research_search.py exists", f.exists())
try:
    ast.parse(f.read_text(encoding="utf-8"))
    check("research_search.py parses", True)
except SyntaxError as e:
    check("research_search.py parses", False, str(e))

init = (SRC / "tools" / "__init__.py").read_text(encoding="utf-8")
check("__init__ imports ResearchSearchTool",
      "from .research_search import ResearchSearchTool" in init)
check("__init__ registers ResearchSearchTool",
      "ResearchSearchTool.name: ResearchSearchTool()" in init)

sys.path.insert(0, str(SRC.parent))
from sunnyware import tools as tools_registry
names = tools_registry.tool_names()
check("research_search in registry", "research_search" in names)
check("registry size >= 75", len(names) >= 75, f"n={len(names)}")

from sunnyware.tools.research_search import ResearchSearchTool
inst = ResearchSearchTool()
check("name == research_search", inst.name == "research_search")
check("description mentions edgar/fred/govcon",
      "edgar" in inst.description.lower() and "fred" in inst.description.lower())
check("parameters have query + sources + limit",
      {"query", "sources", "limit"} <= set(inst.parameters))

# Behavior tests (no network for validation-only cases)
async def probe():
    r1 = await inst.run({})
    r2 = await inst.run({"query": "x", "sources": "bad"})
    r3 = await inst.run({"query": "x", "sources": "edgar,fred,bogus"})
    return r1, r2, r3

r1, r2, r3 = asyncio.run(probe())
check("no query -> error", "error" in r1)
check("bad sources -> error + available",
      "error" in r2 and "available" in r2)
check("mixed valid/invalid -> error",
      "error" in r3 and "bogus" in r3["error"])

# Roles
rt = (SRC / "roles.py").read_text(encoding="utf-8")
check("roles.py mentions research_search", '"research_search"' in rt)

from sunnyware import roles as _roles
actuary = _roles.active_tool_names("actuary") or []
cfo = _roles.active_tool_names("cfo") or []
check("research_search in actuary subset",
      "research_search" in actuary)
check("research_search in cfo subset",
      "research_search" in cfo)

for fp in [SRC / "tools" / "research_search.py",
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
