# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 147 smoke - auditor refinements (a/b/c)."""
from pathlib import Path
import ast, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 147: auditor refinements (a/b/c) ===")

rt = (SRC / "roles.py").read_text(encoding="utf-8")

check("roles.py has _AUDITOR_FIELD_RE", "_AUDITOR_FIELD_RE" in rt)
check("roles.py has regex fallback marker",
      "Part 147c: regex field extraction" in rt)
check("EXAMPLES block present",
      "EXAMPLES (match this exact format)" in rt)
check("TOOL POLICY has 'read_file ONLY'",
      "Use read_file ONLY to read the user's submitted materials" in rt)
# (moved below — R not imported yet)

sys.path.insert(0, str(SRC.parent))
from sunnyware import roles as R

# rag_search still exists for OTHER roles; only verify auditor is clean.
check("auditor prompt has no rag_search",
      "rag_search" not in (R.prompt_addon("auditor") or ""))

tools = set(R.active_tool_names("auditor") or [])
check("auditor tools == 3 (no rag_search)",
      tools == {"calculator", "python_eval", "read_file"},
      "tools=%s" % sorted(tools))

p = R.prompt_addon("auditor") or ""
check("prompt has EXAMPLES", "EXAMPLES" in p)
check("prompt has TOOL POLICY", "TOOL POLICY" in p)
check("prompt <= 3500 chars", len(p) <= 3500, "len=%d" % len(p))

malformed = (
    'The claim is wrong. Verdict follows:\n'
    '"verdict": "Incorrect; 240*0.15=36",\n'
    '"canonical_label": "Miscalculated percentage",\n'
    '"severity": "minor"\n'
)
r = R.extract_auditor_json(malformed)
check("regex fallback extracts malformed JSON",
      isinstance(r, dict) and r.get("canonical_label") == "Miscalculated percentage",
      "got=%s" % r)

prose = 'After analysis: "canonical_label": "Logic gap" then "severity": "moderate".'
r = R.extract_auditor_json(prose)
check("regex fallback extracts prose without braces",
      isinstance(r, dict) and r.get("canonical_label") == "Logic gap")

pure = '{"canonical_label": "Logic gap", "verdict": "ok"}'
r = R.extract_auditor_json(pure)
check("pure JSON still parses", isinstance(r, dict) and r.get("verdict") == "ok")

fenced = "Analysis:\n```json\n{\"canonical_label\": \"Incorrect operator\"}\n```"
r = R.extract_auditor_json(fenced)
check("fenced JSON still parses",
      isinstance(r, dict) and r.get("canonical_label") == "Incorrect operator")

check("empty -> None", R.extract_auditor_json("") is None)
check("garbage -> None", R.extract_auditor_json("random text") is None)

for fp in [SRC / "roles.py"]:
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
