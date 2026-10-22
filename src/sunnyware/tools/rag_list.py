# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""RAG list tool - list documents uploaded to the RAG store."""


class RagListTool:
    name = "rag_list"
    description = (
        "List all documents currently uploaded to the RAG store, with "
        "page-level source names and chunk counts. Use this FIRST when the "
        "user references 'my documents', 'the uploaded file', 'the PDF', etc., "
        "to confirm what is actually available before searching."
    )
    parameters = {}  # no arguments

    async def run(self, args: dict) -> dict:
        # Tenant isolation (auth off -> "default")
        try:
            from .. import tenant as _tenant
            org_id = _tenant.get_key() or "default"
        except Exception:
            org_id = "default"

        try:
            from ..rag import get_store
        except Exception as e:
            return {"error": "rag import failed: " + type(e).__name__ + ": " + str(e)}

        try:
            store = get_store(org_id)
            store._ensure_index()
            meta = store._metadata or []
        except Exception as e:
            return {"error": "store load failed: " + type(e).__name__ + ": " + str(e)}

        # Aggregate by source
        by_source = {}
        for m in meta:
            src = m.get("source") or "(unknown)"
            entry = by_source.setdefault(src, {"source": src, "chunks": 0, "chars": 0})
            entry["chunks"] += 1
            entry["chars"] += len(m.get("text") or "")

        sources = sorted(by_source.values(), key=lambda x: x["source"])

        if not sources:
            return {
                "org_id": org_id,
                "count": 0,
                "total_chunks": 0,
                "sources": [],
                "note": "RAG store is empty. Ask the user to upload a document via the WebUI paperclip button or /api/rag/upload.",
            }

        return {
            "org_id": org_id,
            "count": len(sources),
            "total_chunks": len(meta),
            "sources": sources,
        }
