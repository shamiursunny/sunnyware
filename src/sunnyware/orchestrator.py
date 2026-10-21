# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Agent orchestrator — ReAct-style loop (native tools + prompt-JSON fallback)."""

import json
import re
from typing import Optional

from . import llm as llm_client
from . import circuit_breaker as _cb
from . import memory as memory_store
from . import prompts
from . import tools as tools_registry


# Part 156a: raised from 3. A CFO -> CDO -> worker chain needs at
# least 3 iterations (delegate, sub-delegate, worker answer) before
# returning; any retry blows past 3. Wall-clock timeout remains the
# real guard (SUNNYWARE_AGENT_TIMEOUT; 600s for cfo/cdo roles).
MAX_ITERATIONS = 3  # Part 257: lowered 10 -> 5 (protect tokens from runaway loops)

# Part 90: per-request token budget guard
MAX_REQUEST_TOKENS = 15000
_BUDGET_MESSAGE = (
    "Token budget reached ({used:,} / {cap:,} tokens). I stopped here "
    "to protect your API quota. Try a shorter prompt, or split the "
    "task into smaller steps."
)

def _estimate_tokens(*parts) -> int:
    """Part 90: char-based token estimate. ~4 chars per token is a
    safe universal heuristic across GPT/Gemini/Llama tokenizers."""
    total = 0
    for part in parts:
        if part is None:
            continue
        total += len(part if isinstance(part, str) else str(part))
    return max(1, total // 4)


def _build_tools_schema(role=None) -> list:
    """Build the tools schema, optionally filtered by role (Part 112)."""
    allowed = None
    try:
        from . import roles as _roles
        allowed = _roles.active_tool_names(role)
    except Exception:
        allowed = None
    allowed_set = set(allowed) if allowed is not None else None

    out = []
    for t in tools_registry.list_tools():
        if allowed_set is not None and t["name"] not in allowed_set:
            continue
        props = {}
        required = []
        for pname, pmeta in (t.get("parameters") or {}).items():
            props[pname] = {
                "type": pmeta.get("type", "string"),
                "description": pmeta.get("description", ""),
            }
            if pmeta.get("required"):
                required.append(pname)
        out.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": {
                    "type": "object",
                    "properties": props,
                    "required": required,
                },
            },
        })
    return out


def _parse_json_response(content: str) -> Optional[dict]:
    if not content:
        return None
    s = content.strip()
    if s.startswith("```"):
        lines = s.split("\n")
        if len(lines) >= 3 and lines[-1].strip().startswith("```"):
            s = "\n".join(lines[1:-1])
        else:
            s = "\n".join(lines[1:])
        s = s.strip()
    try:
        parsed = json.loads(s)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    match = re.search(r"\{.*\}", s, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group())
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return None
    return None


# ── Part 31E: tool result truncation (prevents base64 blowup in history) ──
_TOOL_RESULT_MAX_CHARS = 1500
_TOOL_RESULT_B64_FIELDS = ("image_base64", "image_data", "chart_base64")


def _truncate_tool_result(tool_result: dict) -> dict:
    """Return a version safe to append to messages / send back to LLM.

    - Strips base64 image fields -> [image: N bytes]
    - Caps stdout / result / preview / content to 500 chars each
    - Keeps error strings intact (usually short)
    """
    if not isinstance(tool_result, dict):
        return {"result": str(tool_result)[:_TOOL_RESULT_MAX_CHARS]}
    out = {}
    for k, v in tool_result.items():
        if k in _TOOL_RESULT_B64_FIELDS and isinstance(v, str) and v:
            out[k] = "[image: " + str(len(v)) + " bytes base64]"
            continue
        if isinstance(v, str) and len(v) > 500:
            out[k] = v[:500] + "... [truncated, orig " + str(len(v)) + " chars]"
            continue
        out[k] = v
    # Final safety cap on total JSON size
    import json as _json
    serialized = _json.dumps(out, default=str)
    if len(serialized) > _TOOL_RESULT_MAX_CHARS:
        return {"truncated_result": serialized[:_TOOL_RESULT_MAX_CHARS] + "... [truncated]"}
    return out


