# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Search the user's uploaded Library files via SQL text search."""

from .. import state as app_state
from .. import hitl_config as _hc
from .. import tenant as tenant_ctx

class SearchLibraryTool:
    name = "search_library"
    description = (
        "Search the user's uploaded documents and files in their Library. "
        "Use this when the user asks about a document they uploaded, or if you need specific information from their files."
    )
    parameters = {
        "query": {
            "type": "string",
            "description": "The keywords or phrase to search for (e.g., 'revenue', 'vacation policy').",
            "required": True,
        }
    }

    async def run(self, args: dict) -> dict:
        query = str(args.get("query", "")).strip()
        if not query:
            return {"error": "query is required"}

        # Identify the current user to scope the search
        owner = _hc.current_user_key.get() or ""
        if not owner:
            raw = tenant_ctx.get_key()
            if "." in raw and len(raw) > 20:
                try:
                    from ..routes.auth import verify_jwt
                    email = verify_jwt(raw)
                    if email: owner = f"user:{email}"
                except Exception: pass
            if not owner: owner = raw

        if not owner:
            return {"error": "Could not identify user to search library"}

        pool = app_state.get_pool()
        if not pool:
            return {"error": "Database unavailable"}

        try:
            async with pool.acquire() as conn:
                # Search by filename OR content, ignoring images
                rows = await conn.fetch(
                    """
                    SELECT name, LEFT(content, 2000) as snippet
                    FROM library_files
                    WHERE owner_key = $1
                      AND kind != 'image'
                      AND (name ILIKE $2 OR content ILIKE $2)
                    LIMIT 3
                    """,
                    owner,
                    f"%{query}%"
                )

                if not rows:
                    return {"result": "No matching documents found in the user's library."}

                formatted = []
                for r in rows:
                    formatted.append(f"File: {r['name']}\nSnippet:\n{r['snippet']}\n---")

                return {
                    "result": "\n".join(formatted),
                    "count": len(rows)
                }

        except Exception as e:
            return {"error": f"Search failed: {type(e).__name__}: {e}"}
