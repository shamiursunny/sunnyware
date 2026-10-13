# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Citation lookup tool (Part 52, strengthened in Part 73).

Returns full chunk text + sha256 provenance. Every result carries a
pre-formatted citation_string the LLM is instructed to quote verbatim.

Two modes:
  - exact:  {source, chunk_id} -> full text + hash + char offsets
  - search: {query} -> semantic search returning full text
"""
import hashlib
import re

_PAGE_SUFFIX = re.compile(r"\s*\(page\s+\d+\)\s*$", re.IGNORECASE)


def _sha256(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def _normalize_source(s: str) -> str:
    """Strip ' (page N)' suffix so exact lookup accepts either form."""
    if not s:
        return ""
    return _PAGE_SUFFIX.sub("", str(s)).strip()


def _cite_string(source, chunk_id, h):
    return "[citation: " + str(source) + " chunk " + str(chunk_id) + " sha256:" + h + "]"


def _make_result(md, distance=None):
    text = md.get("text") or ""
    h = _sha256(text)
    src = md.get("source")
    cid = md.get("chunk_id")
    out = {
        "source": src,
        "chunk_id": cid,
        "char_start": md.get("char_start"),
        "char_end": md.get("char_end"),
        "page": md.get("page"),
        "text": text,
        "sha256_16": h,
        "citation_string": _cite_string(src, cid, h),
    }
    if distance is not None:
        out["distance"] = distance
    return out


class CitationLookupTool:
    name = "citation_lookup"
    description = (
        "Look up full RAG chunk text + sha256 provenance. Two modes: "
        "{source, chunk_id} for exact, or {query} for semantic search. "
        "MANDATORY OUTPUT RULE: when citing a result, you MUST quote the "
        "sha256_16 hash VERBATIM (all 16 hex characters, no abbreviation) "
        "and print a citation line exactly like the 'citation_string' "
        "field. Do NOT paraphrase the hash. Do NOT say 'the hash is in "
        "metadata'. For every result you quote to the user, print a line "
        "verbatim from the 'cite_these' array of the response."
    )
    parameters = {
        "source": {
            "type": "string",
            "description": "Source file name (exact mode)",
            "required": False,
        },
        "chunk_id": {
            "type": "integer",
            "description": "Chunk index within the source (exact mode)",
            "required": False,
        },
        "query": {
            "type": "string",
            "description": "Natural-language query (search mode)",
            "required": False,
        },
        "k": {
            "type": "integer",
            "description": "Top chunks for search mode (default 3, max 5)",
            "required": False,
        },
    }

    async def run(self, args: dict) -> dict:
        source = (args.get("source") or "").strip()
        chunk_id = args.get("chunk_id")
        query = (args.get("query") or "").strip()

        # Tenant isolation
        try:
            from .. import tenant as _tenant
            org_id = _tenant.get_key() or "default"
        except Exception:
            org_id = "default"

        try:
            from ..rag import embeddings, get_store
        except Exception as e:
            return {"error": "rag import failed: " + type(e).__name__ + ": " + str(e)}

        try:
            store = get_store(org_id)
            store._ensure_index()  # noqa: SLF001
        except Exception as e:
            return {"error": "store load failed: " + type(e).__name__ + ": " + str(e)}

        meta_list = getattr(store, "_metadata", None) or []
        if not meta_list:
            return {"org_id": org_id, "count": 0, "results": [],
                    "note": "no documents in store"}

        # ── Exact mode ──────────────────────────────────────────
        if source and chunk_id is not None:
            try:
                cid = int(chunk_id)
            except (TypeError, ValueError):
                return {"error": "chunk_id must be an integer"}

            want_exact = source
            want_norm = _normalize_source(source)
            match = None
            # Pass 1: exact source string
            for md in meta_list:
                if md.get("source") == want_exact and md.get("chunk_id") == cid:
                    match = md
                    break
            # Pass 2: normalized source
            if match is None:
                for md in meta_list:
                    if (_normalize_source(md.get("source")) == want_norm
                            and md.get("chunk_id") == cid):
                        match = md
                        break

            if match is None:
                return {"mode": "exact", "org_id": org_id, "count": 0,
                        "results": [],
                        "error": f"chunk not found: source={source} chunk_id={cid}"}

            result = _make_result(match)
            return {
                "mode": "exact",
                "org_id": org_id,
                "count": 1,
                "cite_these": [result["citation_string"]],
                "results": [result],
            }

        # ── Search mode ─────────────────────────────────────────
        if query:
            try:
                k = int(args.get("k") or 3)
            except (TypeError, ValueError):
                k = 3
            k = max(1, min(k, 5))

            try:
                qvec = embeddings.embed_one(query)
                hits = store.search(qvec, k=k)
            except Exception as e:
                return {"error": "search failed: " + type(e).__name__ + ": " + str(e)}

            results = []
            for h in hits:
                md = h.get("metadata") or {}
                results.append(_make_result(md, distance=h.get("distance")))

            return {
                "mode": "search",
                "org_id": org_id,
                "query": query,
                "count": len(results),
                "cite_these": [r["citation_string"] for r in results],
                "results": results,
            }

        return {"error": "provide either {source, chunk_id} or {query}"}