# ── Part 31E-ext2: tool-name aliases (gpt-oss-20b sometimes shortens names) ──
_TOOL_ALIASES = {
    "python": "python_eval",
    "pythoneval": "python_eval",
    "py": "python_eval",
    "code": "python_eval",
    "search": "web_search",
    "websearch": "web_search",
    "fetch": "web_fetch",
    "webfetch": "web_fetch",
    "calc": "calculator",
    "calculate": "calculator",
    "time": "current_time",
    "now": "current_time",
    "currenttime": "current_time",
    "date": "date_calc",
    "datecalc": "date_calc",
    "list": "list_files",
    "ls": "list_files",
    "listfiles": "list_files",
    "read": "read_file",
    "readfile": "read_file",
    "write": "write_file",
    "writefile": "write_file",
    "delete": "delete_file",
    "deletefile": "delete_file",
    "rm": "delete_file",
    "rag": "rag_search",
    "ragsearch": "rag_search",
    "memory": "memory_search",
    "memorysearch": "memory_search",
    "recall": "memory_search",
}




def _sanitize_tool_name(name: str) -> str:
    """Part 156b: strip special-token suffixes that some models emit
    (e.g. `delegate_to_agent<|channel|>commentary`, `tool<|end|>`).
    Returns a clean name that can be looked up in the registry.
    """
    if not name or not isinstance(name, str):
        return ""
    cleaned = name.strip()
    # Strip everything starting at a special-token marker
    for marker in ("<|", "|>", "\x00"):
        idx = cleaned.find(marker)
        if idx >= 0:
            cleaned = cleaned[:idx]
    # Drop trailing punctuation / whitespace
    cleaned = cleaned.strip().strip("`'\"")
    return cleaned


def _resolve_tool_name(name: str) -> str:
    """Map common short/abbreviated tool names to canonical ones."""
    # Part 156b: strip special-token suffixes before any lookup
    name = _sanitize_tool_name(name)
    if not name:
        return name
    # Exact match wins
    if tools_registry.get_tool(name):
        return name
    # Alias lookup (case-insensitive)
    key = str(name).strip().lower().replace("-", "").replace("_", "")
    if key in _TOOL_ALIASES:
        return _TOOL_ALIASES[key]
    return name


# ── Part 31F: detect placeholder answers after tool calls ──
_PLACEHOLDER_PATTERNS = (
    "what would you like",
    "how can i help",
    "what next",
    "what would you like to do",
    "let me know if",
    "anything else",
    "would you like me to",
    "happy to help",
    "how may i assist",
)


def _looks_like_placeholder(text: str) -> bool:
    """True if text is a short non-answer placeholder (no tool result used).

    Heuristic:
      - Empty -> placeholder
      - Contains a digit -> real answer (numeric/table result)
      - Matches known placeholder phrases -> placeholder
      - Very short (<15 chars) with no digits -> placeholder
      - Otherwise -> real answer
    """
    if not text:
        return True
    s = text.strip().lower()
    # Any digit -> treat as a real answer (numeric/table results are valid)
    if any(ch.isdigit() for ch in s):
        return False
    for pat in _PLACEHOLDER_PATTERNS:
        if pat in s:
            return True
    if len(s) < 15:
        return True
    return False


# ── Part 31F-ext3: inject real base64 into answers that reference it ──
_IMG_PLACEHOLDERS = (
    "{{image_base64}}",
    "{{ image_base64 }}",
    "{{base64}}",
    "{{ base64 }}",
    "{{image}}",
    "{{ image }}",
    "<IMAGE_BASE64>",
    "<image_base64>",
    "<BASE64>",
)


def _inject_chart_base64(answer: str, steps: list) -> str:
    """If the model wrote a placeholder instead of the real base64 chart,
    substitute the actual base64 from the tool steps."""
    if not answer or not steps:
        return answer

    # Collect the newest valid base64 from any tool step
    real_b64 = None
    for s in reversed(steps):
        r = s.get("result") or {}
        if not isinstance(r, dict):
            continue
        b64 = r.get("image_base64")
        if isinstance(b64, str) and b64 and not b64.startswith("["):
            real_b64 = b64
            break
    if not real_b64:
        return answer

    # Replace any placeholder tokens
    for tok in _IMG_PLACEHOLDERS:
        if tok in answer:
            answer = answer.replace(tok, real_b64)

    # Also handle the case where the model emitted "data:image/png;base64,<short-b64>"
    # with actual (but broken) base64 characters instead of a placeholder.
    import re
    def _sub(m):
        prefix, content = m.group(1), m.group(2)
        # If the content looks like a placeholder (short, contains braces) replace it
        if "{" in content or "}" in content or len(content) < 200:
            return prefix + real_b64 + ")"
        return m.group(0)
    answer = re.sub(
        r"(!\[[^\]]*\]\(data:image/png;base64,)([^)]+)\)",
        _sub,
        answer,
    )
    return answer


