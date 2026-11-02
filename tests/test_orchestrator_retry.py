"""Part 576: Tests for transient error detection in orchestrator."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from sunnyware.orchestrator import _is_transient_error


def test_transient_timeout():
    assert _is_transient_error("Connection timed out") is True
    assert _is_transient_error("TimeoutError: request timed out") is True


def test_transient_connection():
    assert _is_transient_error("ConnectionResetError: connection reset by peer") is True


def test_transient_rate_limit():
    assert _is_transient_error("HTTP 429: rate limit exceeded") is True
    assert _is_transient_error("503 Service Unavailable") is True


def test_permanent_tool_denied():
    assert _is_transient_error("tool_denied") is False


def test_permanent_approval_timeout():
    assert _is_transient_error("approval_timeout") is False


def test_permanent_unknown_tool():
    assert _is_transient_error("unknown tool: foo") is False


def test_permanent_schema_violation():
    assert _is_transient_error("schema_violation") is False


def test_mixed_permanent_wins():
    assert _is_transient_error("tool_denied: connection refused") is False


def test_empty():
    assert _is_transient_error("") is False
