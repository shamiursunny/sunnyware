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

def test_web_fetch_tool_call(client):
    """Web fetch should extract the URL."""
    prompt = "fetch the content of https://example.com"
    with client.stream("POST", "/api/agent/stream", json={
        "input": prompt,
        "session_id": "test-webfetch-494",
    }) as resp:
        assert resp.status_code == 200
        tools = list(_parse_sse(resp))
    assert any(t[0] == "web_fetch" for t in tools), f"web_fetch not found in {tools}"
    assert any(t[1] == {"url": "https://example.com"} for t in tools if t[0] == "web_fetch")


def test_browser_goto_tool_call(client):
    """Browser goto should extract the URL."""
    prompt = "open https://example.com in the browser"
    with client.stream("POST", "/api/agent/stream", json={
        "input": prompt,
        "session_id": "test-browsergoto-494",
    }) as resp:
        assert resp.status_code == 200
        tools = list(_parse_sse(resp))
    assert any(t[0] == "browser_goto" for t in tools), f"browser_goto not found in {tools}"
    assert any(t[1] == {"url": "https://example.com"} for t in tools if t[0] == "browser_goto")


def test_chart_from_data_tool_call(client):
    """Chart from data should extract numbers and chart type."""
    prompt = "plot a bar chart with 10, 20, 30"
    with client.stream("POST", "/api/agent/stream", json={
        "input": prompt,
        "session_id": "test-chart-494",
    }) as resp:
        assert resp.status_code == 200
        tools = list(_parse_sse(resp))
    assert any(t[0] == "chart_from_data" for t in tools), f"chart_from_data not found in {tools}"
    assert any(t[1] == {"data": "[10, 20, 30]", "chart_type": "bar"} for t in tools if t[0] == "chart_from_data")


def test_research_search_tool_call(client):
    """Research search should extract the query."""
    prompt = "research the topic of quantum computing"
    with client.stream("POST", "/api/agent/stream", json={
        "input": prompt,
        "session_id": "test-research-494",
    }) as resp:
        assert resp.status_code == 200
        tools = list(_parse_sse(resp))
    assert any(t[0] == "research_search" for t in tools), f"research_search not found in {tools}"
    assert any(t[1] == {"query": "quantum computing"} for t in tools if t[0] == "research_search")
