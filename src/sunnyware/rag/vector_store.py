# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""FAISS vector store — per-tenant index at /data/vector_store/{org_id}/."""

import json
from pathlib import Path
from typing import List, Dict

import numpy as np


class FPAVectorStore:
    """Local FAISS index. Persists to /data/vector_store/{org_id}/."""

    def __init__(self, org_id: str = "default", dim: int = 384):
        self.org_id = org_id or "default"
        self.dim = dim
        self._index = None
        self._metadata: List[Dict] = []

    def _store_dir(self) -> Path:
        try:
            from .. import paths as _paths
            base = _paths.data_root() / "vector_store" / self.org_id
        except Exception:
            base = Path("./data") / "vector_store" / self.org_id
        base.mkdir(parents=True, exist_ok=True)
        return base

    def _index_path(self) -> Path:
        return self._store_dir() / "index.faiss"

    def _meta_path(self) -> Path:
        return self._store_dir() / "meta.json"

    def _ensure_index(self):
        if self._index is not None:
            return
        try:
            import faiss
        except ImportError:
            raise RuntimeError("faiss-cpu not installed")
        if self._index_path().exists():
            self._index = faiss.read_index(str(self._index_path()))
            self._metadata = json.loads(self._meta_path().read_text(encoding="utf-8"))
        else:
            self._index = faiss.IndexFlatL2(self.dim)
            self._metadata = []

    def add(self, vectors: List[List[float]], metadata: List[Dict]) -> int:
        """Add vectors + metadata pairs. Returns count added."""
        if not vectors:
            return 0
        self._ensure_index()
        arr = np.asarray(vectors, dtype=np.float32)
        if arr.shape[1] != self.dim:
            raise ValueError(f"expected dim {self.dim}, got {arr.shape[1]}")
        self._index.add(arr)
        self._metadata.extend(metadata)
        return len(vectors)

    def search(self, query_vector: List[float], k: int = 3) -> List[Dict]:
        """Return top-k results. Each = {distance, metadata}."""
        if self._index is None:
            self._ensure_index()
        if self._index.ntotal == 0:
            return []
        q = np.asarray([query_vector], dtype=np.float32)
        distances, indices = self._index.search(q, min(k, self._index.ntotal))
        out = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < 0 or idx >= len(self._metadata):
                continue
            out.append({
                "distance": float(dist),
                "metadata": self._metadata[idx],
            })
        return out

    def save(self):
        """Persist index + metadata to disk."""
        self._ensure_index()
        import faiss
        faiss.write_index(self._index, str(self._index_path()))
        self._meta_path().write_text(
            json.dumps(self._metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load(self):
        """Reload from disk. Idempotent."""
        self._index = None
        self._metadata = []
        self._ensure_index()

    def count(self) -> int:
        self._ensure_index()
        return int(self._index.ntotal)

    def clear(self):
        """Wipe the index and metadata. Does not delete files until save()."""
        import faiss
        self._index = faiss.IndexFlatL2(self.dim)
        self._metadata = []

    def status(self) -> dict:
        self._ensure_index()
        return {
            "org_id": self.org_id,
            "dim": self.dim,
            "count": self.count(),
            "store_dir": str(self._store_dir()),
        }
