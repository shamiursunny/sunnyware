"""Part 580: Tests for vector_store search result formatting."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from sunnyware.rag.vector_store import _format_search_result


def test_score_normalization():
    out = _format_search_result(0.0, {"text": "a"}, rank=0)
    assert out["score"] == 1.0
    assert out["rank"] == 0
    assert out["metadata"]["text"] == "a"


def test_score_positive_distance():
    out = _format_search_result(1.0, {"text": "b"}, rank=1)
    assert out["score"] == 0.5
    assert out["rank"] == 1


def test_score_large_distance():
    out = _format_search_result(9.0, {}, rank=2)
    assert out["score"] == 0.1
    assert out["rank"] == 2


def test_score_negative_distance_safety():
    out = _format_search_result(-1.0, {}, rank=0)
    assert out["score"] == 0.0


def test_score_rounding():
    out = _format_search_result(0.12345678, {}, rank=0)
    assert isinstance(out["score"], float)
    assert 0.0 <= out["score"] <= 1.0


def test_preserves_distance_and_metadata():
    md = {"source": "file.pdf", "chunk_id": 3}
    out = _format_search_result(0.5, md, rank=4)
    assert out["distance"] == 0.5
    assert out["metadata"] is md
