# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 128 smoke test - contract clause extractor."""
from pathlib import Path
import ast, asyncio, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 128: contract clause extractor ===")

f = SRC / "tools" / "clause_extractor.py"
check("clause_extractor.py exists", f.exists())
try:
    ast.parse(f.read_text(encoding="utf-8"))
    check("clause_extractor.py parses", True)
except SyntaxError as e:
    check("clause_extractor.py parses", False, str(e))

init = (SRC / "tools" / "__init__.py").read_text(encoding="utf-8")
check("__init__ imports ClauseExtractorTool",
      "from .clause_extractor import ClauseExtractorTool" in init)
check("__init__ registers ClauseExtractorTool",
      "ClauseExtractorTool.name: ClauseExtractorTool()" in init)

sys.path.insert(0, str(SRC.parent))
from sunnyware import tools as tools_registry
names = tools_registry.tool_names()
check("clause_extractor in registry", "clause_extractor" in names)
check("registry size >= 78", len(names) >= 78, f"n={len(names)}")

from sunnyware.tools.clause_extractor import (
    ClauseExtractorTool, extract_clauses, list_clause_types,
)
inst = ClauseExtractorTool()
check("name == clause_extractor", inst.name == "clause_extractor")
check("description mentions clause",
      "clause" in inst.description.lower())
check("parameters include text + clause_types + min_score",
      {"text", "clause_types", "min_score"} <= set(inst.parameters))

# Realistic contract text
contract = (
    "Either party may terminate this Agreement upon 30 days written "
    "notice to the other party. "
    "The Company shall indemnify and hold harmless the Client against "
    "any and all claims arising from the Services. "
    "In no event shall the Company's aggregate liability exceed the "
    "total fees paid in the preceding twelve months. "
    "This Agreement shall be governed by the laws of the State of "
    "Delaware, and the parties consent to the exclusive jurisdiction "
    "of the courts located there. "
    "Client shall pay all invoices within net 30 days of receipt. "
    "The Company warrants that the Services will be performed in a "
    "professional manner. "
    "Neither party shall be liable for delays caused by force majeure "
    "events beyond reasonable control. "
    "Neither party may assign this Agreement without prior written "
    "consent of the other party. "
    "All Confidential Information disclosed under this Agreement "
    "shall remain the property of the disclosing party."
)

r = extract_clauses(contract)
check("extract returned clauses", "clauses" in r and r["clause_count"] >= 5)
types_seen = set(r.get("by_type", {}).keys())
check("termination detected", "termination" in types_seen)
check("indemnification detected", "indemnification" in types_seen)
check("liability detected", "liability" in types_seen)
check("governing_law detected", "governing_law" in types_seen)
check("payment_terms detected", "payment_terms" in types_seen)
check("warranties detected", "warranties" in types_seen)
check("force_majeure detected", "force_majeure" in types_seen)
check("assignment detected", "assignment" in types_seen)
check("confidentiality detected", "confidentiality" in types_seen)
check("each clause has type+text+score+keywords",
      all(("type" in c and "text" in c and "score" in c
           and "keywords_matched" in c) for c in r["clauses"]))
check("each clause has char_start+char_end",
      all(isinstance(c.get("char_start"), int)
          and isinstance(c.get("char_end"), int)
          for c in r["clauses"]))
check("char positions are within input",
      all(0 <= c["char_start"] < len(contract)
          and 0 < c["char_end"] <= len(contract)
          for c in r["clauses"]))

# Filtering
r2 = extract_clauses(contract, clause_types="termination,governing_law")
types2 = set((r2.get("by_type") or {}).keys())
check("filter restricts types",
      types2 <= {"termination", "governing_law"})

# min_score
r3 = extract_clauses(contract, min_score=2)
check("min_score=2 reduces clause count",
      r3.get("clause_count", 0) <= r.get("clause_count", 0))

# Unknown type
r4 = extract_clauses(contract, clause_types="bogus")
check("unknown clause type -> error + available",
      "error" in r4 and "available" in r4)

check("list_clause_types returns >= 10",
      len(list_clause_types()) >= 10)

# Behavior via tool
async def probe():
    r1 = await inst.run({})
    r2 = await inst.run({"action": "list_types"})
    r3 = await inst.run({"text": "Hi there."})
    r4 = await inst.run({"text": contract})
    r5 = await inst.run({"text": contract,
                         "clause_types": "coverage,exclusions,limits"})
    return r1, r2, r3, r4, r5

t1, t2, t3, t4, t5 = asyncio.run(probe())
check("no text -> error", "error" in t1)
check("list_types -> types array",
      isinstance(t2.get("types"), list) and "termination" in t2["types"])
check("too-short text -> error",
      "error" in t3 and "too short" in t3["error"])
check("valid text -> clauses returned",
      t4.get("clause_count", 0) >= 5)
check("filtered call respects filter",
      set((t5.get("by_type") or {}).keys())
      <= {"coverage", "exclusions", "limits"})

# Role wiring
rt = (SRC / "roles.py").read_text(encoding="utf-8")
check("roles.py mentions clause_extractor", '"clause_extractor"' in rt)

from sunnyware import roles as _roles
for role in ("fpa", "actuary", "cfo", "tax"):
    subset = _roles.active_tool_names(role) or []
    check(f"clause_extractor in {role} subset",
          "clause_extractor" in subset)

for fp in [SRC / "tools" / "clause_extractor.py",
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
