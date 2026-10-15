# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 113A smoke test - per-session role persistence."""
from pathlib import Path
import ast, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 113A: per-session role persistence ===")

# 1. sessions.py has set_role + get_role
sess = (SRC / "sessions.py").read_text(encoding="utf-8")
check("sessions.py has set_role", "async def set_role" in sess)
check("sessions.py has get_role", "async def get_role" in sess)
check("set_role writes metadata.role", "jsonb_build_object('role'" in sess)
check("get_role reads metadata->>'role'", "metadata->>'role'" in sess)

# 2. routes/sessions.py has GET + PUT role
routes = (SRC / "routes" / "sessions.py").read_text(encoding="utf-8")
check("GET /api/sessions/{key}/role exists",
      '@router.get("/api/sessions/{session_key}/role")' in routes)
check("PUT /api/sessions/{key}/role exists",
      '@router.put("/api/sessions/{session_key}/role")' in routes)
check("PUT validates via roles registry",
      "is_valid(role)" in routes and "canonical(role)" in routes)
check("PUT rejects unknown roles with 400", 'status_code=400' in routes)

# 3. routes/agent.py persists role on both endpoints
agent = (SRC / "routes" / "agent.py").read_text(encoding="utf-8")
check("agent.py calls set_role (>=2 places)",
      agent.count("await sessions_store.set_role") >= 2)
check("agent.py guards via is_valid",
      "if _roles.is_valid(role):" in agent)

# 4. roles.py exposes public canonical()
sys.path.insert(0, str(SRC.parent))
from sunnyware import roles as _roles
check("roles.canonical is public", hasattr(_roles, "canonical"))
check("canonical('fp&a') -> 'fpa'", _roles.canonical("fp&a") == "fpa")
check("canonical(None) is None", _roles.canonical(None) is None)
check("is_valid still works", _roles.is_valid("actuary") and not _roles.is_valid("nope"))

# 5. Files parse
for f in [SRC / "sessions.py", SRC / "roles.py",
          SRC / "routes" / "sessions.py", SRC / "routes" / "agent.py"]:
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
