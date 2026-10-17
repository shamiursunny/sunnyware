# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 175: SSOReady entry/callback routes.

Endpoints:
  GET  /sso/status                      public - enabled/disabled
  GET  /sso/login/{org_external_id}     browser - redirect to IdP
  GET  /sso/callback?code=...           browser - exchange + show api key
  GET  /sso/users                       admin  - list users
  POST /sso/users                       admin  - create user manually
  POST /sso/users/delete                admin  - delete user

Admin routes use auth.role_for_key() so both SUNNYWARE_API_ROLES env
keys AND SSO-issued api keys work for admin access.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse


router = APIRouter(tags=["sso"])


def _extract_key(req: Request) -> str:
    """Mirror auth.extract_key_from_headers logic (defensive copy)."""
    key = req.headers.get("x-api-key") or ""
    if key:
        return key.strip()
    authz = req.headers.get("authorization") or ""
    if authz.lower().startswith("bearer "):
        return authz[7:].strip()
    return ""


def _require_admin(req: Request):
    """Return None if admin, else a 403 JSONResponse."""
    try:
        from .. import auth as _auth
    except Exception:
        return JSONResponse({"error": "auth unavailable"},
                            status_code=500)
    if not _auth.auth_enabled():
        # Auth off — same policy as rest of app (open)
        return None
    key = _extract_key(req)
    if not key:
        return JSONResponse(
            {"error": "auth_required",
             "detail": "X-API-Key or Authorization: Bearer required"},
            status_code=401,
        )
    role = _auth.role_for_key(key)
    if not _auth.has_role(role, "admin"):
        return JSONResponse(
            {"error": "forbidden",
             "detail": f"admin role required (got {role})"},
            status_code=403,
        )
    return None


@router.get("/sso/status")
async def sso_status():
    """Public: is SSO enabled?"""
    try:
        from .. import sso as _sso
        from .. import user_store as _us
        return {
            **_sso.status(),
            "users_configured": _us.has_any_users(),
        }
    except Exception as e:
        return JSONResponse({"error": f"{type(e).__name__}: {e}"},
                            status_code=500)


@router.get("/sso/login/{org_external_id}")
async def sso_login(org_external_id: str):
    """Start SAML flow: redirect the browser to the IdP."""
    try:
        from .. import sso as _sso
    except Exception as e:
        return JSONResponse({"error": f"{type(e).__name__}: {e}"},
                            status_code=500)
    if not _sso.enabled():
        return JSONResponse(
            {"error": "sso_disabled",
             "detail": "Set SSOREADY_API_KEY to enable SSO"},
            status_code=501,
        )
    r = await _sso.get_redirect_url(org_external_id)
    if not r.get("ok"):
        return JSONResponse({"error": r.get("error", "unknown")},
                            status_code=502)
    return RedirectResponse(r["redirect_url"], status_code=302)


