# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 107: FRED economic data tool.

800,000+ US and international time series. Requires FRED_API_KEY
(free: fredaccount.stlouisfed.org/apikeys)."""
from ._financial_http import get_json, env_required, cache_get, cache_set

_BASE = "https://api.stlouisfed.org/fred"
_TTL = 3600.0

# Frequently-used series IDs for convenience
_POPULAR = {
    "GDP": "Gross Domestic Product",
    "GDPC1": "Real GDP",
    "CPIAUCSL": "Consumer Price Index (All Urban)",
    "CPILFESL": "Core CPI (ex food & energy)",
    "UNRATE": "Unemployment Rate",
    "PAYEMS": "Total Nonfarm Payrolls",
    "FEDFUNDS": "Federal Funds Rate",
    "DGS10": "10-Year Treasury Constant Maturity",
    "DGS2": "2-Year Treasury Constant Maturity",
    "DGS30": "30-Year Treasury Constant Maturity",
    "T10Y2Y": "10Y-2Y Treasury Spread",
    "M2SL": "M2 Money Stock",
    "PCE": "Personal Consumption Expenditures",
    "RSXFS": "Retail Sales ex Food Services",
    "HOUST": "Housing Starts",
    "UMCSENT": "Consumer Sentiment (U Michigan)",
    "VIXCLS": "CBOE Volatility Index (VIX)",
}


class FredEconomicTool:
    name = "fred_economic"
    description = (
        "Query FRED (Federal Reserve Economic Data) for 800k+ economic "
        "time series: GDP, CPI, unemployment, interest rates, treasury "
        "yields, money supply, sentiment, etc. Also supports search by "
        "keyword. Use for macro context in FP&A, forecasting, and "
        "quantitative analysis. Requires FRED_API_KEY env var."
    )
    parameters = {
        "action": {
            "type": "string",
            "description": "One of: series (fetch data), search (find series), info (metadata), popular (list common IDs)",
            "required": True,
        },
        "series_id": {
            "type": "string",
            "description": "FRED series ID (e.g., GDP, CPIAUCSL, DGS10) — for action=series or info",
            "required": False,
        },
        "query": {
            "type": "string",
            "description": "Search text (e.g., 'inflation', 'unemployment') — for action=search",
            "required": False,
        },
        "limit": {
            "type": "integer",
            "description": "Max observations (default 100) or search results (default 10)",
            "required": False,
        },
        "frequency": {
            "type": "string",
            "description": "Optional: d, w, m, q, a (daily, weekly, monthly, quarterly, annual)",
            "required": False,
        },
    }

    async def run(self, args: dict) -> dict:
        action = (args.get("action") or "").strip().lower()
        if not action:
            return {"error": "action is required"}

        if action == "popular":
            return {"popular_series": _POPULAR}

        if action == "search":
            key = env_required("FRED_API_KEY")
            if not key:
                return {"error": "FRED_API_KEY not configured. Set on HF Space secrets."}
            q = (args.get("query") or "").strip()
            if not q:
                return {"error": "query is required for search"}
            limit = int(args.get("limit") or 10)
            ck = f"fred:search:{q}:{limit}"
            cached = cache_get(ck)
            if cached:
                return cached
            r = await get_json(
                f"{_BASE}/series/search",
                params={"search_text": q, "api_key": key, "file_type": "json",
                        "limit": min(limit, 50)},
            )
            if "_http_error" in r:
                return {"error": r["_http_error"], "detail": r.get("_body", "")[:200]}
            sers = r.get("seriess", [])[:limit]
            out = {"query": q, "count": len(sers), "results": [
                {"id": s.get("id"), "title": s.get("title"),
                 "units": s.get("units"), "frequency": s.get("frequency")}
                for s in sers
            ]}
            cache_set(ck, out, _TTL)
            return out

        if action in ("series", "info"):
            key = env_required("FRED_API_KEY")
            if not key:
                return {"error": "FRED_API_KEY not configured. Set on HF Space secrets."}
            sid = (args.get("series_id") or "").strip()
            if not sid:
                return {"error": "series_id is required"}
            if action == "info":
                ck = f"fred:info:{sid}"
                cached = cache_get(ck)
                if cached:
                    return cached
                r = await get_json(
                    f"{_BASE}/series",
                    params={"series_id": sid, "api_key": key, "file_type": "json"},
                )
                if "_http_error" in r:
                    return {"error": r["_http_error"]}
                sers = r.get("seriess", [])
                if not sers:
                    return {"error": f"series {sid} not found"}
                s = sers[0]
                out = {
                    "id": s.get("id"), "title": s.get("title"),
                    "units": s.get("units"), "frequency": s.get("frequency"),
                    "notes": (s.get("notes") or "")[:500],
                    "last_updated": s.get("last_updated"),
                }
                cache_set(ck, out, _TTL)
                return out

            # action == series
            limit = int(args.get("limit") or 100)
            freq = (args.get("frequency") or "").strip().lower()
            params = {"series_id": sid, "api_key": key, "file_type": "json",
                      "sort_order": "desc", "limit": min(limit, 1000)}
            if freq:
                params["frequency"] = freq
            ck = f"fred:obs:{sid}:{limit}:{freq}"
            cached = cache_get(ck)
            if cached:
                return cached
            r = await get_json(f"{_BASE}/series/observations", params=params)
            if "_http_error" in r:
                return {"error": r["_http_error"], "detail": r.get("_body", "")[:200]}
            obs = r.get("observations", [])
            out = {
                "series_id": sid,
                "count": len(obs),
                "observations": [{"date": o.get("date"), "value": o.get("value")}
                                 for o in obs],
            }
            cache_set(ck, out, _TTL)
            return out

        return {"error": f"unknown action: {action}"}
