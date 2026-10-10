# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""RAG package — local embeddings, FAISS, FP&A report generation."""

from . import _threads  # noqa: F401 -- MUST be first (caps threads before torch)
from . import embeddings, chunker, extractor, vector_store, report_generator

__all__ = [
    "embeddings", "chunker", "extractor", "vector_store", "report_generator",
    "get_store", "reset_store_cache",
]

# ── In-memory store cache (per-tenant) ────────────────────
# FAISS indexes are cheap to keep in RAM but expensive to reload
# from disk on every request. Cache by org_id.
_STORES: dict = {}


def get_store(org_id: str = "default"):
    """Return a cached FPAVectorStore for this org. Loads from disk if exists."""
    oid = org_id or "default"
    if oid not in _STORES:
        _STORES[oid] = vector_store.FPAVectorStore(
            org_id=oid, dim=embeddings.dim()
        )
    return _STORES[oid]


def reset_store_cache():
    """Forget all cached stores (used in tests / after manual disk wipes)."""
    _STORES.clear()
