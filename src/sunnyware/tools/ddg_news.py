import asyncio
try:
    from ddgs import DDGS
    _DDGS_AVAILABLE = True
except ImportError:
    _DDGS_AVAILABLE = False

class DDGNewsTool:
    name = "ddg_news"
    description = "Search for general news using DuckDuckGo (free, no API key)."
    keywords = ["general news", "current events", "latest news"]
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "News search query (e.g., 'AI regulation')"},
            "max_results": {"type": "integer", "description": "Max results (default: 5)", "default": 5}
        },
        "required": ["query"]
    }

    async def run(self, query: str, max_results: int = 5) -> dict:
        if not _DDGS_AVAILABLE:
            return {"error": "ddgs package not installed."}

        def _sync_search():
            with DDGS() as ddgs:
                return list(ddgs.news(query, max_results=max_results))

        try:
            results = await asyncio.wait_for(asyncio.to_thread(_sync_search), timeout=20.0)
        except Exception as e:
            return {"error": f"News search failed: {e}"}

        cleaned = []
        for r in results or []:
            cleaned.append({
                "title": (r.get("title") or "")[:120],
                "source": r.get("source") or "",
                "url": r.get("url") or "",
                "date": r.get("date") or ""
            })

        return {"ok": True, "count": len(cleaned), "results": cleaned}
