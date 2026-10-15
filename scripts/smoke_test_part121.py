# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 121 smoke test - lexicon sentiment on insurance_research."""
from pathlib import Path
import ast, asyncio, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 121: sentiment on insurance_research ===")

sf = SRC / "tools" / "_sentiment.py"
check("_sentiment.py exists", sf.exists())
try:
    ast.parse(sf.read_text(encoding="utf-8"))
    check("_sentiment.py parses", True)
except SyntaxError as e:
    check("_sentiment.py parses", False, str(e))

ir = (SRC / "tools" / "insurance_research.py").read_text(encoding="utf-8")
check("insurance_research imports _sentiment",
      "from ._sentiment import score_text" in ir)
check("insurance_research has sentiment action",
      'if action == "sentiment":' in ir)
check("insurance_research lists sentiment in available",
      '"sentiment"' in ir)
check("insurance_research has text param",
      '"text": {' in ir)

sys.path.insert(0, str(SRC.parent))
from sunnyware.tools._sentiment import score_text

s_pos = score_text("Strong growth, profits up, records beat expectations")
check("positive text -> positive", s_pos["label"] == "positive", s_pos["label"])
check("positive score > 0", s_pos["score"] > 0, str(s_pos["score"]))

s_neg = score_text("Weak losses decline, downgraded, defaults risk")
check("negative text -> negative", s_neg["label"] == "negative", s_neg["label"])
check("negative score < 0", s_neg["score"] < 0, str(s_neg["score"]))

s_neu = score_text("The company filed the document yesterday.")
check("neutral text -> neutral", s_neu["label"] == "neutral", s_neu["label"])
check("neutral score == 0", s_neu["score"] == 0)

s_neg2 = score_text("No growth, not profitable")
check("negation flips positive",
      s_neg2["negative_hits"] >= 1 or s_neg2["score"] < 0, str(s_neg2))

s_empty = score_text("")
check("empty text -> neutral", s_empty["label"] == "neutral")

check("result has label/score/hits/samples/coverage",
      {"label", "score", "positive_hits", "negative_hits",
       "samples", "coverage"} <= set(s_pos.keys()))

from sunnyware.tools.insurance_research import InsuranceResearchTool
inst = InsuranceResearchTool()

async def probe():
    r1 = await inst.run({"action": "sentiment"})
    r2 = await inst.run({"action": "sentiment",
                         "text": "Strong profit growth beat expectations"})
    r3 = await inst.run({"action": "sentiment",
                         "text": "Losses widened, downgrade and warnings"})
    r4 = await inst.run({"action": "bogus"})
    return r1, r2, r3, r4

r1, r2, r3, r4 = asyncio.run(probe())
check("sentiment without text -> error",
      "error" in r1 and "text is required" in r1["error"])
check("sentiment positive works",
      r2.get("sentiment", {}).get("label") == "positive")
check("sentiment negative works",
      r3.get("sentiment", {}).get("label") == "negative")
check("unknown action available list includes sentiment",
      "sentiment" in (r4.get("available") or []))

for fp in [SRC / "tools" / "_sentiment.py",
           SRC / "tools" / "insurance_research.py"]:
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
