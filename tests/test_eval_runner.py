"""Tests for eval_runner scoring + case loading."""

from sunnyware.eval_runner import _check_expectations, load_cases


def test_check_contains_all():
    r = _check_expectations({"expect_contains": ["pong"]}, "Pong!", [], None)
    assert r["passed"] is True


def test_check_contains_missing():
    r = _check_expectations({"expect_contains": ["xyz"]}, "pong", [], None)
    assert r["passed"] is False


def test_check_any_match():
    r = _check_expectations({"expect_any": ["a", "b"]}, "has b here", [], None)
    assert r["passed"] is True


def test_check_any_none():
    r = _check_expectations({"expect_any": ["a", "b"]}, "xyz", [], None)
    assert r["passed"] is False


def test_check_tool_called():
    steps = [{"tool": "calculator", "args": {}, "result": {}}]
    r = _check_expectations({"expect_tool_called": "calculator"}, "6", steps, None)
    assert r["passed"] is True


def test_check_tool_not_called():
    r = _check_expectations({"expect_tool_called": "weather"}, "6", [], None)
    assert r["passed"] is False


def test_check_no_tools_required():
    r = _check_expectations({"expect_no_tools": True}, "hello", [], None)
    assert r["passed"] is True
    r2 = _check_expectations({"expect_no_tools": True}, "hello", [{"tool": "echo"}], None)
    assert r2["passed"] is False


def test_check_error_short_circuit():
    r = _check_expectations({"expect_contains": ["hi"]}, "hi", [], "boom")
    assert r["passed"] is False
    assert any("error" in f for f in r["failures"])


def test_check_case_insensitive():
    r = _check_expectations({"expect_contains": ["PONG"]}, "pong here", [], None)
    assert r["passed"] is True


def test_load_cases():
    cases = load_cases()
    assert len(cases) >= 8
    ids = {c["id"] for c in cases}
    assert "echo_1" in ids
    assert "math_simple" in ids
    assert "tool_calculator" in ids
