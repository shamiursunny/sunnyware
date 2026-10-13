# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""LLM client + multi-provider router (Part 32).

Two layers:
  - _chat_single(): low-level OpenAI-compatible call to one endpoint
    with all Part-31 retries (429, tool_use_failed, hallucinated tool names)
  - chat(): routes across providers from providers.load_providers(),
    marks rate-limited ones as cooling, falls through on errors

If LLM_PROVIDERS is unset, chat() uses the legacy single-provider config
(LLM_BASE_URL / LLM_API_KEY / LLM_MODEL).
"""

import asyncio
import json
import os
import re
import time
from typing import Optional

import httpx

from . import providers as _providers
from . import local_llm as _local_llm


DEFAULT_BASE_URL = "http://localhost:11434/v1"
DEFAULT_MODEL = "gemma2-2b-tuned-stable:latest"
DEFAULT_API_KEY = "ollama"


def _legacy_base_url() -> str:
    return os.getenv("LLM_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def _legacy_api_key() -> str:
    return os.getenv("LLM_API_KEY", DEFAULT_API_KEY)


def _legacy_model() -> str:
    return os.getenv("LLM_MODEL", DEFAULT_MODEL)


# Legacy aliases kept for backward compat with existing call sites
def _base_url() -> str:
    return _legacy_base_url()


def _api_key() -> str:
    return _legacy_api_key()


def _model() -> str:
    return _legacy_model()


async def health_check(timeout: float = 5.0) -> dict:
    """Ping /models on the first provider (or legacy config if none)."""
    provs = _providers.load_providers()
    if not provs:
        return {"status": "error", "error": "no providers configured"}
    p = provs[0]
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(
                f"{p.base_url}/models",
                headers={"Authorization": f"Bearer {p.api_key}"},
            )
            if r.status_code != 200:
                return {"status": "error", "error": f"HTTP {r.status_code}"}
            data = r.json()
            models = [m.get("id", "?") for m in data.get("data", [])]
            return {"status": "ok", "models": models[:5], "count": len(models), "provider": p.name}
    except Exception as e:
        return {"status": "error", "error": f"{type(e).__name__}: {e}"}


async def _chat_single(
    prompt: str,
    base_url: str,
    api_key: str,
    model: Optional[str] = None,
    system: Optional[str] = None,
    history: Optional[list] = None,
    tools: Optional[list] = None,
    timeout: float = 60.0,
    _retry_depth: int = 0,
) -> dict:
    """Low-level single-endpoint chat call. Preserves all Part-31 retries."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model or DEFAULT_MODEL,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 2048,
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
                f"{base_url}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
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

                # Part 33: 429 -> fail fast, let router try next provider
                # (previous 20s x 2 retries wasted 40s per broken provider)
                if r.status_code == 429:
                    try:
                        from . import metrics as _m4
                        _m4.incr("llm_rate_limit_fastfail_total")
                    except Exception:
                        pass
                    return {
                        "ok": False,
                        "error": f"HTTP 429: {r.text[:200]}",
                        "latency_ms": latency_ms,
                        "status_code": 429,
                    }

                # Part 31K-ext: hallucinated tool name -> retry with hint
                if r.status_code == 400 and "was not enabled" in r.text and _retry_depth < 2:
                    m = re.search(r"called (\w+) tool", r.text)
                    bad = m.group(1) if m else "unknown"
                    hint = (
                        "\n\nCRITICAL: You just called a tool named '"
                        + bad + "' which does not exist. "
                        "The ONLY tool for running Python code is "
                        "named exactly 'python_eval'. "
                        "Never use 'python' or any other abbreviation. "
                        "Call 'python_eval' now."
                    )
                    new_system = (system or "") + hint
                    try:
                        from . import metrics as _m5
                        _m5.incr("llm_tool_name_hint_retry_total")
                    except Exception:
                        pass
                    await asyncio.sleep(0.3)
                    return await _chat_single(
                        prompt=prompt, base_url=base_url, api_key=api_key,
                        model=model, system=new_system, history=history,
                        tools=tools, timeout=timeout,
                        _retry_depth=_retry_depth + 1,
                    )

                # Part 31F-ext2: tool_use_failed retry
                if r.status_code == 400 and "tool_use_failed" in r.text and _retry_depth < 2:
                    try:
                        from . import metrics as _m3
                        _m3.incr("llm_tool_use_retry_total")
                    except Exception:
                        pass
                    await asyncio.sleep(0.4)
                    return await _chat_single(
                        prompt=prompt, base_url=base_url, api_key=api_key,
                        model=model, system=system, history=history,
                        tools=tools, timeout=timeout,
                        _retry_depth=_retry_depth + 1,
                    )

                return {
                    "ok": False,
                    "error": f"HTTP {r.status_code}: {r.text[:200]}",
                    "latency_ms": latency_ms,
                    "status_code": r.status_code,
                }

            data = r.json()
            msg = data["choices"][0]["message"]
            content = msg.get("content") or ""
            tool_calls = msg.get("tool_calls")

            # Usage tracking (Part 29)
            try:
                from . import usage as _usage
                u = data.get("usage") or {}
                in_tok = int(u.get("prompt_tokens", 0) or 0)
                out_tok = int(u.get("completion_tokens", 0) or 0)
                if in_tok == 0 and out_tok == 0:
                    in_tok = max(1, (len(prompt) if isinstance(prompt, str) else 0) // 4)
                    out_tok = max(1, len(content) // 4)
                await _usage.record(
                    model=data.get("model", model or DEFAULT_MODEL),
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
                "model": data.get("model", model or DEFAULT_MODEL),
                "latency_ms": latency_ms,
            }
    except Exception as e:
        return {
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
            "latency_ms": int((time.time() - start) * 1000),
        }


def _is_rate_limit_error(err: str) -> bool:
    e = (err or "").lower()
    return "429" in e or "rate limit" in e or "tpd" in e or "tpm" in e


async def chat(
    prompt: str,
    model: Optional[str] = None,
    system: Optional[str] = None,
    history: Optional[list] = None,
    tools: Optional[list] = None,
    timeout: float = 90.0,
    _retry_depth: int = 0,
) -> dict:
    """Route across providers. Falls through on rate-limits / errors.

    Legacy single-provider behavior preserved when only one provider is
    configured (LLM_PROVIDERS unset or has one entry).
    """
    provs = _providers.load_providers()
    if not provs:
        return {"ok": False, "error": "no LLM providers configured"}

    # Part 33: auto-resolve best model per provider (adapts when a
    # provider retires a model). Cached per provider for 1h.
    from . import model_resolver as _mr
    _resolved = {}
    for _p in provs:
        if _p.provider_type == "local":
            _resolved[_p.name] = model or _p.model
            continue
        try:
            _res = await _mr.resolve(_p.name, _p.base_url, _p.api_key, model or _p.model)
            _resolved[_p.name] = _res.get("model") or (model or _p.model)
        except Exception:
            _resolved[_p.name] = model or _p.model

    # Single provider — legacy path, minimal overhead
    if len(provs) == 1:
        p = provs[0]
        r = await _chat_single(
            prompt=prompt, base_url=p.base_url, api_key=p.api_key,
            model=_resolved.get(p.name) or model or p.model, system=system, history=history,
            tools=tools, timeout=timeout, _retry_depth=_retry_depth,
        )
        r["provider"] = p.name
        r["resolved_model"] = _resolved.get(p.name)
        if r.get("ok"):
            p.record_success()
        else:
            p.record_failure(r.get("error", ""))
        return r

    # Multi-provider router
    last_err = ""
    for p in provs:
        if p.is_cooling():
            continue

        # Local provider: bypass HTTP, call in-process
        if p.provider_type == "local":
            try:
                from . import metrics as _m
                _m.incr_labeled("llm_provider_attempt", p.name)
            except Exception:
                pass
            r = await _local_llm.chat(
                prompt=prompt, model=p.model, system=system,
                history=history, tools=tools, timeout=max(timeout, 120.0),
            )
            if r.get("ok"):
                p.record_success()
                return r
            p.record_failure(r.get("error", ""))
            last_err = r.get("error", "")
            p.mark_cooldown(10.0)
            continue

        try:
            from . import metrics as _m
            _m.incr_labeled("llm_provider_attempt", p.name)
        except Exception:
            pass

        r = await _chat_single(
            prompt=prompt, base_url=p.base_url, api_key=p.api_key,
            model=_resolved.get(p.name) or model or p.model, system=system, history=history,
            tools=tools, timeout=timeout, _retry_depth=0,
        )
        r["provider"] = p.name
        r["resolved_model"] = _resolved.get(p.name)

        if r.get("ok"):
            p.record_success()
            return r

        err = r.get("error", "")
        last_err = err
        p.record_failure(err)

        if _is_rate_limit_error(err):
            p.mark_cooldown(60.0)
        else:
            p.mark_cooldown(10.0)

    return {
        "ok": False,
        "error": "all providers failed; last: " + (last_err or "unknown"),
        "provider": "none",
    }


_LAST_STREAM_PROVIDER = None


def get_last_stream_provider():
    """Return the provider name that served the most recent stream."""
    return _LAST_STREAM_PROVIDER


async def stream_chat(
    prompt: str,
    model: Optional[str] = None,
    system: Optional[str] = None,
    history: Optional[list] = None,
    timeout: float = 90.0,
):
    """Streaming with provider fallback (Part 57).

    Tries each provider in priority order. Once the first chunk is yielded
    we're committed — a mid-stream failure cannot safely be retried.
    """
    global _LAST_STREAM_PROVIDER
    provs = _providers.load_providers()
    if not provs:
        raise RuntimeError("no providers configured")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": prompt})

    last_err = None
    for p in provs:
        if p.is_cooling():
            last_err = f"{p.name}: cooling"
            continue
        use_model = model or p.model
        payload = {
            "model": use_model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 2048,
            "stream": True,
        }
        yielded_any = False
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST",
                    f"{p.base_url}/chat/completions",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {p.api_key}",
                        "Content-Type": "application/json",
                    },
                ) as r:
                    if r.status_code != 200:
                        body = await r.aread()
                        last_err = f"{p.name}: HTTP {r.status_code}: {body[:120]!r}"
                        if r.status_code == 429:
                            p.mark_cooldown(60.0)
                        p.record_failure(last_err)
                        continue
                    _LAST_STREAM_PROVIDER = p.name
                    p.record_success()
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
                                yielded_any = True
                                yield chunk
                        except Exception:
                            continue
                    return
        except Exception as e:
            last_err = f"{p.name}: {type(e).__name__}: {e}"
            p.record_failure(last_err)
            if yielded_any:
                raise
            continue

    raise RuntimeError(f"all providers failed: {last_err or 'unknown'}")

