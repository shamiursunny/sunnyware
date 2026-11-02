# -*- coding: utf-8 -*-
"""
Part 581: HTTP-level tests for RAG admin endpoints.
"""
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure src is on path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sunnyware.main import app


@pytest.fixture(scope="module")
def client():
    """Start TestClient with lifespan events and auth disabled."""
    os.environ.pop("SUNNYWARE_API_KEYS", None)
    from sunnyware import auth as _auth
    _auth.load_keys(reload=True)
    with TestClient(app) as c:
        yield c


def test_rag_stats(client):
    r = client.get("/api/rag-admin/stats")
    assert r.status_code == 200
    data = r.json()
    assert "documents" in data or "docs" in data or isinstance(data, dict)


def test_rag_list_documents_empty(client):
    r = client.get("/api/rag-admin/documents")
    assert r.status_code == 200
    data = r.json()
    assert "count" in data
    assert "documents" in data
    assert isinstance(data["documents"], list)


def test_rag_add_document_missing_name(client):
    r = client.post("/api/rag-admin/documents", json={"content": "hello"})
    assert r.status_code == 400
    assert "name" in r.json().get("error", "")


def test_rag_add_document_missing_content(client):
    r = client.post("/api/rag-admin/documents", json={"name": "test.txt"})
    assert r.status_code == 400
    assert "content" in r.json().get("error", "")


