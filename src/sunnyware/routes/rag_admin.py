# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 221c: RAG admin routes."""

import asyncio
from fastapi import APIRouter, Request
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
