# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Memory inspection endpoint."""

from fastapi import APIRouter

from ..runtime import ensure_pool
from .. import sessions as sessions_store
from .. import memory as memory_store


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
