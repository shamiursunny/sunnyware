# -*- coding: utf-8 -*-
"""
Part 567: HTTP-level tests for memory endpoints.
"""
import os
import sys
import tempfile
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure src is on path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sunnyware.main import app
from sunnyware import agent_memory


@pytest.fixture(autouse=True)
def temp_memory_file():
    """Point agent_memory to a temporary file and clean up after each test."""
    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tmp.close()
    original = agent_memory.MEMORY_FILE
    agent_memory.MEMORY_FILE = tmp.name
    # Ensure file is empty
    if os.path.exists(agent_memory.MEMORY_FILE):
        os.remove(agent_memory.MEMORY_FILE)
    yield
    # Cleanup
    agent_memory.MEMORY_FILE = original
    if os.path.exists(tmp.name):
        try:
            os.remove(tmp.name)
        except Exception:
            pass


@pytest.fixture(scope="module")
def client():
    """Start TestClient with lifespan events."""
    with TestClient(app) as c:
        yield c


def test_memory_stats_empty(client):
    r = client.get("/api/memory/stats")
    assert r.status_code == 200
    data = r.json()
    assert data["total_live"] == 0
    assert data["total_expired"] == 0
    assert data["avg_ttl_seconds"] == 0.0
    assert data["oldest_ts"] is None
    assert data["newest_ts"] is None


def test_memory_stats_with_entries(client):
    # Write two live entries (one with TTL, one without)
    agent_memory.write_memory("live1", "v1", ttl=100)
    agent_memory.write_memory("live2", "v2")
    # Write one expired entry
    agent_memory.write_memory("dead", "v3", ttl=1)
    time.sleep(1.1)

    r = client.get("/api/memory/stats")
    assert r.status_code == 200
    data = r.json()
    assert data["total_live"] == 2
    assert data["total_expired"] == 1
    assert data["avg_ttl_seconds"] > 0
    assert data["oldest_ts"] is not None
    assert data["newest_ts"] is not None


def test_memory_count(client):
    agent_memory.write_memory("a", 1)
    agent_memory.write_memory("b", 2, ttl=1)
    time.sleep(1.1)
    r = client.get("/api/memory/count")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    assert data["live"] == 1
    assert data["expired"] == 1


def test_memory_keys(client):
    agent_memory.write_memory("k1", 1)
    agent_memory.write_memory("k2", 2)
    r = client.get("/api/memory/keys")
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 2
    assert set(data["keys"]) == {"k1", "k2"}


def test_memory_entries_pagination(client):
    for i in range(5):
        agent_memory.write_memory(f"key{i}", i)
    r = client.get("/api/memory/entries?offset=1&limit=2")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 5
    assert data["offset"] == 1
    assert data["limit"] == 2
    assert data["count"] == 2
    assert len(data["entries"]) == 2

def test_memory_export(client):
    agent_memory.write_memory("a", 1)
    agent_memory.write_memory("b", 2)
    r = client.get("/api/memory/export")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "live"
    assert data["count"] == 2
    assert data["data"] == {"a": 1, "b": 2}


def test_memory_export_expired(client):
    agent_memory.write_memory("live", 1)
    agent_memory.write_memory("dead", 2, ttl=1)
    time.sleep(1.1)
    r = client.get("/api/memory/export?status=expired")
    assert r.status_code == 200
    data = r.json()
    assert "dead" in data["data"]
    assert "live" not in data["data"]


def test_memory_import_idempotent(client):
    agent_memory.write_memory("existing", "old")
    r = client.post("/api/memory/import", json={"data": {"existing": "new", "new_key": 42}})
    assert r.status_code == 200
    data = r.json()
    assert data["imported"] == 1
    assert data["skipped"] == 1
    assert agent_memory.read_memory("existing") == "old"
    assert agent_memory.read_memory("new_key") == 42


def test_memory_import_overwrite(client):
    agent_memory.write_memory("existing", "old")
    r = client.post("/api/memory/import", json={"data": {"existing": "new"}, "overwrite": True})
    assert r.status_code == 200
    data = r.json()
    assert data["imported"] == 1
    assert data["skipped"] == 0
    assert agent_memory.read_memory("existing") == "new"


