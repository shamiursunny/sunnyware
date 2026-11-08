# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""HF Space entrypoint — persists models on /data (Linux) or ./data (Windows)."""

import os
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "/data/.cache/ms-playwright"
import subprocess
import sys

# Install Playwright browsers on startup (HF Space has no pre-installed Chromium)
try:
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=False, timeout=120)
except Exception:
    pass

from pathlib import Path


# ── 1. Load .env first (so we can see what the user configured) ──
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except Exception:
    pass


# ── 2. Pick persistent data dir (only /data on HF Spaces; else ./data) ──
def _pick_persistent_dir():
    is_hf = bool(os.getenv("SPACE_ID") or os.getenv("HF_SPACE"))
    candidates = [Path("/data")] if is_hf else []
    candidates.append(Path("./data"))
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            test = candidate / ".write_test_607"
            test.write_text("ok")
            test.unlink()
            return candidate.resolve()
        except Exception:
            continue
    return Path("./data").resolve()


DATA_DIR = _pick_persistent_dir()
print(f"[start] Persistent data dir: {DATA_DIR}", flush=True)


# ── 3. Compute persistent paths ──
HF_HOME_DIR = DATA_DIR / "huggingface"
MODEL_DIR = DATA_DIR / "models"
HF_HOME_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR.mkdir(parents=True, exist_ok=True)
GGUF_PATH = MODEL_DIR / "qwen2.5-0.5b-instruct-q4_k_m.gguf"


# ── 4. Force persistent paths (overrides .env) ──
def _apply_paths():
    os.environ["HF_HOME"] = str(HF_HOME_DIR)
    os.environ["SENTENCE_TRANSFORMERS_HOME"] = str(HF_HOME_DIR)
    os.environ["LOCAL_MODEL_PATH"] = str(GGUF_PATH)
    os.environ["LOCAL_MODEL_ENABLED"] = "1"
    os.environ["LOCAL_MODEL_CTX"] = "2048"
    os.environ["LOCAL_MODEL_BASE_URL"] = "in-process"
    os.environ["LOCAL_MODEL_API_KEY"] = "local"
    os.environ["LOCAL_MODEL"] = "qwen2.5-0.5b-instruct"

    # Ensure "local" in providers; drop "ollama" on HF Spaces
    _orig = (os.getenv("LLM_PROVIDERS") or "").strip()
    _parts = [p.strip() for p in _orig.split(",") if p.strip()]
    _parts = [p for p in _parts if p != "ollama"]
    if "local" not in _parts:
        _parts.append("local")
    if not _parts:
        _parts = ["groq", "gemini", "openrouter", "local"]
    os.environ["LLM_PROVIDERS"] = ",".join(_parts)


_apply_paths()
print(f"[start] HF_HOME = {os.environ['HF_HOME']}", flush=True)
print(f"[start] LOCAL_MODEL_PATH = {os.environ['LOCAL_MODEL_PATH']}", flush=True)
print(f"[start] LLM_PROVIDERS = {os.environ['LLM_PROVIDERS']}", flush=True)

os.environ.setdefault("GRADIO_SSR_MODE", "false")
os.environ["GRADIO_ANALYTICS_ENABLED"] = "false"

import sys
import threading

sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    import spaces

    @spaces.GPU
    def _dummy_gpu():
        return "ok"

except ImportError:
    pass


def _download_gguf():
    """Download Qwen2.5-0.5B GGUF once to DATA_DIR/models (persistent)."""
    if GGUF_PATH.exists() and GGUF_PATH.stat().st_size > 1_000_000:
        size_mb = GGUF_PATH.stat().st_size // (1024 * 1024)
        print(f"[start] GGUF cached: {GGUF_PATH} ({size_mb} MB) — no download needed", flush=True)
        return
    try:
        from huggingface_hub import hf_hub_download
        print(f"[start] Downloading Qwen2.5-0.5B GGUF → {MODEL_DIR} ...", flush=True)
        hf_hub_download(
            repo_id="Qwen/Qwen2.5-0.5B-Instruct-GGUF",
            filename="qwen2.5-0.5b-instruct-q4_k_m.gguf",
            local_dir=str(MODEL_DIR),
            local_dir_use_symlinks=False,
        )
        if GGUF_PATH.exists():
            size_mb = GGUF_PATH.stat().st_size // (1024 * 1024)
            print(f"[start] GGUF ready: {GGUF_PATH} ({size_mb} MB)", flush=True)
        else:
            print("[start] WARN: GGUF missing after download", flush=True)
    except Exception as e:
        print(f"[start] GGUF download failed: {type(e).__name__}: {e}", flush=True)


def _preload_embedder():
    """Preload bge-small-en-v1.5 from DATA_DIR/huggingface (persistent)."""
    try:
        from sunnyware.rag import embeddings
        embeddings._load()
        print(f"[start] Embedder loaded OK (HF_HOME={os.environ.get('HF_HOME')})", flush=True)
    except Exception as e:
        print(f"[start] Embedder preload failed: {type(e).__name__}: {e}", flush=True)


# ── 5. Import main app (this triggers config.py → load_dotenv(override=True)!) ──
from sunnyware.main import app  # noqa: E402

# ── 6. CRITICAL: Re-apply paths after main.py's load_dotenv ran ──
_apply_paths()
print("[start] Re-applied persistent paths after main.py import", flush=True)
print(f"[start] FINAL LOCAL_MODEL_PATH = {os.environ['LOCAL_MODEL_PATH']}", flush=True)

demo = app


if __name__ == "__main__":
    threading.Thread(target=_download_gguf, daemon=True, name="gguf-download").start()
    threading.Thread(target=_preload_embedder, daemon=True, name="embedder-preload").start()

    app.launch(
        server_name="0.0.0.0",
        server_port=int(os.getenv("PORT", "7860")),
        show_error=True,
        share=False,
        ssr_mode=False,  # Part 230: Disable SSR for mobile OAuth compatibility
    )
