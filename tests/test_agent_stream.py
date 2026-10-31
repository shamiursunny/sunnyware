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

def test_pdf_read_tool_call(client):
    """PDF routing should extract the file name."""
    prompt = "read test.pdf"
    with client.stream("POST", "/api/agent/stream", json={
        "input": prompt,
        "session_id": "test-pdf-492",
    }) as resp:
        assert resp.status_code == 200
        tools = list(_parse_sse(resp))
    assert any(t[0] == "pdf_read" for t in tools), f"pdf_read not found in {tools}"
    assert any(t[1] == {"file": "test.pdf"} for t in tools if t[0] == "pdf_read")


def test_excel_read_tool_call(client):
    """Excel routing should extract the file name."""
    prompt = "read sales.xlsx"
    with client.stream("POST", "/api/agent/stream", json={
        "input": prompt,
        "session_id": "test-excel-492",
    }) as resp:
        assert resp.status_code == 200
        tools = list(_parse_sse(resp))
    assert any(t[0] == "excel_read" for t in tools), f"excel_read not found in {tools}"
    assert any(t[1] == {"file": "sales.xlsx"} for t in tools if t[0] == "excel_read")


def test_sql_sandbox_create_tool_call(client):
    """SQL sandbox create should extract the sandbox name."""
    prompt = "create sql sandbox test"
    with client.stream("POST", "/api/agent/stream", json={
        "input": prompt,
        "session_id": "test-sqlcreate-492",
    }) as resp:
        assert resp.status_code == 200
        tools = list(_parse_sse(resp))
    assert any(t[0] == "sql_sandbox_create" for t in tools), f"sql_sandbox_create not found in {tools}"
    assert any(t[1] == {"name": "test"} for t in tools if t[0] == "sql_sandbox_create")


def test_sql_sandbox_load_csv_tool_call(client):
    """SQL sandbox load_csv should extract name, file, and table."""
    prompt = "load data.csv into sandbox test"
    with client.stream("POST", "/api/agent/stream", json={
        "input": prompt,
        "session_id": "test-sqlload-492",
    }) as resp:
        assert resp.status_code == 200
        tools = list(_parse_sse(resp))
    assert any(t[0] == "sql_sandbox_load_csv" for t in tools), f"sql_sandbox_load_csv not found in {tools}"
    assert any(t[1] == {"name": "test", "file": "data.csv", "table": "data"} for t in tools if t[0] == "sql_sandbox_load_csv")

def test_image_generate_tool_call(client):
    """Image generation should extract the prompt."""
    prompt = "generate an image of a cat"
    with client.stream("POST", "/api/agent/stream", json={
        "input": prompt,
        "session_id": "test-image-493",
    }) as resp:
        assert resp.status_code == 200
        tools = list(_parse_sse(resp))
    assert any(t[0] == "image_generate" for t in tools), f"image_generate not found in {tools}"
    assert any(t[1] == {"prompt": "a cat"} for t in tools if t[0] == "image_generate")


def test_sql_sandbox_execute_tool_call(client):
    """SQL sandbox execute should extract name and SQL."""
    prompt = "run sql in sandbox test: SELECT * FROM t"
    with client.stream("POST", "/api/agent/stream", json={
        "input": prompt,
        "session_id": "test-sqlexec-493",
    }) as resp:
        assert resp.status_code == 200
        tools = list(_parse_sse(resp))
    assert any(t[0] == "sql_sandbox_execute" for t in tools), f"sql_sandbox_execute not found in {tools}"
    assert any(t[1] == {"name": "test", "sql": "SELECT * FROM t"} for t in tools if t[0] == "sql_sandbox_execute")
