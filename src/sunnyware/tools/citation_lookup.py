# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Citation lookup tool (Part 52).

Two modes:
  1. Exact: given {source, chunk_id} -> return the FULL chunk text plus
     sha256 hash for provenance.
  2. Search: given {query} -> semantic search + return full chunk text
     (not the 1200-char truncated excerpt that rag_search emits).

Reg-AI use: pin every claim to a specific chunk with a hash.
"""
import hashlib


def _sha256(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


import re as _re
_PAGE_SUFFIX = _re.compile(r"\s*\(page\s+\d+\)\s*$", _re.IGNORECASE)


def _normalize_source(s: str) -> str:
    """Strip ' (page N)' suffix so exact lookup accepts either form."""
    if not s:
        return ""
    return _PAGE_SUFFIX.sub("", str(s)).strip()


class CitationLookupTool:
    name = "citation_lookup"
    description = (
        "Look up the full, untruncated text of a specific RAG chunk plus a "
        "sha256 hash for provenance. Use when you need to quote a source "
        "verbatim or pin a claim to an exact citation. Two modes: pass "
        "{source, chunk_id} for exact lookup, or {query} for semantic search "
        "that returns full-text chunks."
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

        # ── Exact mode ─────────────────────────────────────────
        if source and chunk_id is not None:
            try:
                cid = int(chunk_id)
            except (TypeError, ValueError):
                return {"error": "chunk_id must be an integer"}
            want = _normalize_source(source)
            for md in meta_list:
                if (_normalize_source(md.get("source")) == want and
                        md.get("chunk_id") == cid):
                    text = md.get("text") or ""
                    return {
                        "mode": "exact",
                        "org_id": org_id,
                        "count": 1,
                        "results": [{
                            "source": md.get("source"),
                            "chunk_id": md.get("chunk_id"),
                            "char_start": md.get("char_start"),
                            "char_end": md.get("char_end"),
                            "page": md.get("page"),
                            "text": text,
                            "sha256_16": _sha256(text),
                        }],
                    }
            return {"mode": "exact", "org_id": org_id, "count": 0,
                    "results": [],
                    "error": f"chunk not found: source={source} chunk_id={cid}"}

        # ── Search mode ────────────────────────────────────────
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
                text = md.get("text") or ""
                results.append({
                    "source": md.get("source"),
                    "chunk_id": md.get("chunk_id"),
                    "char_start": md.get("char_start"),
                    "char_end": md.get("char_end"),
                    "page": md.get("page"),
                    "distance": h.get("distance"),
                    "text": text,
                    "sha256_16": _sha256(text),
                })
            return {
                "mode": "search",
                "org_id": org_id,
                "query": query,
                "count": len(results),
                "results": results,
            }

        return {"error": "provide either {source, chunk_id} or {query}"}
