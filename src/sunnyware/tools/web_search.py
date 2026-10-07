# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Web search tool — DuckDuckGo (no API key required)."""

import asyncio

try:
    from ddgs import DDGS
    _DDGS_AVAILABLE = True
except ImportError:
    try:
        from duckduckgo_search import DDGS
        _DDGS_AVAILABLE = True
    except ImportError:
        DDGS = None
        _DDGS_AVAILABLE = False


def _sync_search(query: str, max_results: int) -> list:
    """Run synchronous DuckDuckGo search (called via asyncio.to_thread)."""
    with DDGS() as ddgs:
        return list(ddgs.text(query, max_results=max_results))


class WebSearchTool:
    name = "web_search"
    description = (
        "Search the web for current information. Returns top results with "
        "title, URL, and snippet. Use for facts, news, current events."
    )
    parameters = {
        "query": {
            "type": "string",
            "description": "Search query (e.g. 'latest AI research')",
            "required": True,
        },
        "max_results": {
            "type": "integer",
            "description": "Max results (1-10, default 5)",
            "required": False,
        },
    }

    async def run(self, args: dict) -> dict:
        if not _DDGS_AVAILABLE:
            return {"error": "ddgs package not installed (pip install ddgs)"}

        query = str(args.get("query", "")).strip()
        if not query:
            return {"error": "query is required"}
        if len(query) > 500:
            return {"error": "query too long (max 500 chars)"}

        try:
            max_results = int(args.get("max_results", 5))
        except Exception:
            max_results = 5
        max_results = max(1, min(max_results, 10))

        try:
            results = await asyncio.wait_for(
                asyncio.to_thread(_sync_search, query, max_results),
                timeout=20.0,
            )
        except asyncio.TimeoutError:
            return {"error": "search timed out after 20s"}
        except Exception as e:
            return {"error": f"search failed: {type(e).__name__}: {e}"}

        cleaned = []
        for r in results or []:
            cleaned.append({
                "title": (r.get("title") or "")[:200],
                "url": (r.get("href") or r.get("url") or "")[:500],
                "snippet": (r.get("body") or r.get("snippet") or "")[:400],
            })

        return {
            "query": query,
            "count": len(cleaned),
            "results": cleaned,
        }