def _inject_plotly_div(answer: str, steps: list) -> str:
    """Part 123: if any tool step returned plotly_json, append an
    interactive chart container div to the answer.

    Uses a base64-encoded data attribute so the marker survives
    markdown parsing. Safe no-op if there is no plotly payload."""
    if not answer or not steps:
        return answer
    if "sunnyware-plotly" in answer:
        return answer
    plotly_json = None
    for s in reversed(steps):
        if not isinstance(s, dict):
            continue
        r = s.get("result") or {}
        if not isinstance(r, dict):
            continue
        pj = r.get("plotly_json")
        if isinstance(pj, str) and pj.strip():
            plotly_json = pj
            break
    if not plotly_json:
        return answer
    try:
        import base64 as _b64
        b64 = _b64.b64encode(plotly_json.encode("utf-8")).decode("ascii")
        return (answer
                + "\n\n<div class=\"sunnyware-plotly\" "
                + "data-plotly-b64=\"" + b64 + "\"></div>\n")
    except Exception:
        return answer


async def _execute_tool(name, args):
    """Part 160: circuit-breaker wrapper around the real executor."""
    try:
        decision = _cb.check(name)
    except Exception:
        decision = {"allow": True}
    if not decision.get("allow"):
        reason = decision.get("reason", "circuit_open")
        detail = (f"tool '{name}' is temporarily disabled after "
                  f"repeated failures") if reason == "circuit_open" else \
                 (f"tool '{name}' is rate limited")
        return {
            "error": reason,
            "detail": detail,
            "retry_after_s": decision.get("retry_after", 60),
        }

    # Part 167: JSON schema validation before execution
    try:
        from . import schema as _schema
        _tool = tools_registry.get_tool(name) if tools_registry else None
        _spec = getattr(_tool, "parameters", None) if _tool else None
        if _spec:
            _v = _schema.validate(name, _spec, args)
            if not _v.get("ok"):
                try:
                    from . import audit as _audit
                    _audit.log(
                        "schema.violation", actor="llm", ok=False,
                        detail=str(_v.get("detail", ""))[:300],
                        tool=name,
                    )
                except Exception:
                    pass
                return {
                    "error": "schema_violation",
                    "detail": _v.get("detail", ""),
                    "schema": _v.get("schema"),
                }
            args = _v.get("args", args)
    except Exception:
        pass

    try:
        result = await _execute_tool_raw(name, args)
    except Exception as e:
        try:
            _cb.record(name, False, f"{type(e).__name__}: {e}")
        except Exception:
            pass
        raise
    ok = True
    err = ""
    try:
        if isinstance(result, dict) and result.get("error"):
            ok = False
            err = str(result.get("error"))[:200]
    except Exception:
        pass
    try:
        _cb.record(name, ok, err)
    except Exception:
        pass
    return result


async def _execute_tool_raw(tool_name: str, tool_args: dict) -> dict:
    """Part 132: span-wrapped wrapper for _execute_tool_impl."""
    # Part 180: HITL Interceptor
    try:
        from . import approval_store as _as
        from . import hitl_config as _hc
        # Part 199: Use hitl_config for auto/approve/deny decisions
        _user_key = _hc.current_user_key.get() or ""
        _decision = _hc.get_decision(tool_name, _user_key)
        if _decision == "deny":
            return {"error": "tool_denied", "detail": f"Tool '{tool_name}' is disabled for this user."}
        if _decision == "approve":
            req = _as.create_request(tool_name, tool_args, user_key=_user_key)
            req_id = req["id"]
            import asyncio
            # Wait up to 120 seconds (60 * 2s)
            for _ in range(60):
                await asyncio.sleep(2)
                current = _as.get_request(req_id)
                if current and current.get("status") == "approved":
                    break
                if current and current.get("status") == "rejected":
                    return {"error": "approval_rejected", "detail": "Action rejected by human."}
            else:
                _as.set_status(req_id, "timeout")
                return {"error": "approval_timeout", "detail": "Action timed out waiting for approval."}
    except Exception:
        pass # Fallback to standard execution if HITL fails

    _span = None
    try:
        from . import tracing as _tr132
        _span = _tr132.add_span("tool_call", str(tool_name), attributes={
            "tool.name": str(tool_name),
            "tool.args_keys": list((tool_args or {}).keys())[:20],
        })
    except Exception:
        _span = None
    try:
        _res = await _execute_tool_impl(tool_name, tool_args)
    except Exception as _e:
        try:
            if _span is not None:
                from . import tracing as _tr132
                _tr132.finish_span(_span, status="error",
                                   extra={"error": str(_e)[:200]})
        except Exception:
            pass
        raise
    try:
        if _span is not None:
            from . import tracing as _tr132
            _is_err = bool(isinstance(_res, dict) and _res.get("error"))
            _keys = (list(_res.keys())[:20]
                     if isinstance(_res, dict) else [])
            _err_str = ""
            if isinstance(_res, dict) and _res.get("error"):
                _err_str = str(_res.get("error"))[:200]
            _tr132.finish_span(
                _span,
                status="error" if _is_err else "ok",
                extra={
                    "tool.result_keys": _keys,
                    "tool.result_error": _err_str,
                },
            )
    except Exception:
        pass
    return _res


