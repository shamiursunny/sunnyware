# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 212: User analytics routes."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from .. import analytics_store as _as

router = APIRouter(tags=["analytics"])


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


@router.get("/api/analytics/overview")
async def overview(req: Request, days: int = 30):
    d = _admin_only(req)
    if d: return d
    return _as.stats_overview(days=days)


@router.get("/api/analytics/users")
async def list_users(req: Request, days: int = 30):
    d = _admin_only(req)
    if d: return d
    users = _as.all_users_summary(days=days)
    return {"count": len(users), "users": users}


@router.get("/api/analytics/user/{email}")
async def user_detail(email: str, req: Request, days: int = 30):
    d = _admin_only(req)
    if d: return d
    summary = _as.user_summary(email, days=days)
    daily = _as.daily_usage(email, days=min(days, 30))
    summary["daily_usage"] = daily
    return summary


@router.get("/api/analytics/events")
async def list_events(req: Request, user: str = "", type: str = "", limit: int = 500):
    d = _admin_only(req)
    if d: return d
    items = _as.list_events(user=user, event_type=type, limit=min(limit, 5000))
    return {"count": len(items), "events": items}


@router.delete("/api/analytics/events")
async def clear_events(req: Request):
    d = _admin_only(req)
    if d: return d
    ok = _as.clear_events()
    return {"ok": ok}

@router.get("/api/analytics/debug-context")
async def debug_context(req: Request):
    """Debug: returns what user the middleware extracted from this request."""
    # No admin check — this is a read-only debug endpoint
    from .. import analytics_store as _as
    ctx_user, ctx_org = _as.get_current()
    state_user = getattr(req.state, "analytics_user", None)
    return {
        "contextvar_user": ctx_user,
        "contextvar_org": ctx_org,
        "request_state_user": state_user,
        "x_api_key_present": bool(req.headers.get("x-api-key")),
        "authorization_present": bool(req.headers.get("authorization")),
    }

