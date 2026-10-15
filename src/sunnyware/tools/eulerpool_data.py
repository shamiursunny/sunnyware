# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 110: Eulerpool multi-source financial data tool."""
import httpx
import json as _json

from ._financial_http import env_required, cache_get, cache_set

_BASE = "https://api.eulerpool.com/api/1"
_TTL = 3600.0

ACTIONS = {
    "profile":                ("/equity/profile/{id}",                          "Company profile. id = ticker or ISIN"),
    "overview":               ("/equity/overview/{id}",                         "Company overview with description. id = ticker"),
    "income_statement":       ("/fundamentals/financials/{id}/income-statement",  "Income statement. id = ticker"),
    "balance_sheet":          ("/fundamentals/financials/{id}/balance-sheet",     "Balance sheet. id = ticker"),
    "cash_flow":              ("/fundamentals/financials/{id}/cash-flow",         "Cash flow. id = ticker"),
    "ratios":                 ("/fundamentals/financials/{id}/ratios",            "Financial ratios. id = ticker"),
    "esg":                    ("/equity/esg-rating/{id}",                         "ESG rating. id = ticker"),
    "dividends":              ("/equity/dividends/{id}",                          "Dividend history. id = ticker"),
    "estimates":              ("/equity/estimates/{id}",                          "Analyst estimates. id = ticker"),
    "analyst_grades":         ("/equity/analyst-grades/{id}",                     "Analyst grades. id = ticker"),
    "candles":                ("/equity/candles/{id}",                            "Stock candles. id = ticker"),
    "bonds_yield_curve":      ("/bonds/yield-curve",                              "US Treasury yield curve"),
    "treasury_yields":        ("/government/treasury/yields",                     "Government treasury yields"),
    "interest_rates":         ("/interest-rates/rates",                           "Interest rate series"),
    "interest_spreads":       ("/interest-rates/spreads",                         "Interest rate spreads"),
    "yield_curve_gen":        ("/interest-rates/yield-curve",                     "Generic yield curve"),
    "fixed_income_analytics": ("/fixed-income/analytics",                         "Fixed income analytics"),
    "spot_curve":             ("/fixed-income/curve/spot",                        "Spot rate curve"),
    "forward_curve":          ("/fixed-income/curve/forward",                     "Forward rate curve"),
    "options_chain":          ("/market/options/{id}",                            "Options chain. id = ticker"),
    "options_greeks":         ("/derivatives/options/greeks/{id}",                "Option Greeks. id = ticker"),
    "options_iv":             ("/derivatives/options/iv-surface/{id}",            "IV surface. id = ticker"),
    "options_flow":           ("/derivatives/options/flow/{id}",                  "Unusual options flow. id = ticker"),
    "macro_fred":             ("/macro/fred/observations/{id}",                   "FRED observations. id = series"),
    "macro_fred_series":      ("/macro/fred/series",                              "List FRED series"),
    "macro_imf":              ("/macro/imf/series",                               "List IMF series"),
    "macro_worldbank":        ("/macro/worldbank/series",                         "List World Bank series"),
    "macro_eurostat":         ("/macro/eurostat/series",                          "List Eurostat series"),
    "macro_ecb":              ("/macro/ecb/series",                               "List ECB series"),
    "macro_bis_credit":       ("/macro/bis/credit-gap",                           "BIS credit-to-GDP gap"),
    "macro_credit_spreads":   ("/macro/credit-spreads",                           "Credit spreads"),
    "macro_countries":        ("/macro/countries",                                "List countries"),
    "macro_gdp":              ("/macro/gdp/{id}",                                 "GDP by country. id = ISO"),
    "institutional_holders":  ("/institutional/13f-holders/{id}",                 "13F holders. id = ticker"),
    "institutional_13f":      ("/institutional/13f/{id}",                         "13F by CIK. id = CIK"),
    "institutional_top":      ("/institutional/top-holders",                      "Top institutional holders"),
    "superinvestors_list":    ("/alternative/superinvestors/list",                "Superinvestor list"),
    "superinvestors_top":     ("/alternative/superinvestors/top-holdings",        "Top superinvestor holdings"),
    "superinvestors_recent":  ("/alternative/superinvestors/recent-activity",     "Recent superinvestor activity"),
    "superinvestors_holdings":("/alternative/superinvestors/holdings/{id}",       "Superinvestor holdings. id = slug"),
    "congress_trades":        ("/alternative/congress-trading",                   "US Congress trades"),
    "insider_trades":         ("/equity/insider-trades/{id}",                     "Insider Form 4. id = ticker"),
    "insider_sentiment":      ("/sentiment/insider-sentiment/{id}",               "Insider sentiment. id = ticker"),
    "google_trends":          ("/alternative/google-trends/{id}",                 "Google Trends. id = ticker"),
    "reddit_mentions":        ("/alternative/reddit-mentions/{id}",               "Reddit mentions. id = ticker"),
    "fear_greed":             ("/alternative/fear-and-greed",                     "Market Fear & Greed"),
    "wikipedia_views":        ("/alternative/wikipedia-pageviews/{id}",           "Wikipedia views. id = ticker"),
    "news_sentiment":         ("/sentiment/news-sentiment/{id}",                  "News sentiment. id = ticker"),
    "social_sentiment":       ("/sentiment/social-sentiment/{id}",                "Social sentiment. id = ticker"),
    "earnings_by_date":       ("/calendar/earnings/{id}",                         "Earnings on date. id = YYYY-MM-DD"),
    "earnings_by_symbol":     ("/calendar/earnings-by-symbol/{id}",               "Earnings history. id = ticker"),
    "earnings_surprises":     ("/calendar/earnings-surprises/{id}",               "Earnings surprises. id = ticker"),
    "economic_calendar":      ("/calendar/economic-calendar",                     "Upcoming macro events"),
    "dividends_calendar":     ("/calendar/dividends/{id}",                        "Dividends by year. id = YYYY"),
    "ipo_calendar":           ("/calendar/ipo",                                   "Upcoming IPOs"),
    "ma_calendar":            ("/calendar/ma-deals",                              "Recent M&A deals"),
    "commodity_list":         ("/commodity/list",                                 "List commodities"),
    "commodity_prices":       ("/commodity/prices",                               "All commodity prices"),
    "commodity_price":        ("/commodity/prices/{id}",                          "Commodity price. id = symbol"),
    "commodity_curve":        ("/commodity/futures-curve/{id}",                   "Futures curve. id = product"),
    "forex_list":             ("/forex/list",                                     "List FX pairs"),
    "forex_rates":            ("/forex/rates/{id}",                               "FX rates. id = base currency"),
    "crypto_global":          ("/crypto-extended/global",                         "Global crypto stats"),
    "crypto_market":          ("/crypto-extended/market-overview",                "Top crypto overview"),
    "crypto_candles":         ("/crypto-extended/candles/{id}",                   "Crypto OHLCV. id = BTC"),
    "crypto_fear_greed":      ("/crypto-extended/fear-greed-history",             "Crypto fear/greed"),
    "deals_ma":               ("/deals/ma",                                       "Recent M&A"),
    "deals_ma_ticker":        ("/deals/ma/{id}",                                  "M&A history. id = ticker"),
    "deals_ma_stats":         ("/deals/ma/stats/monthly",                         "Monthly M&A stats"),
    "screener_universe":      ("/screener/universe",                              "Screener universe"),
    "screener_search":        ("/screener/search/{id}",                           "Search screener. id = query"),
    "risk_portfolio":         ("/risk-models/portfolio-risk",                     "Portfolio risk model"),
    "risk_covariance":        ("/risk-models/covariance",                         "Covariance matrix"),
    "risk_factors":           ("/risk-models/factors",                            "List risk factors"),
    "fama_french":            ("/analytics/fama-french",                          "Fama-French factors"),
    "cftc_cot":               ("/analytics/cftc/tff",                             "CFTC COT positioning"),
    "corporate_events":       ("/analytics/corporate-events",                     "Corporate events feed"),
    "transcripts_search":     ("/transcripts/search",                             "Search transcripts"),
    "earning_calls":          ("/earning-calls/list/{id}",                        "Earnings call list. id = ticker"),
}


