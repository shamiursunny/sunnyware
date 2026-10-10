# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Local embeddings via bge-small-en-v1.5 (CPU, ~130MB)."""

import os
from pathlib import Path

# Redirect model cache to persistent bucket BEFORE importing ST
try:
    from .. import paths as _paths
    hub = str(_paths.data_root() / "hub")
    Path(hub).mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HOME", hub)
    os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", hub)
except Exception:
    pass

_MODEL = None
_MODEL_ID = "BAAI/bge-small-en-v1.5"
_DIM = 384


def _load():
    """Lazy-load model on first use. Cached in /data/hub on HF."""
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    try:
        from sentence_transformers import SentenceTransformer
        # Enforce thread caps AFTER torch import (env vars alone are not enough)
        try:
            from . import _threads as _t
            limits = _t.apply_runtime_limits()
            import logging as _lg
            _lg.getLogger(__name__).info("rag_thread_limits %s", limits)
        except Exception:
            pass
        _MODEL = SentenceTransformer(_MODEL_ID, device="cpu")
        _MODEL.max_seq_length = 512
        return _MODEL
    except Exception as e:
        raise RuntimeError(f"Failed to load embedding model: {e}")


def dim() -> int:
    return _DIM


def model_id() -> str:
    return _MODEL_ID


def is_loaded() -> bool:
    return _MODEL is not None


def embed_texts(texts, batch_size: int = 4):
    """Embed a list of texts. Returns list of 384-dim lists (Python floats)."""
    if not texts:
        return []
    model = _load()
    vectors = model.encode(
        list(texts),
        batch_size=batch_size,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return vectors.tolist()


def embed_one(text: str):
    """Embed a single string. Returns 384-dim list."""
    return embed_texts([text])[0]


def status() -> dict:
    return {
        "model": _MODEL_ID,
        "dim": _DIM,
        "loaded": is_loaded(),
        "hf_home": os.environ.get("HF_HOME", "(default)"),
    }
