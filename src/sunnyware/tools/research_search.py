# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 125: unified multi-source research search.

AlphaSense-style: run one query across multiple external sources in
parallel and merge the results. Composes existing tools — no new
external APIs, no LLM calls.

Sources:
  edgar  -> SEC EDGAR full-text filings (via insurance_research)
  fred   -> FRED economic series (via fred_economic)
  govcon -> USAspending federal recipients (via govcon_data)
"""
import asyncio


_SOURCES = ("edgar", "fred", "govcon")


class ResearchSearchTool:
    name = "research_search"
    description = "Do deep research on a topic across sources. Triggers: research, investigate topic, deep search. Input: query. Returns research summary with citations."
    parameters = {
        "query": {
            "type": "string",
            "description": "Free-text query (keyword or company/entity name)",
            "required": True,
        },
        "sources": {
            "type": "string",
            "description": "Comma-separated: edgar, fred, govcon. Default: all three.",
            "required": False,
        },
        "limit": {
            "type": "integer",
            "description": "Max results per source (default 5, max 10)",
            "required": False,
        },
    }

    async def run(self, args: dict) -> dict:
        q = (args.get("query") or "").strip()
        if not q:
            return {"error": "query is required"}

        raw = (args.get("sources") or ",".join(_SOURCES)).strip().lower()
        sources = [s.strip() for s in raw.split(",") if s.strip()]
        unknown = [s for s in sources if s not in _SOURCES]
        if unknown:
            return {"error": "unknown source(s): " + ", ".join(unknown),
                    "available": list(_SOURCES)}
        if not sources:
            return {"error": "at least one source is required"}

        limit = max(1, min(int(args.get("limit") or 5), 10))

        tasks = {}
        if "edgar" in sources:
            tasks["edgar"] = asyncio.create_task(self._edgar(q, limit))
        if "fred" in sources:
            tasks["fred"] = asyncio.create_task(self._fred(q, limit))
        if "govcon" in sources:
            tasks["govcon"] = asyncio.create_task(self._govcon(q, limit))

        per_source = {}
        merged = []
        for src, t in tasks.items():
            try:
                r = await t
            except Exception as e:
                r = {"items": [],
                     "error": type(e).__name__ + ": " + str(e)}
            items = r.get("items") or []
            per_source[src] = {
                "count": len(items),
                "error": r.get("error"),
            }
            for it in items:
                it = dict(it)
                it["source"] = src
                merged.append(it)

        return {
            "query": q,
            "sources_used": sorted(tasks.keys()),
            "total": len(merged),
            "per_source": per_source,
            "results": merged[:limit * max(1, len(tasks))],
        }

    # ── Source adapters ───────────────────────────────────

    async def _edgar(self, query: str, limit: int) -> dict:
        from .insurance_research import InsuranceResearchTool
        tool = InsuranceResearchTool()
        r = await tool.run({
            "action": "search_filings",
            "query": query,
            "limit": limit,
        })
        if r.get("error"):
            return {"items": [], "error": r["error"]}
        items = []
        for f in (r.get("filings") or [])[:limit]:
            ciks = f.get("cik") or []
            cik0 = ""
            if isinstance(ciks, list) and ciks:
                cik0 = str(ciks[0])
            elif ciks:
                cik0 = str(ciks)
            acc = (f.get("accession") or "").replace("-", "")
            url = None
            if cik0 and acc:
                url = ("https://www.sec.gov/Archives/edgar/data/"
                       + cik0.lstrip("0")
                       + "/" + acc + "/")
            items.append({
                "title": (f.get("display") or
                          ["SEC " + str(f.get("form") or "filing")])[0]
                         if isinstance(f.get("display"), list)
                         else str(f.get("display") or "SEC filing"),
                "snippet": (str(f.get("form") or "") + " · "
                            + str(f.get("file_date") or "")),
                "url": url,
                "extra": {
                    "form": f.get("form"),
                    "file_date": f.get("file_date"),
                    "cik": cik0 or None,
                    "accession": f.get("accession"),
                },
            })
        return {"items": items}

    async def _fred(self, query: str, limit: int) -> dict:
        from .fred_economic import FredEconomicTool
        tool = FredEconomicTool()
        r = await tool.run({
            "action": "search",
            "query": query,
            "limit": limit,
        })
        if r.get("error"):
            return {"items": [], "error": r["error"]}
        rows = r.get("series") or r.get("results") or []
        items = []
        for s in rows[:limit]:
            if not isinstance(s, dict):
                continue
            sid = s.get("id") or s.get("series_id") or ""
            items.append({
                "title": sid,
                "snippet": s.get("title") or "",
                "url": ("https://fred.stlouisfed.org/series/" + sid)
                       if sid else None,
                "extra": {
                    "id": sid,
                    "units": s.get("units"),
                    "frequency": s.get("frequency"),
                },
            })
        return {"items": items}

    async def _govcon(self, query: str, limit: int) -> dict:
        from .govcon_data import GovconDataTool
        tool = GovconDataTool()
        r = await tool.run({
            "action": "recipient_search",
            "keyword": query,
            "limit": limit,
        })
        if r.get("error"):
            return {"items": [], "error": r["error"]}
        items = []
        for x in (r.get("recipients") or [])[:limit]:
            name = x.get("name") or "recipient"
            uei = x.get("uei") or ""
            amt = x.get("amount")
            snippet = "UEI: " + (uei or "n/a")
            if amt is not None:
                try:
                    snippet += " · $" + f"{float(amt):,.0f}"
                except Exception:
                    pass
            items.append({
                "title": name,
                "snippet": snippet,
                "url": None,
                "extra": {
                    "uei": uei or None,
                    "recipient_id": x.get("recipient_id"),
                    "amount": amt,
                },
            })
        return {"items": items}
