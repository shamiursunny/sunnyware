# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 107: SEC EDGAR fundamentals tool.

Fetches XBRL-structured financial data from SEC's public filings API.
No API key required -- SEC asks only for a descriptive User-Agent.

Docs: https://www.sec.gov/edgar/sec-api-documentation
"""
import os
from typing import Optional

from ._financial_http import get_json, cache_get, cache_set


_UA = os.getenv("SEC_USER_AGENT", "Sunnyware/0.1 (shamiur@engineer.com)")
_HEADERS = {"User-Agent": _UA, "Accept": "application/json"}
_CIK_CACHE_TTL = 86400.0
_DATA_TTL = 3600.0

# Common XBRL tags for the three main statements
_INCOME_TAGS = [
    "Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
    "SalesRevenueNet", "CostOfRevenue", "CostOfGoodsAndServicesSold",
    "GrossProfit", "OperatingExpenses", "ResearchAndDevelopmentExpense",
    "SellingGeneralAndAdministrativeExpense", "OperatingIncomeLoss",
    "InterestExpense", "IncomeTaxExpenseBenefit", "NetIncomeLoss",
    "EarningsPerShareBasic", "EarningsPerShareDiluted",
]
_BALANCE_TAGS = [
    "CashAndCashEquivalentsAtCarryingValue", "ShortTermInvestments",
    "AccountsReceivableNetCurrent", "InventoryNet", "AssetsCurrent",
    "PropertyPlantAndEquipmentNet", "Goodwill", "Assets",
    "AccountsPayableCurrent", "LiabilitiesCurrent", "LongTermDebtNoncurrent",
    "Liabilities", "StockholdersEquity", "RetainedEarningsAccumulatedDeficit",
]
_CASHFLOW_TAGS = [
    "NetCashProvidedByUsedInOperatingActivities",
    "NetCashProvidedByUsedInInvestingActivities",
    "NetCashProvidedByUsedInFinancingActivities",
    "PaymentsToAcquirePropertyPlantAndEquipment",
    "PaymentsOfDividends", "ShareBasedCompensation",
    "DepreciationDepletionAndAmortization",
]


async def _get_cik(ticker: str) -> Optional[str]:
    """Look up CIK (zero-padded to 10 digits) for a ticker."""
    ticker = ticker.upper().strip()
    ck = f"cik:{ticker}"
    cached = cache_get(ck)
    if cached:
        return cached
    r = await get_json(
        "https://www.sec.gov/files/company_tickers.json",
        headers=_HEADERS, timeout=15.0,
    )
    if "_http_error" in r:
        return None
    for item in r.values() if isinstance(r, dict) else []:
        if isinstance(item, dict) and item.get("ticker", "").upper() == ticker:
            cik = str(item.get("cik_str", "")).zfill(10)
            cache_set(ck, cik, _CIK_CACHE_TTL)
            return cik
    return None


def _pick_values(units: dict, tag: str, limit: int = 8) -> list:
    """Extract recent entries for an XBRL tag from the units map."""
    facts = units.get(tag)
    if not facts:
        return []
    # facts is a list of {end, val, form, fy, fp, ...}
    # Prefer 10-K / 10-Q and dedupe by end date
    seen = set()
    out = []
    for f in reversed(facts):
        end = f.get("end") or f.get("start")
        form = f.get("form", "")
        if not end or end in seen:
            continue
        if form not in ("10-K", "10-Q", "10-K/A", "10-Q/A", "20-F", "40-F"):
            continue
        seen.add(end)
        out.append({
            "end": end,
            "val": f.get("val"),
            "form": form,
            "fy": f.get("fy"),
            "fp": f.get("fp"),
        })
        if len(out) >= limit:
            break
    return out


async def _fetch_concept(cik: str, taxonomy: str, tag: str) -> dict:
    ck = f"concept:{cik}:{taxonomy}:{tag}"
    cached = cache_get(ck)
    if cached is not None:
        return cached
    url = (
        f"https://data.sec.gov/api/xbrl/companyconcept/"
        f"CIK{cik}/{taxonomy}/{tag}.json"
    )
    r = await get_json(url, headers=_HEADERS, timeout=20.0)
    cache_set(ck, r, _DATA_TTL)
    return r


class EdgarFundamentalsTool:
    name = "edgar_fundamentals"
    description = (
        "Fetch official financial statements from SEC EDGAR (US public "
        "companies only). Returns XBRL-structured income statement, "
        "balance sheet, and cash flow. No API key needed. Use for "
        "authoritative financial reporting data, quarterly or annual. "
        "Ticker examples: AAPL, MSFT, TSLA, BRK.B"
    )
    parameters = {
        "ticker": {
            "type": "string",
            "description": "Stock ticker (e.g., AAPL, MSFT)",
            "required": True,
        },
        "statement": {
            "type": "string",
            "description": "One of: income, balance, cashflow, all (default: all)",
            "required": False,
        },
    }

    async def run(self, args: dict) -> dict:
        ticker = (args.get("ticker") or "").strip().upper()
        if not ticker:
            return {"error": "ticker is required"}
        statement = (args.get("statement") or "all").strip().lower()
        if statement not in ("income", "balance", "cashflow", "all"):
            return {"error": "statement must be one of income/balance/cashflow/all"}

        cik = await _get_cik(ticker)
        if not cik:
            return {"error": f"ticker {ticker} not found in SEC EDGAR (US public cos only)"}

        out = {"ticker": ticker, "cik": cik}

        async def _collect(tags, taxonomy="us-gaap"):
            data = {}
            for tag in tags:
                r = await _fetch_concept(cik, taxonomy, tag)
                if "_http_error" in r:
                    continue
                units = (r.get("units") or {})
                # Try USD first, then USD/shares for EPS
                for unit_key in ("USD", "USD/shares", "shares"):
                    if unit_key in units:
                        vals = _pick_values(units, tag, limit=8)
                        if vals:
                            data[tag] = {"unit": unit_key, "recent": vals}
                            break
            return data

        if statement in ("income", "all"):
            out["income_statement"] = await _collect(_INCOME_TAGS)
        if statement in ("balance", "all"):
            out["balance_sheet"] = await _collect(_BALANCE_TAGS)
        if statement in ("cashflow", "all"):
            out["cash_flow"] = await _collect(_CASHFLOW_TAGS)

        out["source"] = "SEC EDGAR XBRL API (data.sec.gov)"
        return out
