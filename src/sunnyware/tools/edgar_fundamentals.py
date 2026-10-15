# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 107: SEC EDGAR fundamentals tool.

Uses the /companyfacts endpoint: one request per ticker returns ALL
XBRL tags across income, balance sheet, and cash flow. Much faster
than 15+ /companyconcept calls and avoids SEC's 10 req/sec limit.

Docs: https://www.sec.gov/edgar/sec-api-documentation
"""
import os
import httpx
from typing import Optional

from ._financial_http import get_json, cache_get, cache_set


# SEC requires User-Agent in format: "<Company Name> <contact email>"
# No version string, no parentheses.
_DEFAULT_UA = "Sunnyware Financial Research shamiur@engineer.com"
_HEADERS = {
    "User-Agent": os.getenv("SEC_USER_AGENT", _DEFAULT_UA),
    "Accept": "application/json",
    "Accept-Encoding": "gzip, deflate",
    "Host": "data.sec.gov",
}
_CIK_CACHE_TTL = 86400.0   # 1 day
_FACTS_TTL = 3600.0        # 1 hour

# Companyfacts responses can be 5-15 MB. Bypass the 1 MB cap in the
# shared helper by using httpx directly for this one call.
_MAX_FACTS_BYTES = 25 * 1024 * 1024

# Curated tag lists — SEC uses MANY variants for the same concept.
# Ordered: primary (most common) -> fallback.
_INCOME_TAGS = [
    ("Revenues", "Revenue (total)"),
    ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenue (net)"),
    ("RevenueFromContractWithCustomerIncludingAssessedTax", "Revenue (incl tax)"),
    ("SalesRevenueNet", "Sales revenue"),
    ("CostOfRevenue", "Cost of revenue"),
    ("CostOfGoodsAndServicesSold", "COGS"),
    ("GrossProfit", "Gross profit"),
    ("OperatingExpenses", "Operating expenses"),
    ("ResearchAndDevelopmentExpense", "R&D expense"),
    ("SellingGeneralAndAdministrativeExpense", "SG&A expense"),
    ("OperatingIncomeLoss", "Operating income"),
    ("InterestExpense", "Interest expense"),
    ("IncomeTaxExpenseBenefit", "Income tax"),
    ("NetIncomeLoss", "Net income"),
    ("ProfitLoss", "Net profit/loss"),
    ("EarningsPerShareBasic", "EPS basic"),
    ("EarningsPerShareDiluted", "EPS diluted"),
]
_BALANCE_TAGS = [
    ("CashAndCashEquivalentsAtCarryingValue", "Cash & equiv"),
    ("ShortTermInvestments", "Short-term investments"),
    ("MarketableSecuritiesCurrent", "Marketable sec (current)"),
    ("AccountsReceivableNetCurrent", "Accounts receivable"),
    ("InventoryNet", "Inventory"),
    ("AssetsCurrent", "Total current assets"),
    ("PropertyPlantAndEquipmentNet", "PP&E net"),
    ("Goodwill", "Goodwill"),
    ("IntangibleAssetsNetExcludingGoodwill", "Intangibles"),
    ("Assets", "Total assets"),
    ("AccountsPayableCurrent", "Accounts payable"),
    ("LiabilitiesCurrent", "Total current liabilities"),
    ("LongTermDebtNoncurrent", "Long-term debt"),
    ("LongTermDebt", "Total debt"),
    ("Liabilities", "Total liabilities"),
    ("StockholdersEquity", "Stockholders equity"),
    ("RetainedEarningsAccumulatedDeficit", "Retained earnings"),
]
_CASHFLOW_TAGS = [
    ("NetCashProvidedByUsedInOperatingActivities", "CFO"),
    ("NetCashProvidedByUsedInOperatingActivitiesContinuingOperations", "CFO (cont)"),
    ("NetCashProvidedByUsedInInvestingActivities", "CFI"),
    ("NetCashProvidedByUsedInInvestingActivitiesContinuingOperations", "CFI (cont)"),
    ("NetCashProvidedByUsedInFinancingActivities", "CFF"),
    ("NetCashProvidedByUsedInFinancingActivitiesContinuingOperations", "CFF (cont)"),
    ("PaymentsToAcquirePropertyPlantAndEquipment", "Capex"),
    ("PaymentsOfDividends", "Dividends paid"),
    ("PaymentsOfDividendsCommonStock", "Dividends (common)"),
    ("ShareBasedCompensation", "Stock-based comp"),
    ("DepreciationDepletionAndAmortization", "D&A"),
    ("DepreciationAndAmortization", "D&A (alt)"),
    ("FreeCashFlow", "Free cash flow"),
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
        headers={"User-Agent": _HEADERS["User-Agent"],
                 "Accept": "application/json"},
        timeout=15.0,
    )
    if "_http_error" in r:
        print(f"[edgar] ticker lookup failed: {r.get('_http_error')}",
              flush=True)
        return None
    for item in (r.values() if isinstance(r, dict) else []):
        if isinstance(item, dict) and item.get("ticker", "").upper() == ticker:
            cik = str(item.get("cik_str", "")).zfill(10)
            cache_set(ck, cik, _CIK_CACHE_TTL)
            return cik
    return None


async def _fetch_companyfacts(cik: str) -> dict:
    """Fetch ALL facts for a company in ONE request.

    companyfacts responses are 5-15 MB, so we bypass the shared
    helper's 1 MB cap and call httpx directly.
    """
    ck = f"facts:{cik}"
    cached = cache_get(ck)
    if cached is not None:
        return cached

    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    try:
        async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as cli:
            r = await cli.get(url, headers=_HEADERS)
            if r.status_code != 200:
                out = {"_http_error": f"HTTP {r.status_code}",
                       "_body": r.text[:300]}
                cache_set(ck, out, 300.0)
                return out
            data = r.json()
    except Exception as e:
        out = {"_http_error": f"{type(e).__name__}: {e}"}
        cache_set(ck, out, 300.0)
        return out

    cache_set(ck, data, _FACTS_TTL)
    return data


def _pick_values(units: dict, limit: int = 8) -> list:
    """Extract recent SEC-reported values from a units map.

    XBRL data has {unit_name: [ {end, val, form, fy, fp, ...}, ... ]}.
    We prefer 10-K / 10-Q filings, dedupe by end date, take newest.
    """
    seen = set()
    out = []
    for unit_name, facts in units.items():
        # Prefer USD; accept USD/shares and shares too
        if not isinstance(facts, list):
            continue
        for f in reversed(facts):
            end = f.get("end")
            form = f.get("form", "")
            if not end or end in seen:
                continue
            if form not in ("10-K", "10-Q", "10-K/A", "10-Q/A",
                            "20-F", "40-F", "6-K"):
                continue
            seen.add(end)
            out.append({
                "end": end,
                "val": f.get("val"),
                "form": form,
                "fy": f.get("fy"),
                "fp": f.get("fp"),
                "unit": unit_name,
            })
            if len(out) >= limit:
                return out
    return out


def _extract(tags_list, facts_us_gaap: dict) -> dict:
    """Extract a list of (tag, label) pairs from the facts map."""
    out = {}
    for tag, label in tags_list:
        entry = facts_us_gaap.get(tag)
        if not entry:
            continue
        units = entry.get("units") or {}
        vals = _pick_values(units, limit=8)
        if vals:
            out[tag] = {"label": label, "recent": vals}
    return out


class EdgarFundamentalsTool:
    name = "edgar_fundamentals"
    description = (
        "Fetch official financial statements from SEC EDGAR (US public "
        "companies only) via the XBRL API. Returns income statement, "
        "balance sheet, and cash flow data extracted from 10-K / 10-Q "
        "filings. No API key required. Use for authoritative financial "
        "reporting data. Ticker examples: AAPL, MSFT, TSLA, BRK.B"
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
            return {"error": "statement must be income/balance/cashflow/all"}

        cik = await _get_cik(ticker)
        if not cik:
            return {"error": f"ticker {ticker} not found in SEC EDGAR "
                             "(US-listed public cos only)"}

        facts = await _fetch_companyfacts(cik)
        if "_http_error" in facts:
            return {"error": facts["_http_error"],
                    "detail": facts.get("_body", "")[:300]}

        us_gaap = (facts.get("facts") or {}).get("us-gaap") or {}
        if not us_gaap:
            return {"error": "no us-gaap facts found for this company",
                    "cik": cik}

        out = {
            "ticker": ticker,
            "cik": cik,
            "entity_name": facts.get("entityName"),
            "total_us_gaap_tags": len(us_gaap),
        }

        if statement in ("income", "all"):
            out["income_statement"] = _extract(_INCOME_TAGS, us_gaap)
        if statement in ("balance", "all"):
            out["balance_sheet"] = _extract(_BALANCE_TAGS, us_gaap)
        if statement in ("cashflow", "all"):
            out["cash_flow"] = _extract(_CASHFLOW_TAGS, us_gaap)

        out["source"] = "SEC EDGAR companyfacts API (data.sec.gov)"
        return out
