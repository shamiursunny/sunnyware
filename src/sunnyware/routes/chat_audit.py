# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 221b: Chat audit routes."""

import asyncio
import csv
import io
import time
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from .. import chat_audit_store as _cas

router = APIRouter(tags=["chat_audit"])


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


@router.get("/api/chat-audit/stats")
async def stats(req: Request):
    d = _admin_only(req)
    if d: return d
    return _cas.stats()


@router.get("/api/chat-audit/messages")
async def list_messages(req: Request, user: str = "", org_id: str = "", search: str = "", limit: int = 200):
    d = _admin_only(req)
    if d: return d
    items = _cas.list_messages(user=user, org_id=org_id, search=search, limit=min(limit, 1000))
    return {"count": len(items), "messages": items}


@router.get("/api/chat-audit/flagged")
async def list_flagged(req: Request, limit: int = 200):
    d = _admin_only(req)
    if d: return d
    items = _cas.list_flagged(limit=min(limit, 1000))
    return {"count": len(items), "messages": items}


@router.post("/api/chat-audit/messages/{message_id}/flag")
async def flag_message(message_id: str, req: Request):
    d = _admin_only(req)
    if d: return d
    try:
        body = await req.json()
    except Exception:
        body = {}
    result = _cas.flag_message(
        message_id,
        flagged=bool(body.get("flagged", True)),
        reason=body.get("reason", ""),
        reviewer="admin",
    )
    return result


@router.post("/api/chat-audit/log")
async def log_chat_message(req: Request):
    """Called by frontend to log user/assistant messages for audit trail."""
    try:
        body = await req.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    
    # Extract user from JWT
    from .. import analytics_store as _as
    user, org = _as.get_current()
    if not user:
        # Fallback: read from body
        user = (body.get("user") or "").lower().strip()
    
    role = (body.get("role") or "user").strip()
    content = (body.get("content") or "").strip()
    session_id = (body.get("session_id") or "").strip()
    
    if not content:
        return JSONResponse({"error": "content required"}, status_code=400)
    if role not in ("user", "assistant", "system"):
        return JSONResponse({"error": "invalid role"}, status_code=400)
    
    # Part 228: offload sync file I/O to a thread to avoid blocking the event loop
    entry = await asyncio.to_thread(
        _cas.log_message, user, role, content, org_id=org, session_id=session_id
    )
    return {"ok": True, "id": entry["id"]}


@router.get("/api/chat-audit/export")
async def export_csv(req: Request, user: str = "", org_id: str = "", redact: bool = False):
    d = _admin_only(req)
    if d: return d
    messages = _cas.export_messages(user=user, org_id=org_id, limit=5000)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["timestamp", "user", "role", "content", "org_id"])
    for m in messages:
        content = m.get("content", "")
        if redact:
            content = "***REDACTED***"
        writer.writerow([
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(m.get("ts", 0))),
            m.get("user", ""),
            m.get("role", ""),
            content,
            m.get("org_id", ""),
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="chat_audit.csv"'},
    )
