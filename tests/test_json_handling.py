"""Regression test for Part 721 — _build_tools_schema must handle string metadata."""
from sunnyware.orchestrator import _build_tools_schema


def test_build_tools_schema_does_not_crash():
    """If any tool has a non-dict parameters value, _build_tools_schema should
    skip it gracefully rather than raise AttributeError."""
    schema = _build_tools_schema(role=None)
    assert isinstance(schema, list)
    for entry in schema:
        assert isinstance(entry, dict)
        assert entry.get("type") == "function"
