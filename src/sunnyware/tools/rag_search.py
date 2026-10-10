# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""RAG search tool - semantic search over uploaded documents (per-tenant FAISS)."""


class RagSearchTool:
    name = "rag_search"
    description = (
        "Semantic search over documents the user has uploaded to the RAG store. "
        "Use this to answer questions grounded in uploaded PDFs, DOCX, CSV, XLSX, "
        "TXT, or MD files. Returns the top matching chunks with source citations."
    )
    parameters = {
        "query": {
            "type": "string",
            "description": "Natural-language search query",
            "required": True,
        },
        "k": {
            "type": "integer",
            "description": "Number of top chunks to return (default 3, max 10)",
            "required": False,
        },
    }

    async def run(self, args: dict) -> dict:
        query = str(args.get("query", "")).strip()
        if not query:
            return {"error": "query is required"}

        try:
            k = int(args.get("k", 2))  # Part 31I: lowered from 3 -> 2 to save TPM
        except Exception:
            k = 3
        k = max(1, min(k, 10))

        # Tenant isolation (auth off -> "default")
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
            qvec = embeddings.embed_one(query)
        except Exception as e:
            return {"error": "embed failed: " + type(e).__name__ + ": " + str(e)}

        try:
            store = get_store(org_id)
            hits = store.search(qvec, k=k)
        except Exception as e:
            return {"error": "search failed: " + type(e).__name__ + ": " + str(e)}

        results = []
        for h in hits:
            md = h.get("metadata") or {}
            preview = (md.get("text") or "")[:1200]  # Part 31I: cap for TPM budget
            results.append({
                "source": md.get("source"),
                "chunk_id": md.get("chunk_id"),
                "distance": h.get("distance"),
                "preview": preview,
            })

        if not results:
            return {
                "query": query,
                "org_id": org_id,
                "count": 0,
                "results": [],
                "note": "no documents in store - user may need to upload via /api/rag/upload",
            }

        return {
            "query": query,
            "org_id": org_id,
            "count": len(results),
            "results": results,
        }
