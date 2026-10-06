# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""LLM client — OpenAI-compatible HTTP (Ollama, HF Inference, OpenAI)."""

import json
import os
import time
from typing import Optional
import httpx


DEFAULT_BASE_URL = "http://localhost:11434/v1"
DEFAULT_MODEL = "gemma2-2b-tuned-stable:latest"
DEFAULT_API_KEY = "ollama"


def _base_url() -> str:
    return os.getenv("LLM_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def _api_key() -> str:
    return os.getenv("LLM_API_KEY", DEFAULT_API_KEY)


def _model() -> str:
    return os.getenv("LLM_MODEL", DEFAULT_MODEL)


async def health_check(timeout: float = 5.0) -> dict:
    """Ping /models endpoint. Returns {status, models, count} or {status: error}."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(
                f"{_base_url()}/models",
                headers={"Authorization": f"Bearer {_api_key()}"},
            )
            if r.status_code != 200:
                return {"status": "error", "error": f"HTTP {r.status_code}"}
            data = r.json()
            models = [m.get("id", "?") for m in data.get("data", [])]
            return {"status": "ok", "models": models[:5], "count": len(models)}
    except Exception as e:
        return {"status": "error", "error": f"{type(e).__name__}: {e}"}


async def chat(
    prompt: str,
    model: Optional[str] = None,
    system: Optional[str] = None,
    history: Optional[list] = None,
    tools: Optional[list] = None,
    timeout: float = 30.0,
) -> dict:
    """Send chat completion with optional multi-turn history + native tools.

    history: list of {role, content} dicts.
    tools: OpenAI-format tool schemas — enables native tool calling.
    Returns {ok, content, tool_calls, model, latency_ms} or {ok: False, error}.
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model or _model(),
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 500,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(
                f"{_base_url()}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {_api_key()}",
                    "Content-Type": "application/json",
                },
            )
            latency_ms = int((time.time() - start) * 1000)
            if r.status_code != 200:
                return {
                    "ok": False,
                    "error": f"HTTP {r.status_code}: {r.text[:200]}",
                    "latency_ms": latency_ms,
                }
            data = r.json()
            msg = data["choices"][0]["message"]
            content = msg.get("content") or ""
            tool_calls = msg.get("tool_calls")
            return {
                "ok": True,
                "content": content,
                "tool_calls": tool_calls,
                "model": data.get("model", model or _model()),
                "latency_ms": latency_ms,
            }
    except Exception as e:
        return {
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
            "latency_ms": int((time.time() - start) * 1000),
        }


async def stream_chat(
    prompt: str,
    model: Optional[str] = None,
    system: Optional[str] = None,
    history: Optional[list] = None,
    timeout: float = 90.0,
):
    """Async generator yielding text chunks from a streaming chat completion.

    Uses OpenAI-compatible SSE (data: {...} lines, terminates with [DONE]).
    Raises on error — caller handles.
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model or _model(),
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 500,
        "stream": True,
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream(
            "POST",
            f"{_base_url()}/chat/completions",
            json=payload,
            headers={
                "Authorization": f"Bearer {_api_key()}",
                "Content-Type": "application/json",
            },
        ) as r:
            if r.status_code != 200:
                body = await r.aread()
                raise RuntimeError(f"HTTP {r.status_code}: {body[:200]!r}")

            async for raw_line in r.aiter_lines():
                if not raw_line:
                    continue
                line = raw_line.strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                    choice = (obj.get("choices") or [{}])[0]
                    delta = choice.get("delta") or {}
                    chunk = delta.get("content")
                    if chunk:
                        yield chunk
                except Exception:
                    continue
