# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Session endpoints: CRUD + history + export + rewind."""

from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..runtime import ensure_pool
from .. import sessions as sessions_store
from .. import memory as memory_store
from .. import meta


router = APIRouter()


@router.get("/api/sessions")
async def list_sessions(limit: int = 20):
    await ensure_pool()
    items = await sessions_store.list_recent(limit=min(limit, 100))
    return {"count": len(items), "sessions": items}


@router.get("/api/sessions/{session_key}")
async def get_session_detail(session_key: str):
    await ensure_pool()
    sess = await sessions_store.get(session_key)
    if not sess:
        return JSONResponse({"error": "session not found"}, status_code=404)
    history = await memory_store.get_history(sess["id"], limit=50)
    return {"session": sess, "event_count": len(history), "history": history}


@router.delete("/api/sessions/{session_key}")
async def delete_session_endpoint(session_key: str):
    await ensure_pool()
    ok = await sessions_store.delete(session_key)
    return {"deleted": ok, "session_key": session_key}


@router.get("/api/sessions/{session_key}/history")
async def session_history(session_key: str, limit: int = 200):
    await ensure_pool()
    sess = await sessions_store.get(session_key)
    if not sess:
        return JSONResponse({"error": "session not found"}, status_code=404)
    events = await memory_store.get_all_events(sess["id"], max_limit=min(limit, 1000))
    return {"session": sess, "count": len(events), "events": events}


@router.get("/api/sessions/{session_key}/export")
async def session_export(session_key: str):
    await ensure_pool()
    sess = await sessions_store.get(session_key)
    if not sess:
        return JSONResponse({"error": "session not found"}, status_code=404)
    events = await memory_store.get_all_events(sess["id"], max_limit=1000)
    export = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "sunnyware_version": meta.PROJECT_VERSION,
        "session": sess,
        "event_count": len(events),
        "events": events,
    }
    return JSONResponse(
        export,
        headers={"Content-Disposition": f'attachment; filename="session-{session_key}.json"'},
    )


@router.post("/api/sessions/{session_key}/rewind")
async def session_rewind(session_key: str, req: Request):
    await ensure_pool()
    sess = await sessions_store.get(session_key)
    if not sess:
        return JSONResponse({"error": "session not found"}, status_code=404)
    try:
        body = await req.json()
    except Exception:
        body = {}
    to_event = body.get("to_event")
    if to_event is None:
        return JSONResponse({"error": "to_event (event id) required in body"}, status_code=400)
    try:
        to_event = int(to_event)
    except Exception:
        return JSONResponse({"error": "to_event must be an integer"}, status_code=400)
    deleted = await memory_store.delete_events_after(sess["id"], to_event)
    return {
        "session_key": session_key,
        "kept_up_to_event_id": to_event,
        "deleted_count": deleted,
    }
