from pathlib import Path
# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 221c: RAG admin routes."""

import asyncio
from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import JSONResponse
from .. import rag_admin_store as _rag

router = APIRouter(tags=["rag_admin"])


def _admin_only(req: Request):
    from .. import auth as _auth
    key = req.headers.get("x-api-key") or ""
    if not key:
        authz = req.headers.get("authorization") or ""
        if authz.lower().startswith("bearer "):
            key = authz[7:].strip()
    if not _auth.auth_enabled():
        return None
    if not key or not _auth.is_valid_key(key):
        return JSONResponse({"error": "auth_required"}, status_code=401)
    if not _auth.has_role(_auth.role_for_key(key), "admin"):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return None


@router.get("/api/rag-admin/stats")
async def stats(req: Request):
    d = _admin_only(req)
    if d: return d
    return await asyncio.to_thread(_rag.stats)


@router.get("/api/rag-admin/documents")
async def list_docs(req: Request, org_id: str = "", limit: int = 200):
    d = _admin_only(req)
    if d: return d
    docs = await asyncio.to_thread(_rag.list_documents, org_id, min(limit, 500))
    return {"count": len(docs), "documents": docs}


@router.post("/api/rag-admin/documents")
async def add_doc(req: Request):
    d = _admin_only(req)
    if d: return d
    try:
        body = await req.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    name = (body.get("name") or "").strip()
    content = body.get("content") or ""
    org_id = (body.get("org_id") or "").strip()
    mime = (body.get("mime") or "text/plain").strip()
    user = (body.get("user") or "").strip()
    if not name:
        return JSONResponse({"error": "name required"}, status_code=400)
    if not content:
        return JSONResponse({"error": "content required"}, status_code=400)
    if len(content) > 500_000:
        return JSONResponse({"error": "content too large (max 500KB)"}, status_code=400)
    doc = await asyncio.to_thread(_rag.add_document, org_id, user, name, content, mime)
    return {"ok": True, "document": doc}


@router.delete("/api/rag-admin/documents/{doc_id}")
async def delete_doc(doc_id: str, req: Request):
    d = _admin_only(req)
    if d: return d
    return {"ok": await asyncio.to_thread(_rag.delete_document, doc_id)}


@router.get("/api/rag-admin/documents/{doc_id}/chunks")
async def get_chunks(doc_id: str, req: Request, search: str = "", limit: int = 500):
    d = _admin_only(req)
    if d: return d
    chunks = await asyncio.to_thread(_rag.list_chunks, doc_id, "", search, min(limit, 2000))
    return {"count": len(chunks), "chunks": chunks}


@router.get("/api/rag-admin/chunks")
async def search_chunks(req: Request, search: str = "", org_id: str = "", limit: int = 200):
    d = _admin_only(req)
    if d: return d
    chunks = await asyncio.to_thread(_rag.list_chunks, "", org_id, search, min(limit, 2000))
    return {"count": len(chunks), "chunks": chunks}


@router.post("/api/rag-admin/bulk-delete")
async def bulk_delete(req: Request):
    d = _admin_only(req)
    if d: return d
    try:
        body = await req.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    doc_ids = body.get("doc_ids") or []
    if not isinstance(doc_ids, list):
        return JSONResponse({"error": "doc_ids must be list"}, status_code=400)
    count = await asyncio.to_thread(_rag.bulk_delete, doc_ids)
    return {"ok": True, "deleted": count}

@router.get("/api/rag/search")
async def rag_search(q: str = "", k: int = 3):
    """Semantic search over uploaded documents via the RAG vector store.

    Query params:
        q: natural-language search query (required)
        k: number of chunks to return (default 3, max 10)
    """
    q = (q or "").strip()
    if not q:
        return JSONResponse({"error": "missing query parameter 'q'"}, status_code=400)
    k = max(1, min(int(k or 3), 10))
    try:
        from ..tools.rag_search import RagSearchTool
    except Exception as e:
        return JSONResponse(
            {"error": f"rag import failed: {type(e).__name__}: {e}"},
            status_code=500,
        )
    result = await RagSearchTool().run({"query": q, "k": k})
    return result

@router.get("/api/rag/stats")
async def rag_stats():
    """Return public RAG vector store stats (count, dimension, model)."""
    try:
        from ..rag import embeddings, get_store
        from .. import tenant as _tenant
        org_id = _tenant.get_key() or "default"
        store = get_store(org_id)
        return {
            "org_id": org_id,
            "count": store.count(),
            "dim": embeddings.dim(),
            "model": embeddings.model_id(),
            "loaded": embeddings.is_loaded(),
        }
    except Exception as e:
        return JSONResponse(
            {"error": f"{type(e).__name__}: {e}"},
            status_code=500,
        )

