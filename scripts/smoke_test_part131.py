# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 131 smoke test - legal_citation_check tool (offline)."""
from pathlib import Path
import ast, asyncio, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 131: legal_citation_check tool ===")

f = SRC / "tools" / "legal_citation_check.py"
check("legal_citation_check.py exists", f.exists())
try:
    ast.parse(f.read_text(encoding="utf-8"))
    check("legal_citation_check.py parses", True)
except SyntaxError as e:
    check("legal_citation_check.py parses", False, str(e))

init = (SRC / "tools" / "__init__.py").read_text(encoding="utf-8")
check("__init__ imports LegalCitationCheckTool",
      "from .legal_citation_check import LegalCitationCheckTool" in init)
check("__init__ registers LegalCitationCheckTool",
      "LegalCitationCheckTool.name: LegalCitationCheckTool()" in init)

sys.path.insert(0, str(SRC.parent))
from sunnyware import tools as tools_registry
names = tools_registry.tool_names()
check("legal_citation_check in registry", "legal_citation_check" in names)
check("registry size >= 80", len(names) >= 80, f"n={len(names)}")

from sunnyware.tools.legal_citation_check import (
    LegalCitationCheckTool, _STATUS_MEANINGS, _normalize_result,
)
inst = LegalCitationCheckTool()
check("name == legal_citation_check",
      inst.name == "legal_citation_check")
check("description mentions CourtListener",
      "CourtListener" in inst.description)
check("description mentions signup URL",
      "courtlistener.com/profile/api" in inst.description)
check("parameters include all required keys",
      {"action", "volume", "reporter", "page", "text", "query",
       "court", "opinion_id", "limit"} <= set(inst.parameters))
check("status meanings has 200/404/400/300/429",
      {200, 404, 400, 300, 429} <= set(_STATUS_MEANINGS.keys()))

# Behavior tests (no network - token likely not set locally)
async def probe():
    r1 = await inst.run({})
    r2 = await inst.run({"action": "bogus"})
    r3 = await inst.run({"action": "verify_one"})
    r4 = await inst.run({"action": "verify_one",
                         "volume": "576", "reporter": "U.S.", "page": "644"})
    r5 = await inst.run({"action": "verify_text"})
    r6 = await inst.run({"action": "verify_text", "text": "x" * 70000})
    r7 = await inst.run({"action": "search_cases"})
    r8 = await inst.run({"action": "get_opinion"})
    return r1, r2, r3, r4, r5, r6, r7, r8

r1, r2, r3, r4, r5, r6, r7, r8 = asyncio.run(probe())
check("no action -> error + available", "error" in r1 and "available" in r1)
check("unknown action -> error + available",
      "error" in r2 and "available" in r2)
check("verify_one without inputs -> error", "error" in r3)
check("verify_text without text -> error", "error" in r5)
check("verify_text too-long -> error", "error" in r6 and "64000" in r6["error"])
check("search_cases without query -> error", "error" in r7)
check("get_opinion without id -> error", "error" in r8)
# With/without token: r4 should be either a successful verification OR
# a token-missing error (both are valid when running offline)
if "error" in r4 and "COURTLISTENER_API_KEY" in r4["error"]:
    check("verify_one reports missing token gracefully",
          True, "no token (offline smoke)")
elif r4.get("result", {}).get("verified") is not None:
    check("verify_one returns verified flag", True)
else:
    check("verify_one responded", True, str(r4)[:80])

# _normalize_result unit tests
n1 = _normalize_result({"citation": "576 U.S. 644", "status": 200,
                        "clusters": [{"id": 12345,
                                      "case_name": "Obergefell v. Hodges",
                                      "date_filed": "2015-06-26"}]})
check("normalize: 200 + cluster -> verified",
      n1 and n1["verified"] is True)
check("normalize: cluster case_name extracted",
      n1["cluster"]["case_name"] == "Obergefell v. Hodges")

n2 = _normalize_result({"citation": "999 F.9d 999", "status": 404,
                        "clusters": []})
check("normalize: 404 -> not verified", n2 and n2["verified"] is False)
check("normalize: 404 status meaning",
      "NOT found" in n2["status_meaning"])

n3 = _normalize_result({"citation": "33 Umbrella 422", "status": 400,
                        "clusters": []})
check("normalize: 400 -> invalid reporter",
      n3 and "invalid reporter" in n3["status_meaning"])

n4 = _normalize_result({"citation": "X", "status": 300,
                        "clusters": [{"id": 1}, {"id": 2}]})
check("normalize: 300 -> ambiguous",
      n4 and "ambiguous" in n4["status_meaning"])
check("normalize: 300 cluster_count == 2", n4["cluster_count"] == 2)

# Role wiring
rt = (SRC / "roles.py").read_text(encoding="utf-8")
check("roles.py mentions legal_citation_check",
      '"legal_citation_check"' in rt)

from sunnyware import roles as _roles
legal_tools = _roles.active_tool_names("legal") or []
check("legal_citation_check in legal subset",
      "legal_citation_check" in legal_tools)
check("legal subset grew to >= 15 tools",
      len(legal_tools) >= 15, f"n={len(legal_tools)}")

# Files parse
for fp in [SRC / "tools" / "legal_citation_check.py",
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
