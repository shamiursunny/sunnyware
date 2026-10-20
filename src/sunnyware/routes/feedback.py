# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 225: User feedback collection routes."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from .. import feedback_store as _fb

router = APIRouter(tags=["feedback"])


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


@router.post("/api/feedback")
async def submit_feedback(req: Request):
    """Public endpoint: anyone can submit feedback."""
    try:
        body = await req.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    try:
        rating = int(body.get("rating", 0))
    except Exception:
        return JSONResponse({"error": "rating must be 1-5"}, status_code=400)
    if rating < 1 or rating > 5:
        return JSONResponse({"error": "rating must be 1-5"}, status_code=400)

    comment = (body.get("comment") or "").strip()
    page = (body.get("page") or "").strip()
    
    user = ""
    tok = req.headers.get("x-api-key") or ""
    if not tok:
        authz = req.headers.get("authorization") or ""
        if authz.lower().startswith("bearer "):
            tok = authz[7:].strip()
    if tok and tok != "master-admin-key" and "." in tok and len(tok) > 20:
        try:
            from .auth import verify_jwt
            user = verify_jwt(tok) or ""
        except Exception:
            pass

    entry = _fb.add(rating, comment, user=user, page=page)
    return {"ok": True, "id": entry["id"]}


@router.get("/api/admin/feedback")
async def list_feedback(req: Request, limit: int = 200):
    d = _admin_only(req)
    if d: return d
    entries = _fb.list_entries(limit=min(limit, 1000))
    return {"count": len(entries), "entries": entries, "stats": _fb.stats()}


@router.delete("/api/admin/feedback")
async def clear_feedback(req: Request):
    d = _admin_only(req)
    if d: return d
    return {"ok": _fb.clear()}
