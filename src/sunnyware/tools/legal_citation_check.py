# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 131: legal citation verification via CourtListener.

Uses the Free Law Project's CourtListener REST API v4 to verify
case-law citations against a database of 18M+ citations. This is
the anti-hallucination guardrail for the legal role.

Free tier (May 2026): 5 req/min, 50 req/hr, 125 req/day.
Requires COURTLISTENER_API_KEY env var (free signup at
https://www.courtlistener.com/profile/api/).

API reference:
  POST https://www.courtlistener.com/api/rest/v4/citation-lookup/
    Form-encoded body (NOT JSON):
      text=<blob>  OR  volume=<n>&reporter=<abbr>&page=<n>
    Returns a JSON LIST (not dict):
      [{citation, normalized_citations, start_index, end_index,
        status, error_message, clusters}]
    Per-citation status: 200=found, 404=valid-not-found,
      400=invalid-reporter, 300=ambiguous, 429=throttled

Limitations (documented by CourtListener):
  - Does NOT look up statutes, law journals, id., or supra citations
  - Does NOT match citations without volume or page numbers
"""
import hashlib
import json as _json

from ._financial_http import env_required, cache_get, cache_set

_BASE = "https://www.courtlistener.com/api/rest/v4"
_LOOKUP = _BASE + "/citation-lookup/"
_SEARCH = _BASE + "/search/"
_OPINIONS = _BASE + "/opinions/"

# Citations are stable; cache aggressively to respect the tight free tier.
_TTL_LOOKUP = 7 * 24 * 3600.0   # 1 week
_TTL_SEARCH = 24 * 3600.0       # 1 day
_TTL_OPINION = 7 * 24 * 3600.0  # 1 week


def _auth_headers():
    """Return auth header dict or None if no token configured."""
    key = env_required("COURTLISTENER_API_KEY")
    if not key:
        return None
    return {
        "Authorization": "Token " + key,
        "Accept": "application/json",
    }


async def _post_form(url, form_data, headers, timeout=25.0):
    """POST form-encoded (application/x-www-form-urlencoded).

    CourtListener's citation-lookup requires form data, NOT JSON.
    Returns parsed JSON or {'_http_error': '...'}.
    """
    try:
        import httpx
    except Exception:
        return {"_http_error": "httpx not installed"}
    try:
        async with httpx.AsyncClient(timeout=timeout,
                                     follow_redirects=True) as cli:
            r = await cli.post(url, data=form_data, headers=headers)
            if r.status_code >= 400:
                return {
                    "_http_error": "HTTP " + str(r.status_code),
                    "_status": r.status_code,
                    "_body": r.text[:300],
                }
            return r.json()
    except Exception as e:
        return {"_http_error": type(e).__name__ + ": " + str(e)}


async def _get_json(url, params, headers, timeout=20.0):
    try:
        import httpx
    except Exception:
        return {"_http_error": "httpx not installed"}
    try:
        async with httpx.AsyncClient(timeout=timeout,
                                     follow_redirects=True) as cli:
            r = await cli.get(url, params=params, headers=headers)
            if r.status_code >= 400:
                return {
                    "_http_error": "HTTP " + str(r.status_code),
                    "_status": r.status_code,
                    "_body": r.text[:300],
                }
            return r.json()
    except Exception as e:
        return {"_http_error": type(e).__name__ + ": " + str(e)}


_STATUS_MEANINGS = {
    200: "found and matched in CourtListener",
    404: "valid citation but NOT found in CourtListener",
    400: "looks like a citation but invalid reporter",
    300: "ambiguous - multiple matches",
    429: "throttled (too many citations in request)",
}


def _normalize_result(raw):
    """Turn a raw citation-lookup item into our response shape."""
    if not isinstance(raw, dict):
        return None
    status = raw.get("status")
    clusters = raw.get("clusters") or []
    first_cluster = None
    if isinstance(clusters, list) and clusters:
        c0 = clusters[0]
        if isinstance(c0, dict):
            first_cluster = {
                "id": c0.get("id"),
                "case_name": (c0.get("case_name") or
                              c0.get("caseName")),
                "date_filed": (c0.get("date_filed") or
                               c0.get("dateFiled")),
                "docket_id": c0.get("docket_id") or c0.get("docket"),
                "citation_count": c0.get("citation_count"),
                "precedential_status": c0.get("precedential_status"),
                "absolute_url": c0.get("absolute_url"),
            }
    verified = (status == 200 and first_cluster is not None)
    return {
        "citation": raw.get("citation"),
        "normalized_citations": raw.get("normalized_citations") or [],
        "start_index": raw.get("start_index"),
        "end_index": raw.get("end_index"),
        "status": status,
        "status_meaning": _STATUS_MEANINGS.get(status, "unknown"),
        "verified": verified,
        "error_message": raw.get("error_message") or "",
        "cluster": first_cluster,
        "cluster_count": len(clusters) if isinstance(clusters, list) else 0,
    }


class LegalCitationCheckTool:
    name = "legal_citation_check"
    description = (
        "Verify case-law citations against CourtListener's 18M+ citation "
        "database (Free Law Project). This is the anti-hallucination "
        "guardrail for legal work: it catches fabricated case citations "
        "before they reach an attorney. Uses the official CourtListener "
        "REST API v4. Requires COURTLISTENER_API_KEY env var (free "
        "account at https://www.courtlistener.com/profile/api/).\\n\\n"
        "Actions:\\n"
        "  verify_one     - verify a single volume/reporter/page triple "
        "(e.g. '576', 'U.S.', '644')\\n"
        "  verify_text    - extract every citation from a blob of legal "
        "text and verify each (max 64k chars)\\n"
        "  search_cases   - full-text search across case law "
        "(q + optional court / filed_after / filed_before)\\n"
        "  get_opinion    - fetch the full text of one opinion by id\\n"
        "\\n"
        "Limitations (documented by CourtListener): does NOT verify "
        "statutes, law journals, 'id.', or 'supra' citations."
    )
    parameters = {
        "action": {
            "type": "string",
            "description": "One of: verify_one, verify_text, search_cases, get_opinion",
            "required": True,
        },
        "volume": {
            "type": "string",
            "description": "Volume number (for verify_one), e.g. '576'",
            "required": False,
        },
        "reporter": {
            "type": "string",
            "description": "Reporter abbreviation (for verify_one), e.g. 'U.S.', 'F.3d'",
            "required": False,
        },
        "page": {
            "type": "string",
            "description": "Page number (for verify_one), e.g. '644'",
            "required": False,
        },
        "text": {
            "type": "string",
            "description": "Blob of legal text (for verify_text), max 64000 chars",
            "required": False,
        },
        "query": {
            "type": "string",
            "description": "Search query string (for search_cases)",
            "required": False,
        },
        "court": {
            "type": "string",
            "description": "Optional court filter (e.g. 'scotus', 'ca9')",
            "required": False,
        },
        "filed_after": {
            "type": "string",
            "description": "YYYY-MM-DD - filter results filed on or after",
            "required": False,
        },
        "filed_before": {
            "type": "string",
            "description": "YYYY-MM-DD - filter results filed on or before",
            "required": False,
        },
        "opinion_id": {
            "type": "integer",
            "description": "Opinion ID (for get_opinion)",
            "required": False,
        },
        "limit": {
            "type": "integer",
            "description": "Max results for search_cases (default 5, max 20)",
            "required": False,
        },
    }

    async def run(self, args: dict) -> dict:
        action = (args.get("action") or "").strip().lower()
        if not action:
            return {"error": "action is required",
                    "available": ["verify_one", "verify_text",
                                  "search_cases", "get_opinion"]}

        # Validate action BEFORE the token check so offline smoke tests
        # can exercise input validation without a live token.
        if action not in ("verify_one", "verify_text",
                          "search_cases", "get_opinion"):
            return {"error": "unknown action '" + action + "'",
                    "available": ["verify_one", "verify_text",
                                  "search_cases", "get_opinion"]}

        # Shape checks (independent of token)
        if action == "verify_one":
            if not (str(args.get("volume") or "").strip()
                    and str(args.get("reporter") or "").strip()
                    and str(args.get("page") or "").strip()):
                return {"error": "verify_one requires volume, "
                                 "reporter, and page"}
        if action == "verify_text":
            txt = str(args.get("text") or "")
            if not txt.strip():
                return {"error": "text is required for verify_text"}
            if len(txt) > 64000:
                return {"error": "text too long (max 64000 chars); "
                                 "chunk into smaller pieces"}
        if action == "search_cases":
            if not str(args.get("query") or "").strip():
                return {"error": "query is required for search_cases"}
        if action == "get_opinion":
            try:
                int(args.get("opinion_id"))
            except Exception:
                return {"error": "opinion_id (integer) is required"}

        # Token check now happens only if inputs are valid and we
        # actually need to hit the network.
        headers = _auth_headers()
        if headers is None:
            return {
                "error": "COURTLISTENER_API_KEY not configured. "
                         "Get a free token at "
                         "https://www.courtlistener.com/profile/api/ "
                         "and set it on HF Space secrets.",
                "signup_url": "https://www.courtlistener.com/profile/api/",
                "free_tier": "5 req/min, 50 req/hr, 125 req/day",
                "available": ["verify_one", "verify_text",
                              "search_cases", "get_opinion"],
            }

        # ── verify_one ────────────────────────────────────
        if action == "verify_one":
            vol = str(args.get("volume") or "").strip()
            rep = str(args.get("reporter") or "").strip()
            pg = str(args.get("page") or "").strip()
            if not (vol and rep and pg):
                return {"error": "verify_one requires volume, "
                                 "reporter, and page"}
            ck = "cl_cite:" + vol + ":" + rep + ":" + pg
            cached = cache_get(ck)
            if cached is not None:
                out = dict(cached); out["_cached"] = True
                return out

            raw = await _post_form(
                _LOOKUP,
                {"volume": vol, "reporter": rep, "page": pg},
                headers,
            )
            if isinstance(raw, dict) and raw.get("_http_error"):
                return {"error": raw["_http_error"],
                        "status": raw.get("_status")}
            # Citation-lookup returns a LIST
            if isinstance(raw, list) and raw:
                item = _normalize_result(raw[0])
            elif isinstance(raw, dict):
                item = _normalize_result(raw)
            else:
                item = None
            if item is None:
                return {"error": "unexpected response shape",
                        "raw": str(raw)[:300]}
            out = {
                "action": action,
                "input": {"volume": vol, "reporter": rep, "page": pg},
                "result": item,
            }
            cache_set(ck, out, _TTL_LOOKUP)
            return out

        # ── verify_text ───────────────────────────────────
        if action == "verify_text":
            text = str(args.get("text") or "")
            if not text.strip():
                return {"error": "text is required for verify_text"}
            if len(text) > 64000:
                return {"error": "text too long (max 64000 chars); "
                                 "chunk into smaller pieces"}
            # Cache by content hash
            h = hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]
            ck = "cl_text:" + h
            cached = cache_get(ck)
            if cached is not None:
                out = dict(cached); out["_cached"] = True
                return out

            raw = await _post_form(_LOOKUP, {"text": text}, headers)
            if isinstance(raw, dict) and raw.get("_http_error"):
                return {"error": raw["_http_error"],
                        "status": raw.get("_status")}
            if not isinstance(raw, list):
                return {"error": "unexpected response shape",
                        "raw": str(raw)[:300]}

            items = [_normalize_result(x) for x in raw]
            items = [x for x in items if x is not None]
            verified_count = sum(1 for x in items if x.get("verified"))
            out = {
                "action": action,
                "input_length": len(text),
                "citation_count": len(items),
                "verified_count": verified_count,
                "unverified_count": len(items) - verified_count,
                "citations": items,
            }
            cache_set(ck, out, _TTL_LOOKUP)
            return out

        # ── search_cases ──────────────────────────────────
        if action == "search_cases":
            q = str(args.get("query") or "").strip()
            if not q:
                return {"error": "query is required for search_cases"}
            try:
                lim = max(1, min(int(args.get("limit") or 5), 20))
            except Exception:
                lim = 5
            params = {"q": q, "type": "o", "page_size": lim}
            court = (args.get("court") or "").strip()
            if court:
                params["court"] = court
            fa = (args.get("filed_after") or "").strip()
            if fa:
                params["filed_after"] = fa
            fb = (args.get("filed_before") or "").strip()
            if fb:
                params["filed_before"] = fb

            ck = "cl_search:" + _json.dumps(params, sort_keys=True)
            cached = cache_get(ck)
            if cached is not None:
                out = dict(cached); out["_cached"] = True
                return out

            raw = await _get_json(_SEARCH, params, headers)
            if isinstance(raw, dict) and raw.get("_http_error"):
                return {"error": raw["_http_error"],
                        "status": raw.get("_status")}

            results = []
            for r in (raw.get("results") or [])[:lim]:
                if not isinstance(r, dict):
                    continue
                results.append({
                    "case_name": (r.get("caseName") or
                                  r.get("case_name")),
                    "court": r.get("court"),
                    "court_id": r.get("court_id"),
                    "date_filed": (r.get("dateFiled") or
                                   r.get("date_filed")),
                    "cluster_id": r.get("cluster_id"),
                    "opinion_id": r.get("id"),
                    "citation": r.get("citation"),
                    "snippet": r.get("snippet"),
                    "absolute_url": r.get("absolute_url"),
                })
            out = {
                "action": action,
                "query": q,
                "court": court or None,
                "returned": len(results),
                "count": raw.get("count"),
                "results": results,
            }
            cache_set(ck, out, _TTL_SEARCH)
            return out

        # ── get_opinion ───────────────────────────────────
        if action == "get_opinion":
            try:
                oid = int(args.get("opinion_id"))
            except Exception:
                return {"error": "opinion_id (integer) is required"}
            ck = "cl_op:" + str(oid)
            cached = cache_get(ck)
            if cached is not None:
                out = dict(cached); out["_cached"] = True
                return out

            raw = await _get_json(_OPINIONS + str(oid) + "/", None, headers)
            if isinstance(raw, dict) and raw.get("_http_error"):
                return {"error": raw["_http_error"],
                        "status": raw.get("_status")}
            if not isinstance(raw, dict):
                return {"error": "unexpected response shape"}

            # plain_text may be empty; fall back in documented priority
            text = raw.get("plain_text")
            text_source = "plain_text"
            if not text:
                text = raw.get("html_with_citations") or raw.get("html")
                text_source = "html"
            if not text:
                text = raw.get("xml_harvard") or ""
                text_source = "xml_harvard"

            out = {
                "action": action,
                "opinion_id": oid,
                "type": raw.get("type"),
                "author": raw.get("author"),
                "joined_by": raw.get("joined_by"),
                "date_created": raw.get("date_created"),
                "cluster_id": raw.get("cluster"),
                "text_source": text_source,
                "text_length": len(text or ""),
                "text": (text or "")[:200000],  # cap to 200k chars
            }
            cache_set(ck, out, _TTL_OPINION)
            return out

        return {"error": "unknown action '" + action + "'",
                "available": ["verify_one", "verify_text",
                              "search_cases", "get_opinion"]}
