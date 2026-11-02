"""Part 579: Tests for sentence-aware chunking."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from sunnyware.rag.chunker import chunk_text, _split_at_sentence


def test_split_empty():
    assert _split_at_sentence("", 100) == []


def test_split_short_text():
    pieces = _split_at_sentence("Hello world.", 100)
    assert len(pieces) == 1
    assert pieces[0] == "Hello world."


def test_split_respects_sentences():
    text = "First sentence. Second sentence. Third sentence."
    pieces = _split_at_sentence(text, 30)
    assert all(len(p) <= 30 for p in pieces)
    assert len(pieces) >= 2


def test_split_long_sentence():
    text = "A" * 250
    pieces = _split_at_sentence(text, 100)
    assert all(len(p) <= 100 for p in pieces)
    assert sum(len(p) for p in pieces) == 250


def test_chunk_text_short():
    chunks = chunk_text("Hello world. This is short.", source="test.txt", chunk_chars=100)
    assert len(chunks) == 1
    assert chunks[0]["source"] == "test.txt"
    assert chunks[0]["chunk_id"] == 0


def test_chunk_text_long():
    text = ("This is sentence one. " * 50).strip()
    chunks = chunk_text(text, source="test.txt", chunk_chars=200, overlap_chars=20)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c["text"]) <= 200
        assert c["source"] == "test.txt"


def test_chunk_text_empty():
    assert chunk_text("", source="x") == []
    assert chunk_text("   ", source="x") == []
