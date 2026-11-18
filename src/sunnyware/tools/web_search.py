# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Web search tool - DuckDuckGo (no API key required)."""

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


def _sync_search(query: str, max_results: int, backend: str) -> list:
    """Run synchronous DuckDuckGo search (called via asyncio.to_thread)."""
    with DDGS() as ddgs:
        return list(ddgs.text(query, max_results=max_results, backend=backend))


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

    async def run(self, args: dict) -> str:
        if not _DDGS_AVAILABLE:
            return "Error: ddgs package not installed (pip install ddgs)"

        query = str(args.get("query", "")).strip()
        if not query:
            return "Error: query is required"
        if len(query) > 500:
            return "Error: query too long (max 500 chars)"

        try:
            max_results = int(args.get("max_results", 5))
        except Exception:
            max_results = 5
        max_results = max(1, min(max_results, 10))

        # Try multiple backends sequentially to bypass rate-limiting/IP blocks
        results = []
        last_error = None
        
        for backend in ["api", "lite", "html"]:
            try:
                results = await asyncio.wait_for(
                    asyncio.to_thread(_sync_search, query, max_results, backend),
                    timeout=20.0,
                )
                if results:
                    break  # Found results, stop trying other backends
                else:
                    last_error = f"Backend '{backend}' returned no results."
            except asyncio.TimeoutError:
                last_error = f"Backend '{backend}' timed out after 20s."
            except Exception as e:
                last_error = f"Backend '{backend}' failed: {type(e).__name__}: {e}"

        # If all backends failed, return a graceful error instead of crashing
        if not results:
            return f"Web search failed after trying all backends. Last error: {last_error}"

        # Format beautifully as Markdown for the UI
        md_lines = [f"### Web Search Results for: *{query}*\n"]
        
        for i, r in enumerate(results, 1):
            title = (r.get("title") or "No Title")[:200]
            url = (r.get("href") or r.get("url") or "#")[:500]
            snippet = (r.get("body") or r.get("snippet") or "No description available.")[:400]
            
            md_lines.append(f"**{i}. [{title}]({url})**")
            md_lines.append(f"> {snippet}\n")
            
        return "\n".join(md_lines)
