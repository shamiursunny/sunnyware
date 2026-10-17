# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 180: HITL Approvals API."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["approvals"])

def _require_admin(req: Request):
    try:
        from .. import auth as _auth
    except Exception:
        return JSONResponse({"error": "auth unavailable"}, status_code=500)
    if not _auth.auth_enabled():
        return None
    key = req.headers.get("x-api-key") or ""
    if not key:
        authz = req.headers.get("authorization") or ""
        if authz.lower().startswith("bearer "):
            key = authz[7:].strip()
    if not key or not _auth.is_valid_key(key):
        return JSONResponse({"error": "auth_required"}, status_code=401)
    role = _auth.role_for_key(key)
    if not _auth.has_role(role, "admin"):
        return JSONResponse({"error": "forbidden", "detail": f"admin role required (got {role})"}, status_code=403)
    return None

@router.get("/api/approvals")
async def list_approvals(req: Request):
    deny = _require_admin(req)
    if deny is not None: return deny
    try:
        from .. import approval_store as _as
        pending = _as.list_pending()
        return {"count": len(pending), "approvals": pending}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@router.post("/api/approvals/{req_id}/approve")
async def approve_request(req_id: str, req: Request):
    deny = _require_admin(req)
    if deny is not None: return deny
    try:
        from .. import approval_store as _as
        ok = _as.set_status(req_id, "approved")
        return {"ok": ok, "id": req_id, "status": "approved"}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@router.post("/api/approvals/{req_id}/reject")
async def reject_request(req_id: str, req: Request):
    deny = _require_admin(req)
    if deny is not None: return deny
    try:
        from .. import approval_store as _as
        ok = _as.set_status(req_id, "rejected")
        return {"ok": ok, "id": req_id, "status": "rejected"}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
