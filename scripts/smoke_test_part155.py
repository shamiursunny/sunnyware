# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 155 smoke - CDO rewrite + specialist output contract."""
from pathlib import Path
import ast, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 155: CDO rewrite + specialist output contract ===")

rt = (SRC / "role_truthfulness.py").read_text(encoding="utf-8")

check("has SPECIALIST_OUTPUT_CONTRACT",
      "SPECIALIST_OUTPUT_CONTRACT" in rt)
check("has SPECIALIST_ROLES",
      "SPECIALIST_ROLES" in rt)
check("has VALID WORKERS in cdo block",
      "VALID WORKERS (call delegate_to_agent" in rt)
check("has FINAL REPORT FORMAT",
      "FINAL REPORT FORMAT" in rt)
check("has [source: tag instruction",
      "[source: <tool_name>" in rt)
check("has UNABLE TO RETRIEVE instruction",
      "UNABLE TO RETRIEVE" in rt)
check("has NOT VERIFIED instruction",
      "NOT VERIFIED" in rt)

sys.path.insert(0, str(SRC.parent))
from sunnyware import roles as R
from sunnyware import role_truthfulness as RT

cdo = R.prompt_addon("cdo") or ""
check("CDO: VALID WORKERS", "VALID WORKERS" in cdo)
for w in ("fpa", "quant", "actuary", "tax", "legal", "risk_ins", "general"):
    check(f"CDO: lists {w}", w in cdo)
check("CDO: warns auditor user-only",
      "USER-ONLY, do not delegate to auditor" in cdo)
check("CDO: FINAL REPORT FORMAT",
      "FINAL REPORT FORMAT" in cdo)
check("CDO: cross-check status line",
      "matched|flagged|single-source" in cdo)

for name in ("fpa", "quant", "actuary", "tax", "legal", "risk_ins"):
    p = R.prompt_addon(name) or ""
    check(f"{name}: has OUTPUT CONTRACT", "OUTPUT CONTRACT" in p)
    check(f"{name}: has [source: tag",
          "[source: <tool_name>" in p)

for name in ("cfo", "general", "auditor"):
    p = R.prompt_addon(name) or ""
    check(f"{name}: no specialist output contract",
          "OUTPUT CONTRACT (required for every specialist reply)" not in p)

check("SPECIALIST_ROLES contains 6",
      len(RT.SPECIALIST_ROLES) == 6,
      "n=%d" % len(RT.SPECIALIST_ROLES))

for fp in [SRC / "role_truthfulness.py"]:
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
