# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 109: Financial Modeling Prep fundamentals (stable API).

FMP deprecated their v3 (legacy) endpoints in September 2025. New
free-tier accounts can only use the /stable/ endpoints, which take
symbol as a query param (?symbol=AAPL) instead of a path segment.

This tool tries /stable/ first, then falls back to v3 for accounts
that still have legacy access.
"""
import httpx
from ._financial_http import env_required, cache_get, cache_set

_STABLE_BASE = "https://financialmodelingprep.com/stable"
_V3_BASE = "https://financialmodelingprep.com/api/v3"
_TTL = 3600.0


# Endpoint name -> (stable_path, v3_path_template)
# {sym} is replaced with the ticker
_ENDPOINTS = {
    "quote":      ("/quote",                    "/quote/{sym}"),
    "profile":    ("/profile",                  "/profile/{sym}"),
    "income":     ("/income-statement",         "/income-statement/{sym}"),
    "balance":    ("/balance-sheet-statement",  "/balance-sheet-statement/{sym}"),
    "cashflow":   ("/cash-flow-statement",      "/cash-flow-statement/{sym}"),
    "ratios":     ("/ratios",                   "/ratios/{sym}"),
    "metrics":    ("/key-metrics",              "/key-metrics/{sym}"),
    "dcf":        ("/discounted-cash-flow",     "/discounted-cash-flow/{sym}"),
}


async def _fetch(key: str, endpoint: str, sym: str, period: str, limit: int) -> dict:
    """Try /stable/ first; on legacy-block message, retry /v3/."""
    stable_path, v3_path = _ENDPOINTS[endpoint]

    # Build params — symbol is a query param for /stable/
    stable_params = {"symbol": sym, "apikey": key}
    if endpoint not in ("quote", "profile", "dcf"):
        stable_params["period"] = period
        stable_params["limit"] = limit

    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as cli:
            r = await cli.get(f"{_STABLE_BASE}{stable_path}", params=stable_params)
            body_text = r.text[:300]
            # Detect legacy-block (rare on stable but belt-and-suspenders)
            if r.status_code == 200 and "Legacy" not in body_text:
                try:
                    return {"ok": True, "data": r.json(), "endpoint": "stable"}
                except Exception as e:
                    return {"ok": False, "error": f"JSON parse failed: {e}"}
    except Exception as e:
        return {"ok": False, "error": f"stable request failed: {type(e).__name__}: {e}"}

    # Fall back to v3
    v3_url = f"{_V3_BASE}{v3_path.format(sym=sym)}"
    v3_params = {"apikey": key}
    if endpoint not in ("quote", "profile", "dcf"):
        v3_params["period"] = period
        v3_params["limit"] = limit
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as cli:
            r = await cli.get(v3_url, params=v3_params)
            if r.status_code == 200:
                try:
                    return {"ok": True, "data": r.json(), "endpoint": "v3"}
                except Exception as e:
                    return {"ok": False, "error": f"v3 JSON parse failed: {e}"}
            return {"ok": False, "error": f"v3 HTTP {r.status_code}",
                    "detail": r.text[:200]}
    except Exception as e:
        return {"ok": False, "error": f"v3 request failed: {type(e).__name__}: {e}"}


class FmpFundamentalsTool:
    name = "fmp_fundamentals"
    description = (
        "Structured financial statements via Financial Modeling Prep: "
        "quote, profile, income statement, balance sheet, cash flow, "
        "ratios, key metrics, DCF. Uses FMP's /stable/ API (v3 legacy "
        "was deprecated September 2025). Free tier: 250 req/day. "
        "Requires FMP_API_KEY env var."
    )
    parameters = {
        "action": {
            "type": "string",
            "description": "One of: quote, profile, income, balance, cashflow, ratios, metrics, dcf",
            "required": True,
        },
        "ticker": {
            "type": "string",
            "description": "Stock ticker (e.g., AAPL, MSFT)",
            "required": True,
        },
        "period": {
            "type": "string",
            "description": "annual or quarter (default: annual)",
            "required": False,
        },
        "limit": {
            "type": "integer",
            "description": "Number of periods (default: 4, max 40)",
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
        if action not in _ENDPOINTS:
            return {"error": f"unknown action: {action}. "
                             f"Valid: {sorted(_ENDPOINTS.keys())}"}
        period = (args.get("period") or "annual").strip().lower()
        if period not in ("annual", "quarter"):
            period = "annual"
        try:
            limit = min(int(args.get("limit") or 4), 40)
        except (TypeError, ValueError):
            limit = 4

        ck = f"fmp2:{action}:{sym}:{period}:{limit}"
        cached = cache_get(ck)
        if cached:
            return cached

        res = await _fetch(key, action, sym, period, limit)
        if not res.get("ok"):
            return {"error": res.get("error"),
                    "detail": res.get("detail", "")}

        data = res["data"]
        # Trim large arrays
        if isinstance(data, list):
            out = {
                "action": action,
                "ticker": sym,
                "endpoint": res["endpoint"],
                "count": len(data),
                "data": data[:limit] if action not in ("quote", "profile") else data[:1],
            }
        else:
            out = {"action": action, "ticker": sym,
                   "endpoint": res["endpoint"], "data": data}
        cache_set(ck, out, _TTL)
        return out
