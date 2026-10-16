# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 156 smoke - CFO stop rule + MAX_ITERATIONS + tool name sanitize."""
from pathlib import Path
import ast, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 156 ===")

ot = (SRC / "orchestrator.py").read_text(encoding="utf-8")
rt = (SRC / "role_truthfulness.py").read_text(encoding="utf-8")

check("orchestrator: MAX_ITERATIONS = 10",
      "MAX_ITERATIONS = 10" in ot)
check("orchestrator: Part 156a marker",
      "Part 156a: raised from 3" in ot)
check("orchestrator: _sanitize_tool_name defined",
      "def _sanitize_tool_name" in ot)
check("orchestrator: sanitize CALLED in _resolve_tool_name",
      "Part 156b: strip special-token suffixes before any lookup" in ot)

check("roles: CFO HARD STOP RULE",
      "HARD STOP RULE" in rt)
check("roles: CFO exactly ONCE",
      "exactly ONCE per user" in rt)
check("roles: CFO 'That reply IS the deliverable'",
      "That reply IS the deliverable" in rt)

sys.path.insert(0, str(SRC.parent))
from sunnyware import roles as R
cfo = R.prompt_addon("cfo") or ""
check("CFO prompt has HARD STOP RULE", "HARD STOP RULE" in cfo)
check("CFO prompt has exactly ONCE", "exactly ONCE" in cfo)

import importlib
mod = importlib.import_module("sunnyware.orchestrator")
sanitize = getattr(mod, "_sanitize_tool_name", None)
if sanitize:
    check("sanitize: plain name unchanged",
          sanitize("delegate_to_agent") == "delegate_to_agent")
    check("sanitize: strips <|channel|>commentary",
          sanitize("delegate_to_agent<|channel|>commentary") == "delegate_to_agent")
    check("sanitize: strips trailing |>",
          sanitize("calculator|>") == "calculator")
    check("sanitize: strips backticks",
          sanitize("`delegate_to_agent`") == "delegate_to_agent")
    check("sanitize: empty -> empty", sanitize("") == "")
    check("sanitize: None -> empty", sanitize(None) == "")
    resolve = getattr(mod, "_resolve_tool_name", None)
    if resolve:
        check("resolve sanitizes before lookup",
              resolve("delegate_to_agent<|channel|>commentary")
              == "delegate_to_agent")
    else:
        check("resolve present", False, "not found")
else:
    check("sanitize present", False, "not found")

for fp in [SRC / "orchestrator.py", SRC / "role_truthfulness.py"]:
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
