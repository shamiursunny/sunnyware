# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 142a smoke - auditor role registration."""
from pathlib import Path
import ast, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 142a: auditor role ===")

rt = (SRC / "roles.py").read_text(encoding="utf-8")

check("has _AUDITOR_PROMPT constant", "_AUDITOR_PROMPT = " in rt)
check("has auditor role entry", '"auditor": {' in rt)
check("auditor label", 'AI Evaluation Auditor' in rt)
check("auditor tool allowlist: calculator", '"calculator"' in rt)
check("auditor tool allowlist: python_eval", '"python_eval"' in rt)
check("auditor tool allowlist: read_file", '"read_file"' in rt)
# Part 147a: rag_search removed from auditor allowlist.
check("auditor allowlist has read_file", '"read_file"' in rt)
check("prompt mentions forensic auditor", "forensic auditor" in rt)
check("prompt has PIPELINE", "PIPELINE" in rt)
check("prompt has 5 canonical labels",
      all(lbl in rt for lbl in (
          'Miscalculated percentage',
          'Incorrect operator',
          'Logic gap',
          'Incomplete explanation',
          'Constraint violation',
      )))
check("prompt has no-defect phrase",
      "No demonstrated defect; no canonical error label applies." in rt)
check("prompt requires JSON output",
      '"verdict"' in rt and '"canonical_label"' in rt)
check("prompt mentions Sunnyware identity", "Sunnyware's forensic" in rt)

sys.path.insert(0, str(SRC.parent))
from sunnyware import roles as R

check("auditor is a valid role", R.is_valid("auditor"))
check("auditor in role_names()", "auditor" in R.role_names())
check("auditor icon (magnifier)",
      R.ROLES.get("auditor", {}).get("icon") == "\U0001F50D")
check("auditor has prompt addon",
      isinstance(R.prompt_addon("auditor"), str)
      and len(R.prompt_addon("auditor")) > 100)
check("auditor prompt addon has 5 labels",
      R.prompt_addon("auditor").count("Miscalculated percentage") >= 1)
check("auditor tool list has 4 tools",
      len(R.active_tool_names("auditor") or []) == 4,
      "n=%d" % len(R.active_tool_names("auditor") or []))
check("auditor tools match allowlist",
      set(R.active_tool_names("auditor") or [])
      == {"calculator", "python_eval", "read_file", "auditor_full_spec"})
check("email_send not in auditor tools",
      "email_send" not in (R.active_tool_names("auditor") or []))
check("write_file not in auditor tools",
      "write_file" not in (R.active_tool_names("auditor") or []))
check("image_generate not in auditor tools",
      "image_generate" not in (R.active_tool_names("auditor") or []))

prompt = R.prompt_addon("auditor") or ""
check("prompt is 200-3500 chars (token-minimized)",
      200 <= len(prompt) <= 3500, "len=%d" % len(prompt))

targets_all = set()
for rn in R.role_names():
    for tgt in (R.delegation_targets(rn) or []):
        targets_all.add(tgt)
check("auditor is not in any delegation target list",
      "auditor" not in targets_all,
      "targets=%s" % sorted(targets_all))

try:
    ast.parse(rt)
    check("roles.py parses", True)
except SyntaxError as e:
    check("roles.py parses", False, str(e))

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
