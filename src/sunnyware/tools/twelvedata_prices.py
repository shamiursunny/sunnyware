# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 109: Twelve Data multi-asset prices + indicators."""
from ._financial_http import get_json, env_required, cache_get, cache_set

_BASE = "https://api.twelvedata.com"
_TTL = 300.0


class TwelveDataTool:
    name = "twelvedata_prices"
    description = (
        "Multi-asset market data via Twelve Data: stocks, ETFs, forex, "
        "and crypto across 190k+ symbols. Free tier: 800 req/day, 8/min. "
        "Requires TWELVEDATA_API_KEY env var."
    )
    parameters = {
        "action": {
            "type": "string",
            "description": "One of: quote, time_series, price, rsi, macd",
            "required": True,
        },
        "symbol": {
            "type": "string",
            "description": "Symbol (e.g., AAPL, EUR/USD, BTC/USD, SPY)",
            "required": True,
        },
        "interval": {
            "type": "string",
            "description": "For time_series: 1min, 5min, 15min, 1h, 1day, 1week, 1month",
            "required": False,
        },
        "outputsize": {
            "type": "integer",
            "description": "Number of bars (default 30)",
            "required": False,
        },
    }

    async def run(self, args: dict) -> dict:
        key = env_required("TWELVEDATA_API_KEY")
        if not key:
            return {"error": "TWELVEDATA_API_KEY not configured. Set on HF Space secrets."}
        action = (args.get("action") or "").strip().lower()
        sym = (args.get("symbol") or "").strip()
        if not sym:
            return {"error": "symbol is required"}

        ck = f"td:{action}:{sym}:{args.get('interval','')}:{args.get('outputsize','')}"
        cached = cache_get(ck)
        if cached:
            return cached

        if action == "quote":
            r = await get_json(f"{_BASE}/quote",
                               params={"symbol": sym, "apikey": key})
        elif action == "price":
            r = await get_json(f"{_BASE}/price",
                               params={"symbol": sym, "apikey": key})
        elif action == "time_series":
            interval = (args.get("interval") or "1day").strip()
            size = min(int(args.get("outputsize") or 30), 5000)
            r = await get_json(f"{_BASE}/time_series",
                               params={"symbol": sym, "interval": interval,
                                       "outputsize": size, "apikey": key})
        elif action == "rsi":
            interval = (args.get("interval") or "1day").strip()
            r = await get_json(f"{_BASE}/rsi",
                               params={"symbol": sym, "interval": interval,
                                       "time_period": 14, "apikey": key})
        elif action == "macd":
            interval = (args.get("interval") or "1day").strip()
            r = await get_json(f"{_BASE}/macd",
                               params={"symbol": sym, "interval": interval,
                                       "apikey": key})
        else:
            return {"error": f"unknown action: {action}"}

        if "_http_error" in r:
            return {"error": r["_http_error"], "detail": r.get("_body","")[:200]}
        # TwelveData uses {"code": 4xx, "message": ...} for errors
        if isinstance(r, dict) and "code" in r and r.get("code") != 200:
            return {"error": r.get("message", "twelvedata error"),
                    "code": r.get("code")}
        cache_set(ck, r, _TTL)
        return r
