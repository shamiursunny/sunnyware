# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 113B smoke test - role-specific result rendering."""
from pathlib import Path
import ast, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 113B: role-specific result rendering ===")

# 1. roles.py has style() helper
sys.path.insert(0, str(SRC.parent))
from sunnyware import roles as _roles
check("roles.style callable", callable(getattr(_roles, "style", None)))
for key in ("general", "fpa", "quant", "actuary", "tax"):
    st = _roles.style(key)
    check(f"style({key}) returns dict with accent",
          isinstance(st, dict) and st.get("accent", "").startswith("#"))
check("style unknown -> general accent",
      _roles.style("nope")["accent"] == _roles.style("general")["accent"])
check("style(None) -> general accent",
      _roles.style(None)["accent"] == _roles.style("general")["accent"])

# 2. /stream route emits role meta in start event
agent = (SRC / "routes" / "agent.py").read_text(encoding="utf-8")
check("/stream start event has _role_meta", "_role_meta" in agent)
check("/stream emits accent", "_role_meta[\"accent\"]" in agent)
check("/stream emits chip", "_role_meta[\"chip\"]" in agent)
check("/stream uses _roles.style", "_roles.style(role)" in agent)

# 3. WebUI CSS + JS
ui = (SRC / "webui.py").read_text(encoding="utf-8")
check("CSS: fpa accent rule", '#chat[data-role="fpa"] .msg.agent' in ui)
check("CSS: quant accent rule", '#chat[data-role="quant"] .msg.agent' in ui)
check("CSS: actuary accent rule", '#chat[data-role="actuary"] .msg.agent' in ui)
check("CSS: tax accent rule", '#chat[data-role="tax"] .msg.agent' in ui)
check("CSS: fpa chip ::before", "FP&A" in ui and "::before" in ui)
check("SSE handler reads data.role", "chat.dataset.role = data.role" in ui)
check("SSE handler reads data.accent", "data.accent" in ui)
check("initRoleSelector sets dataset.role",
      "Part 113B: apply session role on boot" in ui)
check("persistRoleToSession updates dataset.role",
      "Part 113B: reflect role color" in ui)
check("syncRoleFromSession updates dataset.role",
      "Part 113B: sync chat container role" in ui)

# 4. Files parse
for f in [SRC / "roles.py", SRC / "routes" / "agent.py", SRC / "webui.py"]:
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
