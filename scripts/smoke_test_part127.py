# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 127 smoke test - earnings_call transcript summarizer."""
from pathlib import Path
import ast, asyncio, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 127: earnings_call transcript summarizer ===")

f = SRC / "tools" / "earnings_call.py"
check("earnings_call.py exists", f.exists())
try:
    ast.parse(f.read_text(encoding="utf-8"))
    check("earnings_call.py parses", True)
except SyntaxError as e:
    check("earnings_call.py parses", False, str(e))

init = (SRC / "tools" / "__init__.py").read_text(encoding="utf-8")
check("__init__ imports EarningsCallTool",
      "from .earnings_call import EarningsCallTool" in init)
check("__init__ registers EarningsCallTool",
      "EarningsCallTool.name: EarningsCallTool()" in init)

sys.path.insert(0, str(SRC.parent))
from sunnyware import tools as tools_registry
names = tools_registry.tool_names()
check("earnings_call in registry", "earnings_call" in names)
check("registry size >= 77", len(names) >= 77, f"n={len(names)}")

from sunnyware.tools.earnings_call import (
    EarningsCallTool, summarize_transcript,
)
inst = EarningsCallTool()
check("name == earnings_call", inst.name == "earnings_call")
check("description mentions earnings",
      "earnings" in inst.description.lower())
check("parameters include transcript + max_per_theme",
      {"transcript", "max_per_theme"} <= set(inst.parameters))

# Build a rich test transcript
transcript = (
    "Good afternoon everyone and thank you for joining our Q3 earnings call. "
    "Total revenue for the quarter came in at $4.2 billion, up 12% year over year. "
    "Our gross margin expanded 180 basis points to 47.3%, reflecting a stronger mix. "
    "Operating margin was 22%, above our guidance range. "
    "We are raising full year guidance to $16.8 billion in revenue. "
    "We expect Q4 revenue to grow in the high single digits. "
    "Capital expenditures were $210 million in the quarter, primarily for data center capacity. "
    "We returned $500 million to shareholders through dividends and buybacks. "
    "Demand remains robust with record backlog and strong customer renewals. "
    "However, we are seeing some softness in EMEA and macro uncertainty is a headwind. "
    "Restructuring charges of $30 million were incurred to improve operational efficiency. "
    "Looking ahead, we are confident in the trajectory and our competitive position. "
    "This concludes our prepared remarks and we will now take your questions."
)

s = summarize_transcript(transcript, max_per_theme=2)
check("summary has sentence_count",
      isinstance(s.get("sentence_count"), int) and s["sentence_count"] >= 10)
check("summary has sentiment",
      isinstance(s.get("sentiment"), dict)
      and s["sentiment"].get("label") in ("positive", "negative", "neutral"))
check("summary has themes",
      isinstance(s.get("themes"), dict) and len(s["themes"]) >= 5)
check("revenue theme has mentions",
      s["themes"]["revenue"]["mentions"] >= 1)
check("guidance theme has mentions",
      s["themes"]["guidance"]["mentions"] >= 1)
check("margin theme has mentions",
      s["themes"]["margin"]["mentions"] >= 1)
check("capex theme has mentions",
      s["themes"]["capex"]["mentions"] >= 1)
check("risk theme has mentions",
      s["themes"]["risk"]["mentions"] >= 1)
check("revenue top sentence mentions revenue",
      any("revenue" in item["sentence"].lower()
          for item in s["themes"]["revenue"]["top"]))
check("themes_covered includes 'revenue'",
      "revenue" in (s.get("themes_covered") or []))

# Behavior via tool
async def probe():
    r1 = await inst.run({})
    r2 = await inst.run({"transcript": ""})
    r3 = await inst.run({"transcript": "Hi. Bye."})
    r4 = await inst.run({"transcript": transcript, "max_per_theme": 1})
    return r1, r2, r3, r4

r1, r2, r3, r4 = asyncio.run(probe())
check("no transcript -> error", "error" in r1)
check("empty transcript -> error", "error" in r2)
check("too-short transcript -> error",
      "error" in r3 and "too short" in r3["error"])
check("valid transcript -> summary",
      "themes" in r4 and "sentiment" in r4)
check("max_per_theme respected",
      all(len(v["top"]) <= 1 for v in r4["themes"].values()))

# Role wiring
rt = (SRC / "roles.py").read_text(encoding="utf-8")
check("roles.py mentions earnings_call", '"earnings_call"' in rt)

from sunnyware import roles as _roles
for role in ("fpa", "actuary", "cfo"):
    subset = _roles.active_tool_names(role) or []
    check(f"earnings_call in {role} subset",
          "earnings_call" in subset, f"present={'earnings_call' in subset}")

for fp in [SRC / "tools" / "earnings_call.py",
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