async def _execute_tool_impl(tool_name: str, tool_args: dict) -> dict:
    from . import metrics as _metrics
    # Part 31E-ext2: resolve alias -> canonical name
    resolved = _resolve_tool_name(tool_name)
    if resolved != tool_name:
        try:
            from . import metrics as _m2
            _m2.incr_labeled("tool_alias_resolved", str(tool_name) + "->" + resolved)
        except Exception:
            pass
    tool_name = resolved
    _metrics.incr("tool_calls_total")
    _metrics.incr_labeled("tool_calls_by_name", tool_name)
    tool = tools_registry.get_tool(tool_name)
    if tool is None:
        return {"error": f"unknown tool: {tool_name}"}
    # Part 48: audit trail — fire-and-forget, never blocks
    import time as _time
    from . import audit as _audit
    _t0 = _time.time()
    _result = None
    _err = None
    try:
        _result = await tool.run(tool_args)
        if not isinstance(_result, dict):
            _result = {"result": _result}
        return _result
    except Exception as e:
        _err = f"{type(e).__name__}: {e}"
        return {"error": _err}
    finally:
        _latency_ms = int((_time.time() - _t0) * 1000)
        try:
            _audit.log_tool_call(tool_name, tool_args, _result, _err, _latency_ms)
        except Exception:
            pass


async def _emit(on_event, event: dict) -> None:
    """Fire event callback if provided (best-effort)."""
    if on_event is None:
        return
    try:
        await on_event(event)
    except Exception:
        pass


async def run_agent(
    prompt: str,
    session_uuid: Optional[str] = None,
    model: Optional[str] = None,
    system: Optional[str] = None,
    use_native_tools: Optional[bool] = None,
    on_event=None,
    role: Optional[str] = None,
) -> dict:
    """Part 114: public entry — sets role context for nested delegation.

    Part 119: also records per-role run/success/failure/latency metrics.
    Every metric call is wrapped in try/except and never affects behavior.
    """
    from .tools.delegate_to_agent import _CURRENT_ROLE
    _role_token = _CURRENT_ROLE.set(role or "general")

    # Part 132: trace instrumentation (safe)
    _tr132 = None
    _trace_id = None
    try:
        from . import tracing as _tr132
        _parent_trace = _tr132.current_trace_id()
        _trace_id = _tr132.start_trace(
            role=role, session_uuid=session_uuid, prompt=prompt,
            parent_trace_id=_parent_trace,
        )
    except Exception:
        _tr132 = None
        _trace_id = None

    # ── Part 119: metric instrumentation (safe) ──
    import time as _t119
    _t0_119 = _t119.time()
    _role_key = (str(role or "general").strip().lower() or "general")
    try:
        from . import metrics as _m119
    except Exception:
        _m119 = None
    try:
        if _m119 is not None:
            _m119.incr_labeled("agent_runs_total", _role_key)
    except Exception:
        pass

    try:
        _result_119 = await _run_agent_body(
            prompt=prompt,
            session_uuid=session_uuid,
            model=model,
            system=system,
            use_native_tools=use_native_tools,
            on_event=on_event,
            role=role,
        )
    except Exception:
        try:
            if _m119 is not None:
                _m119.incr_labeled("agent_failure_total", _role_key)
        except Exception:
            pass
        try:
            if _tr132 is not None and _trace_id:
                _tr132.finish_trace(status="error")
        except Exception:
            pass
        _CURRENT_ROLE.reset(_role_token)
        raise

    try:
        if _m119 is not None:
            _m119.incr_labeled("agent_success_total", _role_key)
            _ms = int((_t119.time() - _t0_119) * 1000)
            _m119.incr_labeled("agent_latency_ms_total", _role_key, _ms)
            _m119.incr_labeled("agent_latency_ms_count", _role_key, 1)
            try:
                _iters = int((_result_119 or {}).get("iterations") or 0)
                if _iters > 0:
                    _m119.incr_labeled("agent_iterations_total",
                                       _role_key, _iters)
            except Exception:
                pass
    except Exception:
        pass

    try:
        if _tr132 is not None and _trace_id:
            _tr132.finish_trace(
                status="ok",
                result_summary={
                    "iterations": (_result_119 or {}).get("iterations"),
                    "steps_count": len(
                        (_result_119 or {}).get("steps") or []
                    ),
                    "answer_preview": (
                        (_result_119 or {}).get("answer") or ""
                    )[:200],
                },
            )
    except Exception:
        pass

    _CURRENT_ROLE.reset(_role_token)
    return _result_119


