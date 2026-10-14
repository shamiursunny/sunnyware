# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Agent orchestrator — ReAct-style loop (native tools + prompt-JSON fallback)."""

import json
import re
from typing import Optional

from . import llm as llm_client
from . import memory as memory_store
from . import prompts
from . import tools as tools_registry


MAX_ITERATIONS = 3  # Part 88: lowered 7 -> 3 (was burning 6 LLM calls per message)

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


def _build_tools_schema() -> list:
    out = []
    for t in tools_registry.list_tools():
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


def _resolve_tool_name(name: str) -> str:
    """Map common short/abbreviated tool names to canonical ones."""
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


async def _execute_tool(tool_name: str, tool_args: dict) -> dict:
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
) -> dict:
    history = []
    if session_uuid:
        history = await memory_store.build_context(session_uuid, max_turns=4)

    await _emit(on_event, {"type": "start"})

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
        system_prompt = prompts.compact_prompt(context_str)

    if system:
        system_prompt = system + "\n\n" + system_prompt

    tools_schema = _build_tools_schema() if use_native_tools else None
    steps = []

    messages = list(history)
    messages.append({"role": "user", "content": prompt})

    _placeholder_retry_used = False
    _last_provider = None
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
            if _dup_streak >= 2 and steps:
                last = steps[-1]
                return {
                    "ok": True,
                    "content": "Result: " + json.dumps(_truncate_tool_result(last.get("result", {}))),
                    "steps": steps,
                    "iterations": iteration + 1,
                    "provider": _last_provider,
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
            if _dup_streak >= 2:
                return {
                    "ok": True,
                    "content": "Result: " + json.dumps(_truncate_tool_result(tool_result)),
                    "steps": steps,
                    "iterations": iteration + 1,
                    "provider": _last_provider,
                "attachments": _attachments,
                }
            continue

        if parsed is not None and "answer" in parsed:
            _ans = str(parsed.get("answer", ""))
            _ans = _inject_chart_base64(_ans, steps)
            await _emit(on_event, {"type": "answer", "text": _ans})
            return {
                "ok": True,
                "answer": _ans,
                "steps": steps,
                "provider": _last_provider,
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
                "answer": _inject_chart_base64(content, steps),
                "steps": steps,
                "provider": _last_provider,
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
    "attachments": _attachments,
    }
