# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Thread caps for CPU-bound ML work (safe on old laptops).

MUST be imported before torch/sentence_transformers/numpy BLAS init.
Sets OMP/MKL/OpenBLAS env vars + provides runtime torch/faiss limiters.

Override via env:
  SUNNYWARE_CPU_THREADS=2   -> force 2 threads
  SUNNYWARE_CPU_THREADS=1   -> absolute minimum (safest, slowest)
"""

import os


def _detect_threads() -> int:
    """Half of logical cores, capped at 4 (old-laptop safe zone)."""
    try:
        total = os.cpu_count() or 4
    except Exception:
        total = 4
    half = max(1, total // 2)
    return min(half, 4)


_THREADS = max(1, int(os.getenv("SUNNYWARE_CPU_THREADS", str(_detect_threads()))))

# These MUST be set before torch / numpy BLAS loads.
for _var in (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ.setdefault(_var, str(_THREADS))

# HF tokenizer spawns its own thread pool -> disable.
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


def threads() -> int:
    return _THREADS


def apply_runtime_limits() -> dict:
    """Call AFTER torch is imported. Double-locks thread count at runtime."""
    out = {"threads": _THREADS, "torch": False, "faiss": False}
    try:
        import torch
        torch.set_num_threads(_THREADS)
        try:
            torch.set_num_interop_threads(1)
        except Exception:
            pass
        out["torch"] = True
    except Exception as e:
        out["torch_error"] = type(e).__name__ + ": " + str(e)
    try:
        import faiss
        faiss.omp_set_num_threads(_THREADS)
        out["faiss"] = True
    except Exception:
        pass
    return out
