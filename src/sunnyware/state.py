# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Application state — asyncpg pool + lazy init."""

import asyncio
import os
import sys
from typing import Optional
import asyncpg


# Windows event loop fix for asyncpg
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except AttributeError:
        pass


_pool: Optional[asyncpg.Pool] = None


async def init_pool(dsn: Optional[str] = None) -> bool:
    """Initialize asyncpg connection pool. Idempotent."""
    global _pool
    if _pool is not None:
        return True

    url = dsn or os.getenv("NEON_DATABASE_URL")
    if not url:
        return False

    try:
        _pool = await asyncio.wait_for(
            asyncpg.create_pool(
                url,
                min_size=0,          # lazy — no connections until needed
                max_size=5,
                command_timeout=30,
                statement_cache_size=0,
                timeout=15,
            ),
            timeout=20,
        )
        return True
    except Exception as e:
        print(f"[state] pool init failed: {type(e).__name__}: {e}", file=sys.stderr)
        _pool = None
        return False


async def close_pool() -> None:
    """Close pool on shutdown."""
    global _pool
    if _pool is not None:
        try:
            await _pool.close()
        except Exception:
            pass
        _pool = None


def get_pool() -> Optional[asyncpg.Pool]:
    """Return current pool or None."""
    return _pool


async def health_check() -> dict:
    """Return health info for /health/ready endpoint."""
    if _pool is None:
        return {"status": "not_initialized"}

    try:
        async with _pool.acquire() as conn:
            version = await conn.fetchval("SELECT version()")
            return {
                "status": "ok",
                "version": version.split(",")[0] if version else "unknown",
            }
    except Exception as e:
        return {"status": "error", "error": str(e)}
