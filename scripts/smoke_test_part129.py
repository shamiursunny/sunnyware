# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 129 smoke test - legal + risk_ins agents."""
from pathlib import Path
import ast, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 129: legal + risk_ins agents ===")

sys.path.insert(0, str(SRC.parent))
from sunnyware import roles as R

check("roles count is 9", len(R.ROLES) == 9, f"n={len(R.ROLES)}")
check("'legal' present", "legal" in R.ROLES)
check("'risk_ins' present", "risk_ins" in R.ROLES)

# Labels + icons
check("legal label", R.ROLES["legal"]["label"] == "Financial Legal Assistant")
check("risk_ins label",
      R.ROLES["risk_ins"]["label"] == "Financial Risk & Insurance")
check("legal has icon", bool(R.ROLES["legal"]["icon"]))
check("risk_ins has icon", bool(R.ROLES["risk_ins"]["icon"]))

# Aliases
check("attorney -> legal", R.canonical("attorney") == "legal")
check("counsel -> legal", R.canonical("counsel") == "legal")
check("compliance -> legal", R.canonical("compliance") == "legal")
check("risk -> risk_ins", R.canonical("risk") == "risk_ins")
check("insurance_risk -> risk_ins",
      R.canonical("insurance_risk") == "risk_ins")
check("investment_risk -> risk_ins",
      R.canonical("investment_risk") == "risk_ins")

# Styles
check("legal accent slate", R.style("legal")["accent"] == "#64748b")
check("risk_ins accent red", R.style("risk_ins")["accent"] == "#ef4444")
check("legal chip LEGAL", R.style("legal")["chip"] == "LEGAL")
check("risk_ins chip RISK/INS", R.style("risk_ins")["chip"] == "RISK/INS")

# Delegation
check("cdo can delegate to legal", R.can_delegate("cdo", "legal"))
check("cdo can delegate to risk_ins", R.can_delegate("cdo", "risk_ins"))
check("cfo CANNOT delegate to legal", not R.can_delegate("cfo", "legal"))
check("cfo CANNOT delegate to risk_ins", not R.can_delegate("cfo", "risk_ins"))
check("cfo delegates only to cdo", R.delegation_targets("cfo") == ["cdo"])
cdo_t = R.delegation_targets("cdo")
check("cdo targets include legal + risk_ins",
      "legal" in cdo_t and "risk_ins" in cdo_t)
check("cdo targets count is 7", len(cdo_t) == 7, f"n={len(cdo_t)}")
check("legal cannot delegate", R.delegation_targets("legal") == [])
check("risk_ins cannot delegate", R.delegation_targets("risk_ins") == [])

# Tool subsets
legal_tools = R.active_tool_names("legal") or []
risk_tools = R.active_tool_names("risk_ins") or []
check("legal subset >= 10 tools", len(legal_tools) >= 10, f"n={len(legal_tools)}")
check("risk_ins subset >= 12 tools", len(risk_tools) >= 12, f"n={len(risk_tools)}")
check("legal has clause_extractor", "clause_extractor" in legal_tools)
check("legal has document_library", "document_library" in legal_tools)
check("legal has research_search", "research_search" in legal_tools)
check("legal has delegate_to_agent", "delegate_to_agent" in legal_tools)
check("risk_ins has python_eval", "python_eval" in risk_tools)
check("risk_ins has insurance_research", "insurance_research" in risk_tools)
check("risk_ins has govcon_data", "govcon_data" in risk_tools)
check("risk_ins has research_search", "research_search" in risk_tools)
check("risk_ins has delegate_to_agent", "delegate_to_agent" in risk_tools)
check("risk_ins subset < 60 (proper filtering)", len(risk_tools) < 60)

# Prompts
legal_addon = R.prompt_addon("legal")
risk_addon = R.prompt_addon("risk_ins")
check("legal prompt mentions not-legal-advice",
      "not legal advice" in legal_addon.lower())
check("legal prompt mentions attorney review",
      "attorney review" in legal_addon.lower())
check("legal prompt mentions PRIVILEGED",
      "PRIVILEGED" in legal_addon)
check("risk_ins prompt mentions VaR", "VaR" in risk_addon)
check("risk_ins prompt mentions chainladder", "chainladder" in risk_addon)
check("risk_ins prompt mentions confidence", "confidence" in risk_addon.lower())

# webui dropdown
ui = (SRC / "webui.py").read_text(encoding="utf-8")
check("webui has legal option", 'value="legal"' in ui)
check("webui has risk_ins option", 'value="risk_ins"' in ui)

# Files parse
for fp in [SRC / "roles.py", SRC / "webui.py"]:
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
