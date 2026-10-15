# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 108: MarketAux news + sentiment tool."""
from ._financial_http import get_json, env_required, cache_get, cache_set

_BASE = "https://api.marketaux.com/v1"
_TTL = 600.0


class MarketauxNewsTool:
    name = "marketaux_news"
    description = (
        "Financial news with entity tagging and sentiment scores across "
        "5000+ sources and 80+ markets. Free tier: 100 req/day, 3 "
        "articles per request. Requires MARKETAUX_API_KEY env var."
    )
    parameters = {
        "symbols": {
            "type": "string",
            "description": "Comma-separated tickers (e.g., AAPL,MSFT) — optional",
            "required": False,
        },
        "keywords": {
            "type": "string",
            "description": "Search keywords (e.g., 'inflation', 'earnings beat') — optional",
            "required": False,
        },
        "language": {
            "type": "string",
            "description": "Language code (default: en)",
            "required": False,
        },
        "filter_entities": {
            "type": "string",
            "description": "true/false — only return articles mentioning entities (default: true)",
            "required": False,
        },
        "limit": {
            "type": "integer",
            "description": "Articles to return (default 3, max 3 on free tier)",
            "required": False,
        },
    }

    async def run(self, args: dict) -> dict:
        key = env_required("MARKETAUX_API_KEY")
        if not key:
            return {"error": "MARKETAUX_API_KEY not configured. Set on HF Space secrets."}
        params = {"api_token": key, "language": (args.get("language") or "en")}
        if args.get("symbols"):
            params["symbols"] = args["symbols"]
        if args.get("keywords"):
            params["search"] = args["keywords"]
        fe = (args.get("filter_entities") or "true").strip().lower()
        if fe in ("true", "false"):
            params["filter_entities"] = fe
        params["limit"] = min(int(args.get("limit") or 3), 3)

        ck = f"marketaux:{params.get('symbols','')}:{params.get('search','')}:{params['language']}"
        cached = cache_get(ck)
        if cached:
            return cached
        r = await get_json(f"{_BASE}/news/all", params=params)
        if "_http_error" in r:
            return {"error": r["_http_error"], "detail": r.get("_body","")[:200]}
        articles = r.get("data", [])
        out = {"count": len(articles), "articles": [
            {
                "title": a.get("title"),
                "source": a.get("source"),
                "published_at": a.get("published_at"),
                "url": a.get("url"),
                "snippet": (a.get("snippet") or "")[:300],
                "entities": [{"symbol": e.get("symbol"), "name": e.get("name"),
                              "sentiment_score": e.get("sentiment_score"),
                              "industry": e.get("industry")}
                             for e in (a.get("entities") or [])[:5]],
            }
            for a in articles
        ]}
        cache_set(ck, out, _TTL)
        return out
