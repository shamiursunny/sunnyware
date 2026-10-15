# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 107: Finnhub quotes, news, fundamentals, earnings."""
from ._financial_http import get_json, env_required, cache_get, cache_set

_BASE = "https://finnhub.io/api/v1"
_TTL_QUOTE = 60.0
_TTL_LONG = 3600.0


class FinnhubTool:
    name = "finnhub_quote"
    description = (
        "Real-time quotes (15-min delayed on free tier), company profiles, "
        "company/market news, earnings calendar, and basic fundamentals "
        "via Finnhub. Requires FINNHUB_API_KEY env var (free tier: 60/min)."
    )
    parameters = {
        "action": {
            "type": "string",
            "description": "One of: quote, profile, company_news, market_news, earnings, metrics",
            "required": True,
        },
        "symbol": {
            "type": "string",
            "description": "Ticker symbol (e.g., AAPL) — for quote/profile/news/metrics",
            "required": False,
        },
        "from_date": {
            "type": "string",
            "description": "YYYY-MM-DD (news/earnings start) — default: 7 days ago",
            "required": False,
        },
        "to_date": {
            "type": "string",
            "description": "YYYY-MM-DD (news/earnings end) — default: today",
            "required": False,
        },
        "category": {
            "type": "string",
            "description": "market_news category: general, forex, crypto, merger",
            "required": False,
        },
    }

    async def run(self, args: dict) -> dict:
        key = env_required("FINNHUB_API_KEY")
        if not key:
            return {"error": "FINNHUB_API_KEY not configured. Set on HF Space secrets."}
        action = (args.get("action") or "").strip().lower()
        if not action:
            return {"error": "action is required"}
        sym = (args.get("symbol") or "").strip().upper()

        import datetime as _dt
        today = _dt.date.today()
        default_from = (today - _dt.timedelta(days=7)).isoformat()
        from_d = (args.get("from_date") or default_from).strip()
        to_d = (args.get("to_date") or today.isoformat()).strip()

        if action == "quote":
            if not sym:
                return {"error": "symbol required for quote"}
            ck = f"fin:quote:{sym}"
            cached = cache_get(ck)
            if cached:
                return cached
            r = await get_json(f"{_BASE}/quote", params={"symbol": sym, "token": key})
            if "_http_error" in r:
                return {"error": r["_http_error"], "detail": r.get("_body", "")[:200]}
            out = {"symbol": sym, "current": r.get("c"), "high": r.get("h"),
                   "low": r.get("l"), "open": r.get("o"), "prev_close": r.get("pc"),
                   "change": r.get("d"), "change_pct": r.get("dp"),
                   "timestamp": r.get("t")}
            cache_set(ck, out, _TTL_QUOTE)
            return out

        if action == "profile":
            if not sym:
                return {"error": "symbol required for profile"}
            ck = f"fin:prof:{sym}"
            cached = cache_get(ck)
            if cached:
                return cached
            r = await get_json(f"{_BASE}/stock/profile2", params={"symbol": sym, "token": key})
            if "_http_error" in r:
                return {"error": r["_http_error"]}
            out = {
                "symbol": sym, "name": r.get("name"), "exchange": r.get("exchange"),
                "industry": r.get("finnhubIndustry"), "country": r.get("country"),
                "currency": r.get("currency"), "ipo": r.get("ipo"),
                "market_cap_musd": r.get("marketCapitalization"),
                "shares_outstanding_m": r.get("shareOutstanding"),
                "logo": r.get("logo"), "weburl": r.get("weburl"),
            }
            cache_set(ck, out, _TTL_LONG)
            return out

        if action == "company_news":
            if not sym:
                return {"error": "symbol required for company_news"}
            ck = f"fin:news:{sym}:{from_d}:{to_d}"
            cached = cache_get(ck)
            if cached:
                return cached
            r = await get_json(
                f"{_BASE}/company-news",
                params={"symbol": sym, "from": from_d, "to": to_d, "token": key},
            )
            if isinstance(r, dict) and "_http_error" in r:
                return {"error": r["_http_error"]}
            if isinstance(r, list):
                out = {"symbol": sym, "count": len(r), "articles": [
                    {"headline": a.get("headline"), "source": a.get("source"),
                     "datetime": a.get("datetime"), "url": a.get("url"),
                     "summary": (a.get("summary") or "")[:300]}
                    for a in r[:30]
                ]}
                cache_set(ck, out, _TTL_LONG)
                return out
            return {"error": "unexpected response shape"}

        if action == "market_news":
            cat = (args.get("category") or "general").strip().lower()
            ck = f"fin:mnews:{cat}"
            cached = cache_get(ck)
            if cached:
                return cached
            r = await get_json(f"{_BASE}/news", params={"category": cat, "token": key})
            if isinstance(r, dict) and "_http_error" in r:
                return {"error": r["_http_error"]}
            if isinstance(r, list):
                out = {"category": cat, "count": len(r), "articles": [
                    {"headline": a.get("headline"), "source": a.get("source"),
                     "datetime": a.get("datetime"), "url": a.get("url")}
                    for a in r[:30]
                ]}
                cache_set(ck, out, _TTL_LONG)
                return out
            return {"error": "unexpected response shape"}

        if action == "earnings":
            ck = f"fin:earn:{sym}:{from_d}:{to_d}"
            cached = cache_get(ck)
            if cached:
                return cached
            params = {"from": from_d, "to": to_d, "token": key}
            if sym:
                params["symbol"] = sym
            r = await get_json(f"{_BASE}/calendar/earnings", params=params)
            if "_http_error" in r:
                return {"error": r["_http_error"]}
            earns = r.get("earningsCalendar", [])[:40]
            out = {"count": len(earns), "earnings": [
                {"symbol": e.get("symbol"), "date": e.get("date"),
                 "hour": e.get("hour"), "eps_est": e.get("epsEstimate"),
                 "rev_est": e.get("revenueEstimate")}
                for e in earns
            ]}
            cache_set(ck, out, _TTL_LONG)
            return out

        if action == "metrics":
            if not sym:
                return {"error": "symbol required for metrics"}
            ck = f"fin:met:{sym}"
            cached = cache_get(ck)
            if cached:
                return cached
            r = await get_json(
                f"{_BASE}/stock/metric",
                params={"symbol": sym, "metric": "all", "token": key},
            )
            if "_http_error" in r:
                return {"error": r["_http_error"]}
            m = r.get("metric", {}) if isinstance(r, dict) else {}
            keep = ["peTTM", "pbQuarterly", "psTTM", "roeTTM", "roaTTM",
                    "grossMarginTTM", "operatingMarginTTM", "netProfitMarginTTM",
                    "currentRatioQuarterly", "quickRatioQuarterly",
                    "debtEquityQuarterly", "52WeekHigh", "52WeekLow",
                    "beta", "dividendYieldIndicatedAnnual"]
            out = {"symbol": sym, "metrics": {k: m.get(k) for k in keep if m.get(k) is not None}}
            cache_set(ck, out, _TTL_LONG)
            return out

        return {"error": f"unknown action: {action}"}
