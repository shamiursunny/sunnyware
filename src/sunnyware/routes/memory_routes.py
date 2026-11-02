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
    deleted = agent_memory.delete_memory(key)
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
    agent_memory.clear_memory()
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
      {"data": {"k1": v1, "k2": v2}, "ttl": 0, "overwrite": false}
    or the full export format:
      {"version": 1, "count": N, "data": {...}}

    If `overwrite` is false (default), existing keys are skipped.
    """
    data = request.get("data") or {}
    ttl = int(request.get("ttl", 0))
    overwrite = bool(request.get("overwrite", False))
    if not isinstance(data, dict):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="data must be an object")

    existing = {e["key"] for e in agent_memory.list_memory()}
    imported = 0
    skipped = 0
    for k, v in data.items():
        if not overwrite and k in existing:
            skipped += 1
            continue
        agent_memory.write_memory(k, v, ttl=ttl)
        imported += 1
    return {"ok": True, "imported": imported, "skipped": skipped, "overwrite": overwrite}

@router.get("/api/memory/keys")
async def memory_keys():
    """Return only the keys from shared agent memory."""
    entries = agent_memory.list_memory()
    return {"count": len(entries), "keys": [e["key"] for e in entries]}

@router.post("/api/memory/rename")
async def memory_rename(request: dict):
    """Rename a key in shared agent memory.

    Body: {"old_key": str, "new_key": str}
    """
    old_key = request.get("old_key")
    new_key = request.get("new_key")
    if not old_key or not new_key:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="missing old_key or new_key")
    renamed = agent_memory.rename_memory(old_key, new_key)
    return {"ok": True, "old_key": old_key, "new_key": new_key, "renamed": renamed}

@router.post("/api/memory/touch")
async def memory_touch(request: dict):
    """Refresh timestamp and optionally extend TTL of a key without changing its value.

    Body: {"key": str, "ttl": int (optional)}
    """
    key = request.get("key")
    ttl = int(request.get("ttl", 0))
    if not key:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="missing key")
    touched = agent_memory.touch_memory(key, ttl=ttl)
    return {"ok": True, "key": key, "touched": touched, "ttl": ttl}

@router.get("/api/memory/get")
async def memory_get(key: str = ""):
    """Return a single memory entry with metadata, or 404 if missing."""
    if not key:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="missing key")
    entry = agent_memory.get_memory_entry(key)
    if entry is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="key not found or expired")
    return entry

@router.post("/api/memory/prune")
async def memory_prune():
    """Remove all expired entries from shared memory and return the count."""
    removed = agent_memory.prune_expired_memory()
    return {"ok": True, "removed": removed}

@router.post("/api/memory/ttl")
async def memory_set_ttl(request: dict):
    """Set or change the TTL of an existing key without modifying its value.

    Body: {"key": str, "ttl": int}   (ttl=0 removes expiry)
    """
    key = request.get("key")
    ttl = int(request.get("ttl", 0))
    if not key:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="missing key")
    updated = agent_memory.set_memory_ttl(key, ttl=ttl)
    return {"ok": True, "key": key, "ttl": ttl, "updated": updated}

@router.get("/api/memory/entries")
async def memory_entries(offset: int = 0, limit: int = 50):
    """Return a paginated list of memory entries.

    Query params:
        offset: number of entries to skip (default 0)
        limit: maximum entries to return (default 50, max 200)
    """
    if limit > 200:
        limit = 200
    entries = agent_memory.list_memory()
    total = len(entries)
    page = entries[offset:offset + limit]
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "count": len(page),
        "entries": page,
    }

@router.get("/api/memory/expired")
async def memory_expired():
    """List all expired entries (without removing them)."""
    entries = agent_memory.list_expired_memory()
    return {"count": len(entries), "entries": entries}

@router.get("/api/memory/count")
async def memory_count():
    """Return quick counts: total, live, and expired entries."""
    entries = agent_memory.list_memory()
    expired = agent_memory.list_expired_memory()
    total = len(entries) + len(expired)
    return {
        "total": total,
        "live": len(entries),
        "expired": len(expired),
    }

@router.post("/api/memory/cleanup")
async def memory_cleanup():
    """Prune expired entries and return before/after counts."""
    before_live = len(agent_memory.list_memory())
    before_expired = len(agent_memory.list_expired_memory())
    removed = agent_memory.prune_expired_memory()
    after_live = len(agent_memory.list_memory())
    return {
        "ok": True,
        "before_live": before_live,
        "before_expired": before_expired,
        "removed": removed,
        "after_live": after_live,
    }

@router.post("/api/memory/bulk-delete")
async def memory_bulk_delete(request: dict):
    """Delete multiple keys in one call.

    Body: {"keys": ["k1", "k2", ...]}
    """
    keys = request.get("keys") or []
    if not isinstance(keys, list):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="keys must be a list")
    result = agent_memory.bulk_delete_memory(keys)
    return {"ok": True, **result}

@router.post("/api/memory/bulk-write")
async def memory_bulk_write(request: dict):
    """Write multiple key-value pairs in one call.

    Body: {"items": {"k1": v1, "k2": v2}, "ttl": int (optional)}
    """
    items = request.get("items") or {}
    ttl = int(request.get("ttl", 0))
    if not isinstance(items, dict):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="items must be an object")
    written = agent_memory.bulk_write_memory(items, ttl=ttl)
    return {"ok": True, "written": written}

