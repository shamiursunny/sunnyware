# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Session CRUD via Neon Postgres (asyncpg pool from state.py)."""

import json
from typing import Optional
from . import state as app_state


async def get_or_create(session_key: str, metadata: Optional[dict] = None) -> Optional[str]:
    """Idempotent: returns session UUID as string, or None if DB unavailable."""
    pool = app_state.get_pool()
    if pool is None:
        return None

    meta_json = json.dumps(metadata or {})
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO sessions (session_key, metadata)
                VALUES ($1, $2::jsonb)
                ON CONFLICT (session_key) DO UPDATE
                    SET updated_at = NOW()
                RETURNING id
                """,
                session_key, meta_json,
            )
            return str(row["id"]) if row else None
    except Exception:
        return None


async def get(session_key: str) -> Optional[dict]:
    """Fetch session by key. Returns dict or None."""
    pool = app_state.get_pool()
    if pool is None:
        return None
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, session_key, created_at, updated_at, metadata FROM sessions WHERE session_key = $1",
                session_key,
            )
            if not row:
                return None
            return {
                "id": str(row["id"]),
                "session_key": row["session_key"],
                "created_at": row["created_at"].isoformat(),
                "updated_at": row["updated_at"].isoformat(),
                "metadata": row["metadata"],
            }
    except Exception:
        return None


async def list_recent(limit: int = 20) -> list:
    """List recent sessions."""
    pool = app_state.get_pool()
    if pool is None:
        return []
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, session_key, created_at, updated_at, metadata
                FROM sessions
                ORDER BY updated_at DESC
                LIMIT $1
                """,
                limit,
            )
            return [
                {
                    "id": str(r["id"]),
                    "session_key": r["session_key"],
                    "created_at": r["created_at"].isoformat(),
                    "updated_at": r["updated_at"].isoformat(),
                    "metadata": r["metadata"],
                }
                for r in rows
            ]
    except Exception:
        return []


async def delete(session_key: str) -> bool:
    """Delete session (cascade removes events)."""
    pool = app_state.get_pool()
    if pool is None:
        return False
    try:
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM sessions WHERE session_key = $1", session_key
            )
            return result.startswith("DELETE 1")
    except Exception:
        return False


async def health_check() -> dict:
    """Verify sessions table is accessible."""
    pool = app_state.get_pool()
    if pool is None:
        return {"status": "no_pool"}
    try:
        async with pool.acquire() as conn:
            count = await conn.fetchval("SELECT COUNT(*) FROM sessions")
            return {"status": "ok", "count": count}
    except Exception as e:
        return {"status": "error", "error": f"{type(e).__name__}: {e}"}
