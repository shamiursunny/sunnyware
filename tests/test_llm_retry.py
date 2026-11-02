"""Part 577: Tests for transient HTTP status detection in llm.py."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from sunnyware.llm import _is_transient_http_status


def test_transient_5xx():
    assert _is_transient_http_status(500) is True
    assert _is_transient_http_status(502) is True
    assert _is_transient_http_status(503) is True
    assert _is_transient_http_status(504) is True


def test_not_transient():
    assert _is_transient_http_status(200) is False
    assert _is_transient_http_status(400) is False
    assert _is_transient_http_status(401) is False
    assert _is_transient_http_status(403) is False
    assert _is_transient_http_status(404) is False
    assert _is_transient_http_status(429) is False
