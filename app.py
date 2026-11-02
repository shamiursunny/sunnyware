# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""HF Space entrypoint — launches sunnyware app with local model preload."""

import os

# ── CRITICAL: Set HF_HOME BEFORE any HuggingFace imports ──
os.environ.setdefault("HF_HOME", "/tmp/huggingface")
os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", "/tmp/huggingface")
os.environ["GRADIO_SSR_MODE"] = "false"
os.environ["GRADIO_ANALYTICS_ENABLED"] = "false"

# ── Local model configuration (llama-cpp-python, in-process) ──
os.environ.setdefault("LOCAL_MODEL_ENABLED", "1")
os.environ.setdefault("LOCAL_MODEL_CTX", "2048")
os.environ.setdefault("LOCAL_MODEL_BASE_URL", "in-process")
os.environ.setdefault("LOCAL_MODEL_API_KEY", "local")
os.environ.setdefault("LOCAL_MODEL", "qwen2.5-0.5b-instruct")

# Ensure LLM_PROVIDERS includes "local" as final fallback
_providers_env = (os.getenv("LLM_PROVIDERS") or "").strip()
if _providers_env and "local" not in _providers_env.split(","):
    os.environ["LLM_PROVIDERS"] = _providers_env + ",local"
elif not _providers_env:
    os.environ["LLM_PROVIDERS"] = "groq,gemini,openrouter,local"

import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    import spaces

    @spaces.GPU
    def _dummy_gpu():
        return "ok"

except ImportError:
    pass


# ── Determine writable data directory ──
def _pick_data_dir():
    for candidate in (Path("/data"), Path("/tmp/sunnyware")):
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            test = candidate / ".write_test"
            test.write_text("ok")
            test.unlink()
            return candidate
        except Exception:
            continue
    return Path("/tmp/sunnyware")


DATA_DIR = _pick_data_dir()
MODEL_DIR = DATA_DIR / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)
GGUF_PATH = MODEL_DIR / "qwen2.5-0.5b-instruct-q4_k_m.gguf"
os.environ.setdefault("LOCAL_MODEL_PATH", str(GGUF_PATH))


def _download_gguf():
    """Download the Qwen2.5-0.5B GGUF in the background (idempotent)."""
    if GGUF_PATH.exists() and GGUF_PATH.stat().st_size > 1_000_000:
        print(f"[start] GGUF already present: {GGUF_PATH}", flush=True)
        return
    try:
        from huggingface_hub import hf_hub_download
        print("[start] Downloading Qwen2.5-0.5B-Instruct GGUF (~400 MB)...", flush=True)
        hf_hub_download(
            repo_id="Qwen/Qwen2.5-0.5B-Instruct-GGUF",
            filename="qwen2.5-0.5b-instruct-q4_k_m.gguf",
            local_dir=str(MODEL_DIR),
            local_dir_use_symlinks=False,
        )
        # hf_hub_download sometimes places the file in a subdir
        for candidate in MODEL_DIR.rglob("qwen2.5-0.5b-instruct-q4_k_m.gguf"):
            if candidate != GGUF_PATH and candidate.exists():
                candidate.replace(GGUF_PATH)
                break
        print(f"[start] GGUF ready: {GGUF_PATH} ({GGUF_PATH.stat().st_size // 1024 // 1024} MB)", flush=True)
    except Exception as e:
        print(f"[start] GGUF download failed: {type(e).__name__}: {e}", flush=True)


def _preload_embedder():
    """Preload the bge-small-en-v1.5 embedder in background."""
    try:
        from sunnyware.rag import embeddings
        embeddings._load()
        print("[start] Embedder loaded OK", flush=True)
    except Exception as e:
        print(f"[start] Embedder preload failed: {type(e).__name__}: {e}", flush=True)


# ── Import the app AFTER env setup ──
from sunnyware.main import app  # noqa: E402

demo = app


if __name__ == "__main__":
    # Kick off background preloads
    threading.Thread(target=_download_gguf, daemon=True, name="gguf-download").start()
    threading.Thread(target=_preload_embedder, daemon=True, name="embedder-preload").start()

    app.launch(
        server_name="0.0.0.0",
        server_port=int(os.getenv("PORT", "7860")),
        show_error=True,
        share=False,
    )
