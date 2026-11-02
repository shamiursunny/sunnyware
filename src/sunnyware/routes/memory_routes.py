# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Memory inspection endpoint."""

from fastapi import APIRouter

from ..runtime import ensure_pool
from .. import sessions as sessions_store
from .. import memory as memory_store
from .. import agent_memory


router = APIRouter()


@router.get("/api/memory/context")
async def memory_context(q: str, session_id: str = None):
    await ensure_pool()
    exclude_uuid = None
    if session_id:
        sess = await sessions_store.get(session_id)
        if sess:
            exclude_uuid = sess["id"]

    events = await memory_store.select_relevant_events(
        q, exclude_session_uuid=exclude_uuid, limit=5
    )
    formatted = memory_store.format_context(events)

    return {
        "query": q,
        "exclude_session": session_id,
        "count": len(events),
        "events": events,
        "formatted_context": formatted,
    }

@router.get("/api/memory/list")
async def memory_list():
    """Return all non-expired entries from shared agent memory."""
    return {
        "count": len(agent_memory.list_memory()),
        "entries": agent_memory.list_memory(),
    }

@router.post("/api/memory/write")
async def memory_write(request: dict):
    """Write a key-value pair to shared agent memory.

    Body: {"key": str, "value": any, "ttl": int (optional)}
    """
    key = request.get("key")
    value = request.get("value")
    ttl = int(request.get("ttl", 0))
    if not key:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="missing key")
    agent_memory.write_memory(key, value, ttl=ttl)
    return {"ok": True, "key": key, "ttl": ttl}

@router.delete("/api/memory/delete/{key}")
async def memory_delete(key: str):
    """Delete a key from shared agent memory."""
    import json, os
    deleted = False
    if os.path.exists(agent_memory.MEMORY_FILE):
        with agent_memory._lock:
            try:
                with open(agent_memory.MEMORY_FILE, "r") as f:
                    data = json.load(f)
                if key in data:
                    del data[key]
                    with open(agent_memory.MEMORY_FILE, "w") as f:
                        json.dump(data, f)
                    deleted = True
            except Exception:
                pass
    return {"ok": True, "key": key, "deleted": deleted}

@router.get("/api/memory/stats")
async def memory_stats():
    """Return summary statistics for shared agent memory."""
    entries = agent_memory.list_memory()
    total = len(entries)
    with_expiry = sum(1 for e in entries if e.get("expires_at"))
    return {
        "total_entries": total,
        "with_expiry": with_expiry,
        "without_expiry": total - with_expiry,
    }

@router.get("/api/memory/search")
async def memory_search(q: str = ""):
    """Search shared agent memory for keys or values containing the query (case-insensitive)."""
    if not q.strip():
        return {"query": q, "count": 0, "entries": []}
    needle = q.strip().lower()
    entries = agent_memory.list_memory()
    matches = []
    for e in entries:
        key_s = str(e.get("key", "")).lower()
        val_s = str(e.get("value", "")).lower()
        if needle in key_s or needle in val_s:
            matches.append(e)
    return {"query": q, "count": len(matches), "entries": matches}

@router.delete("/api/memory/clear")
async def memory_clear():
    """Delete ALL entries from shared agent memory."""
    import json, os
    with agent_memory._lock:
        if os.path.exists(agent_memory.MEMORY_FILE):
            try:
                os.remove(agent_memory.MEMORY_FILE)
            except Exception:
                pass
    return {"ok": True, "cleared": True}

@router.get("/api/memory/export")
async def memory_export():
    """Export all non-expired memory entries as a JSON object."""
    entries = agent_memory.list_memory()
    return {
        "version": 1,
        "exported_at": __import__("time").time(),
        "count": len(entries),
        "data": {e["key"]: e["value"] for e in entries},
    }

@router.post("/api/memory/import")
async def memory_import(request: dict):
    """Import memory entries from a JSON backup.

    Accepts either:
      {"data": {"k1": v1, "k2": v2}, "ttl": 0}
    or the full export format:
      {"version": 1, "count": N, "data": {...}}
    """
    data = request.get("data") or {}
    ttl = int(request.get("ttl", 0))
    if not isinstance(data, dict):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="data must be an object")
    imported = 0
    for k, v in data.items():
        agent_memory.write_memory(k, v, ttl=ttl)
        imported += 1
    return {"ok": True, "imported": imported}

