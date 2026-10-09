# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Session cleanup job — deletes sessions older than TTL (across all tenants)."""

import os

from .. import state as app_state


async def run():
    try:
        ttl_days = int(os.getenv("SUNNYWARE_SESSION_TTL_DAYS", "30") or 30)
    except Exception:
        ttl_days = 30
    if ttl_days <= 0:
        return {"skipped": True, "reason": "TTL <= 0"}

    pool = app_state.get_pool()
    if pool is None:
        return {"skipped": True, "reason": "no pool"}

    try:
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM sessions WHERE updated_at < NOW() - make_interval(days => $1)",
                ttl_days,
            )
        deleted = int(result.split()[1]) if result.startswith("DELETE") else 0
        return {"deleted": deleted, "ttl_days": ttl_days}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}
