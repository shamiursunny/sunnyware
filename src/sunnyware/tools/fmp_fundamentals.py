# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 109: Financial Modeling Prep fundamentals."""
from ._financial_http import get_json, env_required, cache_get, cache_set

_BASE = "https://financialmodelingprep.com/api/v3"
_TTL = 3600.0


class FmpFundamentalsTool:
    name = "fmp_fundamentals"
    description = (
        "Structured financial statements via Financial Modeling Prep: "
        "income statement, balance sheet, cash flow, ratios, key metrics, "
        "DCF, and analyst estimates. Free tier: 250 req/day. "
        "Requires FMP_API_KEY env var."
    )
    parameters = {
        "action": {
            "type": "string",
            "description": "One of: income, balance, cashflow, ratios, metrics, dcf, profile",
            "required": True,
        },
        "ticker": {
            "type": "string",
            "description": "Stock ticker (e.g., AAPL)",
            "required": True,
        },
        "period": {
            "type": "string",
            "description": "annual or quarter (default: annual)",
            "required": False,
        },
        "limit": {
            "type": "integer",
            "description": "Number of periods (default: 4)",
            "required": False,
        },
    }

    async def run(self, args: dict) -> dict:
        key = env_required("FMP_API_KEY")
        if not key:
            return {"error": "FMP_API_KEY not configured. Set on HF Space secrets."}
        action = (args.get("action") or "").strip().lower()
        sym = (args.get("ticker") or "").strip().upper()
        if not sym:
            return {"error": "ticker is required"}
        period = (args.get("period") or "annual").strip().lower()
        if period not in ("annual", "quarter"):
            period = "annual"
        limit = min(int(args.get("limit") or 4), 40)

        # FMP endpoint mapping
        paths = {
            "income": f"/income-statement/{sym}",
            "balance": f"/balance-sheet-statement/{sym}",
            "cashflow": f"/cash-flow-statement/{sym}",
            "ratios": f"/ratios/{sym}",
            "metrics": f"/key-metrics/{sym}",
            "dcf": f"/discounted-cash-flow/{sym}",
            "profile": f"/profile/{sym}",
        }
        if action not in paths:
            return {"error": f"unknown action: {action}"}

        ck = f"fmp:{action}:{sym}:{period}:{limit}"
        cached = cache_get(ck)
        if cached:
            return cached

        params = {"apikey": key}
        if action != "profile" and action != "dcf":
            params["period"] = period
            params["limit"] = limit

        r = await get_json(f"{_BASE}{paths[action]}", params=params)
        if "_http_error" in r:
            return {"error": r["_http_error"], "detail": r.get("_body","")[:200]}
        # FMP returns {"Error Message": "..."} for invalid
        if isinstance(r, dict) and "Error Message" in r:
            return {"error": r["Error Message"]}

        # Trim large arrays to keep responses small
        if isinstance(r, list):
            out = {"action": action, "ticker": sym, "count": len(r),
                   "data": r[:limit]}
        else:
            out = {"action": action, "ticker": sym, "data": r}
        cache_set(ck, out, _TTL)
        return out
