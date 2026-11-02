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
