# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 207: WorkOS Admin Panel routes."""

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["workos-admin"])

def _require_admin(req: Request):
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
    role = _auth.role_for_key(key)
    if not _auth.has_role(role, "admin"):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return None


@router.get("/api/admin/workos/users")
async def list_workos_users(req: Request):
    """List all users from WorkOS User Management API."""
    deny = _require_admin(req)
    if deny: return deny
    
    import os
    api_key = os.getenv("WORKOS_API_KEY", "")
    if not api_key:
        return JSONResponse({"error": "WORKOS_API_KEY not set"}, status_code=501)

    try:
        async with httpx.AsyncClient(timeout=15.0) as cli:
            r = await cli.get(
                "https://api.workos.com/user_management/users",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if r.status_code != 200:
                return JSONResponse({"error": r.text[:300]}, status_code=r.status_code)
            data = r.json()
            return {"users": data.get("data", []), "list_metadata": data.get("list_metadata", {})}
    except Exception as e:
        return JSONResponse({"error": f"{type(e).__name__}: {e}"}, status_code=500)


@router.get("/api/admin/workos/organizations")
async def list_workos_orgs(req: Request):
    """List all organizations from WorkOS."""
    deny = _require_admin(req)
    if deny: return deny
    
    import os
    api_key = os.getenv("WORKOS_API_KEY", "")
    if not api_key:
        return JSONResponse({"error": "WORKOS_API_KEY not set"}, status_code=501)

    try:
        async with httpx.AsyncClient(timeout=15.0) as cli:
            r = await cli.get(
                "https://api.workos.com/organizations",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if r.status_code != 200:
                return JSONResponse({"error": r.text[:300]}, status_code=r.status_code)
            data = r.json()
            return {"organizations": data.get("data", []), "list_metadata": data.get("list_metadata", {})}
    except Exception as e:
        return JSONResponse({"error": f"{type(e).__name__}: {e}"}, status_code=500)
