# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Text chunking — 1024-token chunks with 100-token overlap."""

from typing import List, Dict

CHUNK_CHARS = 4096   # ~1024 tokens (4 chars/token heuristic)
OVERLAP_CHARS = 400  # ~100 tokens


def chunk_text(text: str, source: str, chunk_chars: int = CHUNK_CHARS,
               overlap_chars: int = OVERLAP_CHARS) -> List[Dict]:
    """Split text into overlapping chunks. Each chunk has metadata."""
    if not text or not text.strip():
        return []

    text = text.strip()
    step = max(1, chunk_chars - overlap_chars)
    chunks = []
    idx = 0
    chunk_id = 0
    while idx < len(text):
        piece = text[idx:idx + chunk_chars]
        if not piece.strip():
            break
        chunks.append({
            "chunk_id": chunk_id,
            "source": source,
            "char_start": idx,
            "char_end": idx + len(piece),
            "text": piece,
        })
        chunk_id += 1
        idx += step
        if len(piece) < chunk_chars:
            break
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
