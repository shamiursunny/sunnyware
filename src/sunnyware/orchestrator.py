# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Agent orchestrator — supports BOTH native (OpenAI/Groq) and prompt-based tools.

Flow per iteration:
  1. Call LLM with tools= (native). Groq/GPT-4 use tool_calls.
  2. If LLM returned tool_calls → execute, feed back, loop.
  3. Else if LLM content has JSON {"tool":..., "args":...} → execute (Ollama path).
  4. Else if content has JSON {"answer":...} → return answer.
  5. Else → treat raw content as final answer (fallback).
"""

import json
import re
from typing import Optional

from . import llm as llm_client
from . import memory as memory_store
from . import tools as tools_registry


MAX_ITERATIONS = 5


def _build_tools_schema() -> list:
    """Build OpenAI-format tools schema from registry."""
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


def _build_native_system_prompt() -> str:
    """Minimal system prompt for native tool calling.

    Native models (Groq gpt-oss, OpenAI gpt-4o) already understand the tools=
    schema — do NOT include JSON protocol instructions or we confuse them.
    """
    names = ", ".join(tools_registry.tool_names()) or "(none)"
    return (
        "You are Sunnyware, a concise AI agent. "
        f"You have these tools available: {names}. "
        "Use a tool when you need real information. "
        "Otherwise answer the user directly and briefly."
    )


def _build_system_prompt() -> str:
    tools_lines = []
    for t in tools_registry.list_tools():
        params = json.dumps(t["parameters"]) if t["parameters"] else "{}"
        tools_lines.append(f"- {t['name']}: {t['description']} | params: {params}")
    tools_block = "\n".join(tools_lines) if tools_lines else "(no tools available)"

    return f"""You are Sunnyware, an AI agent that can call tools.

Available tools:
{tools_block}

Behavior:
- Call a tool when you need real information (e.g., current time).
- Otherwise, answer directly and concisely.
- Keep answers short."""


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


async def _execute_tool(tool_name: str, tool_args: dict) -> dict:
    tool = tools_registry.get_tool(tool_name)
    if tool is None:
        return {"error": f"unknown tool: {tool_name}"}
    try:
        result = await tool.run(tool_args)
        if not isinstance(result, dict):
            result = {"result": result}
        return result
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


async def run_agent(
    prompt: str,
    session_uuid: Optional[str] = None,
    model: Optional[str] = None,
    system: Optional[str] = None,
    use_native_tools: Optional[bool] = None,
) -> dict:
    """Execute the agent loop.

    use_native_tools: if True, pass OpenAI tools param (Groq/GPT).
                      if False, use prompt-based JSON protocol (Ollama).
                      if None, auto-detect from config (default).
    """
    history = []
    if session_uuid:
        history = await memory_store.build_context(session_uuid, max_turns=5)

    # Choose system prompt based on mode
    if use_native_tools is None:
        try:
            from .config import load_config
            cfg = load_config()
            use_native_tools = getattr(cfg, "llm_native_tools", False)
        except Exception:
            use_native_tools = False

    if use_native_tools:
        system_prompt = _build_native_system_prompt()
    else:
        system_prompt = _build_system_prompt()

    if system:
        system_prompt = system + "\n\n" + system_prompt

    tools_schema = _build_tools_schema() if use_native_tools else None
    steps = []

    # OpenAI-style message history for native protocol
    messages = list(history)
    messages.append({"role": "user", "content": prompt})

    for iteration in range(MAX_ITERATIONS):
        # Only pass tools on iteration 0 — subsequent turns use message history
        result = await llm_client.chat(
            prompt if iteration == 0 else "Continue.",
            model=model,
            system=system_prompt,
            history=history if iteration == 0 else messages,
            tools=tools_schema if (iteration == 0 and use_native_tools) else None,
        )

        if not result.get("ok"):
            return {
                "ok": False,
                "error": result.get("error", "LLM call failed"),
                "steps": steps,
                "iterations": iteration + 1,
            }

        content = (result.get("content") or "").strip()
        native_calls = result.get("tool_calls")

        # ── Path 1: Native tool calls (Groq/GPT) ──
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
                    tool_result = await _execute_tool(tool_name, tool_args)

                steps.append({
                    "iteration": iteration + 1,
                    "tool": tool_name,
                    "args": tool_args,
                    "result": tool_result,
                    "protocol": "native",
                })

                messages.append({
                    "role": "tool",
                    "tool_call_id": call.get("id", ""),
                    "content": json.dumps(tool_result),
                })
            continue

        # ── Path 2: Prompt-based JSON (Ollama) ──
        parsed = _parse_json_response(content)

        if parsed is not None and "tool" in parsed:
            tool_name = str(parsed.get("tool", ""))
            tool_args = parsed.get("args") or {}
            if not isinstance(tool_args, dict):
                tool_args = {}
            tool_result = await _execute_tool(tool_name, tool_args)
            steps.append({
                "iteration": iteration + 1,
                "tool": tool_name,
                "args": tool_args,
                "result": tool_result,
                "protocol": "prompt-json",
            })
            messages.append({"role": "assistant", "content": content})
            messages.append({
                "role": "user",
                "content": f"Tool result: {json.dumps(tool_result)}. Now give final answer.",
            })
            continue

        if parsed is not None and "answer" in parsed:
            return {
                "ok": True,
                "answer": str(parsed.get("answer", "")),
                "steps": steps,
                "iterations": iteration + 1,
            }

        # ── Path 3: Plain text answer ──
        if content:
            return {
                "ok": True,
                "answer": content,
                "steps": steps,
                "iterations": iteration + 1,
            }

        # Empty content — if we have steps, return partial; else error
        if steps:
            return {
                "ok": True,
                "answer": f"(completed {len(steps)} tool call(s), no final answer)",
                "steps": steps,
                "iterations": iteration + 1,
            }
        return {
            "ok": False,
            "error": "empty LLM response (model returned no content and no tool calls)",
            "steps": steps,
            "iterations": iteration + 1,
        }

    return {
        "ok": True,
        "answer": "Maximum reasoning iterations reached without a final answer.",
        "steps": steps,
        "iterations": MAX_ITERATIONS,
        "truncated": True,
    }
