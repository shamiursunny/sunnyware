# -*- coding: utf-8 -*-
"""
Part 496: Direct keyword_route tests for tools that are flaky via /api/agent/stream.
Deterministic and fast.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sunnyware.keyword_router import keyword_route


def test_sql_sandbox_drop_routing():
    """sql_sandbox_drop extracts name from prompt."""
    result = keyword_route("drop sandbox test")
    assert result == {"tool": "sql_sandbox_drop", "args": {"name": "test"}}


def test_api_call_routing():
    """api_call extracts URL and method from prompt."""
    result = keyword_route("make a GET request to https://api.example.com/data")
    assert result is not None
    assert result["tool"] == "api_call"
    assert result["args"] == {"url": "https://api.example.com/data", "method": "GET"}


def test_api_call_post_routing():
    """api_call detects POST method."""
    result = keyword_route("make a POST request to https://api.example.com/data")
    assert result is not None
    assert result["tool"] == "api_call"
    assert result["args"]["method"] == "POST"