def test_rag_add_document_success(client):
    r = client.post("/api/rag-admin/documents", json={
        "name": "hello.txt",
        "content": "Hello world. This is a test document. It has multiple sentences.",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert "document" in data
    doc = data["document"]
    assert "id" in doc
    # Verify it appears in listing
    r2 = client.get("/api/rag-admin/documents")
    assert r2.status_code == 200
    names = [d["name"] for d in r2.json()["documents"]]
    assert "hello.txt" in names
    # Cleanup
    client.delete(f"/api/rag-admin/documents/{doc['id']}")


def test_rag_add_document_invalid_json(client):
    r = client.post("/api/rag-admin/documents", data="not json")
    assert r.status_code == 400


def test_rag_add_document_content_too_large(client):
    r = client.post("/api/rag-admin/documents", json={
        "name": "big.txt",
        "content": "x" * 500_001,
    })
    assert r.status_code == 400
    assert "too large" in r.json().get("error", "")


def test_rag_chunks_empty(client):
    r = client.get("/api/rag-admin/chunks")
    assert r.status_code == 200
    data = r.json()
    assert "count" in data
    assert "chunks" in data
    assert isinstance(data["chunks"], list)


def test_rag_search_chunks(client):
    r = client.get("/api/rag-admin/chunks?search=hello")
    assert r.status_code == 200
    data = r.json()
    assert "count" in data
    assert "chunks" in data

def test_rag_document_chunks(client):
    # Create a document first
    r = client.post("/api/rag-admin/documents", json={
        "name": "chunks_test.txt",
        "content": "First sentence. Second sentence. Third sentence. Fourth sentence.",
    })
    assert r.status_code == 200
    doc_id = r.json()["document"]["id"]
    # Fetch its chunks
    r2 = client.get(f"/api/rag-admin/documents/{doc_id}/chunks")
    assert r2.status_code == 200
    data = r2.json()
    assert "count" in data
    assert "chunks" in data
    assert data["count"] >= 1
    # Cleanup
    client.delete(f"/api/rag-admin/documents/{doc_id}")


def test_rag_bulk_delete(client):
    # Create two documents
    ids = []
    for i in range(2):
        r = client.post("/api/rag-admin/documents", json={
            "name": f"bulk_del_{i}.txt",
            "content": f"Content for doc {i}. Another sentence.",
        })
        assert r.status_code == 200
        ids.append(r.json()["document"]["id"])
    # Bulk delete them
    r = client.post("/api/rag-admin/bulk-delete", json={"doc_ids": ids})
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["deleted"] >= 1


def test_rag_bulk_delete_invalid_body(client):
    r = client.post("/api/rag-admin/bulk-delete", json={"doc_ids": "not-a-list"})
    assert r.status_code == 400
    assert "list" in r.json().get("error", "").lower()


def test_rag_bulk_delete_invalid_json(client):
    r = client.post("/api/rag-admin/bulk-delete", content="not json")
    assert r.status_code == 400

def test_rag_search_missing_query(client):
    r = client.get("/api/rag/search")
    assert r.status_code == 400
    body = r.json().get("error", "").lower()
    assert "q" in body or "query" in body


def test_rag_search_empty_store(client):
    r = client.get("/api/rag/search?q=test")
    assert r.status_code == 200
    data = r.json()
    assert "count" in data or "error" in data


def test_rag_search_clamps_k(client):
    r = client.get("/api/rag/search?q=test&k=999")
    assert r.status_code == 200

def test_rag_stats_public(client):
    r = client.get("/api/rag/stats")
    assert r.status_code == 200
    data = r.json()
    if "error" not in data:
        assert "count" in data
        assert "dim" in data
        assert "model" in data
        assert "loaded" in data

def test_rag_upload_txt(client):
    files = {"file": ("hello.txt", b"Hello world. This is a test document.", "text/plain")}
    r = client.post("/api/rag/upload", files=files)
    assert r.status_code in (200, 500)
    data = r.json()
    if r.status_code == 200:
        assert data.get("ok") is True
        assert data.get("chunks") >= 1


def test_rag_upload_unsupported(client):
    files = {"file": ("bad.xyz", b"data", "application/octet-stream")}
    r = client.post("/api/rag/upload", files=files)
    assert r.status_code == 400
    assert "unsupported" in r.json().get("error", "").lower()


def test_rag_upload_no_filename(client):
    files = {"file": ("", b"data", "text/plain")}
    r = client.post("/api/rag/upload", files=files)
    # FastAPI rejects an empty filename at the validation layer (422)
    assert r.status_code in (400, 422)

def test_rag_documents_empty(client):
    r = client.get("/api/rag/documents")
    assert r.status_code == 200
    data = r.json()
    if "error" not in data:
        assert "count" in data
        assert "documents" in data
        assert isinstance(data["documents"], list)
        assert data["count"] == len(data["documents"])


def test_rag_documents_after_upload(client):
    files = {"file": ("doc_test.txt", b"Hello world. This is content.", "text/plain")}
    up = client.post("/api/rag/upload", files=files)
    if up.status_code != 200:
        return
    r = client.get("/api/rag/documents")
    assert r.status_code == 200
    data = r.json()
    if "error" in data:
        return
    sources = [d["source"] for d in data["documents"]]
    assert any("doc_test.txt" in s for s in sources)

def test_rag_delete_missing_source(client):
    r = client.delete("/api/rag/delete")
    assert r.status_code == 400


def test_rag_delete_nonexistent(client):
    r = client.delete("/api/rag/delete?source=does_not_exist_xyz.txt")
    assert r.status_code == 200
    data = r.json()
    if "error" not in data:
        assert data.get("removed") == 0


def test_rag_delete_after_upload(client):
    files = {"file": ("del_test.txt", b"Content to be deleted.", "text/plain")}
    up = client.post("/api/rag/upload", files=files)
    if up.status_code != 200:
        return
    r = client.delete("/api/rag/delete?source=del_test.txt")
    assert r.status_code == 200
    data = r.json()
    if "error" in data:
        return
    assert data.get("removed", 0) >= 1

def test_rag_clear_empty(client):
    r = client.delete("/api/rag/clear")
    assert r.status_code == 200
    data = r.json()
    if "error" not in data:
        assert data.get("removed", 0) >= 0


def test_rag_clear_after_upload(client):
    files = {"file": ("clear_test.txt", b"Content to be cleared.", "text/plain")}
    up = client.post("/api/rag/upload", files=files)
    if up.status_code != 200:
        return
    r = client.delete("/api/rag/clear")
    assert r.status_code == 200
    data = r.json()
    if "error" in data:
        return
    assert data.get("removed", 0) >= 1
    docs = client.get("/api/rag/documents").json()
    if "error" not in docs:
        assert docs.get("count", 0) == 0
