# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 224a: Impersonation routes."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from .. import impersonation_store as _imp
from .auth import _generate_jwt

router = APIRouter(tags=["impersonation"])


def _admin_only(req: Request):
    from .. import auth as _auth
    key = req.headers.get("x-api-key") or ""
    if not key:
        authz = req.headers.get("authorization") or ""
        if authz.lower().startswith("bearer "):
            key = authz[7:].strip()
    if not _auth.auth_enabled():
        return None
    if not key or not _auth.is_valid_key(key):
        return JSONResponse({"error": "auth_required"}, status_code=401)
    if not _auth.has_role(_auth.role_for_key(key), "admin"):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return None


@router.post("/api/impersonate/start")
async def start_impersonation(req: Request):
    d = _admin_only(req)
    if d: return d
    try:
        body = await req.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    target = (body.get("target") or "").strip().lower()
    reason = (body.get("reason") or "").strip()
    if not target:
        return JSONResponse({"error": "target email required"}, status_code=400)
    # Verify target exists as a user (optional) – we'll just accept any email.
    admin_user = "admin"
    result = _imp.start(admin_user, target, reason)
    # Generate a JWT for the target user
    token = _generate_jwt(target)
    return {
        "ok": True,
        "impersonation_token": result["token"],
        "user_jwt": token,
        "target": target,
        "expires_in": result["expires_in"],
    }


@router.post("/api/impersonate/stop")
async def stop_impersonation(req: Request):
    d = _admin_only(req)
    if d: return d
    try:
        body = await req.json()
    except Exception:
        body = {}
    token = body.get("token", "")
    if not token:
        return JSONResponse({"error": "token required"}, status_code=400)
    ok = _imp.stop(token)
    return {"ok": ok}


@router.get("/api/impersonate/verify")
async def verify_impersonation(req: Request):
    token = req.headers.get("x-impersonate-token") or ""
    if not token:
        return {"valid": False}
    session = _imp.verify(token)
    if not session:
        return {"valid": False}
    return {"valid": True, "admin": session["admin"], "target": session["target"]}
