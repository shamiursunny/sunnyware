"""Tests for orchestrator JSON parsing + schema building."""

from sunnyware.orchestrator import _parse_json_response, _build_tools_schema


def test_parse_direct_json():
    assert _parse_json_response('{"answer": "hi"}') == {"answer": "hi"}


def test_parse_markdown_fence():
    r = _parse_json_response('```json\n{"tool": "echo", "args": {}}\n```')
    assert r == {"tool": "echo", "args": {}}


def test_parse_extra_text():
    r = _parse_json_response('blah blah {"answer": "hi"} trailing')
    assert r == {"answer": "hi"}


def test_parse_invalid():
    assert _parse_json_response("not json") is None


def test_parse_empty():
    assert _parse_json_response("") is None


def test_parse_none():
    assert _parse_json_response(None) is None


def test_schema_has_function_type():
    schemas = _build_tools_schema()
    assert len(schemas) >= 14
    assert schemas[0]["type"] == "function"
    assert "name" in schemas[0]["function"]
    assert "parameters" in schemas[0]["function"]


def test_schema_parameters_shape():
    schemas = _build_tools_schema()
    for s in schemas:
        params = s["function"]["parameters"]
        assert params["type"] == "object"
        assert isinstance(params["properties"], dict)
        assert isinstance(params["required"], list)
