# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 221a: Webhook routes."""

import time
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from .. import webhooks_store as _ws

router = APIRouter(tags=["webhooks"])

EVENTS = [
    "user.signup",
    "user.login",
    "plan.upgraded",
    "plan.cancelled",
    "provider.cooldown",
    "error",
    "*",
]


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


@router.get("/api/webhooks/events")
async def list_events(req: Request):
    d = _admin_only(req)
    if d: return d
    return {"events": EVENTS}


@router.get("/api/webhooks/endpoints")
async def list_endpoints(req: Request):
    d = _admin_only(req)
    if d: return d
    endpoints = _ws.list_endpoints()
    return {"count": len(endpoints), "endpoints": endpoints}


@router.post("/api/webhooks/endpoints")
async def add_endpoint(req: Request):
    d = _admin_only(req)
    if d: return d
    try:
        body = await req.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    url = (body.get("url") or "").strip()
    name = (body.get("name") or "").strip()
    events = body.get("events") or ["*"]
    secret = body.get("secret") or ""
    if not url.startswith(("http://", "https://")):
        return JSONResponse({"error": "url must start with http(s)://"}, status_code=400)
    if not isinstance(events, list):
        return JSONResponse({"error": "events must be list"}, status_code=400)
    ep = _ws.add_endpoint(url, name, events, secret)
    return {"ok": True, "endpoint": ep}


@router.delete("/api/webhooks/endpoints/{eid}")
async def delete_endpoint(eid: str, req: Request):
    d = _admin_only(req)
    if d: return d
    ok = _ws.delete_endpoint(eid)
    return {"ok": ok}


@router.post("/api/webhooks/endpoints/{eid}/toggle")
async def toggle_endpoint(eid: str, req: Request):
    d = _admin_only(req)
    if d: return d
    ok = _ws.toggle_endpoint(eid)
    return {"ok": ok}


@router.post("/api/webhooks/endpoints/{eid}/test")
async def test_endpoint(eid: str, req: Request):
    d = _admin_only(req)
    if d: return d
    endpoints = _ws.list_endpoints()
    ep = next((e for e in endpoints if e.get("id") == eid), None)
    if not ep:
        return JSONResponse({"error": "endpoint not found"}, status_code=404)
    fired = _ws.fire_event("test.ping", {"message": "Test from Sunnyware admin", "endpoint_id": eid})
    return {"ok": True, "fired": fired, "note": "Check delivery log in a few seconds"}


@router.get("/api/webhooks/deliveries")
async def list_deliveries(req: Request, limit: int = 100):
    d = _admin_only(req)
    if d: return d
    deliveries = _ws.list_deliveries(limit=min(limit, 500))
    return {"count": len(deliveries), "deliveries": deliveries}


@router.delete("/api/webhooks/deliveries")
async def clear_deliveries(req: Request):
    d = _admin_only(req)
    if d: return d
    return {"ok": _ws.clear_deliveries()}
