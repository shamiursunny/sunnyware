

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
        _n_threads = int(_os.getenv("LOCAL_MODEL_N_THREADS", "2")) or 2  # Part 625: default 2 threads for 2-core HF Spaces
        print(f"[local_llm] Loading Qwen2.5 with n_threads={_n_threads}", flush=True)
        _MODEL = Llama(
            model_path=path,
            n_ctx=int(os.getenv("LOCAL_MODEL_CTX", "512")) or 512,  # Part 630: smaller ctx = faster
            n_threads=_n_threads,
            n_batch=64,  # Part 630
            
            
            use_mlock=False,
            verbose=__import__("os").getenv("LOCAL_MODEL_VERBOSE", "").lower() in ("1", "true", "yes"),
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
    if system and len(system) > 200:  # Part 629: shorter system prompt for speed
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
            _mt = max_tokens or int(os.getenv("LOCAL_MODEL_MAX_TOKENS", "64"))  # Part 630: allow full responses  # Part 625: cap at 48 default
            kwargs = {
                "messages": messages,
                "temperature": 0.1,
                "stream": False,
                "max_tokens": _mt,
                "top_p": 0.95,
                "repeat_penalty": 1.0,  # Part 627: revert to working value
                "stop": ["<|im_end|>", "<|endoftext|>"],  # Part 627: restore working stop tokens
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
            # Part 627: Diagnostic instrumentation
            import time as _diag_t
            _diag_start = _diag_t.time()
            _n_msgs = len(kwargs.get("messages", []))
            _chars = sum(len(str(m.get("content", ""))) for m in kwargs.get("messages", []))
            print(f"[local_llm.run] START: {_n_msgs} msgs, {_chars} chars, "
                  f"max_tokens={kwargs.get('max_tokens')}, temp={kwargs.get('temperature')}",
                  flush=True)
            # Tokenizer health check
            try:
                _test_tokens = llama.tokenize(b"<|im_start|>user\nhi<|im_end|>\n")
                print(f"[local_llm.run] Tokenizer OK ({len(_test_tokens)} tokens for test)", flush=True)
            except Exception as _te:
                print(f"[local_llm.run] TOKENIZER ERROR: {_te}", flush=True)

            # Acquire native lock
            if not _NATIVE_LOCK.acquire(blocking=False):
                print("[local_llm.run] BUSY: native lock held by previous call", flush=True)
                raise RuntimeError("local model busy (previous call still running)")

            try:
                print(f"[local_llm.run] Calling create_chat_completion...", flush=True)
                # Part 628: Bypass create_chat_completion — it hangs on the Qwen2.5
                # chat template in llama-cpp-python 0.3.16. Use manual ChatML instead.
                _chatml_parts = []
                for _cm in messages:
                    _crole = _cm.get("role", "user")
                    _ccontent = _cm.get("content", "")
                    _chatml_parts.append(f"<|im_start|>{_crole}\n{_ccontent}<|im_end|>\n")
                _chatml_parts.append("<|im_start|>assistant\n")
                _manual_prompt = "".join(_chatml_parts)
                print(f"[local_llm.run] PROMPT (first 200): {_manual_prompt[:200]!r}", flush=True)
                _raw = llama.create_completion(
                    prompt=_manual_prompt,
                    max_tokens=_mt,
                    temperature=0.1,
                    top_p=0.95,
                    repeat_penalty=1.0,
                    stop=["<|im_end|>", "<|endoftext|>"],
                    echo=False,
                )
                _raw_text = ""
                try:
                    _raw_text = (_raw["choices"][0].get("text") or "")
                except Exception:
                    pass
                _res = {
                    "choices": [{
                        "message": {"role": "assistant", "content": _raw_text, "tool_calls": None},
                        "finish_reason": (_raw.get("choices") or [{}])[0].get("finish_reason", "stop"),
                    }],
                    "usage": _raw.get("usage", {}) or {},
                }
                _elapsed = _diag_t.time() - _diag_start
                _usage = _res.get("usage", {}) or {}
                _preview = ""
                try:
                    _preview = (_res["choices"][0]["message"].get("content") or "")[:80]
                except Exception:
                    pass
                print(f"[local_llm.run] RETURNED in {_elapsed:.1f}s: "
                      f"prompt_tokens={_usage.get('prompt_tokens', '?')}, "
                      f"completion_tokens={_usage.get('completion_tokens', '?')}, "
                      f"content_preview={_preview!r}", flush=True)
                return _res
            except Exception as _re:
                print(f"[local_llm.run] ERROR after {_diag_t.time() - _diag_start:.1f}s: {_re}", flush=True)
                raise
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
