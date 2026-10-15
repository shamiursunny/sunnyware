# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 135 smoke test - RBAC layer."""
from pathlib import Path
import ast, os, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 135: RBAC layer ===")

# 1. auth.py structure
at = (SRC / "auth.py").read_text(encoding="utf-8")
check("auth.py has _ROLE_HIERARCHY", "_ROLE_HIERARCHY" in at)
check("auth.py has _parse_roles", "def _parse_roles" in at)
check("auth.py has load_roles", "def load_roles" in at)
check("auth.py has default_role", "def default_role" in at)
check("auth.py has role_for_key", "def role_for_key" in at)
check("auth.py has role_level", "def role_level" in at)
check("auth.py has has_role", "def has_role" in at)

# 2. tenant.py structure
tt = (SRC / "tenant.py").read_text(encoding="utf-8")
check("tenant.py has set_role", "def set_role" in tt)
check("tenant.py has get_role", "def get_role" in tt)
check("tenant.py has reset_role", "def reset_role" in tt)
check("tenant.py has _role contextvar", "_role: contextvars" in tt)

# 3. main.py middleware
mt = (SRC / "main.py").read_text(encoding="utf-8")
check("main.py has Part 135 marker",
      "Part 135: set the request role" in mt)
check("main.py calls set_role", "_tenant.set_role(_role)" in mt)
check("main.py calls role_for_key", "role_for_key(_incoming_key)" in mt)

# 4. routes/meta.py structure
rt = (SRC / "routes" / "meta.py").read_text(encoding="utf-8")
check("meta.py has /api/auth/whoami", '"/api/auth/whoami"' in rt)
check("meta.py has _check_admin", "def _check_admin" in rt)
check("meta.py has _forbidden", "def _forbidden" in rt)
check("meta.py: reset guarded", "Part 135: admin-only" in rt)
check("meta.py: _check_admin called >= 3x",
      rt.count("_check_admin()") >= 3,
      f"count={rt.count('_check_admin()')}")

# 5. Pure role logic
sys.path.insert(0, str(SRC.parent))
from sunnyware import auth as A

check("default_role is admin", A.default_role() == "admin", A.default_role())
check("readonly < analyst", A.role_level("readonly") < A.role_level("analyst"))
check("analyst < admin", A.role_level("analyst") < A.role_level("admin"))
check("admin level == 3", A.role_level("admin") == 3)
check("bogus level == 0", A.role_level("bogus") == 0)
check("empty level == 0", A.role_level("") == 0)

check("admin has admin", A.has_role("admin", "admin") is True)
check("admin has analyst", A.has_role("admin", "analyst") is True)
check("admin has readonly", A.has_role("admin", "readonly") is True)
check("analyst has analyst", A.has_role("analyst", "analyst") is True)
check("analyst has readonly", A.has_role("analyst", "readonly") is True)
check("analyst lacks admin", A.has_role("analyst", "admin") is False)
check("readonly has readonly", A.has_role("readonly", "readonly") is True)
check("readonly lacks analyst", A.has_role("readonly", "analyst") is False)
check("readonly lacks admin", A.has_role("readonly", "admin") is False)
check("bogus lacks readonly", A.has_role("bogus", "readonly") is False)

# role_for_key via env
os.environ["SUNNYWARE_API_ROLES"] = "keyA:admin,keyB:analyst,keyC:readonly"
A._ROLES_CACHE = None
check("env: keyA -> admin", A.role_for_key("keyA") == "admin")
check("env: keyB -> analyst", A.role_for_key("keyB") == "analyst")
check("env: keyC -> readonly", A.role_for_key("keyC") == "readonly")
check("env: unknown -> default (admin)",
      A.role_for_key("stranger") == "admin")

# malformed entries silently skipped
os.environ["SUNNYWARE_API_ROLES"] = "good:admin,bad,no_role:, :analyst,key1:badrole,key2:analyst"
A._ROLES_CACHE = None
roles = A.load_roles(reload=True)
check("malformed 'bad' skipped", "bad" not in roles)
check("malformed 'no_role:' skipped", "no_role" not in roles)
check("malformed ':analyst' skipped", "" not in roles)
check("malformed 'key1:badrole' skipped", "key1" not in roles)
check("valid kept: good", roles.get("good") == "admin")
check("valid kept: key2", roles.get("key2") == "analyst")

# default role override
os.environ["SUNNYWARE_DEFAULT_ROLE"] = "analyst"
check("SUNNYWARE_DEFAULT_ROLE=analyst applied",
      A.default_role() == "analyst")
check("unknown key uses new default",
      A.role_for_key("never-seen") == "analyst")
os.environ["SUNNYWARE_DEFAULT_ROLE"] = "bogus"
check("bogus default falls back to admin",
      A.default_role() == "admin")

del os.environ["SUNNYWARE_DEFAULT_ROLE"]
del os.environ["SUNNYWARE_API_ROLES"]
A._ROLES_CACHE = None

# tenant contextvar roundtrip
from sunnyware import tenant as T
T.reset_role()
check("tenant.get_role default empty", T.get_role() == "")
T.set_role("analyst")
check("tenant.set_role/get_role roundtrip", T.get_role() == "analyst")
T.reset_role()
check("tenant.reset_role clears", T.get_role() == "")

# files parse
for fp in [SRC / "auth.py", SRC / "tenant.py",
           SRC / "main.py", SRC / "routes" / "meta.py"]:
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