async def _run_agent_body(
    prompt: str,
    session_uuid: Optional[str] = None,
    model: Optional[str] = None,
    system: Optional[str] = None,
    use_native_tools: Optional[bool] = None,
    on_event=None,
    role: Optional[str] = None,
) -> dict:
    # Part 114d: resolve role -> allowed tool set for both native and
    # compact paths. None means "no filtering" (general role).
    _allowed = None
    try:
        from . import roles as _roles_mod
        _allowed = _roles_mod.active_tool_names(role)
    except Exception:
        _allowed = None
    _allowed_set = set(_allowed) if _allowed else None

    history = []
    if session_uuid:
        history = await memory_store.build_context(session_uuid, max_turns=4)

    _role_style = {}
    try:
        from . import roles as _roles
        _role_style = _roles.style(role) or {}
    except Exception:
        _role_style = {}
    await _emit(on_event, {
        "type": "start",
        "role": role or "general",
        "accent": _role_style.get("accent", ""),
        "chip": _role_style.get("chip", ""),
    })

    if use_native_tools is None:
        try:
            from .config import load_config
            cfg = load_config()
            use_native_tools = getattr(cfg, "llm_native_tools", False)
        except Exception:
            use_native_tools = False

    relevant_events = await memory_store.select_relevant_events(
        prompt, exclude_session_uuid=session_uuid, limit=3
    )
    context_str = memory_store.format_context(relevant_events)

    if use_native_tools:
        system_prompt = prompts.native_prompt(context_str)
    else:
        system_prompt = prompts.compact_prompt(
            context_str, allowed_tools=_allowed
        )

    # Part 112: inject role persona prompt addon (prepended before base)
    _role_addon = ""
    try:
        from . import roles as _roles
        _role_addon = _roles.prompt_addon(role) or ""
    except Exception:
        _role_addon = ""
    if _role_addon:
        system_prompt = _role_addon + "\n\n" + system_prompt

    # Part 199d: prevent wasteful retries when HITL times out or denies
    _anti_retry = (
        "\n\nCRITICAL TOOL RULE: If a tool returns an error like "
        "'approval_timeout', 'tool_denied', or 'approval_rejected', "
        "do NOT call the same tool again in this turn. "
        "Instead, tell the user the tool is pending approval or has been blocked, "
        "and suggest they either approve it in /admin or use a different approach."
    )
    system_prompt = system_prompt + _anti_retry

    # Part 169: A/B prompt experiment injection.
    # Deterministic per (session_uuid, experiment). No live experiment
    # -> pick_variant returns (None, None) and this is a no-op.
    _ab_arm = None
    try:
        from . import ab_testing as _ab
        _ab_arm, _ab_extra = _ab.pick_variant(
            str(session_uuid or ""), str(role or "")
        )
        if _ab_arm == "b" and _ab_extra:
            system_prompt = _ab_extra + "\n\n" + system_prompt
    except Exception:
        pass

    if system:
        system_prompt = system + "\n\n" + system_prompt

    tools_schema = _build_tools_schema(role=role) if use_native_tools else None
    steps = []

    messages = list(history)
    messages.append({"role": "user", "content": prompt})

    _placeholder_retry_used = False
    _last_provider = None
    _last_model = None
    _seen_calls = {}          # Part 88c: tool_name -> list[(args, result)]
    _dup_streak = 0
    _tokens_used = 0          # Part 90: cumulative tokens
    _attachments = []         # Part 106: list of saved image refs
    # Part 96: fixed overhead to subtract from real usage so the
    # budget guard measures conversational cost, not tool schemas.
    _tools_overhead = 0
    if use_native_tools and tools_schema:
        _tools_overhead = _estimate_tokens(str(tools_schema))

    def _find_duplicate(tool_name, args):
        """Subset/superset match: LLMs sometimes drop optional keys on
        repeat calls. {name, sql} and {sql} are the SAME call."""
        for prev_args, prev_result in _seen_calls.get(tool_name, []):
            if all(k in prev_args and prev_args[k] == v for k, v in args.items()):
                return prev_result
            if all(k in args and args[k] == v for k, v in prev_args.items()):
                return prev_result
        return None

    def _record_call(tool_name, args, result):
        _seen_calls.setdefault(tool_name, []).append((args, result))

    # Part 274: Try local Jarvis routing before cloud LLM
    # This replaces the expensive cloud tool-calling loop with a fast,
    # token-efficient local model + RAG retrieval.
    try:
        from . import jarvis_agent as _jarvis
        _jarvis_result = await _jarvis.jarvis_route(prompt)
        if _jarvis_result:
            _tool_name = _jarvis_result.get("tool")
            _tool_args = _jarvis_result.get("args", {})
            # Respect role tool restrictions
            if _allowed_set is None or _tool_name in _allowed_set:
                from .tools import get_tool
                _tool_obj = get_tool(_tool_name)
                if _tool_obj:
                    try:
                        _tool_result = await _tool_obj.run(_tool_args)
                        await _emit(on_event, {
                            "type": "tool_call", "tool": _tool_name,
                            "args": _tool_args, "protocol": "jarvis",
                        })
                        await _emit(on_event, {
                            "type": "tool_result", "tool": _tool_name,
                            "result": _tool_result,
                        })
                        _final_prompt = (
                            "User asked: " + prompt + "\n\n"
                            + "Tool `" + _tool_name + "` was called and returned: "
                            + json.dumps(_tool_result) + "\n\n"
                            + "Write a concise final answer based on this result."
                        )
                        _final_res = await llm_client.chat(
                            prompt=_final_prompt,
                            model=model,
                            system=system_prompt,
                            history=history,
                            tools=None,
                        )
                        if _final_res.get("ok"):
                            steps.append({
                                "iteration": 1,
                                "tool": _tool_name,
                                "args": _tool_args,
                                "result": _tool_result,
                                "protocol": "jarvis",
                            })
                            return {
                                "ok": True,
                                "content": (_final_res.get("content") or "").strip(),
                                "steps": steps,
                                "iterations": 2,
                                "provider": _final_res.get("provider"),
                                "resolved_model": _final_res.get("resolved_model"),
                                "attachments": _attachments,
                            }
                    except Exception as _je:
                        pass  # Tool failed — fall through to normal loop
    except Exception:
        pass  # Jarvis disabled / model not loaded — fall through

    for iteration in range(MAX_ITERATIONS):
        result = await llm_client.chat(
            prompt if iteration == 0 else "Continue.",
            model=model,
            system=system_prompt,
            history=history if iteration == 0 else messages,
            tools=tools_schema if use_native_tools else None,
        )

        if not result.get("ok"):
            return {
                "ok": False,
                "error": result.get("error", "LLM call failed"),
                "steps": steps,
                "iterations": iteration + 1,
                "attachments": _attachments,
            }

        content = (result.get("content") or "").strip()
        native_calls = result.get("tool_calls")
        _last_provider = result.get("provider") or _last_provider
        _last_model = result.get("resolved_model") or _last_model

        # Part 90: cumulative token budget guard.
        # NOTE: tools_schema is intentionally NOT counted here - it's a
        # fixed infrastructure cost (~8700 tokens for 58 tool schemas) that
        # would trip the budget on any request. We only count conversational
        # content: prompt, system, response, and the growing message history.
        # Part 96: prefer real provider-reported tokens (accurate);
        # fall back to char/4 heuristic for providers that omit usage.
        _real = int(result.get("tokens_total", 0) or 0)
        if _real > 0:
            _tokens_used += max(0, _real - _tools_overhead)
        else:
            # heuristic fallback -- prompt is already inside messages,
            # so skip it to avoid double-counting (Part 96 fix)
            _tokens_used += _estimate_tokens(
                system_prompt, content,
                "".join(str(m) for m in messages),
            )
        if _tokens_used >= MAX_REQUEST_TOKENS:
            _budget_text = _BUDGET_MESSAGE.format(
                used=_tokens_used, cap=MAX_REQUEST_TOKENS
            )
            try:
                await _emit(on_event, {
                    "type": "budget_exceeded",
                    "used": _tokens_used,
                    "cap": MAX_REQUEST_TOKENS,
                })
            except Exception:
                pass
            return {
                "ok": True,
                "answer": _budget_text,
                "content": _budget_text,
                "steps": steps,
                "iterations": iteration + 1,
                "provider": _last_provider,
                "resolved_model": _last_model,
                "budget_exceeded": True,
                "tokens_used": _tokens_used,
                "attachments": _attachments,
            }

        if native_calls:
            messages.append({
                "role": "assistant",
                "content": content or "",
                "tool_calls": native_calls,
            })
            for call in native_calls:
                try:
                    fn = call["function"]
                    tool_name = fn["name"]
                    args_raw = fn.get("arguments", "{}")
                    tool_args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
                    if not isinstance(tool_args, dict):
                        tool_args = {}
                except Exception as e:
                    tool_args = {}
                    tool_name = "unknown"
                    tool_result = {"error": f"parse error: {e}"}
                else:
                    cached = _find_duplicate(tool_name, tool_args)
                    if cached is not None:
                        _dup_streak += 1
                        tool_result = cached
                        await _emit(on_event, {"type": "tool_result", "tool": tool_name, "result": tool_result, "cached": True})
                    else:
                        _dup_streak = 0
                        await _emit(on_event, {"type": "tool_call", "tool": tool_name, "args": tool_args, "protocol": "native"})
                        if _allowed_set is not None and tool_name not in _allowed_set:
                            tool_result = {
                                "error": "tool '" + str(tool_name) +
                                         "' not allowed for role '" + str(role) + "'",
                                "allowed": sorted(_allowed_set),
                            }
                        else:
                            tool_result = await _execute_tool(tool_name, tool_args)
                        _record_call(tool_name, tool_args, tool_result)
                        # Part 106: capture any attachment URL
                        _aurl = (tool_result or {}).get("attachment_url")
                        if _aurl:
                            _attachments.append({
                                "url": _aurl,
                                "id": (tool_result or {}).get("attachment_id"),
                                "ext": (tool_result or {}).get("attachment_ext"),
                                "kind": "image",
                                "tool": tool_name,
                            })
                        await _emit(on_event, {"type": "tool_result", "tool": tool_name, "result": tool_result})
                steps.append({
                    "iteration": iteration + 1,
                    "tool": tool_name,
                    "args": tool_args,
                    "result": tool_result,
                    "protocol": "native",
                })
                if _dup_streak > 0:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call.get("id", ""),
                        "content": (
                            "DUPLICATE CALL — you already called '"
                            + tool_name
                            + "' with identical arguments. Previous result: "
                            + json.dumps(_truncate_tool_result(tool_result))
                            + ". STOP calling tools and give your final answer NOW."
                        ),
                    })
                else:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call.get("id", ""),
                        "content": json.dumps(_truncate_tool_result(tool_result)),
                    })
            # Part 271: Force final answer after 2 tool calls to prevent loops
            if (len(steps) >= 2 or _dup_streak >= 2) and steps:
                last = steps[-1]
                return {
                    "ok": True,
                    "content": "Result: " + json.dumps(_truncate_tool_result(last.get("result", {}))),
                    "steps": steps,
                    "iterations": iteration + 1,
                    "provider": _last_provider,
                    "resolved_model": _last_model,
                    "attachments": _attachments,
                }
            continue

        parsed = _parse_json_response(content)

        if parsed is not None and "tool" in parsed:
            tool_name = str(parsed.get("tool", ""))
            tool_args = parsed.get("args") or {}
            if not isinstance(tool_args, dict):
                tool_args = {}
            cached = _find_duplicate(tool_name, tool_args)
            if cached is not None:
                _dup_streak += 1
                tool_result = cached
                await _emit(on_event, {"type": "tool_result", "tool": tool_name, "result": tool_result, "cached": True})
                feedback = ("DUPLICATE CALL — you already called '" + tool_name
                            + "' with equivalent args. Previous result: "
                            + json.dumps(_truncate_tool_result(tool_result))
                            + ". STOP calling tools and give final answer NOW.")
            else:
                _dup_streak = 0
                await _emit(on_event, {"type": "tool_call", "tool": tool_name, "args": tool_args, "protocol": "prompt-json"})
                tool_result = await _execute_tool(tool_name, tool_args)
                _record_call(tool_name, tool_args, tool_result)
                # Part 106: capture attachment URL from prompt-json path
                _aurl = (tool_result or {}).get("attachment_url")
                if _aurl:
                    _attachments.append({
                        "url": _aurl,
                        "id": (tool_result or {}).get("attachment_id"),
                        "ext": (tool_result or {}).get("attachment_ext"),
                        "kind": "image",
                        "tool": tool_name,
                    })
                await _emit(on_event, {"type": "tool_result", "tool": tool_name, "result": tool_result})
                feedback = ("Tool result: "
                            + json.dumps(_truncate_tool_result(tool_result))
                            + ". Now give final answer.")
            steps.append({
                "iteration": iteration + 1,
                "tool": tool_name,
                "args": tool_args,
                "result": tool_result,
                "protocol": "prompt-json",
            })
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content": feedback})
            # Part 271: Force final answer after 2 tool calls to prevent loops
            if len(steps) >= 2 or _dup_streak >= 2:
                return {
                    "ok": True,
                    "content": "Result: " + json.dumps(_truncate_tool_result(tool_result)),
                    "steps": steps,
                    "iterations": iteration + 1,
                    "provider": _last_provider,
                    "resolved_model": _last_model,
                "attachments": _attachments,
                }
            continue

        if parsed is not None and "answer" in parsed:
            _ans = str(parsed.get("answer", ""))
            _ans = _inject_chart_base64(_inject_plotly_div(_ans, steps), steps)
            await _emit(on_event, {"type": "answer", "text": _ans})
            return {
                "ok": True,
                "answer": _ans,
                "steps": steps,
                "provider": _last_provider,
                "resolved_model": _last_model,
                "iterations": iteration + 1,
                "attachments": _attachments,
            }

        if content:
            # Part 31F: if a tool ran but the model didn't answer (placeholder),
            # retry once with a hard directive before giving up.
            if steps and not _placeholder_retry_used and _looks_like_placeholder(content):
                _placeholder_retry_used = True
                try:
                    from . import metrics as _m
                    _m.incr("placeholder_retry_total")
                except Exception:
                    pass
                messages.append({"role": "assistant", "content": content})
                messages.append({
                    "role": "user",
                    "content": (
                        "You already have the tool result above. "
                        "Answer the original request now using that result. "
                        "Do NOT ask the user what to do next. "
                        "Deliver the concrete numeric/textual answer in one short reply."
                    ),
                })
                continue
            return {
                "ok": True,
                "answer": _inject_chart_base64(_inject_plotly_div(content, steps), steps),
                "steps": steps,
                "provider": _last_provider,
                "resolved_model": _last_model,
                "iterations": iteration + 1,
                "attachments": _attachments,
            }

        if steps:
            # Part 31F-ext: empty content after a tool result -> retry once
            # with a hard directive before falling back to the placeholder.
            if not _placeholder_retry_used:
                _placeholder_retry_used = True
                try:
                    from . import metrics as _m
                    _m.incr("empty_after_tool_retry_total")
                except Exception:
                    pass
                messages.append({
                    "role": "user",
                    "content": (
                        "You have the tool result above. "
                        "Write a short final answer that uses that result. "
                        "For charts, just say the chart is ready. "
                        "Do NOT return empty content."
                    ),
                })
                continue
            return {
                "ok": True,
                "answer": f"(completed {len(steps)} tool call(s), no final answer)",
                "steps": steps,
                "iterations": iteration + 1,
                "attachments": _attachments,
            }
        return {
            "ok": False,
            "error": "empty LLM response (model returned no content and no tool calls)",
            "steps": steps,
            "iterations": iteration + 1,
            "attachments": _attachments,
        }

    # Part 32: on iteration exhaustion, force the model to summarize what
    # it found so the user doesn't get a silent failure.
    if steps:
        try:
            from . import metrics as _m
            _m.incr("agent_forced_summary_total")
        except Exception:
            pass
        try:
            messages.append({
                "role": "user",
                "content": (
                    "You've reached the iteration limit. Do NOT call more tools. "
                    "In one short paragraph, tell the user exactly what you DID find "
                    "in the tool results above, and what you did NOT find. If nothing "
                    "relevant was found, say so explicitly."
                ),
            })
            _final = await llm_client.chat(
                prompt="Summarize what you found from the tool results above in one paragraph.",
                model=model, system=system_prompt, history=messages,
                tools=None, timeout=30.0,
            )
            if _final.get("ok"):
                _txt = (_final.get("content") or "").strip()
                if _txt:
                    return {
                        "ok": True,
                        "answer": _txt,
                        "steps": steps,
                        "iterations": MAX_ITERATIONS,
                        "forced_summary": True,
                        "provider": _last_provider,
                        "resolved_model": _last_model,
                    "attachments": _attachments,
                    }
        except Exception:
            pass

    return {
        "ok": True,
        "answer": "Maximum reasoning iterations reached without a final answer.",
        "steps": steps,
        "iterations": MAX_ITERATIONS,
        "truncated": True,
        "provider": _last_provider,
        "resolved_model": _last_model,
    "attachments": _attachments,
    }
