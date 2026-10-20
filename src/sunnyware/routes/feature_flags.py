# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 224b: Feature flag routes."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from .. import feature_flags_store as _ffs

router = APIRouter(tags=["feature_flags"])


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


@router.get("/api/feature-flags")
async def list_flags(req: Request):
    d = _admin_only(req)
    if d: return d
    flags = _ffs.list_flags()
    return {"count": len(flags), "flags": flags}


@router.post("/api/feature-flags")
async def create_flag(req: Request):
    d = _admin_only(req)
    if d: return d
    try:
        body = await req.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    flag_id = (body.get("id") or "").strip()
    name = (body.get("name") or "").strip()
    description = (body.get("description") or "").strip()
    if not flag_id or not flag_id.replace("_", "").isalnum():
        return JSONResponse({"error": "invalid flag id (use letters, numbers, underscores)"}, status_code=400)
    result = _ffs.create_flag(flag_id, name, description)
    if "error" in result:
        return JSONResponse(result, status_code=400)
    return {"ok": True, "flag": result}


@router.patch("/api/feature-flags/{flag_id}")
async def update_flag(flag_id: str, req: Request):
    d = _admin_only(req)
    if d: return d
    try:
        body = await req.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    patch = {}
    if "global_pct" in body:
        try:
            pct = int(body["global_pct"])
            patch["global_pct"] = max(0, min(100, pct))
        except Exception:
            return JSONResponse({"error": "global_pct must be 0-100"}, status_code=400)
    if "enabled_orgs" in body and isinstance(body["enabled_orgs"], list):
        patch["enabled_orgs"] = [str(x) for x in body["enabled_orgs"]]
    if "enabled_plans" in body and isinstance(body["enabled_plans"], list):
        patch["enabled_plans"] = [str(x) for x in body["enabled_plans"]]
    result = _ffs.update_flag(flag_id, patch)
    return {"ok": True, "flag": result}


@router.delete("/api/feature-flags/{flag_id}")
async def delete_flag(flag_id: str, req: Request):
    d = _admin_only(req)
    if d: return d
    return {"ok": _ffs.delete_flag(flag_id)}


@router.post("/api/feature-flags/{flag_id}/override")
async def set_override(flag_id: str, req: Request):
    d = _admin_only(req)
    if d: return d
    try:
        body = await req.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    key = (body.get("key") or "").strip()
    value = bool(body.get("value", True))
    if not key:
        return JSONResponse({"error": "key required"}, status_code=400)
    return _ffs.set_override(flag_id, key, value)


@router.get("/api/feature-flags/{flag_id}/overrides")
async def get_overrides(flag_id: str, req: Request):
    d = _admin_only(req)
    if d: return d
    return {"overrides": _ffs.get_overrides(flag_id)}


@router.get("/api/feature-flags/evaluate")
async def evaluate_all(req: Request):
    """Public evaluation — called by frontend to check which features are on for this user."""
    from .. import analytics_store as _as
    user, org = _as.get_current()
    plan = ""
    if user:
        try:
            from .. import saas_store as _s
            o = _s.get_org_by_email(user)
            if o:
                plan = o.get("plan", "")
                org = o.get("id", org)
        except Exception:
            pass
    result = _ffs.evaluate_all(org_id=org, plan=plan, user_email=user)
    return {"flags": result}
