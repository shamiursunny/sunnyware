# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 112 smoke test - role personas + tool subsetting."""
from pathlib import Path
import ast, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 112: role personas + tool subsetting ===")

# 1. roles.py exists + parses
roles_file = SRC / "roles.py"
check("roles.py exists", roles_file.exists())
roles_src = roles_file.read_text(encoding="utf-8") if roles_file.exists() else ""
try:
    ast.parse(roles_src)
    check("roles.py parses", True)
except SyntaxError as e:
    check("roles.py parses", False, str(e))

# 2. ROLES has expected keys
sys.path.insert(0, str(SRC.parent))
from sunnyware import roles as _roles
for key in ("general", "fpa", "quant", "actuary", "tax"):
    check(f"role '{key}' present", key in _roles.ROLES)

# 3. Resolver handles aliases + unknown
check("resolve 'fp&a' -> fpa", _roles.get_role("fp&a") is _roles.ROLES["fpa"])
check("resolve None -> general", _roles.get_role(None) is _roles.ROLES["general"])
check("resolve unknown -> general", _roles.get_role("xyzzy") is _roles.ROLES["general"])
check("is_valid('actuary')", _roles.is_valid("actuary"))
check("not is_valid('nope')", not _roles.is_valid("nope"))

# 4. Tool subsetting
check("general -> None (all tools)", _roles.active_tool_names("general") is None)

for key in ("fpa", "quant", "actuary", "tax"):
    subset = _roles.active_tool_names(key)
    check(f"{key} returns a subset", subset is not None and len(subset) > 0,
          f"{len(subset) if subset else 0} tools")

actuary = _roles.active_tool_names("actuary") or []
check("actuary includes python_eval", "python_eval" in actuary)
check("actuary includes an edgar_* tool",
      any(n.startswith("edgar_") for n in actuary))

# 5. Orchestrator is role-aware
orch = (SRC / "orchestrator.py").read_text(encoding="utf-8")
check("orchestrator _build_tools_schema takes role",
      "def _build_tools_schema(role=None)" in orch)
check("orchestrator run_agent takes role",
      "role: Optional[str] = None," in orch)
check("orchestrator injects role addon", "_role_addon" in orch)

# 6. Routes read role
routes = (SRC / "routes" / "agent.py").read_text(encoding="utf-8")
check("routes read role in /run", 'role = body.get("role")' in routes)
check("routes read role twice (run + stream)",
      routes.count('role = body.get("role")') >= 2)
check("/api/roles endpoint exists",
      '"/api/roles"' in routes or "'/api/roles'" in routes)

# 7. Prompt addon content sanity
check("actuary addon mentions chainladder",
      "chainladder" in _roles.prompt_addon("actuary"))
check("quant addon mentions backtesting",
      "backtesting" in _roles.prompt_addon("quant").lower())
check("fpa addon mentions ratios",
      "ratios" in _roles.prompt_addon("fpa").lower())

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
