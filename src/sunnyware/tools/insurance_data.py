# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 113D: US state insurance regulator data.

Uses Socrata's public discovery + fetch APIs (no key required) to
search and pull datasets from state Departments of Insurance open-data
portals. All portals share the same Socrata API surface.

Actions:
  states    - list the states + Socrata domains this tool knows about
  discover  - search Socrata discovery for insurance datasets
  inspect   - get column metadata for a dataset
  fetch     - fetch rows from a dataset (limit N)
"""
from ._financial_http import get_json, cache_get, cache_set

_DISCOVERY_BASE = "https://api.us.socrata.com/api/catalog/v1"

# Known state Department of Insurance open-data portals.
_STATE_PORTALS = {
    "TX": ("data.texas.gov",    "Texas Department of Insurance (TDI)"),
    "NY": ("data.ny.gov",       "NY Department of Financial Services"),
    "CT": ("data.ct.gov",       "Connecticut Insurance Department"),
    "WA": ("data.wa.gov",       "Washington Office of Insurance Commissioner"),
    "IL": ("data.illinois.gov", "Illinois Department of Insurance"),
    "CO": ("data.colorado.gov", "Colorado Division of Insurance"),
    "OR": ("data.oregon.gov",   "Oregon Division of Financial Regulation"),
    "VT": ("data.vermont.gov",  "Vermont Department of Financial Regulation"),
}

_TTL_DISCOVERY = 24 * 3600.0   # dataset metadata changes slowly
_TTL_INSPECT   = 24 * 3600.0
_TTL_FETCH     = 3600.0        # dataset rows refresh periodically


class InsuranceDataTool:
    name = "insurance_data"
    description = (
        "US state insurance regulator data via Socrata open-data APIs "
        "(no key required). Searchable across TX TDI, NY DFS, CT, WA, "
        "IL, CO, OR, VT Department of Insurance portals. Returns "
        "complaints, licenses, rate filings, market-conduct datasets, "
        "and any other insurance-related dataset those regulators "
        "publish. Use action=discover to find dataset IDs, then "
        "action=inspect for column metadata, then action=fetch to pull "
        "rows."
    )
    parameters = {
        "action": {
            "type": "string",
            "description": "One of: states, discover, inspect, fetch",
            "required": True,
        },
        "state": {
            "type": "string",
            "description": "Two-letter state code (TX, NY, CT, WA, IL, CO, OR, VT). Optional for discover (searches all if omitted). Required for inspect/fetch.",
            "required": False,
        },
        "query": {
            "type": "string",
            "description": "Search terms for action=discover (e.g. 'complaints', 'rate filing', 'license')",
            "required": False,
        },
        "dataset_id": {
            "type": "string",
            "description": "Socrata dataset ID (from discover). Required for inspect/fetch.",
            "required": False,
        },
        "limit": {
            "type": "integer",
            "description": "Max records (fetch) or results per domain (discover). Default 20.",
            "required": False,
        },
    }

    async def run(self, args: dict) -> dict:
        action = (args.get("action") or "").strip().lower()
        if not action:
            return {"error": "action is required"}

        if action == "states":
            return {
                "states": [
                    {"code": code, "domain": dom, "agency": label}
                    for code, (dom, label) in _STATE_PORTALS.items()
                ],
                "note": "All portals use Socrata. Pass state=XX to discover.",
            }

        _KNOWN = ("discover", "inspect", "fetch")
        if action not in _KNOWN:
            return {
                "error": f"unknown action '{action}'",
                "available": ["states", *_KNOWN],
            }

        state = (args.get("state") or "").strip().upper()
        limit = max(1, min(int(args.get("limit") or 20), 200))
        query = (args.get("query") or "").strip() or "insurance"

        if action == "discover":
            if state:
                if state not in _STATE_PORTALS:
                    return {
                        "error": f"state '{state}' not in catalog",
                        "available": sorted(_STATE_PORTALS.keys()),
                    }
                domains = [_STATE_PORTALS[state][0]]
            else:
                domains = [d for d, _ in _STATE_PORTALS.values()]

            results = []
            for dom in domains:
                ck = f"ins:disc:{dom}:{query}:{limit}"
                cached = cache_get(ck)
                if cached is not None:
                    results.extend(cached)
                    continue
                body = await get_json(
                    _DISCOVERY_BASE,
                    params={"search_context": dom, "q": query, "limit": limit},
                    timeout=20.0,
                )
                if isinstance(body, dict) and body.get("_http_error"):
                    results.append({"domain": dom, "error": body["_http_error"]})
                    continue
                items = []
                for r in (body.get("results") or []):
                    res = r.get("resource") or {}
                    if not res.get("id"):
                        continue
                    items.append({
                        "domain": dom,
                        "dataset_id": res.get("id"),
                        "name": res.get("name"),
                        "description": (res.get("description") or "")[:300],
                        "updated_at": res.get("updatedAt"),
                    })
                cache_set(ck, items, _TTL_DISCOVERY)
                results.extend(items)

            return {
                "query": query,
                "state": state or "ALL",
                "count": len(results),
                "datasets": results[:limit * len(domains)],
            }

        # inspect / fetch require state + dataset_id
        did = (args.get("dataset_id") or "").strip()
        if not did:
            return {"error": "dataset_id required"}
        if not state or state not in _STATE_PORTALS:
            return {
                "error": "state required (must be one of the known portals)",
                "available": sorted(_STATE_PORTALS.keys()),
            }
        dom = _STATE_PORTALS[state][0]

        if action == "inspect":
            ck = f"ins:meta:{dom}:{did}"
            cached = cache_get(ck)
            if cached is not None:
                cached = dict(cached); cached["_cached"] = True
                return cached
            body = await get_json(f"https://{dom}/api/views/{did}.json",
                                  timeout=20.0)
            if isinstance(body, dict) and body.get("_http_error"):
                return {"error": body["_http_error"],
                        "status": body.get("_status")}
            out = {
                "dataset_id": did,
                "domain": dom,
                "name": body.get("name") if isinstance(body, dict) else None,
                "description": ((body.get("description") or "")[:800]
                                if isinstance(body, dict) else ""),
                "columns": [
                    {"name": c.get("name"), "type": c.get("dataTypeName")}
                    for c in ((body.get("columns") or [])
                              if isinstance(body, dict) else [])
                ][:40],
            }
            cache_set(ck, out, _TTL_INSPECT)
            return out

        if action == "fetch":
            ck = f"ins:fetch:{dom}:{did}:{limit}"
            cached = cache_get(ck)
            if cached is not None:
                cached = dict(cached); cached["_cached"] = True
                return cached
            body = await get_json(
                f"https://{dom}/resource/{did}.json",
                params={"$limit": limit},
                timeout=25.0,
            )
            if isinstance(body, dict) and body.get("_http_error"):
                return {"error": body["_http_error"],
                        "status": body.get("_status")}
            rows = body if isinstance(body, list) else []
            out = {
                "dataset_id": did,
                "domain": dom,
                "row_count": len(rows),
                "rows": rows,
            }
            cache_set(ck, out, _TTL_FETCH)
            return out

        return {
            "error": f"unknown action '{action}'",
            "available": ["states", "discover", "inspect", "fetch"],
        }
