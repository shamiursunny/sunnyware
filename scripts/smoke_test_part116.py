# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 116 smoke test - role config export/import."""
from pathlib import Path
import ast, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 116: role config export/import ===")

sys.path.insert(0, str(SRC.parent))
from sunnyware import roles as _roles

# 1. Functions exist
check("export_roles exists", callable(getattr(_roles, "export_roles", None)))
check("import_roles exists", callable(getattr(_roles, "import_roles", None)))

# 2. Export shape
snap = _roles.export_roles()
check("export version", snap.get("version") == 1)
check("export has default_role", snap.get("default_role") == _roles.DEFAULT_ROLE)
check("export has 7 roles", len(snap.get("roles") or []) == len(_roles.ROLES))
roles_by_key = {r["key"]: r for r in snap["roles"]}
for k in ("general", "fpa", "quant", "actuary", "tax", "cfo", "cdo"):
    check(f"export contains '{k}'", k in roles_by_key)
check("cfo export has accent", roles_by_key["cfo"]["accent"] == "#8b5cf6")
check("cdo export has delegate_to []",
      roles_by_key["cdo"]["delegate_to"] == sorted(_roles._DELEGATION_MATRIX["cdo"]))
check("cfo delegates to cdo", roles_by_key["cfo"]["delegate_to"] == ["cdo"])

# 3. Import validates good payload
ok, errors = _roles.import_roles(snap)
check("import valid snapshot", ok and not errors, str(errors[:2]))

# 4. Import rejects bad payloads
ok, errors = _roles.import_roles(None)
check("import rejects None", not ok and "object" in errors[0])
ok, errors = _roles.import_roles({"version": 99})
check("import rejects version", not ok)
ok, errors = _roles.import_roles({"version": 1, "roles": "nope"})
check("import rejects non-list roles", not ok)
ok, errors = _roles.import_roles({"version": 1, "roles": [{"key": "bogus"}]})
check("import rejects unknown key", not ok and any("unknown role" in e for e in errors))
ok, errors = _roles.import_roles({"version": 1, "roles": [{"key": "fpa"}]})
check("import rejects missing label", not ok and any("label" in e for e in errors))

# 5. Routes registered
rt = (SRC / "routes" / "agent.py").read_text(encoding="utf-8")
check("GET /api/roles/export route", '@router.get("/api/roles/export")' in rt)
check("POST /api/roles/import route", '@router.post("/api/roles/import")' in rt)

# 6. Files parse
for f in [SRC / "roles.py", SRC / "routes" / "agent.py"]:
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
