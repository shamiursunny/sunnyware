

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
import os
import time
from typing import Optional

_LOCK = asyncio.Lock()
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
        raise
    try:
        _MODEL = Llama(
            model_path=path,
            n_ctx=int(os.getenv("LOCAL_MODEL_CTX", "4096")),
            n_threads=int(os.getenv("LOCAL_MODEL_THREADS", "2")),
            n_batch=256,
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
    return await asyncio.to_thread(_load_sync)




async def chat(
    prompt: str,
    model: Optional[str] = None,
    system: Optional[str] = None,
    history: Optional[list] = None,
    tools: Optional[list] = None,
    timeout: float = 120.0,
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
            kwargs = {
                "messages": messages,
                "temperature": 0.1,
                "stream": False,
                "max_tokens": 4096,
                "top_p": 0.95,
                "repeat_penalty": 1.0, # Force JSON output instantly
            }
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
            return llama.create_chat_completion(**kwargs)

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
