# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Memory / event log via Neon (append-only events table)."""

import json
from typing import Optional
from . import state as app_state


async def log_event(
    session_uuid: str, event_type: str, payload: Optional[dict] = None
) -> Optional[int]:
    """Append event. Returns event id, or None if DB unavailable.

    Silently no-ops when DB/pool unavailable — never fails the request path.
    """
    pool = app_state.get_pool()
    if pool is None or not session_uuid:
        return None
    try:
        async with pool.acquire() as conn:
            event_id = await conn.fetchval(
                """
                INSERT INTO events (session_id, event_type, payload)
                VALUES ($1::uuid, $2, $3::jsonb)
                RETURNING id
                """,
                session_uuid, event_type, json.dumps(payload or {}),
            )
            return event_id
    except Exception:
        return None


async def get_history(session_uuid: str, limit: int = 50) -> list:
    """Get recent events for a session (oldest first)."""
    pool = app_state.get_pool()
    if pool is None or not session_uuid:
        return []
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, event_type, payload, created_at
                FROM events
                WHERE session_id = $1::uuid
                ORDER BY id DESC
                LIMIT $2
                """,
                session_uuid, limit,
            )
            return [
                {
                    "id": r["id"],
                    "event_type": r["event_type"],
                    "payload": r["payload"],
                    "created_at": r["created_at"].isoformat(),
                }
                for r in reversed(rows)
            ]
    except Exception:
        return []


async def count_events(session_uuid: str) -> int:
    """Count events for a session."""
    pool = app_state.get_pool()
    if pool is None or not session_uuid:
        return 0
    try:
        async with pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT COUNT(*) FROM events WHERE session_id = $1::uuid",
                session_uuid,
            ) or 0
    except Exception:
        return 0


def _extract_content(payload) -> str:
    """Extract 'content' from payload (JSONB may arrive as str or dict)."""
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            return ""
    if isinstance(payload, dict):
        return payload.get("content", "") or ""
    return ""


async def build_context(session_uuid: str, max_turns: int = 10) -> list:
    """Build OpenAI-format messages array from session history.

    Returns list of {role, content} dicts in chronological order.
    Only includes user_message and assistant_message events.
    Caps at max_turns turns (2 events per turn).
    """
    pool = app_state.get_pool()
    if pool is None or not session_uuid:
        return []
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT event_type, payload
                FROM events
                WHERE session_id = $1::uuid
                  AND event_type IN ('user_message', 'assistant_message')
                ORDER BY id DESC
                LIMIT $2
                """,
                session_uuid, max_turns * 2,
            )
        messages = []
        for r in reversed(rows):
            content = _extract_content(r["payload"])
            if not content:
                continue
            if r["event_type"] == "user_message":
                messages.append({"role": "user", "content": content})
            elif r["event_type"] == "assistant_message":
                messages.append({"role": "assistant", "content": content})
        return messages
    except Exception:
        return []


async def health_check() -> dict:
    """Verify events table accessible."""
    pool = app_state.get_pool()
    if pool is None:
        return {"status": "no_pool"}
    try:
        async with pool.acquire() as conn:
            count = await conn.fetchval("SELECT COUNT(*) FROM events")
            return {"status": "ok", "count": count}
    except Exception as e:
        return {"status": "error", "error": f"{type(e).__name__}: {e}"}
