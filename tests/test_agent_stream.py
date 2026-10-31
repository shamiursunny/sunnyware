# -*- coding: utf-8 -*-
"""
Part 491: Integration tests for /api/agent/stream tool-calling.
Covers calculator (safe), web_search (network), and email routing safety check.
"""
import os
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Load .env so LLM providers are available
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sunnyware.main import app


@pytest.fixture(scope="module")
def client():
    """Start TestClient with lifespan events."""
    with TestClient(app) as c:
        yield c


def _parse_sse(response):
    """Yield (tool_name, args) for each tool_call event."""
    for line in response.iter_lines():
        if not line:
            continue
        if isinstance(line, bytes):
            line = line.decode("utf-8", errors="replace")
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload:
            continue
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if data.get("type") == "tool_call":
            yield data.get("tool"), data.get("args")


def test_calculator_tool_call(client):
    """Calculator should be routed for a math prompt."""
    prompt = "What is 123 * 456? Use the calculator tool."
    with client.stream("POST", "/api/agent/stream", json={
        "input": prompt,
        "session_id": "test-calculator-491",
    }) as resp:
        assert resp.status_code == 200
        tools = list(_parse_sse(resp))
    assert any(t[0] == "calculator" for t in tools), f"calculator not found in {tools}"


def test_web_search_tool_call(client):
    """Web search should be routed for a search prompt."""
    prompt = "Search the web for python tutorials"
    with client.stream("POST", "/api/agent/stream", json={
        "input": prompt,
        "session_id": "test-websearch-491",
    }) as resp:
        assert resp.status_code == 200
        tools = list(_parse_sse(resp))
    assert any(t[0] == "web_search" for t in tools), f"web_search not found in {tools}"


def test_email_placeholder_routes_to_configured(client):
    """A placeholder email should trigger email_configured safety check."""
    prompt = "Send an email to test@example.com saying hello"
    with client.stream("POST", "/api/agent/stream", json={
        "input": prompt,
        "session_id": "test-email-placeholder-491",
    }) as resp:
        assert resp.status_code == 200
        tools = list(_parse_sse(resp))
    assert any(t[0] == "email_configured" for t in tools), f"email_configured not found in {tools}"


@pytest.mark.skip(reason="Email to real address sends actual email — verify manually")
def test_email_real_routes_to_send(client):
    """A real email should route to email_send (manual verification only)."""
    prompt = "Send an email to shamiur.sunny@gmail.com saying hello"
    with client.stream("POST", "/api/agent/stream", json={
        "input": prompt,
        "session_id": "test-email-real-491",
    }) as resp:
        assert resp.status_code == 200
        tools = list(_parse_sse(resp))
    assert any(t[0] == "email_send" for t in tools)
