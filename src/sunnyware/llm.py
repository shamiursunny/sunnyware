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
    _retry_depth: int = 0,
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
        "temperature": 0.2,
        # Part 31G: reasoning models (gpt-oss) burn most of max_tokens on
        # internal reasoning before producing output. 500 was too small:
        # empty responses when reasoning used the whole budget.
        "max_tokens": 2000,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    start = time.time()
    try:
        from . import metrics as _metrics
        _metrics.incr("llm_calls_total")
    except Exception:
        pass
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
                try:
                    from . import metrics as _metrics2
                    _metrics2.incr("llm_errors_total")
                except Exception:
                    pass
                # Part 31I: 429 rate limit -> wait for window reset + retry
                if (r.status_code == 429
                        and _retry_depth < 2):
                    try:
                        from . import metrics as _m4
                        _m4.incr("llm_rate_limit_retry_total")
                    except Exception:
                        pass
                    import asyncio as _aio
                    await _aio.sleep(20.0)
                    return await chat(
                        prompt=prompt, model=model, system=system,
                        history=history, tools=tools, timeout=timeout,
                        _retry_depth=_retry_depth + 1,
                    )
                # Part 31K-ext: Groq rejected hallucinated tool name
                # ('Model called python tool which was not enabled').
                # Retry with a system hint forcing the exact tool name.
                if (r.status_code == 400
                        and "was not enabled" in r.text
                        and _retry_depth < 2):
                    import re as _re
                    _m = _re.search(r"called (\w+) tool", r.text)
                    _bad = _m.group(1) if _m else "unknown"
                    _hint = (
                        "\n\nCRITICAL: You just called a tool named '"
                        + _bad + "' which does not exist. "
                        "The ONLY tool for running Python code is "
                        "named exactly 'python_eval'. "
                        "Never use 'python' or any other abbreviation. "
                        "Call 'python_eval' now."
                    )
                    _new_system = (system or "") + _hint
                    try:
                        from . import metrics as _m5
                        _m5.incr("llm_tool_name_hint_retry_total")
                    except Exception:
                        pass
                    import asyncio as _aio
                    await _aio.sleep(0.3)
                    return await chat(
                        prompt=prompt, model=model, system=_new_system,
                        history=history, tools=tools, timeout=timeout,
                        _retry_depth=_retry_depth + 1,
                    )
                # Part 31F-ext2: retry once on Groq tool_use_failed
                # (gpt-oss models sometimes emit malformed JSON args)
                if (r.status_code == 400
                        and "tool_use_failed" in r.text
                        and _retry_depth < 2):
                    try:
                        from . import metrics as _m3
                        _m3.incr("llm_tool_use_retry_total")
                    except Exception:
                        pass
                    import asyncio as _aio
                    await _aio.sleep(0.4)
                    return await chat(
                        prompt=prompt, model=model, system=system,
                        history=history, tools=tools, timeout=timeout,
                        _retry_depth=_retry_depth + 1,
                    )
                return {
                    "ok": False,
                    "error": f"HTTP {r.status_code}: {r.text[:200]}",
                    "latency_ms": latency_ms,
                }
            data = r.json()
            msg = data["choices"][0]["message"]
            content = msg.get("content") or ""
            tool_calls = msg.get("tool_calls")

            # Part 29: record token usage + cost
            try:
                from . import usage as _usage
                u = data.get("usage") or {}
                in_tok = int(u.get("prompt_tokens", 0) or 0)
                out_tok = int(u.get("completion_tokens", 0) or 0)
                if in_tok == 0 and out_tok == 0:
                    # Approximate from content (small local models may not report usage)
                    in_tok = max(1, (len(prompt) if isinstance(prompt, str) else 0) // 4)
                    out_tok = max(1, len(content) // 4)
                await _usage.record(
                    model=data.get("model", model or _model()),
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                    latency_ms=latency_ms,
                )
            except Exception:
                pass

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
        "temperature": 0.2,
        "max_tokens": 2000,
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
