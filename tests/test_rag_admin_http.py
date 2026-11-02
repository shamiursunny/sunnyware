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