@router.get("/sso/callback", response_class=HTMLResponse)
async def sso_callback(saml_access_code: str = "", code: str = ""):
    """SAML response handler. Exchanges code, upserts user, shows key."""
    try:
        from .. import sso as _sso
        from .. import user_store as _us
    except Exception as e:
        return HTMLResponse(f"<h1>SSO error</h1><pre>{e}</pre>",
                            status_code=500)
    if not _sso.enabled():
        return HTMLResponse(
            "<h1>SSO not configured</h1>"
            "<p>Set <code>SSOREADY_API_KEY</code> to enable.</p>",
            status_code=501,
        )
    access_code = saml_access_code or code
    if not access_code:
        return HTMLResponse(
            "<h1>Missing SAML access code</h1>"
            "<p>Query params <code>saml_access_code</code> or "
            "<code>code</code> are required.</p>",
            status_code=400,
        )
    r = await _sso.redeem(access_code)
    if not r.get("ok"):
        return HTMLResponse(
            f"<h1>SSO failed</h1><pre>{r.get('error', 'unknown')}</pre>",
            status_code=502,
        )
    email = r["email"]
    org_id = r.get("org_id", "")
    existing = _us.get(email)
    # First-time users default to analyst; admins can promote later
    role = existing.get("role") if existing else "analyst"
    record = _us.upsert(email=email, org_id=org_id, role=role)
    api_key = record.get("api_key", "")
    return HTMLResponse(f"""<!doctype html>
<html><head><meta charset="utf-8">
<title>Sunnyware - Signed In</title>
<style>
 body{{background:#0b0d12;color:#e7ecf3;font:14px/1.5 system-ui;
      padding:40px;max-width:640px;margin:0 auto}}
 h1{{font-size:22px;margin:0 0 20px}}
 .ok{{color:#2ecc71;font-size:12px;letter-spacing:.4px;
      text-transform:uppercase;border:1px solid #2ecc71;padding:3px 10px;
      border-radius:14px;display:inline-block;margin-bottom:16px}}
 code,.key{{font-family:ui-monospace,Menlo,monospace;font-size:13px;
      background:#1b202b;padding:10px 14px;border-radius:6px;
      display:block;word-break:break-all;margin:8px 0;
      border:1px solid #232a38}}
 .muted{{color:#8892a6;font-size:12px;margin-top:20px}}
 a{{color:#5b8def;text-decoration:none}}
 a:hover{{text-decoration:underline}}
 button{{background:#5b8def;color:#fff;border:0;padding:8px 16px;
      border-radius:6px;font:inherit;cursor:pointer;font-size:13px}}
</style></head><body>
<span class="ok">Signed in</span>
<h1>Welcome, {email}</h1>
<p>Your API key (copy it now — it will not be shown again):</p>
<code class="key" id="key">{api_key}</code>
<button onclick="navigator.clipboard.writeText(
  document.getElementById('key').textContent);
  this.textContent='Copied!';
  setTimeout(()=>this.textContent='Copy',1500);">Copy</button>
<p class="muted">Send this key as <code>X-API-Key: &lt;key&gt;</code>
 or <code>Authorization: Bearer &lt;key&gt;</code> on every request.</p>
<p class="muted"><a href="/ui">Go to app &rarr;</a></p>
</body></html>""",
                         status_code=200)


@router.get("/sso/users")
async def sso_users_list(req: Request):
    """Admin: list all SSO users (api_key redacted)."""
    deny = _require_admin(req)
    if deny is not None:
        return deny
    try:
        from .. import user_store as _us
        return {"count": len(_us.list_all()),
                "users": _us.list_all()}
    except Exception as e:
        return JSONResponse({"error": f"{type(e).__name__}: {e}"},
                            status_code=500)


@router.post("/sso/users")
async def sso_users_create(req: Request):
    """Admin: create a user manually (e.g. seed an admin)."""
    deny = _require_admin(req)
    if deny is not None:
        return deny
    try:
        body = await req.json()
    except Exception:
        body = {}
    email = (body.get("email") or "").strip().lower()
    role = (body.get("role") or "analyst").strip().lower()
    if not email:
        return JSONResponse({"error": "email required"}, status_code=400)
    if role not in ("admin", "analyst", "readonly"):
        return JSONResponse(
            {"error": f"invalid role: {role}"}, status_code=400)
    try:
        from .. import user_store as _us
        record = _us.upsert(email=email, role=role)
        return {"ok": True, "user": record}
    except Exception as e:
        return JSONResponse({"error": f"{type(e).__name__}: {e}"},
                            status_code=500)


@router.post("/sso/users/delete")
async def sso_users_delete(req: Request):
    """Admin: delete a user."""
    deny = _require_admin(req)
    if deny is not None:
        return deny
    try:
        body = await req.json()
    except Exception:
        body = {}
    email = (body.get("email") or "").strip().lower()
    if not email:
        return JSONResponse({"error": "email required"}, status_code=400)
    try:
        from .. import user_store as _us
        ok = _us.delete(email)
        return {"ok": ok, "email": email}
    except Exception as e:
        return JSONResponse({"error": f"{type(e).__name__}: {e}"},
                            status_code=500)
