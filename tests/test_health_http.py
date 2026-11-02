# -*- coding: utf-8 -*-
"""
Part 578: HTTP-level test for the /health/ready endpoint.
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


def test_health_ready(client):
    r = client.get("/health/ready")
    assert r.status_code == 200
    data = r.json()
    assert "checks" in data
    assert "status" in data
    assert data["status"] in ("ok", "degraded")
    assert "lifespan_ran" in data["checks"]
    assert "llm" in data["checks"]
    assert "tools" in data["checks"]
