# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Search past events in memory (Neon events table)."""

from .. import state as app_state


class MemorySearchTool:
    name = "memory_search"
    description = "Search past conversation events across all sessions for a keyword or phrase."
    parameters = {
        "query": {
            "type": "string",
            "description": "Text to search for (case-insensitive substring)",
            "required": True,
        },
        "limit": {
            "type": "integer",
            "description": "Max results (default 10, max 50)",
            "required": False,
        },
    }

    async def run(self, args: dict) -> dict:
        query = str(args.get("query", "")).strip()
        if not query:
            return {"error": "query is required"}
        try:
            limit = int(args.get("limit", 10))
        except Exception:
            limit = 10
        limit = max(1, min(limit, 50))

        pool = app_state.get_pool()
        if pool is None:
            return {"error": "database unavailable"}

        pattern = f"%{query}%"
        # Part 24: scope to current tenant
        try:
            from .. import tenant as _tenant
            owner = _tenant.get_key()
        except Exception:
            owner = ""
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT e.id, e.event_type, e.payload, e.created_at, s.session_key
                    FROM events e
                    JOIN sessions s ON s.id = e.session_id
                    WHERE e.payload::text ILIKE $1
                      AND s.owner_key = $3
                    ORDER BY e.id DESC
                    LIMIT $2
                    """,
                    pattern, limit, owner,
                )
        except Exception as e:
            return {"error": f"search failed: {type(e).__name__}: {e}"}

        return {
            "query": query,
            "count": len(rows),
            "results": [
                {
                    "id": r["id"],
                    "event_type": r["event_type"],
                    "session_key": r["session_key"],
                    "payload": r["payload"],
                    "created_at": r["created_at"].isoformat(),
                }
                for r in rows
            ],
        }
