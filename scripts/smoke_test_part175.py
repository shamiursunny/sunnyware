# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 175 smoke - SSOReady integration (Phase 1)."""
from pathlib import Path
import ast, os, sys, tempfile

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" +
          (f"  ({detail})" if detail else ""))

print("=== Part 175: SSOReady integration (Phase 1) ===")

# ─── Files exist ───
for f in ("user_store.py", "sso.py", "routes/sso.py"):
    p = SRC / f
    check(f"{f} exists", p.exists())

# ─── user_store has all required functions ───
us = (SRC / "user_store.py").read_text(encoding="utf-8")
for fn in ("def get(", "def upsert(", "def delete(", "def list_all(",
           "def role_for_api_key(", "def email_for_api_key(",
           "def has_any_users("):
    check(f"user_store: {fn}", fn in us)

# ─── sso.py ───
ss = (SRC / "sso.py").read_text(encoding="utf-8")
for fn in ("def enabled(", "async def get_redirect_url(",
           "async def redeem(", "def status("):
    check(f"sso: {fn}", fn in ss)
check("sso: uses httpx", "import httpx" in ss)
check("sso: env keys configured",
      "SCALEKIT_ENVIRONMENT_URL" in ss
      and "SCALEKIT_CLIENT_ID" in ss
      and "SCALEKIT_CLIENT_SECRET" in ss)

# ─── routes/sso.py ───
rt = (SRC / "routes" / "sso.py").read_text(encoding="utf-8")
for ep in ('"/sso/status"', '"/sso/login/{org_external_id}"',
           '"/sso/callback"', '"/sso/users"',
           '"/sso/users/delete"'):
    check(f"route: {ep}", ep in rt)
check("routes: 501 when disabled", "501" in rt)
check("routes: RedirectResponse used", "RedirectResponse" in rt)
check("routes: HTMLResponse used", "HTMLResponse" in rt)

# ─── auth.py wired ───
at = (SRC / "auth.py").read_text(encoding="utf-8")
check("auth: role_for_key checks user_store",
      "user_store as _us" in at and "role_for_api_key" in at)
check("auth: is_valid_key checks user_store",
      "is_valid_key" in at and "user_store" in at)

# ─── main.py wired ───
mt = (SRC / "main.py").read_text(encoding="utf-8")
check("main: sso_routes imported",
      "from .routes import sso as sso_routes" in mt)
check("main: sso router included",
      "include_router(sso_routes.router" in mt)

# ─── Functional: user_store ───
tmpdir = tempfile.mkdtemp(prefix="sso_smoke_")
os.environ["SUNNYWARE_USERS_STORE"] = os.path.join(tmpdir, "users.json")
sys.path.insert(0, str(SRC.parent))
from sunnyware import user_store as US

check("empty store", US.has_any_users() is False)
check("get missing returns None", US.get("nobody@x.com") is None)

# Create user
rec = US.upsert(email="alice@acme.com", org_id="acme", role="admin")
check("upsert creates user", rec.get("email") == "alice@acme.com")
check("upsert issues api_key", rec.get("api_key", "").startswith("sk_"))
check("upsert sets org_id", rec.get("org_id") == "acme")
check("upsert sets role", rec.get("role") == "admin")

# Get back
got = US.get("alice@acme.com")
check("get returns same api_key",
      got and got.get("api_key") == rec.get("api_key"))

# Case-insensitive email
check("email is case-insensitive",
      US.get("ALICE@ACME.COM") is not None)

# Update role
US.upsert(email="alice@acme.com", role="analyst")
check("upsert updates role", US.get("alice@acme.com").get("role") == "analyst")

# Reverse lookup by key
check("role_for_api_key works",
      US.role_for_api_key(rec["api_key"]) == "analyst")
check("email_for_api_key works",
      US.email_for_api_key(rec["api_key"]) == "alice@acme.com")
check("role_for_api_key miss returns None",
      US.role_for_api_key("sk_nonexistent") is None)

# List (redacted)
lst = US.list_all()
check("list returns 1", len(lst) == 1)
check("list redacts api_key",
      "api_key" not in lst[0] and "api_key_preview" in lst[0])

# Delete
ok = US.delete("alice@acme.com")
check("delete succeeds", ok is True)
check("deleted user gone", US.get("alice@acme.com") is None)
check("delete nonexistent returns False",
      US.delete("nobody@x.com") is False)

# ─── Functional: sso helper ───
os.environ.pop("SCALEKIT_ENVIRONMENT_URL", None)
os.environ.pop("SCALEKIT_CLIENT_ID", None)
os.environ.pop("SCALEKIT_CLIENT_SECRET", None)
from sunnyware import sso as SSO
check("sso disabled without key", SSO.enabled() is False)
check("sso status has_client_id=False",
      SSO.status().get("has_client_id") is False)

# ─── auth integration ───
from sunnyware import auth as AUTH
rec2 = US.upsert(email="bob@x.com", role="readonly")
check("auth.role_for_key returns SSO role",
      AUTH.role_for_key(rec2["api_key"]) == "readonly")
check("auth.is_valid_key accepts SSO key",
      AUTH.is_valid_key(rec2["api_key"]) is True)
check("auth.is_valid_key rejects unknown",
      AUTH.is_valid_key("sk_unknown") is False)
US.delete("bob@x.com")

# ─── Files parse ───
for fp in [SRC / "user_store.py", SRC / "sso.py",
           SRC / "routes" / "sso.py", SRC / "auth.py", SRC / "main.py"]:
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
