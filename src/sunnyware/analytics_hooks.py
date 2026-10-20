import os
# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 212: Monkey-patch LLM + tool calls to log analytics."""

import time

try:
    import tiktoken
    _TIKTOKEN_ENC = tiktoken.get_encoding("cl100k_base")
except Exception:
    _TIKTOKEN_ENC = None

def _count_tokens(text: str) -> int:
    if not text:
        return 0
    if _TIKTOKEN_ENC is not None:
        try:
            return len(_TIKTOKEN_ENC.encode(str(text)))
        except Exception:
            pass
    return len(str(text)) // 4  # Fallback



def _extract_user_from_stack():
    """Walk the call stack to find any `request` object with user info."""
    try:
        import inspect
        import base64
        import json
        for frame_info in inspect.stack():
            frame = frame_info.frame
            req = frame.f_locals.get("request") or frame.f_locals.get("req")
            if req is None:
                continue
            # 1. Try request.state first
            state = getattr(req, "state", None)
            if state is not None:
                u = getattr(state, "analytics_user", None) or getattr(state, "user", None)
                if u:
                    return u
            # 2. Fallback: parse JWT from X-API-Key header
            headers = getattr(req, "headers", None)
            if headers is not None:
                key = headers.get("x-api-key") or ""
                if not key:
                    authz = headers.get("authorization", "")
                    if authz.lower().startswith("bearer "):
                        key = authz[7:].strip()
                if key and key != os.getenv("SUNNYWARE_MASTER_KEY", "master-admin-key") and "." in key and len(key) > 20:
                    try:
                        b64 = key.split(".")[0]
                        padded = b64 + "=" * (-len(b64) % 4)
                        payload = json.loads(base64.urlsafe_b64decode(padded))
                        u = payload.get("sub") or payload.get("email") or ""
                        if u:
                            return u
                    except Exception:
                        pass
    except Exception:
        pass
    return ""


def _log_llm(result: dict, model_hint: str = ""):
    try:
        from . import analytics_store as _as
        from . import llm_dashboard_store as _lds
        user, org = _as.get_current()
        if not user:
            user = _extract_user_from_stack()
        if not user:
            user = "anonymous"
        print(f"[analytics] logged LLM call for user={user}")

        provider = result.get("provider", "unknown")
        model = result.get("resolved_model") or model_hint or ""
        ok = bool(result.get("ok"))
        
        tokens = 0
        usage = result.get("usage") or result.get("token_usage")
        if isinstance(usage, dict):
            tokens = int(usage.get("total_tokens") or (usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)))
        elif isinstance(usage, int):
            tokens = usage
        
        if tokens == 0:
            tokens = int(result.get("total_tokens") or result.get("tokens", 0))
            
        if tokens == 0:
            # Exact count using tiktoken
            prompt_tokens = _count_tokens(result.get("prompt", ""))
            completion_tokens = _count_tokens(result.get("content", ""))
            tokens = prompt_tokens + completion_tokens

            
        latency = float(result.get("latency_ms") or 0)
        error = str(result.get("error") or "")[:500]

        # Cost calculation
        cfg = _lds.get_provider_config(provider)
        cost_per_1k = float(cfg.get("cost_per_1k_cents", 0.0))
        cost_cents = (tokens / 1000.0) * cost_per_1k if tokens else 0.0

        # Telemetry: try contextvars first, fall back to request state
        tel = _as.get_telemetry()
        ip = tel.get("ip", "")
        ua = tel.get("ua", "")
        device = tel.get("device", "")
        loc = tel.get("location", "")
        # Fallback: try to find request in stack
        if not ip or not device:
            try:
                import inspect
                for frame_info in inspect.stack():
                    frame = frame_info.frame
                    req = frame.f_locals.get("request") or frame.f_locals.get("req")
                    if req is not None:
                        st = getattr(req, "state", None)
                        if st:
                            if not ip:
                                ip = getattr(st, "ip", "") or ""
                            if not ua:
                                ua = getattr(st, "ua", "") or ""
                            if not device:
                                device = getattr(st, "device", "") or ""
                            if not loc:
                                loc = getattr(st, "location", "") or ""
                        if not ip:
                            headers = getattr(req, "headers", None)
                            if headers:
                                ip = headers.get("x-forwarded-for", "").split(",")[0].strip() or ""
                                if not ip and hasattr(req, "client") and req.client:
                                    ip = req.client.host or ""
                                if not ua:
                                    ua = headers.get("user-agent", "") or ""
                        break
            except Exception:
                pass
        # Final fallback: device name from UA if possible
        if not device and ua:
            if "Mobile" in ua:
                device = "Mobile"
            elif "Tablet" in ua:
                device = "Tablet"
            elif "Windows" in ua:
                device = "Windows"
            elif "Macintosh" in ua:
                device = "Mac"
            elif "Linux" in ua:
                device = "Linux"

        _lds.log_llm_call(provider, model, ok, tokens, latency, error, user)
        _as.log_event(user, "chat",
                      org_id=org, provider=provider, model=model,
                      tokens=tokens, latency_ms=latency, ok=ok, error=error,
                      cost_cents=cost_cents, ip=ip, ua=ua, device=device, location=loc)
    except Exception:
        pass


def _log_tool(name: str, latency_ms: float, ok: bool, error: str = ""):
    try:
        from . import analytics_store as _as
        user, org = _as.get_current()
        if not user:
            user = _extract_user_from_stack() or "anonymous"
        _as.log_event(user, "tool",
                      org_id=org, tool_name=name,
                      latency_ms=latency_ms, ok=ok, error=error)
    except Exception:
        pass


def install() -> dict:
    result = {"llm_patched": False, "tool_patched": False}
    try:
        from . import llm as _llm
        if not getattr(_llm, "_analytics_patched", False):
            _orig_chat = _llm.chat

            async def _wrapped_chat(*args, **kwargs):
                from . import llm_dashboard_store as _lds
                cfg = _lds.get_orchestrator_config()
                if cfg.get("disable_all"):
                    return {"ok": False, "error": "Global LLM disable switch is ON (Speed Breaker)"}
                
                model_hint = kwargs.get("model") or (args[1] if len(args) > 1 else "")
                
                t0 = time.time()
                try:
                    r = await _orig_chat(*args, **kwargs)
                except Exception as e:
                    _log_llm({"ok": False, "error": str(e),
                              "latency_ms": (time.time()-t0)*1000}, model_hint)
                    raise
                if not r.get("latency_ms"):
                    r["latency_ms"] = (time.time()-t0)*1000
                _log_llm(r, model_hint)
                return r

            _llm.chat = _wrapped_chat
            _llm._analytics_patched = True
            result["llm_patched"] = True
    except Exception as e:
        result["llm_error"] = str(e)

    try:
        from . import orchestrator as _orch
        if not getattr(_orch, "_analytics_patched", False):
            _orig_tool = _orch._execute_tool_impl

            async def _wrapped_tool(name, args):
                t0 = time.time()
                try:
                    r = await _orig_tool(name, args)
                    _log_tool(name, (time.time()-t0)*1000, True, "")
                    return r
                except Exception as e:
                    _log_tool(name, (time.time()-t0)*1000, False, str(e))
                    raise

            _orch._execute_tool_impl = _wrapped_tool
            _orch._analytics_patched = True
            result["tool_patched"] = True
    except Exception as e:
        result["tool_error"] = str(e)

    return result
