# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 124 smoke test - auto-narrative from tables."""
from pathlib import Path
import ast, asyncio, json, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 124: auto-narrative from tables ===")

f = SRC / "tools" / "narrate_table.py"
check("narrate_table.py exists", f.exists())
try:
    ast.parse(f.read_text(encoding="utf-8"))
    check("narrate_table.py parses", True)
except SyntaxError as e:
    check("narrate_table.py parses", False, str(e))

init = (SRC / "tools" / "__init__.py").read_text(encoding="utf-8")
check("__init__ imports NarrateTableTool",
      "from .narrate_table import NarrateTableTool" in init)
check("__init__ registers NarrateTableTool",
      "NarrateTableTool.name: NarrateTableTool()" in init)

sys.path.insert(0, str(SRC.parent))
from sunnyware import tools as tools_registry
names = tools_registry.tool_names()
check("narrate_table in registry", "narrate_table" in names)
check("registry size >= 74", len(names) >= 74, f"n={len(names)}")

from sunnyware.tools.narrate_table import NarrateTableTool, build_narrative
inst = NarrateTableTool()
check("name == narrate_table", inst.name == "narrate_table")
check("description mentions LLM-free",
      "deterministic" in inst.description.lower()
      or "no llm" in inst.description.lower())
check("parameters have rows + title",
      {"rows", "title"} <= set(inst.parameters))

# Direct call — basic table
rows = [
    {"region": "US",  "premium": 100, "year": 2022},
    {"region": "US",  "premium": 120, "year": 2023},
    {"region": "EU",  "premium": 80,  "year": 2022},
    {"region": "EU",  "premium": 110, "year": 2023},
    {"region": "APAC","premium": 50,  "year": 2022},
    {"region": "APAC","premium": 70,  "year": 2023},
]
nar, summ = build_narrative(rows, title="Insurance Premiums")
check("narrative is non-empty", isinstance(nar, str) and len(nar) > 30)
check("narrative mentions row count", "6 rows" in nar)
check("narrative mentions premium column", "premium" in nar)
check("narrative mentions sum",
      "sum=530" in nar or "sum=530.00" in nar)
check("narrative mentions trend (down)",
      "trending down" in nar)
check("narrative mentions region categorical",
      "region" in nar and "US" in nar)
check("summary has row_count", summ.get("row_count") == 6)
check("summary has columns list",
      isinstance(summ.get("columns"), list) and len(summ["columns"]) == 3)
check("summary numeric_summary has premium",
      "premium" in summ.get("numeric_summary", {}))
check("summary categorical_summary has region",
      "region" in summ.get("categorical_summary", {}))

# Behavior via tool
async def probe():
    r1 = await inst.run({})
    r2 = await inst.run({"rows": "not json"})
    r3 = await inst.run({"rows": {"not": "list"}})
    r4 = await inst.run({"rows": json.dumps(rows), "title": "T"})
    r5 = await inst.run({"rows": json.dumps([])})
    return r1, r2, r3, r4, r5

r1, r2, r3, r4, r5 = asyncio.run(probe())
check("missing rows -> error", "error" in r1)
check("bad json -> error", "error" in r2 and "valid JSON" in r2["error"])
check("non-list rows -> error",
      "error" in r3 and "array of objects" in r3["error"])
check("valid rows -> narrative",
      "narrative" in r4 and "T" in r4["narrative"])
check("empty list -> graceful",
      "narrative" in r5 and "No rows" in r5["narrative"])

# All-numeric edge case
nums_only = [{"x": 1, "y": 10}, {"x": 2, "y": 20}, {"x": 3, "y": 30}]
n2, s2 = build_narrative(nums_only, title="Numbers")
check("all-numeric works", "Numeric columns" in n2)

# Empty rows
n3, s3 = build_narrative([])
check("empty rows -> no data", "No rows" in n3 and s3.get("row_count") == 0)

# Files parse
for fp in [SRC / "tools" / "narrate_table.py",
           SRC / "tools" / "__init__.py"]:
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
