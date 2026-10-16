# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 146 smoke - auditor JSON extraction + prompt tool policy."""
from pathlib import Path
import ast, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 146: auditor JSON extraction + tool policy ===")

rt = (SRC / "roles.py").read_text(encoding="utf-8")
at = (SRC / "routes" / "agent.py").read_text(encoding="utf-8")

check("roles.py has extract_auditor_json",
      "def extract_auditor_json" in rt)
check("roles.py has fenced-JSON regex",
      "_AUDITOR_JSON_FENCE" in rt)
check("roles.py has bare-object regex",
      "_AUDITOR_BARE_OBJ" in rt)
check("auditor prompt has TOOL POLICY",
      "TOOL POLICY:" in rt)
check("auditor prompt forbids rag_search for fallacies",
      "Do NOT use rag_search" in rt)

check("agent.py has _auditor_verdict_or_none",
      "def _auditor_verdict_or_none" in at)
check("agent.py uses auditor_verdict in response",
      '"auditor_verdict"' in at)

sys.path.insert(0, str(SRC.parent))
from sunnyware import roles as R

p = R.prompt_addon("auditor") or ""
check("auditor prompt has TOOL POLICY", "TOOL POLICY:" in p)
check("auditor prompt is <= 2500 chars", len(p) <= 2500,
      "len=%d" % len(p))

pure = '{"verdict": "ok", "canonical_label": "Logic gap"}'
r = R.extract_auditor_json(pure)
check("extract pure JSON", isinstance(r, dict) and r.get("verdict") == "ok")

fenced = (
    "Here is my analysis:\n\n"
    "```json\n"
    '{"verdict": "no defect", "canonical_label": "No demonstrated defect; no canonical error label applies."}\n'
    "```\n"
)
r = R.extract_auditor_json(fenced)
check("extract fenced JSON",
      isinstance(r, dict) and r.get("verdict") == "no defect")

prose = 'Analysis done. {"canonical_label": "Miscalculated percentage"} end.'
r = R.extract_auditor_json(prose)
check("extract prose+bare JSON",
      isinstance(r, dict) and r.get("canonical_label") == "Miscalculated percentage")

check("extract None -> None", R.extract_auditor_json(None) is None)
check("extract empty -> None", R.extract_auditor_json("") is None)
check("extract garbage -> None", R.extract_auditor_json("no json here") is None)

fenced2 = "```\n{\"verdict\": \"x\"}\n```"
r = R.extract_auditor_json(fenced2)
check("extract bare-fenced JSON", isinstance(r, dict) and r.get("verdict") == "x")

for fp in [SRC / "roles.py", SRC / "routes" / "agent.py"]:
    try:
        ast.parse(fp.read_text(encoding="utf-8"))
        check(f"{fp.name} parses", True)
    except SyntaxError as e:
        check(f"{fp.name} parses", False, str(e))

passed = sum(1 for _, ok, _ in checks if ok)
total = len(checks)
print("")
print(f"{passed}/{total} checks passed")
if passed < total:
    for name, ok, detail in checks:
        if not ok:
            print(f"  - {name} {detail}")
    sys.exit(1)
print("ALL PASS")
