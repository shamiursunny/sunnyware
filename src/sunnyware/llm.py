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
import contextvars
import os
import re
import time
from typing import Optional

import httpx

from . import providers as _providers
from . import local_llm as _local_llm
from . import provider_limits_config as _plc


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
        "max_tokens": 8192,
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
            reasoning = msg.get("reasoning") or ""
            tool_calls = msg.get("tool_calls")

            # Usage tracking (Part 29) + Part 96: expose real token counts
            in_tok = 0
            out_tok = 0
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
                "tokens_in": in_tok,
                "tokens_out": out_tok,
                "tokens_total": in_tok + out_tok,
            }
    except Exception as e:
        return {
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
            "latency_ms": int((time.time() - start) * 1000),
        }


def _estimate_tools_tokens(tools) -> int:
    """Part 144: estimate tokens for a tool-schema list.

    Uses char/4 heuristic; safe upper bound for routing decisions.
    """
    if not tools:
        return 0
    try:
        return len(json.dumps(tools)) // 4
    except Exception:
        return 0


def _estimate_prompt_tokens(prompt, system, history) -> int:
    """Part 99: char/4 heuristic for total conversation size.

    Counts prompt + system + all history message contents. Used to
    pre-filter providers that would reject the request (e.g. Groq's
    8k input cap returns HTTP 413)."""
    total = 0
    if isinstance(prompt, str):
        total += len(prompt)
    if isinstance(system, str):
        total += len(system)
    for m in (history or []):
        if isinstance(m, dict):
            c = m.get("content")
            if isinstance(c, str):
                total += len(c)
    return max(1, total // 4)


def _is_empty_response(r: dict) -> bool:
    """Part 101: True if a provider returned ok=True but with empty
    content AND no tool calls. Treat as failure so the next provider
    gets a chance. When the LLM is expected to make a tool call, the
    tool_calls field will be non-empty, so this check is safe."""
    if not isinstance(r, dict) or not r.get("ok"):
        return False
    content = (r.get("content") or "").strip()
    tool_calls = r.get("tool_calls") or []
    return (not content) and (not tool_calls)


def _is_too_large_error(err: str) -> bool:
    """Part 100: detect HTTP 413 / 'request too large' / context overflow."""
    e = (err or "").lower()
    return (
        "413" in e
        or "request too large" in e
        or "request entity too large" in e
        or "payload too large" in e
        or "context length" in e
        or "maximum context" in e
        or "too many tokens" in e
    )


def _is_rate_limit_error(err: str) -> bool:
    e = (err or "").lower()
    return (
        "429" in e
        or "rate limit" in e
        or "rate_limit" in e
        or "tpd" in e
        or "tpm" in e
        # Part 143: Pollinations FREE_LIMIT (returns HTTP 402, not 429)
        or "402" in e
        or "free_limit" in e
        # Part 143: explicit "Retry after Ns" hints (any provider)
        or "retry after" in e
        or "retry_after" in e
    )


def _parse_retry_after(err: str) -> int:
    """Part 143: extract 'Retry after Ns' / 'retry_after: N' hint.

    Returns seconds (1..600) or 0 if no hint found.
    """
    m = re.search(
        r"retry[\s_\-]*after[:\s]+?(\d+)",
        err or "",
        re.IGNORECASE,
    )
    if m:
        try:
            return max(1, min(int(m.group(1)), 600))
        except Exception:
            pass
    return 0


async def chat(
    prompt: str,
    model: Optional[str] = None,
    system: Optional[str] = None,
    history: Optional[list] = None,
    tools: Optional[list] = None,
    timeout: float = 90.0,
    _retry_depth: int = 0,
) -> dict:
    # Part 422: Truncate history globally to prevent 17k token errors
    history = history[-4:] if history else []


    # Part 410: Skip local model for general chat (fast cloud answer)
        # THE STRICT ROUTER: Only use local if tools are present AND keywords match
    _tool_keywords = [
        "calculate", "math", "time", "weather", "search", "web", "http",
        "file", "read", "write", "pdf", "excel", "sql", "csv", "email",
        "webhook", "schedule", "kpi", "chart", "narrate", "financial",
        "stock", "option", "risk", "insurance", "python", "run code",
        "query", "select", "insert", "update", "delete", "list", "show"
    ]
    _has_tool = any(kw in prompt.lower() for kw in _tool_keywords) if prompt else False
    
    _priority = (os.getenv("LLM_PROVIDERS") or "").split(",")
    if "local" in [n.strip().lower() for n in _priority] and _has_tool:
        from . import local_llm as _llm
        from .agent_memory import read_memory
        if _llm.is_enabled():
            try:
                # Give it time to think and generate tools
                # Part 379: Truncate history and tools for local CPU inference
                _local_history = history  # Full history, no limit
                _local_tools = tools if (tools and len(tools) <= 15) else []
                # Part 396: Shared Memory Check
                _last_tool = read_memory("last_tool_execution")
                if _last_tool and isinstance(_last_tool, dict):
                    prompt += f"\n\n[Shared Memory Context]: The tool '{_last_tool.get('tool')}' was already executed with args {_last_tool.get('args')}."
                
                # Truncate massive system prompt for CPU speed
                _local_system = (system[:200] if system else "You are a helpful assistant.")
                local_res = await _llm.chat(
                    prompt=prompt,
                    system=_local_system,
                    history=_local_history,
                    tools=_local_tools,
                    timeout=300.0  # 60s is enough for Qwen to finish
                )
                if local_res.get("ok") and (local_res.get("content") or local_res.get("tool_calls")):
                    # Check if the content is just empty reasoning
                    content = local_res.get("content", "").strip()
                    if content or local_res.get("tool_calls"):
                        return local_res
                # If we get here, local failed or returned empty. Fall through to cloud.
                print(f"[llm.chat] Local model failed/empty, falling back to cloud: {local_res.get('error')}", flush=True)
            except Exception as e:
                print(f"[llm.chat] Local model exception, falling back to cloud: {e}", flush=True)
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
            tools=(tools if getattr(p, "supports_tools", True) else None),
            timeout=timeout, _retry_depth=_retry_depth,
        )
        r["provider"] = p.name
        r["resolved_model"] = _resolved.get(p.name)
        if r.get("ok"):
            p.record_success()
        else:
            p.record_failure(r.get("error", ""))
        return r

    # Multi-provider router
    # Part 99: pre-filter providers whose max_prompt_tokens would reject
    # this request (e.g. Groq 413 on >8k input). Falls back to trying all
    # non-cooling providers if the size filter would exclude everything.
    _prompt_tokens = _estimate_prompt_tokens(prompt, system, history)
    # Part 144: include tool-schema tokens so providers that can't fit
    # the full tool set are skipped cleanly instead of 413ing at HTTP.
    _tools_tokens = _estimate_tools_tokens(tools) if tools else 0
    _required_tokens = _prompt_tokens + _tools_tokens
    _any_eligible = any(
        (not p.is_cooling())
        and (not p.max_prompt_tokens
             or _required_tokens <= p.max_prompt_tokens)
        for p in provs
    )

    last_err = ""
    for p in provs:
        if p.is_cooling():
            continue
        if (
            _any_eligible
            and p.max_prompt_tokens
            and _required_tokens > p.max_prompt_tokens
        ):
            # Part 99 + 144: skip provider that can't fit prompt+tools
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
                history=history, tools=tools, timeout=min(timeout, 5.0),  # Part 268: Cap HTTP timeout to prevent long hangs
            )
            if r.get("ok") and _is_empty_response(r):
                # Part 101: empty response from local model — try next
                _err = "empty LLM response (no content, no tool calls)"
                last_err = _err
                p.record_failure(_err)
                p.mark_cooldown(10.0)
                try:
                    from . import metrics as _m
                    _m.incr_labeled("llm_provider_empty_response", p.name)
                except Exception:
                    pass
                continue
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
            tools=(tools if getattr(p, "supports_tools", True) else None),
            timeout=timeout, _retry_depth=0,
        )
        r["provider"] = p.name
        r["resolved_model"] = _resolved.get(p.name)

        # Part 101: treat empty responses as failures so we try the
        # next provider instead of returning ok=True with no content.
        if r.get("ok") and _is_empty_response(r):
            _err = "empty LLM response (no content, no tool calls)"
            last_err = _err
            p.record_failure(_err)
            p.mark_cooldown(15.0)
            try:
                from . import metrics as _m
                _m.incr_labeled("llm_provider_empty_response", p.name)
            except Exception:
                pass
            continue

        if r.get("ok"):
            p.record_success()
            return r

        err = r.get("error", "")
        last_err = err
        p.record_failure(err)

        # Part 100: learn from 413 / context-overflow errors.
        # Lower this provider's max_prompt_tokens and persist it.
        if _is_too_large_error(err):
            try:
                from . import provider_limits as _pl
                _old = p.max_prompt_tokens
                _new = _pl.learn_limit(p.name, _prompt_tokens, _old)
                if _new != _old:
                    p.max_prompt_tokens = _new
                    try:
                        from . import metrics as _m
                        _m.incr_labeled("provider_limit_learned", p.name)
                    except Exception:
                        pass
            except Exception:
                pass
            # Short cooldown so we don't retry this provider in the
            # same request or immediately after.
            p.mark_cooldown(60.0)
            continue

        if _is_rate_limit_error(err):
            # Part 143 + 145: provider + error-type aware cooldown.
            # Retry hint wins; RPD exhaustion waits until reset;
            # RPM exhaustion waits ~1 minute; default 60s.
            try:
                _cd = _plc.compute_cooldown(p.name, err)
            except Exception:
                _cd = 60.0
            p.mark_cooldown(float(_cd))
        else:
            p.mark_cooldown(10.0)

    # Part 102: if every provider failed on this pass, consider one
    # retry. Cooldowns are transient (10-60s); if a provider will be
    # available within 20s, wait briefly and recurse once.
    if _retry_depth == 0:
        # Part 153: DO NOT reload — reload creates new Provider
        # objects and discards cooldowns/success/fail counters set
        # during this request. Use the in-memory list directly.
        _fresh = provs

        _cooling = [p for p in _fresh if p.is_cooling()]
        _ready = [p for p in _fresh if not p.is_cooling()]
        _min_cool = min(
            (p.cooldown_remaining() for p in _cooling),
            default=999.0,
        )
        print(
            f"[llm.chat] all providers failed (last: {last_err!r}); "
            f"cooling={len(_cooling)} ready={len(_ready)} "
            f"min_cool={_min_cool:.1f}s retry_depth={_retry_depth}",
            flush=True,
        )

        # Part 154: raised from 20s to 40s (env-configurable) so that
        # pollinations' 35s IP-floor cooldown is within range. The wait
        # cap is also raised to match, otherwise we'd sleep only 8s and
        # still be cooling when we recurse.
        try:
            _retry_wait_max = float(
                os.getenv("SUNNYWARE_RETRY_WAIT_MAX_S", "40")
            )
        except Exception:
            _retry_wait_max = 40.0
        if _min_cool <= _retry_wait_max and not _ready:
            # Wait the full cooldown (+1s safety) so the recursion has a
            # chance to succeed instead of hitting the same wall.
            _wait = min(_min_cool + 1.0, _retry_wait_max + 5.0)
            try:
                from . import metrics as _m
                _m.incr_labeled("llm_request_retried", "once")
            except Exception:
                pass
            print(f"[llm.chat] retrying once after {_wait:.1f}s wait",
                  flush=True)
            await asyncio.sleep(_wait)
            # Recurse with _retry_depth=1 so we never retry again
            return await chat(
                prompt,
                model=model,
                system=system,
                history=history,
                tools=tools,
                timeout=timeout,
                _retry_depth=1,
            )

    return {
        "ok": False,
        "error": "all providers failed; last: " + (last_err or "unknown"),
        "provider": "none",
    }


_LAST_STREAM_PROVIDER_CTX = contextvars.ContextVar("_LAST_STREAM_PROVIDER", default=None)


def get_last_stream_provider():
    """Return the provider name that served the most recent stream."""
    return _LAST_STREAM_PROVIDER_CTX.get()


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
            "max_tokens": 8192,
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
                    _LAST_STREAM_PROVIDER_CTX.set(p.name)
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

