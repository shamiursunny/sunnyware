# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 221c: RAG document + chunk management."""

import json
import os
import secrets
import time
from pathlib import Path
from typing import Optional

DOCS_FILE = "rag_documents.json"
CHUNKS_FILE = "rag_chunks.json"


def _base() -> Path:
    data = Path("/data")
    if data.exists() and os.access(str(data), os.W_OK):
        return data
    return Path("data")


def _load(name: str) -> dict:
    p = _base() / name
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(name: str, data: dict) -> bool:
    p = _base() / name
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(p)
        return True
    except Exception:
        return False


def _chunk_text(text: str, max_chars: int = 2000) -> list:
    """Split by paragraphs, then merge into chunks under max_chars."""
    paragraphs = [p.strip() for p in (text or "").split("\n\n") if p.strip()]
    chunks = []
    buf = ""
    for p in paragraphs:
        if len(buf) + len(p) + 2 <= max_chars:
            buf = (buf + "\n\n" + p).strip() if buf else p
        else:
            if buf:
                chunks.append(buf)
            if len(p) > max_chars:
                # Split long paragraph
                for i in range(0, len(p), max_chars):
                    chunks.append(p[i:i + max_chars])
                buf = ""
            else:
                buf = p
    if buf:
        chunks.append(buf)
    return chunks


def add_document(org_id: str, user: str, name: str, content: str, mime: str = "text/plain") -> dict:
    """Add a document + chunk it immediately (chunking is CPU-only, no LLM)."""
    docs = _load(DOCS_FILE)
    did = "doc_" + secrets.token_hex(8)
    now = time.time()
    text = content or ""
    chunk_list = _chunk_text(text)
    doc = {
        "id": did,
        "ts": now,
        "org_id": org_id or "",
        "user": (user or "").lower().strip(),
        "name": (name or "Untitled")[:200],
        "mime": mime or "text/plain",
        "size_bytes": len(text.encode("utf-8")),
        "chunk_count": len(chunk_list),
        "status": "chunked",
        "preview": text[:300],
    }
    docs[did] = doc
    _save(DOCS_FILE, docs)

    # Save chunks
    chunks = _load(CHUNKS_FILE)
    for i, c in enumerate(chunk_list):
        cid = "chk_" + secrets.token_hex(6)
        chunks[cid] = {
            "id": cid,
            "doc_id": did,
            "org_id": org_id or "",
            "index": i,
            "text": c[:4000],
            "ts": now,
        }
    _save(CHUNKS_FILE, chunks)
    return doc


def list_documents(org_id: str = "", limit: int = 200) -> list:
    docs = _load(DOCS_FILE)
    items = list(docs.values())
    if org_id:
        items = [d for d in items if d.get("org_id") == org_id]
    items.sort(key=lambda x: x.get("ts", 0), reverse=True)
    return items[:limit]


def get_document(doc_id: str) -> Optional[dict]:
    return _load(DOCS_FILE).get(doc_id)


def delete_document(doc_id: str) -> bool:
    docs = _load(DOCS_FILE)
    if doc_id not in docs:
        return False
    del docs[doc_id]
    _save(DOCS_FILE, docs)

    # Remove chunks
    chunks = _load(CHUNKS_FILE)
    for cid in [k for k, v in chunks.items() if v.get("doc_id") == doc_id]:
        del chunks[cid]
    _save(CHUNKS_FILE, chunks)
    return True


def list_chunks(doc_id: str = "", org_id: str = "", search: str = "", limit: int = 500) -> list:
    chunks = _load(CHUNKS_FILE)
    items = list(chunks.values())
    if doc_id:
        items = [c for c in items if c.get("doc_id") == doc_id]
    if org_id:
        items = [c for c in items if c.get("org_id") == org_id]
    if search:
        s = search.lower()
        items = [c for c in items if s in (c.get("text") or "").lower()]
    items.sort(key=lambda x: (x.get("doc_id", ""), x.get("index", 0)))
    return items[:limit]


def reindex_document(doc_id: str) -> dict:
    docs = _load(DOCS_FILE)
    if doc_id not in docs:
        return {"ok": False, "error": "document not found"}
    doc = docs[doc_id]
    # We don't store full content — return error asking for re-upload
    return {"ok": False, "error": "Full content not stored. Please re-upload to reindex."}


def bulk_delete(doc_ids: list) -> int:
    count = 0
    for did in doc_ids:
        if delete_document(did):
            count += 1
    return count


def stats() -> dict:
    docs = _load(DOCS_FILE)
    chunks = _load(CHUNKS_FILE)
    total_size = sum(d.get("size_bytes", 0) for d in docs.values())
    orgs = set(d.get("org_id", "") for d in docs.values() if d.get("org_id"))
    return {
        "total_documents": len(docs),
        "total_chunks": len(chunks),
        "total_bytes": total_size,
        "unique_orgs": len(orgs),
    }
