# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Text chunking — 1024-token chunks with 100-token overlap."""

from typing import List, Dict

CHUNK_CHARS = 4096   # ~1024 tokens (4 chars/token heuristic)
OVERLAP_CHARS = 400  # ~100 tokens


import re as _re579

_SENTENCE_SPLIT = _re579.compile(r"(?<=[.!?])\s+|\n+")


def _split_at_sentence(text: str, max_chars: int) -> list:
    """Split text into pieces <= max_chars, preferring sentence boundaries.

    Falls back to hard character split when a single sentence exceeds max_chars.
    """
    if not text:
        return []
    pieces = []
    buf = ""
    for part in _SENTENCE_SPLIT.split(text):
        if not part:
            continue
        # If a single part is too long, hard-split it
        while len(part) > max_chars:
            head, part = part[:max_chars], part[max_chars:]
            if buf:
                pieces.append(buf)
                buf = ""
            pieces.append(head)
        candidate = (buf + " " + part).strip() if buf else part.strip()
        if len(candidate) <= max_chars:
            buf = candidate
        else:
            if buf:
                pieces.append(buf)
            buf = part.strip()
    if buf:
        pieces.append(buf)
    return pieces


def chunk_text(text: str, source: str, chunk_chars: int = CHUNK_CHARS,
               overlap_chars: int = OVERLAP_CHARS) -> List[Dict]:
    """Split text into overlapping chunks. Each chunk has metadata."""
    if not text or not text.strip():
        return []

    text = text.strip()
    chunks = []
    chunk_id = 0
    pos = 0
    for piece in _split_at_sentence(text, chunk_chars):
        if not piece.strip():
            continue
        char_start = text.find(piece, pos)
        if char_start < 0:
            char_start = pos
        char_end = char_start + len(piece)
        chunks.append({
            "chunk_id": chunk_id,
            "source": source,
            "char_start": char_start,
            "char_end": char_end,
            "text": piece,
        })
        chunk_id += 1
        pos = max(pos, char_end - overlap_chars)
    return chunks


def chunk_rows(rows: List[Dict], source: str, template: str = None) -> List[Dict]:
    """Convert spreadsheet rows into semantic string chunks."""
    chunks = []
    for i, row in enumerate(rows):
        if template:
            try:
                txt = template.format(**row)
            except Exception:
                txt = " | ".join(f"{k}: {v}" for k, v in row.items())
        else:
            txt = " | ".join(f"{k}: {v}" for k, v in row.items())
        chunks.append({
            "chunk_id": i,
            "source": source,
            "char_start": 0,
            "char_end": len(txt),
            "text": txt,
        })
    return chunks
