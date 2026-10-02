# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Application state — asyncpg pool + lazy init."""

import asyncio
import os
import sys
from typing import Optional
import asyncpg


if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except AttributeError:
        pass


_pool: Optional[asyncpg.Pool] = None
_last_error: Optional[str] = None


async def init_pool(dsn: Optional[str] = None) -> bool:
    """Initialize asyncpg connection pool. Idempotent."""
    global _pool, _last_error
    if _pool is not None:
        return True

    url = dsn or os.getenv("NEON_DATABASE_URL")
    if not url:
        _last_error = "NEON_DATABASE_URL not set"
        print(f"[state] {_last_error}", file=sys.stderr)
        return False

    # Log masked URL info
    try:
        host = url.split("@")[1].split("/")[0] if "@" in url else "?"
        print(f"[state] init_pool url_len={len(url)} host={host}", file=sys.stderr)
    except Exception:
        pass

    try:
        _pool = await asyncio.wait_for(
            asyncpg.create_pool(
                url,
                min_size=1,          # Force immediate connection — catch errors early
                max_size=5,
                command_timeout=30,
                statement_cache_size=0,
                timeout=15,
            ),
            timeout=20,
        )
        print("[state] pool created OK", file=sys.stderr)
        _last_error = None
        return True
    except Exception as e:
        _last_error = f"{type(e).__name__}: {e}"
        print(f"[state] pool init failed: {_last_error}", file=sys.stderr)
        _pool = None
        return False


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        try:
            await _pool.close()
        except Exception:
            pass
        _pool = None


def get_pool() -> Optional[asyncpg.Pool]:
    return _pool


def get_last_error() -> Optional[str]:
    return _last_error


async def health_check() -> dict:
    """Return health info for /health/ready endpoint."""
    if _pool is None:
        return {"status": "not_initialized", "error": _last_error or "pool is None"}

    try:
        async with _pool.acquire() as conn:
            version = await conn.fetchval("SELECT version()")
            return {
                "status": "ok",
                "version": version.split(",")[0] if version else "unknown",
            }
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        print(f"[state] health_check failed: {err}", file=sys.stderr)
        return {"status": "error", "error": err}
