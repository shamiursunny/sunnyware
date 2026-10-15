# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 117: insurance research via SEC EDGAR + FRED.

Two confirmed, free, key-free/keyed sources:

  1. SEC EDGAR (no key required, User-Agent required):
       - https://efts.sec.gov/LATEST/search-index  (full-text search)
       - https://data.sec.gov/submissions/CIK{...}.json (filings by CIK)

  2. FRED (existing FRED_API_KEY, no new key):
       - https://api.stlouisfed.org/fred/series/search
       - https://api.stlouisfed.org/fred/series/observations

NAIC and AmericasSuretyBonds do NOT expose public JSON APIs; this
tool deliberately does not scrape them.

Actions:
  search_filings   - EDGAR full-text search (insurance terms, forms 10-K etc.)
  company_filings  - recent SEC filings for a CIK
  fred_search      - FRED search filtered to insurance-sector terms
  fred_series      - fetch observations for a specific FRED series id
"""
import json as _json
import os
import urllib.parse

from ._financial_http import get_json, env_required, cache_get, cache_set

_EDGAR_FTS = "https://efts.sec.gov/LATEST/search-index"
_EDGAR_SUBS = "https://data.sec.gov/submissions"
_FRED_BASE = "https://api.stlouisfed.org/fred"

# SEC requires a proper User-Agent with contact info. Sunnyware's
# registered contact is already in meta.py; reuse that.
_EDGAR_UA = "Sunnyware shamiur@engineer.com"

_TTL_FTS = 900.0      # 15 min
_TTL_SUBS = 3600.0    # 1 hour
_TTL_FRED = 3600.0    # 1 hour


# Curated insurance-related FRED series that are known to exist.
# Callers can also pass an arbitrary series id to fred_series.
_POPULAR_FRED = {
    "CCSA":          "Continued Claims (Insured Unemployment)",
    "CCNSA":         "Continued Claims (Insured Unemployment), NSA",
    "ICSA":          "Initial Claims (Insured Unemployment)",
    "ICNSA":         "Initial Claims, NSA",
    "PCU5241265241262": "PPI: Direct Health & Medical Insurance Carriers",
    "PCU5241265241260": "PPI: Direct Health & Medical Insurance Carriers",
    "PCU52412652412603": "PPI: Direct Health Insurance Carriers",
    "PCU52412652412604": "PPI: Direct Life Insurance Carriers",
    "PCU52412652412605": "PPI: Direct Property & Casualty Insurance Carriers",
    "PCU52412652412606": "PPI: Direct Title Insurance Carriers",
}


class InsuranceResearchTool:
    name = "insurance_research"
    description = (
        "Insurance-domain research via SEC EDGAR (insurer filings) and "
        "FRED (insurance-industry economic series). Uses only public, "
        "verified endpoints. Actions:\n"
        "  search_filings  - full-text EDGAR search, e.g. query='IBNR' "
        "forms='10-K' to find insurers discussing reserving\n"
        "  company_filings - recent SEC filings for a specific CIK\n"
        "  fred_search     - FRED search (auto-appends 'insurance' unless "
        "raw=true)\n"
        "  fred_series     - observations for a FRED series id (e.g. CCSA)"
    )
    parameters = {
        "action": {
            "type": "string",
            "description": "One of: search_filings, company_filings, fred_search, fred_series",
            "required": True,
        },
        "query": {
            "type": "string",
            "description": "Free-text search terms (for search_filings, fred_search)",
            "required": False,
        },
        "forms": {
            "type": "string",
            "description": "EDGAR form filter, e.g. '10-K', '10-Q', '8-K'",
            "required": False,
        },
        "cik": {
            "type": "string",
            "description": "SEC CIK (digits, zero-padded to 10), for company_filings",
            "required": False,
        },
        "series_id": {
            "type": "string",
            "description": "FRED series id (e.g. CCSA), for fred_series",
            "required": False,
        },
        "limit": {
            "type": "integer",
            "description": "Max results (default 10, max 40)",
            "required": False,
        },
        "raw": {
            "type": "boolean",
            "description": "For fred_search: if true, don't append 'insurance' to query",
            "required": False,
        },
    }

    async def run(self, args: dict) -> dict:
        action = (args.get("action") or "").strip().lower()
        if not action:
            return {"error": "action is required"}

        limit = max(1, min(int(args.get("limit") or 10), 40))

        # ── EDGAR: full-text search ───────────────────────
        if action == "search_filings":
            q = (args.get("query") or "").strip()
            if not q:
                return {"error": "query is required for search_filings"}
            forms = (args.get("forms") or "").strip()
            ck = f"ins_fts:{q}:{forms}:{limit}"
            cached = cache_get(ck)
            if cached is not None:
                cached = dict(cached); cached["_cached"] = True
                return cached

            # EDGAR FTS uses q= with optional quoted phrases.
            params = {"q": q, "dateRange": "custom",
                      "startdt": "2015-01-01", "enddt": "2030-01-01"}
            if forms:
                params["forms"] = forms

            body = await get_json(
                _EDGAR_FTS,
                params=params,
                headers={"User-Agent": _EDGAR_UA,
                         "Accept": "application/json"},
                timeout=20.0,
            )
            if isinstance(body, dict) and body.get("_http_error"):
                return {"error": body["_http_error"],
                        "status": body.get("_status")}

            hits = []
            for h in ((body.get("hits") or {}).get("hits") or [])[:limit]:
                src = h.get("_source") or {}
                hits.append({
                    "file_date": src.get("file_date"),
                    "form": src.get("form_type"),
                    "cik": src.get("ciks") or [],
                    "display": src.get("display_names") or [],
                    "accession": h.get("_id"),
                })
            out = {
                "action": action,
                "query": q,
                "forms": forms or "any",
                "total_hits": ((body.get("hits") or {}).get("total") or {}).get("value"),
                "returned": len(hits),
                "filings": hits,
            }
            cache_set(ck, out, _TTL_FTS)
            return out

        # ── EDGAR: company filings by CIK ─────────────────
        if action == "company_filings":
            cik = (args.get("cik") or "").strip().lstrip("0")
            if not cik or not cik.isdigit():
                return {"error": "cik must be digits (SEC CIK number)"}
            cik_padded = cik.zfill(10)
            ck = f"ins_subs:{cik_padded}"
            cached = cache_get(ck)
            if cached is not None:
                cached = dict(cached); cached["_cached"] = True
                return cached

            body = await get_json(
                f"{_EDGAR_SUBS}/CIK{cik_padded}.json",
                headers={"User-Agent": _EDGAR_UA,
                         "Accept": "application/json"},
                timeout=20.0,
            )
            if isinstance(body, dict) and body.get("_http_error"):
                return {"error": body["_http_error"],
                        "status": body.get("_status")}
            if not isinstance(body, dict):
                return {"error": "unexpected response shape"}

            recent = (body.get("filings") or {}).get("recent") or {}
            forms   = recent.get("form") or []
            dates   = recent.get("filingDate") or []
            accs    = recent.get("accessionNumber") or []
            docs    = recent.get("primaryDocument") or []
            descs   = recent.get("primaryDocDescription") or []

            rows = []
            for i in range(min(limit, len(forms))):
                acc = accs[i] if i < len(accs) else ""
                rows.append({
                    "form": forms[i],
                    "date": dates[i] if i < len(dates) else "",
                    "accession": acc,
                    "primary_doc": docs[i] if i < len(docs) else "",
                    "description": descs[i] if i < len(descs) else "",
                    "url": (
                        "https://www.sec.gov/Archives/edgar/data/"
                        + cik_padded + "/" + acc.replace("-", "")
                        + "/" + (docs[i] if i < len(docs) else "")
                    ) if acc and i < len(docs) else "",
                })

            out = {
                "action": action,
                "cik": cik_padded,
                "name": body.get("name"),
                "sic": body.get("sic"),
                "sic_description": body.get("sicDescription"),
                "tickers": body.get("tickers") or [],
                "returned": len(rows),
                "filings": rows,
            }
            cache_set(ck, out, _TTL_SUBS)
            return out

        # ── FRED: search ──────────────────────────────────
        if action == "fred_search":
            key = env_required("FRED_API_KEY")
            if not key:
                return {"error": "FRED_API_KEY not configured"}
            q = (args.get("query") or "").strip()
            raw = bool(args.get("raw"))
            if not q:
                return {"error": "query is required"}
            search_text = q if raw else (q + " insurance")
            ck = f"ins_fred_search:{search_text}:{limit}"
            cached = cache_get(ck)
            if cached is not None:
                cached = dict(cached); cached["_cached"] = True
                return cached

            body = await get_json(
                f"{_FRED_BASE}/series/search",
                params={"search_text": search_text, "api_key": key,
                        "file_type": "json", "limit": limit},
                timeout=15.0,
            )
            if isinstance(body, dict) and body.get("_http_error"):
                return {"error": body["_http_error"],
                        "status": body.get("_status")}
            series = []
            for s in (body.get("seriess") or [])[:limit]:
                series.append({
                    "id": s.get("id"),
                    "title": s.get("title"),
                    "units": s.get("units"),
                    "frequency": s.get("frequency_short"),
                    "last_updated": s.get("last_updated"),
                })
            out = {
                "action": action,
                "query": search_text,
                "count": body.get("count"),
                "returned": len(series),
                "series": series,
            }
            cache_set(ck, out, _TTL_FRED)
            return out

        # ── FRED: series observations ─────────────────────
        if action == "fred_series":
            key = env_required("FRED_API_KEY")
            if not key:
                return {"error": "FRED_API_KEY not configured"}
            sid = (args.get("series_id") or "").strip().upper()
            if not sid:
                return {"error": "series_id is required"}
            ck = f"ins_fred_series:{sid}:{limit}"
            cached = cache_get(ck)
            if cached is not None:
                cached = dict(cached); cached["_cached"] = True
                return cached

            body = await get_json(
                f"{_FRED_BASE}/series/observations",
                params={"series_id": sid, "api_key": key,
                        "file_type": "json", "limit": limit,
                        "sort_order": "desc"},
                timeout=15.0,
            )
            if isinstance(body, dict) and body.get("_http_error"):
                return {"error": body["_http_error"],
                        "status": body.get("_status")}
            obs = []
            for o in (body.get("observations") or [])[:limit]:
                obs.append({"date": o.get("date"),
                            "value": o.get("value")})
            return {
                "action": action,
                "series_id": sid,
                "popular_ids": _POPULAR_FRED,
                "observations": obs,
            }

        return {
            "error": f"unknown action '{action}'",
            "available": ["search_filings", "company_filings",
                          "fred_search", "fred_series"],
        }
