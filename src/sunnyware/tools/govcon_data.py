# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 118: US federal contract + spending data via USAspending.gov.

Source: USAspending.gov API v2 (Treasury-operated, keyless).
Verified live: POST /api/v2/search/spending_by_award/ returns real
contracts (HTTP 200, JSON).

Replaces the earlier SAM.gov plan (which requires an emailed OTP we
could not receive). USAspending is the authoritative source for what
federal money was actually spent, where, and on whom.

Actions:
  award_search         - search federal contracts/awards by NAICS code,
                         recipient name, agency, time period, state
  recipient_search     - search recipient organizations by name/keyword
  spending_by_category - roll-up spending by category (NAICS, agency,
                         state, recipient, etc.)
"""
import json as _json

from ._financial_http import get_json, cache_get, cache_set

_BASE = "https://api.usaspending.gov/api/v2"

_TTL_AWARDS = 900.0
_TTL_RECIP = 3600.0
_TTL_CAT = 900.0

# Award type codes (USAspending v2):
#   A,B,C,D  = contracts (BPA call, purchase order, delivery order, definitive)
#   IDV_*    = indefinite delivery vehicles
_DEFAULT_AWARD_TYPES = ["A", "B", "C", "D"]


class GovconDataTool:
    name = "govcon_data"
    description = (
        "US federal contract + spending data via USAspending.gov (no API "
        "key required). Treasury-operated, authoritative source for what "
        "federal agencies actually spent. Actions:\n"
        "  award_search         - search contracts by NAICS, recipient, "
        "agency, state, time period. Use NAICS 524126 for insurance "
        "carriers to see which insurers hold federal contracts.\n"
        "  recipient_search     - find recipient orgs by name (e.g. 'AIG', "
        "'UnitedHealth') and get their recipient_id + UEI.\n"
        "  spending_by_category - aggregate spending roll-up by category "
        "(naics, awarding_agency, recipient_state, federal_account, etc.)"
    )
    parameters = {
        "action": {
            "type": "string",
            "description": "One of: award_search, recipient_search, spending_by_category",
            "required": True,
        },
        "keyword": {
            "type": "string",
            "description": "Recipient name or free-text (recipient_search) or recipient_name filter (award_search)",
            "required": False,
        },
        "naics": {
            "type": "string",
            "description": "NAICS code (6-digit preferred). 524126 = Direct Property & Casualty Insurance Carriers",
            "required": False,
        },
        "agency": {
            "type": "string",
            "description": "Awarding agency toptier code (e.g. '075' for HHS, '097' for DoD) or name",
            "required": False,
        },
        "state": {
            "type": "string",
            "description": "Recipient 2-letter state code (e.g. TX)",
            "required": False,
        },
        "start_date": {
            "type": "string",
            "description": "YYYY-MM-DD (defaults to 1 year ago)",
            "required": False,
        },
        "end_date": {
            "type": "string",
            "description": "YYYY-MM-DD (defaults to today)",
            "required": False,
        },
        "category": {
            "type": "string",
            "description": "For spending_by_category: naics, awarding_agency, funding_agency, recipient_state, recipient, federal_account, cfda",
            "required": False,
        },
        "limit": {
            "type": "integer",
            "description": "Max results (default 10, max 40)",
            "required": False,
        },
    }

    async def run(self, args: dict) -> dict:
        action = (args.get("action") or "").strip().lower()
        if not action:
            return {"error": "action is required"}

        limit = max(1, min(int(args.get("limit") or 10), 40))

        # ── award_search ─────────────────────────────────
        if action == "award_search":
            payload_filters = {
                "award_type_codes": _DEFAULT_AWARD_TYPES,
                "time_period": [{
                    "start_date": (args.get("start_date")
                                   or (__import__("datetime").date.today()
                                       - __import__("datetime").timedelta(days=364)
                                       ).isoformat()),
                    "end_date":   (args.get("end_date")
                                   or __import__("datetime").date.today().isoformat()),
                }],
            }
            naics = (args.get("naics") or "").strip()
            keyword = (args.get("keyword") or "").strip()
            state = (args.get("state") or "").strip().upper()
            agency = (args.get("agency") or "").strip()

            if naics:
                payload_filters["naics_codes"] = [naics]
            if keyword:
                payload_filters["recipient_search_text"] = [keyword]
            if state:
                payload_filters["recipient_locations"] = [{
                    "country": "USA", "state": state,
                }]
            if agency:
                payload_filters["agencies"] = [{
                    "type": "awarding", "tier": "toptier", "name": agency,
                }]

            user_filter_count = sum([
                1 for v in (naics, keyword, state, agency) if v
            ])
            if user_filter_count == 0:
                return {"error": "award_search requires at least one of: "
                                 "naics, keyword, state, agency"}

            body = {
                "filters": payload_filters,
                "fields": ["Award ID", "Recipient Name", "Award Amount",
                           "Awarding Agency", "Start Date", "End Date",
                           "Award Type", "recipient_id"],
                "limit": limit, "page": 1,
                "sort": "Award Amount", "order": "desc",
                "subawards": False,
            }
            ck = "govcon_awards:" + _json.dumps(body, sort_keys=True)
            cached = cache_get(ck)
            if cached is not None:
                cached = dict(cached); cached["_cached"] = True
                return cached

            resp = await get_json(
                _BASE + "/search/spending_by_award/",
                params=None,
                headers={"Content-Type": "application/json"},
                timeout=30.0,
            ) if False else await _post_json(_BASE + "/search/spending_by_award/", body)

            if isinstance(resp, dict) and resp.get("_http_error"):
                return {"error": resp["_http_error"],
                        "status": resp.get("_status")}

            rows = []
            for r in (resp.get("results") or [])[:limit]:
                rows.append({
                    "award_id": r.get("Award ID"),
                    "recipient": r.get("Recipient Name"),
                    "amount": r.get("Award Amount"),
                    "agency": r.get("Awarding Agency"),
                    "start_date": r.get("Start Date"),
                    "end_date": r.get("End Date"),
                    "award_type": r.get("Award Type"),
                    "recipient_id": r.get("recipient_id"),
                })
            out = {
                "action": action,
                "filters": payload_filters,
                "returned": len(rows),
                "page_metadata": resp.get("page_metadata"),
                "awards": rows,
            }
            cache_set(ck, out, _TTL_AWARDS)
            return out

        # ── recipient_search ─────────────────────────────
        if action == "recipient_search":
            kw = (args.get("keyword") or "").strip()
            if not kw:
                return {"error": "recipient_search requires 'keyword'"}
            body = {
                "keyword": kw, "limit": limit, "page": 1,
                "order": "desc", "sort": "amount",
                "award_type": "all",
            }
            ck = f"govcon_recip:{kw}:{limit}"
            cached = cache_get(ck)
            if cached is not None:
                cached = dict(cached); cached["_cached"] = True
                return cached

            resp = await _post_json(_BASE + "/recipient/duns/", body)
            if isinstance(resp, dict) and resp.get("_http_error"):
                return {"error": resp["_http_error"],
                        "status": resp.get("_status")}

            rows = []
            for r in (resp.get("results") or [])[:limit]:
                rows.append({
                    "name": r.get("name"),
                    "recipient_id": r.get("id"),
                    "uei": r.get("uei") or r.get("duns"),
                    "recipient_level": r.get("recipient_level"),
                    "amount": r.get("amount"),
                    "state": r.get("state_province"),
                })
            out = {
                "action": action, "keyword": kw,
                "returned": len(rows), "recipients": rows,
            }
            cache_set(ck, out, _TTL_RECIP)
            return out

        # ── spending_by_category ─────────────────────────
        if action == "spending_by_category":
            cat = (args.get("category") or "naics").strip().lower()
            allowed = {"naics", "awarding_agency", "funding_agency",
                       "recipient_state", "recipient", "federal_account",
                       "cfda"}
            if cat not in allowed:
                return {"error": f"unknown category '{cat}'",
                        "available": sorted(allowed)}
            import datetime as _dt
            body = {
                "filters": {
                    "award_type_codes": _DEFAULT_AWARD_TYPES,
                    "time_period": [{
                        "start_date": (args.get("start_date")
                                       or (_dt.date.today()
                                           - _dt.timedelta(days=364)
                                           ).isoformat()),
                        "end_date":   (args.get("end_date")
                                       or _dt.date.today().isoformat()),
                    }],
                },
                "limit": limit, "page": 1,
            }
            naics = (args.get("naics") or "").strip()
            state = (args.get("state") or "").strip().upper()
            if naics:
                body["filters"]["naics_codes"] = [naics]
            if state:
                body["filters"]["recipient_locations"] = [{
                    "country": "USA", "state": state,
                }]
            ck = f"govcon_cat:{cat}:" + _json.dumps(body, sort_keys=True)
            cached = cache_get(ck)
            if cached is not None:
                cached = dict(cached); cached["_cached"] = True
                return cached

            # Category belongs in the URL path (verified live), NOT in
            # the request body — body-form returns HTTP 404.
            resp = await _post_json(
                _BASE + "/search/spending_by_category/" + cat + "/",
                body,
            )
            if isinstance(resp, dict) and resp.get("_http_error"):
                return {"error": resp["_http_error"],
                        "status": resp.get("_status")}

            rows = []
            for r in (resp.get("results") or [])[:limit]:
                rows.append({
                    "code": r.get("code"),
                    "name": r.get("name"),
                    "amount": r.get("amount"),
                    "recipient_id": r.get("recipient_id"),
                    "uei": r.get("uei"),
                })
            out = {
                "action": action, "category": cat,
                "returned": len(rows),
                "results": rows,
            }
            cache_set(ck, out, _TTL_CAT)
            return out

        return {
            "error": f"unknown action '{action}'",
            "available": ["award_search", "recipient_search",
                          "spending_by_category"],
        }


async def _post_json(url: str, body: dict) -> dict:
    """Tiny POST-JSON helper (uses httpx, mirrors get_json error shape)."""
    import json as _j
    try:
        import httpx
    except Exception:
        return {"_http_error": "httpx not installed"}
    try:
        async with httpx.AsyncClient(timeout=30.0,
                                     follow_redirects=True) as cli:
            r = await cli.post(url, json=body,
                               headers={"Accept": "application/json"})
            if r.status_code >= 400:
                return {"_http_error": f"HTTP {r.status_code}",
                        "_status": r.status_code,
                        "_body": r.text[:300]}
            return r.json()
    except Exception as e:
        return {"_http_error": f"{type(e).__name__}: {e}"}
