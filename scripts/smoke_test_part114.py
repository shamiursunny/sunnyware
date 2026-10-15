# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 114 smoke test - CFO + CDO supervisor delegation."""
from pathlib import Path
import ast, asyncio, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 114: CFO + CDO supervisor delegation ===")

sys.path.insert(0, str(SRC.parent))
from sunnyware import roles as _roles

# 1. New roles present
for key in ("cfo", "cdo"):
    check(f"role '{key}' defined", key in _roles.ROLES)
check("cfo icon is briefcase", _roles.ROLES["cfo"]["icon"] == "\U0001F4BC")
check("cdo icon is clipboard", _roles.ROLES["cdo"]["icon"] == "\U0001F4CB")
check("cfo label", _roles.ROLES["cfo"]["label"] == "Chief Financial Officer")
check("cdo label", _roles.ROLES["cdo"]["label"] == "Chief Delivery Officer")

# 2. Styles
check("cfo style accent", _roles.style("cfo")["accent"] == "#8b5cf6")
check("cdo style accent", _roles.style("cdo")["accent"] == "#06b6d4")
check("cfo chip label", _roles.style("cfo")["chip"] == "CFO")
check("cdo chip label", _roles.style("cdo")["chip"] == "CDO")

# 3. Aliases
check("alias 'chief' -> cfo", _roles.canonical("chief") == "cfo")
check("alias 'chief financial officer' -> cfo",
      _roles.canonical("chief financial officer") == "cfo")

# 4. Delegation matrix
check("cfo -> cdo allowed", _roles.can_delegate("cfo", "cdo"))
check("cfo -> actuary DENIED", not _roles.can_delegate("cfo", "actuary"))
check("cdo -> actuary allowed", _roles.can_delegate("cdo", "actuary"))
check("cdo -> quant allowed", _roles.can_delegate("cdo", "quant"))
check("cdo -> fpa allowed", _roles.can_delegate("cdo", "fpa"))
check("cdo -> tax allowed", _roles.can_delegate("cdo", "tax"))
check("cdo -> cfo DENIED", not _roles.can_delegate("cdo", "cfo"))
check("cdo -> cdo DENIED", not _roles.can_delegate("cdo", "cdo"))
check("actuary -> anything DENIED", not _roles.can_delegate("actuary", "cdo"))
check("general -> anything DENIED", not _roles.can_delegate("general", "cdo"))
check("cfo targets == ['cdo']", _roles.delegation_targets("cfo") == ["cdo"])
check("cdo targets include actuary+quant+fpa+tax+general",
      set(_roles.delegation_targets("cdo")) ==
      {"actuary", "quant", "fpa", "tax", "general"})

# 5. Delegate tool registered
from sunnyware import tools as tools_registry
names = tools_registry.tool_names()
check("delegate_to_agent in registry", "delegate_to_agent" in names)
check("registry size now 69", len(names) >= 69, f"n={len(names)}")

# 6. CFO + CDO tool subsets include delegate_to_agent
cfo_tools = _roles.active_tool_names("cfo") or []
cdo_tools = _roles.active_tool_names("cdo") or []
check("cfo tools include delegate_to_agent", "delegate_to_agent" in cfo_tools)
check("cdo tools include delegate_to_agent", "delegate_to_agent" in cdo_tools)
check("cfo tools include email_send", "email_send" in cfo_tools)
check("cdo tools include python_eval", "python_eval" in cdo_tools)
check("cfo subset is small (< 20)", len(cfo_tools) < 20, f"n={len(cfo_tools)}")
check("cdo subset is small (< 10)", len(cdo_tools) < 10, f"n={len(cdo_tools)}")
check("worker (actuary) does NOT have delegate_to_agent",
      "delegate_to_agent" not in (_roles.active_tool_names("actuary") or []))

# 7. Delegate tool behavior (no real LLM call)
from sunnyware.tools.delegate_to_agent import (
    DelegateToAgentTool, _CURRENT_ROLE, _DELEGATION_DEPTH, _DELEGATION_PATH,
    _MAX_DEPTH,
)
inst = DelegateToAgentTool()
check("tool name", inst.name == "delegate_to_agent")
check("max depth is 3", _MAX_DEPTH == 3)

async def probe_validation():
    # Set role = cfo (top of hierarchy)
    tok = _CURRENT_ROLE.set("cfo")
    try:
        r_missing_agent = await inst.run({"task": "do x"})
        r_missing_task  = await inst.run({"agent": "cdo"})
        r_unknown       = await inst.run({"agent": "xyzzy", "task": "do x"})
        r_denied        = await inst.run({"agent": "actuary", "task": "do x"})
        # depth guard: force depth to max
        dtok = _DELEGATION_DEPTH.set(_MAX_DEPTH)
        r_depth         = await inst.run({"agent": "cdo", "task": "do x"})
        _DELEGATION_DEPTH.reset(dtok)
        # cycle: pretend we already visited cdo
        ptok = _DELEGATION_PATH.set(("cdo",))
        r_cycle         = await inst.run({"agent": "cdo", "task": "do x"})
        _DELEGATION_PATH.reset(ptok)
        return r_missing_agent, r_missing_task, r_unknown, r_denied, r_depth, r_cycle
    finally:
        _CURRENT_ROLE.reset(tok)

rm, rt_, ru, rd, rdep, rcyc = asyncio.run(probe_validation())
check("missing agent -> error", "error" in rm and "agent is required" in rm["error"])
check("missing task -> error", "error" in rt_ and "task is required" in rt_["error"])
check("unknown agent -> error", "error" in ru and "unknown agent" in ru["error"])
check("cfo -> actuary denied at tool layer", "error" in rd and "cannot delegate" in rd["error"])
check("depth guard fires at max", "error" in rdep and "max delegation depth" in rdep["error"])
check("cycle guard fires", "error" in rcyc and "cycle detected" in rcyc["error"])

# 8. Orchestrator wrapped
ot = (SRC / "orchestrator.py").read_text(encoding="utf-8")
check("orchestrator has _run_agent_body", "async def _run_agent_body(" in ot)
check("orchestrator sets _CURRENT_ROLE", "_CURRENT_ROLE.set(role" in ot)

# 9. Routes extended timeout for supervisor roles
rt2 = (SRC / "routes" / "agent.py").read_text(encoding="utf-8")
check("routes has supervisor timeout bump",
      "Part 114: supervisor roles chain sub-agents" in rt2)

# 10. Files parse
for f in [SRC / "roles.py",
          SRC / "orchestrator.py",
          SRC / "routes" / "agent.py",
          SRC / "tools" / "delegate_to_agent.py",
          SRC / "tools" / "__init__.py"]:
    try:
        ast.parse(f.read_text(encoding="utf-8"))
        check(f"{f.name} parses", True)
    except SyntaxError as e:
        check(f"{f.name} parses", False, str(e))

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