class EulerpoolDataTool:
    name = "eulerpool_data"
    description = (
        "Multi-source financial data via Eulerpool API (447 endpoints). "
        "NEW capabilities over other tools: bonds / fixed income, options "
        "(Greeks/IV/flow), 13F institutional holdings, superinvestor "
        "tracking, congressional trading, insider trades, economic "
        "calendar, Google Trends, Reddit mentions, Fear & Greed, commodity "
        "futures curves, crypto, risk models, Fama-French factors, CFTC COT, "
        "and earnings call transcripts. Requires EULERPOOL_API_KEY env var."
    )
    parameters = {
        "action": {
            "type": "string",
            "description": "Endpoint name (e.g. profile, bonds_yield_curve, options_chain, congress_trades, macro_fred, institutional_holders). Use a specific action per call.",
            "required": True,
        },
        "identifier": {
            "type": "string",
            "description": "Ticker (AAPL), ISIN, CIK, FRED series (GDP), country code (US), date (2026-10-15), year (2025), currency (USD), crypto symbol (BTC), or slug — only when the action needs it.",
            "required": False,
        },
        "params": {
            "type": "string",
            "description": "Optional JSON string of extra query params, e.g. \"{\"period\": \"quarter\"}\"",
            "required": False,
        },
    }

    async def run(self, args: dict) -> dict:
        key = env_required("EULERPOOL_API_KEY")
        if not key:
            return {"error": "EULERPOOL_API_KEY not configured. Set on HF Space secrets."}
        action = (args.get("action") or "").strip().lower()
        if not action:
            return {"error": "action is required"}
        if action not in ACTIONS:
            return {"error": f"unknown action '{action}'", "available": sorted(ACTIONS.keys())}
        path_tmpl, desc = ACTIONS[action]
        ident = (args.get("identifier") or "").strip()
        if "{id}" in path_tmpl and not ident:
            return {"error": f"identifier required for '{action}'. Expected: {desc}"}
        path = path_tmpl.replace("{id}", ident) if "{id}" in path_tmpl else path_tmpl
        extra = {}
        if args.get("params"):
            try:
                extra = _json.loads(args["params"])
                if not isinstance(extra, dict):
                    return {"error": "params must be a JSON object"}
            except Exception as e:
                return {"error": f"params not valid JSON: {e}"}
        ck = f"euler:{action}:{ident}:{sorted(extra.items())}"
        cached = cache_get(ck)
        if cached is not None:
            cached = dict(cached); cached["_cached"] = True
            return cached
        params = dict(extra); params["token"] = key
        try:
            async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as cli:
                r = await cli.get(f"{_BASE}{path}", params=params)
        except Exception as e:
            return {"error": f"request failed: {type(e).__name__}: {e}"}
        if r.status_code == 401:
            return {"error": "Eulerpool 401 — invalid key"}
        if r.status_code == 429:
            return {"error": "Eulerpool 429 — rate limit"}
        if r.status_code >= 400:
            return {"error": f"Eulerpool HTTP {r.status_code}", "detail": r.text[:300]}
        try:
            data = r.json()
        except Exception:
            return {"error": "non-JSON response", "body": r.text[:300]}
        out = {"action": action, "identifier": ident or None, "description": desc, "data": data}
        cache_set(ck, out, _TTL)
        return out
