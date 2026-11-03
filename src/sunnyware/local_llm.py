

# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""In-process llama.cpp wrapper for the local model fallback (Part 32).

Loads a GGUF model lazily on first use, keeps it in memory, and exposes
a synchronous chat() that mirrors the OpenAI-compatible response shape
used by the rest of the router.

Thread-safety: a single asyncio.Lock serializes all calls because the
underlying llama.cpp context is not thread-safe and one model = one
request at a time.
"""

import asyncio
import threading
import os
import time
from typing import Optional

_LOCK = asyncio.Lock()
_LOAD_LOCK = asyncio.Lock()

# Part 620: Serializes native llama.cpp calls so that a timed-out
# call cannot race with a retry (prevents GGML_ASSERT crash).
_NATIVE_LOCK = threading.Lock()
_MODEL = None  # type: ignore
_LOAD_ERROR: str = ""


def _enabled() -> bool:
    return (os.getenv("LOCAL_MODEL_ENABLED", "0") or "0").strip() in ("1", "true", "yes")


def _model_path() -> str:
    return (os.getenv("LOCAL_MODEL_PATH") or "").strip()


def is_enabled() -> bool:
    return _enabled() and bool(_model_path())


def is_loaded() -> bool:
    return _MODEL is not None


def load_error() -> str:
    return _LOAD_ERROR


def _load_sync():
    """Synchronous load — runs in a thread via asyncio.to_thread."""
    global _MODEL, _LOAD_ERROR
    if _MODEL is not None:
        return _MODEL
    path = _model_path()
    if not path:
        _LOAD_ERROR = "LOCAL_MODEL_PATH not set"
        raise RuntimeError(_LOAD_ERROR)
    if not os.path.exists(path):
        _LOAD_ERROR = "GGUF not found at " + path
        raise RuntimeError(_LOAD_ERROR)
    try:
        from llama_cpp import Llama
    except Exception as e:
        _LOAD_ERROR = "llama_cpp import failed: " + type(e).__name__ + ": " + str(e)
        raise ImportError(_LOAD_ERROR) from e
    try:
        # Part 623: use all available cores for faster generation
        import os as _os
        _n_threads = int(_os.getenv("LOCAL_MODEL_N_THREADS", "0")) or min(4, _os.cpu_count() or 2)
        print(f"[local_llm] Loading Qwen2.5 with n_threads={_n_threads}", flush=True)
        _MODEL = Llama(
            model_path=path,
            n_ctx=min(int(os.getenv("LOCAL_MODEL_CTX", "2048")), 2048),
            n_threads=_n_threads,
            n_batch=512,
            
            
            use_mlock=False,
            verbose=False,
        )
        _LOAD_ERROR = ""
        return _MODEL
    except Exception as e:
        _LOAD_ERROR = "load failed: " + type(e).__name__ + ": " + str(e)
        raise


async def _ensure_loaded():
    if _MODEL is not None:
        return _MODEL
    async with _LOAD_LOCK:
        if _MODEL is not None:
            return _MODEL
        return await asyncio.to_thread(_load_sync)




async def chat(
    prompt: str,
    model: Optional[str] = None,
    system: Optional[str] = None,
    history: Optional[list] = None,
    tools: Optional[list] = None,
    timeout: float = 120.0,
    max_tokens: Optional[int] = None,
) -> dict:
    """In-process chat completion. Mirrors llm._chat_single() response shape.

    Note: 'model' argument is ignored — the loaded GGUF is the only model.
    Tool calling: llama.cpp handles tool parsing via the model's chat
    template. If tools fail to parse, response comes back as plain text.
    """
    if not is_enabled():
        return {
            "ok": False,
            "error": "local model not enabled (set LOCAL_MODEL_ENABLED=1 and LOCAL_MODEL_PATH)",
            "provider": "local",
        }

    # Part 453: Truncate for local model (context window is 8192)
    if system and len(system) > 500:
        system = system[:500] + "... [truncated]"
    if prompt and len(prompt) > 500:
        prompt = prompt[:500] + "... [truncated]"
    if history and len(history) > 2:
        history = history[-2:]  # Part 623: keep 2 msgs for coherence
    if tools:
        tools = [t for t in tools if isinstance(t, dict)][:5]

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": prompt})

    start = time.time()
    async with _LOCK:
        try:
            llama = await _ensure_loaded()
        except Exception as e:
            return {
                "ok": False,
                "error": "load failed: " + type(e).__name__ + ": " + str(e),
                "provider": "local",
                "latency_ms": int((time.time() - start) * 1000),
            }

        def _run():
            _mt = max_tokens or int(os.getenv("LOCAL_MODEL_MAX_TOKENS", "128"))
            kwargs = {
                "messages": messages,
                "temperature": 0.1,
                "stream": False,
                "max_tokens": _mt,
                "top_p": 0.95,
                "repeat_penalty": 1.1,
                # No custom "stop" — let Qwen's chat template handle it naturally
            }
            if tools:
                import json
                clean_tools = []
                for t in tools:
                    if isinstance(t, str):
                        try:
                            t = json.loads(t)
                        except Exception:
                            continue
                    if isinstance(t, dict):
                        clean_tools.append(t)
                if clean_tools:
                    kwargs["tools"] = clean_tools
                    kwargs["tool_choice"] = "auto"
            # Part 620: Non-blocking native lock — if a previous call is
            # still running (asyncio timeout doesn't kill the C thread),
            # fail fast instead of crashing llama.cpp with concurrent writes.
            if not _NATIVE_LOCK.acquire(blocking=False):
                raise RuntimeError("local model busy (previous call still running)")
            try:
                return llama.create_chat_completion(**kwargs)
            finally:
                _NATIVE_LOCK.release()

        try:
            resp = await asyncio.wait_for(
                asyncio.to_thread(_run),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            return {
                "ok": False,
                "error": "local model timeout (" + str(int(timeout)) + "s)",
                "provider": "local",
                "latency_ms": int((time.time() - start) * 1000),
            }
        except Exception as e:
            return {
                "ok": False,
                "error": type(e).__name__ + ": " + str(e),
                "provider": "local",
                "latency_ms": int((time.time() - start) * 1000),
            }

    latency_ms = int((time.time() - start) * 1000)
    try:
        msg = resp["choices"][0]["message"]
    except Exception:
        return {
            "ok": False,
            "error": "malformed response from local model",
            "provider": "local",
            "latency_ms": latency_ms,
        }

    content = (msg.get("content") or "").strip()
    tool_calls = msg.get("tool_calls") or None

    return {
        "ok": True,
        "content": content,
        "tool_calls": tool_calls,
        "model": os.path.basename(_model_path()) or "local",
        "provider": "local",
        "latency_ms": latency_ms,
    }


async def preload() -> dict:
    """Warm up the model at startup (optional). Returns status."""
    if not is_enabled():
        return {"status": "disabled"}
    try:
        await _ensure_loaded()
        return {"status": "loaded", "path": _model_path()}
    except Exception as e:
        return {"status": "error", "error": type(e).__name__ + ": " + str(e)}


def status() -> dict:
    return {
        "enabled": _enabled(),
        "path": _model_path() or "(not set)",
        "loaded": is_loaded(),
        "load_error": _LOAD_ERROR,
    }