@router.post("/api/rag/upload")
async def rag_upload(file: UploadFile = File(...)):
    """Upload a file, extract text, chunk, embed, and add to the vector store.

    Supports: .pdf, .docx, .txt, .md, .csv, .xlsx, .xls
    """
    import tempfile
    import os as _os

    try:
        from ..rag import extractor, chunker, embeddings, get_store
        from .. import tenant as _tenant
    except Exception as e:
        return JSONResponse(
            {"error": f"rag import failed: {type(e).__name__}: {e}"},
            status_code=500,
        )

    # Validate extension
    filename = (file.filename or "").strip()
    if not filename:
        return JSONResponse({"error": "filename required"}, status_code=400)
    ext = _os.path.splitext(filename)[1].lower()
    if ext not in extractor.EXTRACTORS:
        supported = ", ".join(extractor.supported_extensions())
        return JSONResponse(
            {"error": f"unsupported extension '{ext}'. Supported: {supported}"},
            status_code=400,
        )

    # Save to a temp file
    suffix = ext
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp_path = tmp.name
    tmp.close()
    try:
        contents = await file.read()
        with open(tmp_path, "wb") as f:
            f.write(contents)

        # Extract text blocks
        try:
            blocks = extractor.extract(Path(tmp_path))
        except Exception as e:
            return JSONResponse(
                {"error": f"extract failed: {type(e).__name__}: {e}"},
                status_code=500,
            )
        if not blocks:
            return JSONResponse(
                {"error": "no text extracted from file"},
                status_code=400,
            )

        # Chunk + embed
        all_chunks = []
        for block in blocks:
            src = filename  # use original filename, not temp path
            if "rows" in block:
                chunks = chunker.chunk_rows(block["rows"], src)
            else:
                text = block.get("text") or ""
                chunks = chunker.chunk_text(text, src) if text.strip() else []
            all_chunks.extend(chunks)

        if not all_chunks:
            return JSONResponse(
                {"error": "no chunks produced"},
                status_code=400,
            )

        texts = [c["text"] for c in all_chunks]
        try:
            vectors = embeddings.embed_texts(texts)
        except Exception as e:
            return JSONResponse(
                {"error": f"embed failed: {type(e).__name__}: {e}"},
                status_code=500,
            )

        # Add to vector store
        org_id = _tenant.get_key() or "default"
        store = get_store(org_id)
        added = store.add(vectors, [
            {"source": c["source"], "chunk_id": c["chunk_id"], "text": c["text"]}
            for c in all_chunks
        ])
        try:
            store.save()
        except Exception:
            pass

        return {
            "ok": True,
            "filename": filename,
            "org_id": org_id,
            "blocks": len(blocks),
            "chunks": added,
        }
    finally:
        try:
            _os.remove(tmp_path)
        except Exception:
            pass

@router.get("/api/rag/documents")
async def rag_documents():
    """List unique document sources in the RAG vector store."""
    try:
        from ..rag import get_store
        from .. import tenant as _tenant
        org_id = _tenant.get_key() or "default"
        store = get_store(org_id)
        sources = store.list_sources()
        return {
            "org_id": org_id,
            "count": len(sources),
            "documents": sources,
        }
    except Exception as e:
        return JSONResponse(
            {"error": f"{type(e).__name__}: {e}"},
            status_code=500,
        )

@router.delete("/api/rag/delete")
async def rag_delete(source: str = ""):
    """Delete all chunks matching `source` from the RAG vector store."""
    source = (source or "").strip()
    if not source:
        return JSONResponse({"error": "missing query parameter 'source'"}, status_code=400)
    try:
        from ..rag import get_store
        from .. import tenant as _tenant
        org_id = _tenant.get_key() or "default"
        store = get_store(org_id)
        removed = store.delete_source(source)
        try:
            store.save()
        except Exception:
            pass
        return {"ok": True, "source": source, "removed": removed}
    except Exception as e:
        return JSONResponse(
            {"error": f"{type(e).__name__}: {e}"},
            status_code=500,
        )

@router.delete("/api/rag/clear")
async def rag_clear():
    """Remove ALL documents from the RAG vector store."""
    try:
        from ..rag import get_store
        from .. import tenant as _tenant
        org_id = _tenant.get_key() or "default"
        store = get_store(org_id)
        removed = store.clear_all()
        try:
            store.save()
        except Exception:
            pass
        return {"ok": True, "org_id": org_id, "removed": removed}
    except Exception as e:
        return JSONResponse(
            {"error": f"{type(e).__name__}: {e}"},
            status_code=500,
        )