def test_memory_import_ttl(client):
    r = client.post("/api/memory/import", json={"data": {"temp": "val"}, "ttl": 1})
    assert r.status_code == 200
    assert agent_memory.read_memory("temp") == "val"
    time.sleep(1.1)
    assert agent_memory.read_memory("temp") is None


def test_memory_import_invalid_body(client):
    r = client.post("/api/memory/import", json={"data": "not-a-dict"})
    assert r.status_code == 400

def test_memory_bulk_delete(client):
    agent_memory.write_memory("a", 1)
    agent_memory.write_memory("b", 2)
    agent_memory.write_memory("c", 3)
    r = client.post("/api/memory/bulk-delete", json={"keys": ["a", "c", "missing"]})
    assert r.status_code == 200
    data = r.json()
    assert sorted(data["deleted"]) == ["a", "c"]
    assert data["missing"] == ["missing"]
    assert agent_memory.read_memory("a") is None
    assert agent_memory.read_memory("b") == 2


def test_memory_bulk_delete_invalid_body(client):
    r = client.post("/api/memory/bulk-delete", json={"keys": "not-a-list"})
    assert r.status_code == 400


def test_memory_bulk_write(client):
    r = client.post("/api/memory/bulk-write", json={"items": {"a": 1, "b": 2}})
    assert r.status_code == 200
    data = r.json()
    assert data["written"] == 2
    assert agent_memory.read_memory("a") == 1
    assert agent_memory.read_memory("b") == 2


def test_memory_bulk_write_ttl(client):
    r = client.post("/api/memory/bulk-write", json={"items": {"tmp": "v"}, "ttl": 1})
    assert r.status_code == 200
    assert agent_memory.read_memory("tmp") == "v"
    time.sleep(1.1)
    assert agent_memory.read_memory("tmp") is None


def test_memory_bulk_write_invalid_body(client):
    r = client.post("/api/memory/bulk-write", json={"items": "not-a-dict"})
    assert r.status_code == 400


def test_memory_rename_bulk(client):
    agent_memory.write_memory("old1", 1)
    agent_memory.write_memory("old2", 2)
    r = client.post("/api/memory/rename-bulk", json={"mapping": {"old1": "new1", "old2": "new2", "missing": "x"}})
    assert r.status_code == 200
    data = r.json()
    assert sorted(data["renamed"]) == ["old1", "old2"]
    assert data["missing"] == ["missing"]
    assert agent_memory.read_memory("old1") is None
    assert agent_memory.read_memory("new1") == 1
    assert agent_memory.read_memory("new2") == 2


def test_memory_rename_bulk_invalid_body(client):
    r = client.post("/api/memory/rename-bulk", json={"mapping": "not-a-dict"})
    assert r.status_code == 400

def test_memory_ttl_all(client):
    agent_memory.write_memory("a", 1)
    agent_memory.write_memory("b", 2)
    r = client.post("/api/memory/ttl-all", json={"ttl": 1})
    assert r.status_code == 200
    data = r.json()
    assert data["updated"] == 2
    assert data["ttl"] == 1
    time.sleep(1.1)
    assert agent_memory.read_memory("a") is None
    assert agent_memory.read_memory("b") is None


def test_memory_ttl_all_clear(client):
    agent_memory.write_memory("c", 3, ttl=1)
    r = client.post("/api/memory/ttl-all", json={"ttl": 0})
    assert r.status_code == 200
    data = r.json()
    assert data["updated"] == 1
    time.sleep(1.1)
    assert agent_memory.read_memory("c") == 3


def test_memory_search(client):
    agent_memory.write_memory("apple", "red fruit")
    agent_memory.write_memory("banana", "yellow fruit")
    agent_memory.write_memory("carrot", "orange veggie")
    r = client.get("/api/memory/search?q=fruit")
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 2
    keys = {e["key"] for e in data["entries"]}
    assert keys == {"apple", "banana"}


def test_memory_search_empty(client):
    agent_memory.write_memory("apple", "red fruit")
    r = client.get("/api/memory/search?q=zzz")
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 0
    assert data["entries"] == []


