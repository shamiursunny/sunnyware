# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Session CRUD via Neon — scoped by tenant (API key)."""

import json
from typing import Optional

from . import state as app_state
from . import tenant as tenant_ctx


def _owner() -> str:
    """Current tenant key. Empty string when auth is off (legacy shared)."""
    return tenant_ctx.get_key()


async def get_or_create(session_key: str, metadata: Optional[dict] = None) -> Optional[str]:
    """Idempotent: returns session UUID as string, or None if DB unavailable."""
    pool = app_state.get_pool()
    if pool is None:
        return None
    owner = _owner()
    meta_json = json.dumps(metadata or {})
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO sessions (session_key, owner_key, metadata)
                VALUES ($1, $2, $3::jsonb)
                ON CONFLICT (session_key, owner_key) DO UPDATE
                    SET updated_at = NOW()
                RETURNING id
                """,
                session_key, owner, meta_json,
            )
            return str(row["id"]) if row else None
    except Exception:
        return None


async def get(session_key: str) -> Optional[dict]:
    """Fetch session by key scoped to current tenant."""
    pool = app_state.get_pool()
    if pool is None:
        return None
    owner = _owner()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, session_key, owner_key, created_at, updated_at, metadata
                FROM sessions
                WHERE session_key = $1 AND owner_key = $2
                """,
                session_key, owner,
            )
            if not row:
                return None
            return {
                "id": str(row["id"]),
                "session_key": row["session_key"],
                "owner_key": row["owner_key"],
                "created_at": row["created_at"].isoformat(),
                "updated_at": row["updated_at"].isoformat(),
                "metadata": row["metadata"],
            }
    except Exception:
        return None


async def list_recent(limit: int = 20) -> list:
    """List recent sessions (current tenant only)."""
    pool = app_state.get_pool()
    if pool is None:
        return []
    owner = _owner()
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, session_key, owner_key, created_at, updated_at, metadata
                FROM sessions
                WHERE owner_key = $1
                ORDER BY updated_at DESC
                LIMIT $2
                """,
                owner, limit,
            )
            return [
                {
                    "id": str(r["id"]),
                    "session_key": r["session_key"],
                    "owner_key": r["owner_key"],
                    "created_at": r["created_at"].isoformat(),
                    "updated_at": r["updated_at"].isoformat(),
                    "metadata": r["metadata"],
                }
                for r in rows
            ]
    except Exception:
        return []


async def delete(session_key: str) -> bool:
    """Delete session (current tenant only); cascades to events."""
    pool = app_state.get_pool()
    if pool is None:
        return False
    owner = _owner()
    try:
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM sessions WHERE session_key = $1 AND owner_key = $2",
                session_key, owner,
            )
            return result.startswith("DELETE 1")
    except Exception:
        return False


async def health_check() -> dict:
    """Verify sessions table accessible."""
    pool = app_state.get_pool()
    if pool is None:
        return {"status": "no_pool"}
    try:
        async with pool.acquire() as conn:
            count = await conn.fetchval("SELECT COUNT(*) FROM sessions")
            return {"status": "ok", "count": count}
    except Exception as e:
        return {"status": "error", "error": f"{type(e).__name__}: {e}"}