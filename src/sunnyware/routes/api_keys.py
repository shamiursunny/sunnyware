# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 221a: API key management routes."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from .. import api_keys_store as _aks

router = APIRouter(tags=["api_keys"])


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


@router.get("/api/api-keys")
async def list_keys(req: Request, org_id: str = "", user_email: str = ""):
    d = _admin_only(req)
    if d: return d
    keys = _aks.list_keys(org_id=org_id or None, user_email=user_email or None)
    return {"count": len(keys), "keys": keys}


@router.post("/api/api-keys")
async def create_key(req: Request):
    d = _admin_only(req)
    if d: return d
    try:
        body = await req.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    name = (body.get("name") or "").strip()
    org_id = (body.get("org_id") or "").strip()
    user_email = (body.get("user_email") or "").strip()
    scopes = body.get("scopes") or ["read"]
    rate_limit = int(body.get("rate_limit_per_min") or 60)
    if not name:
        return JSONResponse({"error": "name required"}, status_code=400)
    if not isinstance(scopes, list):
        return JSONResponse({"error": "scopes must be list"}, status_code=400)
    result = _aks.create_key(org_id, user_email, name, scopes, rate_limit)
    return {"ok": True, "key": result}


@router.post("/api/api-keys/{key_id}/revoke")
async def revoke_key(key_id: str, req: Request):
    d = _admin_only(req)
    if d: return d
    ok = _aks.revoke_key(key_id)
    return {"ok": ok}


@router.delete("/api/api-keys/{key_id}")
async def delete_key(key_id: str, req: Request):
    d = _admin_only(req)
    if d: return d
    ok = _aks.delete_key(key_id)
    return {"ok": ok}