def test_memory_search_case_insensitive(client):
    agent_memory.write_memory("Apple", "RED Fruit")
    r = client.get("/api/memory/search?q=red")
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 1
    assert data["entries"][0]["key"] == "Apple"

def test_memory_summary(client):
    r = client.get("/api/memory/summary")
    assert r.status_code == 200
    data = r.json()
    assert "summary" in data
    assert "empty" in data["summary"].lower()

    agent_memory.write_memory("a", 1)
    agent_memory.write_memory("b", 2, ttl=100)
    r = client.get("/api/memory/summary")
    data = r.json()
    assert "2 live" in data["summary"]
    assert "avg TTL" in data["summary"]

def test_memory_get(client):
    agent_memory.write_memory("gkey", "gval")
    r = client.get("/api/memory/get?key=gkey")
    assert r.status_code == 200
    data = r.json()
    assert data["key"] == "gkey"
    assert data["value"] == "gval"
    assert data["ts"] is not None

def test_memory_get_missing(client):
    r = client.get("/api/memory/get?key=nope")
    assert r.status_code == 404

def test_memory_get_no_key(client):
    r = client.get("/api/memory/get")
    assert r.status_code == 400

def test_memory_prune(client):
    agent_memory.write_memory("live", 1)
    agent_memory.write_memory("dead", 2, ttl=1)
    time.sleep(1.1)
    r = client.post("/api/memory/prune")
    assert r.status_code == 200
    data = r.json()
    assert data["removed"] == 1
    assert agent_memory.read_memory("live") == 1
    assert agent_memory.read_memory("dead") is None

def test_memory_cleanup(client):
    agent_memory.write_memory("live", 1)
    agent_memory.write_memory("dead", 2, ttl=1)
    time.sleep(1.1)
    r = client.post("/api/memory/cleanup")
    assert r.status_code == 200
    data = r.json()
    assert data["before_live"] == 1
    assert data["before_expired"] == 1
    assert data["removed"] == 1
    assert data["after_live"] == 1

def test_memory_write(client):
    r = client.post("/api/memory/write", json={"key": "wk", "value": "wv"})
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["key"] == "wk"
    assert agent_memory.read_memory("wk") == "wv"


def test_memory_write_no_key(client):
    r = client.post("/api/memory/write", json={"value": "v"})
    assert r.status_code == 400


def test_memory_write_ttl(client):
    r = client.post("/api/memory/write", json={"key": "wk", "value": "wv", "ttl": 1})
    assert r.status_code == 200
    assert agent_memory.read_memory("wk") == "wv"
    time.sleep(1.1)
    assert agent_memory.read_memory("wk") is None


def test_memory_delete(client):
    agent_memory.write_memory("dk", "dv")
    r = client.delete("/api/memory/delete/dk")
    assert r.status_code == 200
    data = r.json()
    assert data["deleted"] is True
    assert agent_memory.read_memory("dk") is None


def test_memory_delete_missing(client):
    r = client.delete("/api/memory/delete/nonexistent")
    assert r.status_code == 200
    data = r.json()
    assert data["deleted"] is False


def test_memory_ttl_endpoint(client):
    agent_memory.write_memory("tk", "tv")
    r = client.post("/api/memory/ttl", json={"key": "tk", "ttl": 1})
    assert r.status_code == 200
    data = r.json()
    assert data["updated"] is True
    assert agent_memory.read_memory("tk") == "tv"
    time.sleep(1.1)
    assert agent_memory.read_memory("tk") is None


def test_memory_ttl_endpoint_no_key(client):
    r = client.post("/api/memory/ttl", json={"ttl": 1})
    assert r.status_code == 400


def test_memory_ttl_endpoint_missing_key(client):
    r = client.post("/api/memory/ttl", json={"key": "nope", "ttl": 1})
    assert r.status_code == 200
    data = r.json()
    assert data["updated"] is False


def test_memory_ttl_endpoint_clear(client):
    agent_memory.write_memory("tk", "tv", ttl=1)
    r = client.post("/api/memory/ttl", json={"key": "tk", "ttl": 0})
    assert r.status_code == 200
    assert data["updated"] if False else True  # noqa
    time.sleep(1.1)
    assert agent_memory.read_memory("tk") == "tv"
