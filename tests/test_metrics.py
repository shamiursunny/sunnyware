"""Tests for in-memory metrics."""

from sunnyware import metrics


def test_incr_increments():
    metrics.reset()
    metrics.incr("requests_total", 3)
    assert metrics.snapshot()["requests_total"] == 3


def test_incr_default_one():
    metrics.reset()
    metrics.incr("requests_total")
    assert metrics.snapshot()["requests_total"] == 1


def test_incr_labeled():
    metrics.reset()
    metrics.incr_labeled("tool_calls_by_name", "echo", 2)
    snap = metrics.snapshot()
    assert snap["tool_calls_by_name"]["echo"] == 2


def test_incr_labeled_multiple():
    metrics.reset()
    metrics.incr_labeled("tool_calls_by_name", "echo")
    metrics.incr_labeled("tool_calls_by_name", "calculator")
    metrics.incr_labeled("tool_calls_by_name", "echo")
    snap = metrics.snapshot()
    assert snap["tool_calls_by_name"]["echo"] == 2
    assert snap["tool_calls_by_name"]["calculator"] == 1


def test_snapshot_has_all_counters():
    snap = metrics.snapshot()
    for key in ("requests_total", "tool_calls_total", "llm_calls_total",
                "llm_errors_total", "errors_total", "uptime_seconds", "persist"):
        assert key in snap


def test_snapshot_persist_block():
    snap = metrics.snapshot()
    p = snap["persist"]
    assert "enabled" in p
    assert "last_flush_unix" in p
    assert "dirty_keys" in p
    assert "loaded_from_db" in p


def test_reset_zeros_counters():
    metrics.incr("requests_total", 10)
    metrics.reset()
    assert metrics.snapshot()["requests_total"] == 0


def test_reset_clears_labels():
    metrics.incr_labeled("tool_calls_by_name", "echo")
    metrics.reset()
    assert metrics.snapshot()["tool_calls_by_name"] == {}


def test_uptime_nonnegative():
    snap = metrics.snapshot()
    assert snap["uptime_seconds"] >= 0
