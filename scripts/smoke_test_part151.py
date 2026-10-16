# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 151 smoke - universal truthfulness + orchestration hardening."""
from pathlib import Path
import ast, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 151: universal truthfulness + orchestration ===")

mod_p = SRC / "role_truthfulness.py"
check("role_truthfulness.py exists", mod_p.exists())
mt = mod_p.read_text(encoding="utf-8") if mod_p.exists() else ""
check("has TRUTHFULNESS_CLAUSE", "TRUTHFULNESS_CLAUSE" in mt)
check("has MANDATORY_TOOLS dict", "MANDATORY_TOOLS" in mt)
check("has clause_for function", "def clause_for" in mt)

rt = (SRC / "roles.py").read_text(encoding="utf-8")
check("roles.py imports _rt", "import role_truthfulness as _rt" in rt)
check("roles.py wraps prompt_addon",
      "def _prompt_addon_base(role_name)" in rt and
      "extra = _rt.clause_for(role_name)" in rt)

sys.path.insert(0, str(SRC.parent))
from sunnyware import roles as R
from sunnyware import role_truthfulness as RT

for name in ("fpa", "quant", "actuary", "tax", "cfo", "cdo",
             "legal", "risk_ins", "auditor", "general"):
    p = R.prompt_addon(name) or ""
    check(f"{name}: has TRUTHFULNESS RULES",
          "TRUTHFULNESS RULES" in p)

for name in ("fpa", "quant", "actuary", "tax", "legal",
             "risk_ins", "cfo", "cdo"):
    p = R.prompt_addon(name) or ""
    expect = RT.MANDATORY_TOOLS.get(name, "")[:25]
    check(f"{name}: has mandatory-tools block",
          bool(expect) and expect in p)

cfo_p = R.prompt_addon("cfo") or ""
# Part 156 rewrote the CFO workflow; accept either marker.
check("CFO: cites CDO cross-check",
      ("verified by CDO cross-check" in cfo_p)
      or ("Cross-check status: verified by CDO" in cfo_p)
      or ("HARD STOP RULE" in cfo_p))

cdo_p = R.prompt_addon("cdo") or ""
check("CDO: has CROSS-CHECK RULE",
      "CROSS-CHECK RULE" in cdo_p)
check("CDO: mentions TWO independent specialists",
      "TWO independent specialists" in cdo_p)

extra = RT.clause_for("does-not-exist")
check("clause_for(unknown) has TRUTHFULNESS",
      "TRUTHFULNESS RULES" in extra)
check("clause_for(unknown) no per-role block",
      "MANDATORY TOOL USE" not in extra)

for fp in [mod_p, SRC / "roles.py"]:
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
