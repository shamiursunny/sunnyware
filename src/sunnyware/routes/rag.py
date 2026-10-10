# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""RAG endpoints: /api/rag/upload, /query, /status, /reset.

Per-tenant isolation: org_id comes from tenant.get_key().
When auth is OFF, org_id = "" → normalized to "default" (shared bucket).
"""

import time
import tempfile
from pathlib import Path

from fastapi import APIRouter, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse

from .. import tenant as tenant_ctx
from ..rag import chunker, embeddings, extractor, report_generator
from ..rag import get_store


router = APIRouter()

MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB


def _current_org() -> str:
    """Return org_id for this request. Empty key → 'default'."""
    key = ""
    try:
        key = tenant_ctx.get_key() or ""
    except Exception:
        pass
    return key or "default"


@router.get("/api/rag/status")
async def rag_status():
    """Return current store stats + embedding model info."""
    org_id = _current_org()
    try:
        store = get_store(org_id)
        st = store.status()
    except Exception as e:
        return JSONResponse(
            {"error": f"{type(e).__name__}: {e}"}, status_code=500
        )
    return {
        "org_id": org_id,
        "count": st["count"],
        "dim": st["dim"],
        "store_dir": st["store_dir"],
        "model": embeddings.model_id(),
        "model_loaded": embeddings.is_loaded(),
        "supported_extensions": extractor.supported_extensions(),
        "max_upload_mb": MAX_UPLOAD_BYTES // (1024 * 1024),
    }


@router.post("/api/rag/upload")
async def rag_upload(
    file: UploadFile = File(...),
    reset: bool = Form(False),
):
    """Upload a file, extract → chunk → embed → add to FAISS, persist to disk.

    Form fields:
      file  : the file (required)
      reset : bool — clear the store before adding (default false)
    """
    t0 = time.time()
    org_id = _current_org()

    # ── Validate filename + extension ──
    filename = (file.filename or "upload.bin").strip()
    # sanitize: keep only basename, strip path separators
    filename = Path(filename).name.replace("\\", "_").replace("/", "_")
    ext = Path(filename).suffix.lower()
    if ext not in extractor.supported_extensions():
        return JSONResponse(
            {
                "error": f"unsupported extension: {ext}",
                "supported": extractor.supported_extensions(),
            },
            status_code=400,
        )

    # ── Read & size-check ──
    try:
        data = await file.read()
    except Exception as e:
        return JSONResponse(
            {"error": f"read failed: {type(e).__name__}: {e}"}, status_code=400
        )
    if not data:
        return JSONResponse({"error": "empty file"}, status_code=400)
    if len(data) > MAX_UPLOAD_BYTES:
        return JSONResponse(
            {"error": f"file too large ({len(data)} bytes > {MAX_UPLOAD_BYTES})"},
            status_code=413,
        )

    # ── Extract (via temp file, cleaned up after) ──
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=ext, delete=False, prefix="rag_upload_"
        ) as tmp:
            tmp.write(data)
            tmp_path = Path(tmp.name)

        blocks = extractor.extract(tmp_path)
    except Exception as e:
        return JSONResponse(
            {"error": f"extract failed: {type(e).__name__}: {e}"}, status_code=422
        )
    finally:
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass

    # ── Rewrite source names: temp file → user filename ──
    # extractor.py uses path.name for the source field, which is the temp name.
    # Replace it so citations show the user's original filename.
    tmp_name = tmp_path.name if tmp_path else ""
    if tmp_name:
        for b in blocks:
            if "source" in b and b["source"]:
                b["source"] = b["source"].replace(tmp_name, filename)

    # ── Chunk ──
    chunks = []
    for b in blocks:
        if "rows" in b:
            chunks.extend(chunker.chunk_rows(b["rows"], b["source"]))
        elif b.get("text"):
            chunks.extend(chunker.chunk_text(b["text"], b["source"]))

    if not chunks:
        return JSONResponse(
            {"error": "no extractable text found in file"}, status_code=422
        )

    # ── Embed ──
    try:
        vectors = embeddings.embed_texts([c["text"] for c in chunks])
    except Exception as e:
        return JSONResponse(
            {"error": f"embed failed: {type(e).__name__}: {e}"}, status_code=500
        )

    # ── Add to store ──
    try:
        store = get_store(org_id)
        if reset:
            store.clear()
        added = store.add(vectors, chunks)
        store.save()
        total = store.count()
    except Exception as e:
        return JSONResponse(
            {"error": f"store failed: {type(e).__name__}: {e}"}, status_code=500
        )

    elapsed_ms = int((time.time() - t0) * 1000)

    try:
        from .. import metrics as _metrics
        _metrics.incr("rag_uploads_total")
        _metrics.incr_labeled("rag_uploads_by_ext", ext.lstrip("."))
    except Exception:
        pass

    return {
        "ok": True,
        "org_id": org_id,
        "filename": filename,
        "extension": ext,
        "chunks_added": added,
        "total_count": total,
        "reset": reset,
        "elapsed_ms": elapsed_ms,
    }


@router.post("/api/rag/query")
async def rag_query(req: Request):
    """Retrieve top-k chunks for a query.

    JSON body:
      query       : str  (required)
      k           : int  (default 3)
      with_prompt : bool (default false) — include full LLM prompt
    """
    try:
        body = await req.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}

    query = (body.get("query") or "").strip()
    if not query:
        return JSONResponse({"error": "missing 'query'"}, status_code=400)

    try:
        k = int(body.get("k", 3))
    except Exception:
        k = 3
    k = max(1, min(k, 20))

    with_prompt = bool(body.get("with_prompt", False))
    with_narrative = bool(body.get("with_narrative", False))
    narrative_model = body.get("narrative_model") or None
    org_id = _current_org()

    # ── Embed query ──
    try:
        qvec = embeddings.embed_one(query)
    except Exception as e:
        return JSONResponse(
            {"error": f"embed failed: {type(e).__name__}: {e}"}, status_code=500
        )

    # ── Search ──
    try:
        store = get_store(org_id)
        hits = store.search(qvec, k=k)
    except Exception as e:
        return JSONResponse(
            {"error": f"search failed: {type(e).__name__}: {e}"}, status_code=500
        )

    results = []
    for h in hits:
        md = h.get("metadata", {}) or {}
        preview = (md.get("text") or "")[:240]
        results.append({
            "distance": h.get("distance"),
            "source": md.get("source"),
            "chunk_id": md.get("chunk_id"),
            "char_start": md.get("char_start"),
            "char_end": md.get("char_end"),
            "preview": preview,
        })

    try:
        from .. import metrics as _metrics
        _metrics.incr("rag_queries_total")
    except Exception:
        pass

    out = {
        "query": query,
        "org_id": org_id,
        "k": k,
        "hits": results,
    }
    if with_prompt:
        out["prompt"] = report_generator.build_prompt(query, [
            {"source": r["source"], "chunk_id": r["chunk_id"],
             "text": (h.get("metadata") or {}).get("text", "")}
            for r, h in zip(results, hits)
        ])

    if with_narrative:
        chunks_for_llm = []
        for h in hits:
            md = h.get("metadata") or {}
            chunks_for_llm.append({
                "source": md.get("source"),
                "chunk_id": md.get("chunk_id"),
                "text": md.get("text") or md.get("preview") or "",
            })
        gen = await report_generator.generate_narrative(
            query, chunks_for_llm, model=narrative_model
        )
        if gen.get("ok"):
            out["narrative"] = gen["narrative"]
            out["narrative_model"] = gen.get("model")
            out["narrative_latency_ms"] = gen.get("latency_ms")
        else:
            out["narrative_error"] = gen.get("error")
            out["narrative_fallback"] = gen.get("fallback")
            out["narrative_latency_ms"] = gen.get("latency_ms")

    return out


@router.post("/api/rag/reset")
async def rag_reset():
    """Clear the vector store for the current org and persist the empty index."""
    org_id = _current_org()
    try:
        store = get_store(org_id)
        store.clear()
        store.save()
    except Exception as e:
        return JSONResponse(
            {"error": f"{type(e).__name__}: {e}"}, status_code=500
        )
    return {"ok": True, "org_id": org_id, "count": store.count()}
