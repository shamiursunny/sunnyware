# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 108: Tiingo historical prices + intraday (9y depth)."""
from ._financial_http import get_json, env_required, cache_get, cache_set

_BASE = "https://api.tiingo.com/tiingo"
_TTL = 1800.0


class TiingoPricesTool:
    name = "tiingo_prices"
    description = (
        "Historical OHLCV prices via Tiingo: 9 years of daily data and "
        "extended intraday (minute/hourly). Free tier: 1000 req/day, "
        "500 unique symbols/month. Requires TIINGO_API_KEY env var."
    )
    parameters = {
        "action": {
            "type": "string",
            "description": "One of: eod (end-of-day), intraday (minute/hourly), meta (ticker info)",
            "required": True,
        },
        "ticker": {
            "type": "string",
            "description": "Stock ticker (e.g., AAPL)",
            "required": True,
        },
        "start_date": {
            "type": "string",
            "description": "YYYY-MM-DD (optional for eod)",
            "required": False,
        },
        "end_date": {
            "type": "string",
            "description": "YYYY-MM-DD (optional for eod)",
            "required": False,
        },
        "frequency": {
            "type": "string",
            "description": "Intraday frequency: 1min, 5min, 15min, 1hour (default: 5min)",
            "required": False,
        },
    }

    async def run(self, args: dict) -> dict:
        key = env_required("TIINGO_API_KEY")
        if not key:
            return {"error": "TIINGO_API_KEY not configured. Set on HF Space secrets."}
        action = (args.get("action") or "").strip().lower()
        sym = (args.get("ticker") or "").strip().upper()
        if not sym:
            return {"error": "ticker is required"}

        headers = {"Content-Type": "application/json",
                   "Authorization": f"Token {key}"}

        if action == "meta":
            ck = f"tiingo:meta:{sym}"
            cached = cache_get(ck)
            if cached:
                return cached
            r = await get_json(f"{_BASE}/daily/{sym}", headers=headers,
                               params={"limit": 1})
            if isinstance(r, list) and r:
                item = r[-1]
                out = {"ticker": sym, "exchange": item.get("exchangeCode"),
                       "latest_date": item.get("date"),
                       "latest_close": item.get("close")}
                cache_set(ck, out, _TTL)
                return out
            return {"error": "no data for ticker", "detail": str(r)[:200]}

        if action == "eod":
            params = {}
            if args.get("start_date"):
                params["startDate"] = args["start_date"]
            if args.get("end_date"):
                params["endDate"] = args["end_date"]
            ck = f"tiingo:eod:{sym}:{params.get('startDate','')}:{params.get('endDate','')}"
            cached = cache_get(ck)
            if cached:
                return cached
            r = await get_json(f"{_BASE}/daily/{sym}", headers=headers, params=params or None)
            if isinstance(r, dict) and "_http_error" in r:
                return {"error": r["_http_error"], "detail": r.get("_body","")[:200]}
            if not isinstance(r, list):
                return {"error": "unexpected shape", "detail": str(r)[:200]}
            rows = r[-500:]
            out = {"ticker": sym, "count": len(rows), "bars": [
                {"date": b.get("date"), "close": b.get("close"),
                 "open": b.get("open"), "high": b.get("high"),
                 "low": b.get("low"), "volume": b.get("volume")}
                for b in rows
            ]}
            cache_set(ck, out, _TTL)
            return out

        if action == "intraday":
            freq = (args.get("frequency") or "5min").strip()
            params = {"resampleFreq": freq}
            if args.get("start_date"):
                params["startDate"] = args["start_date"]
            if args.get("end_date"):
                params["endDate"] = args["end_date"]
            ck = f"tiingo:intra:{sym}:{freq}:{params.get('startDate','')}"
            cached = cache_get(ck)
            if cached:
                return cached
            r = await get_json(f"{_BASE}/iex/{sym}/prices",
                               headers=headers, params=params)
            if isinstance(r, dict) and "_http_error" in r:
                return {"error": r["_http_error"], "detail": r.get("_body","")[:200]}
            if not isinstance(r, list):
                return {"error": "unexpected shape", "detail": str(r)[:200]}
            rows = r[:1000]
            out = {"ticker": sym, "frequency": freq, "count": len(rows), "bars": [
                {"date": b.get("date"), "close": b.get("close"),
                 "open": b.get("open"), "high": b.get("high"),
                 "low": b.get("low"), "volume": b.get("volume")}
                for b in rows
            ]}
            cache_set(ck, out, _TTL)
            return out

        return {"error": f"unknown action: {action}"}
