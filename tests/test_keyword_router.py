"""Smoke tests for the keyword router — verifies math detection and tool routing."""
import pytest
from sunnyware.keyword_router import keyword_route


def test_math_adds_to_calculator():
    result = keyword_route("1/2 + 2")
    assert result is not None
    assert result["tool"] == "calculator"
    assert "expression" in result["args"]


def test_math_pure_expression():
    result = keyword_route("2 + 2")
    assert result is not None
    assert result["tool"] == "calculator"


def test_greeting_returns_none():
    assert keyword_route("hello") is None


def test_empty_returns_none():
    assert keyword_route("") is None
