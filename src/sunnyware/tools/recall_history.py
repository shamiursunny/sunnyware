# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Recall past conversation events across all sessions (Part 49).

Searches the Neon events table by keyword, returns matching
{ session_key, event_type, ts, snippet } rows, most recent first.
"""
from .. import state as app_state


class RecallHistoryTool:
    name = "recall_history"
    description = (
        "Search past conversation events across all sessions. "
        "Use when the user asks 'what did we discuss earlier', "
        "'find where I mentioned X', or needs historical context."
    )
    parameters = {
        "query": {
            "type": "string",
            "description": "Keyword or phrase to search for in past messages",
            "required": True,
        },
        "days": {
            "type": "integer",
            "description": "How many days back to search (default 30)",
            "required": False,
        },
        "limit": {
            "type": "integer",
            "description": "Max results to return (default 10, max 50)",
            "required": False,
        },
    }

    async def run(self, args: dict) -> dict:
        query = (args.get("query") or "").strip()
        if not query:
            return {"error": "query is required"}
        try:
            days = max(1, min(int(args.get("days") or 30), 3650))
            limit = max(1, min(int(args.get("limit") or 10), 50))
        except (TypeError, ValueError):
            return {"error": "days and limit must be integers"}

        pool = app_state.get_pool()
        if pool is None:
            return {"error": "database unavailable"}

        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT s.session_key,
                           e.event_type,
                           e.payload->>'content' AS content,
                           e.created_at
                    FROM events e
                    JOIN sessions s ON s.id = e.session_id
                    WHERE e.created_at > NOW() - make_interval(days => $1)
                      AND e.payload->>'content' ILIKE '%' || $2 || '%'
                    ORDER BY e.created_at DESC
                    LIMIT $3
                    """,
                    days, query, limit,
                )
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}

        results = []
        for r in rows:
            content = r["content"] or ""
            results.append({
                "session": r["session_key"],
                "type": r["event_type"],
                "ts": r["created_at"].isoformat() if r["created_at"] else "",
                "snippet": content[:200] + ("..." if len(content) > 200 else ""),
            })

        return {
            "query": query,
            "days": days,
            "count": len(results),
            "results": results,
        }
