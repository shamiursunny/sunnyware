# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Agent orchestrator — ReAct-style loop: think → tool call → observe → answer.

Protocol (prompt-based, works with any OpenAI-compatible model):

  LLM must respond with valid JSON only:
    {"tool": "<name>", "args": {...}}   → call a tool
    {"answer": "<text>"}                → final answer

The orchestrator parses, executes, feeds result back, loops until answer or
max iterations. If the LLM doesn't follow JSON protocol, its raw text is
returned as the answer (graceful fallback).
"""

import json
import re
from typing import Optional

from . import llm as llm_client
from . import memory as memory_store
from . import tools as tools_registry


MAX_ITERATIONS = 5


def _build_system_prompt() -> str:
    tools_lines = []
    for t in tools_registry.list_tools():
        params = json.dumps(t["parameters"]) if t["parameters"] else "{}"
        tools_lines.append(f"- {t['name']}: {t['description']} | params: {params}")
    tools_block = "\n".join(tools_lines) if tools_lines else "(no tools available)"

    return f"""You are Sunnyware, an AI agent that can call tools.

Available tools:
{tools_block}

RESPONSE FORMAT — you must respond with ONLY a single JSON object, nothing else.

To call a tool:
{{"tool": "tool_name", "args": {{"param": "value"}}}}

To give a final answer:
{{"answer": "your final answer text"}}

Rules:
1. Output valid JSON only — no markdown, no code fences, no explanation.
2. If you need information, call a tool first.
3. When you have enough information, provide a final answer.
4. Keep answers concise."""


def _parse_json_response(content: str) -> Optional[dict]:
    """Extract JSON object from LLM output (may include markdown fences)."""
    if not content:
        return None
    s = content.strip()

    # Strip markdown code fences if present
    if s.startswith("```"):
        lines = s.split("\n")
        # Drop first line (```json or ```) and last line (```)
        if len(lines) >= 3 and lines[-1].strip().startswith("```"):
            s = "\n".join(lines[1:-1])
        else:
            s = "\n".join(lines[1:])
        s = s.strip()

    # Direct parse
    try:
        parsed = json.loads(s)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    # Find first {...} block
    match = re.search(r"\{.*\}", s, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group())
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return None
    return None


async def run_agent(
    prompt: str,
    session_uuid: Optional[str] = None,
    model: Optional[str] = None,
    system: Optional[str] = None,
) -> dict:
    """Execute the agent loop.

    Returns dict:
      {ok: bool, answer: str, steps: list, iterations: int}
      or {ok: False, error: str, steps: list}
    """
    # Load multi-turn history (conversation only — not tool calls)
    history = []
    if session_uuid:
        history = await memory_store.build_context(session_uuid, max_turns=5)

    system_prompt = _build_system_prompt()
    if system:
        system_prompt = system + "\n\n" + system_prompt

    # Accumulate tool interaction for this turn
    extra_messages = []
    steps = []

    for iteration in range(MAX_ITERATIONS):
        if iteration == 0:
            current_prompt = prompt
            current_history = history
        else:
            current_prompt = "Continue. Respond with ONLY a JSON object."
            current_history = history + extra_messages

        result = await llm_client.chat(
            current_prompt,
            model=model,
            system=system_prompt,
            history=current_history,
        )

        if not result.get("ok"):
            return {
                "ok": False,
                "error": result.get("error", "LLM call failed"),
                "steps": steps,
                "iterations": iteration + 1,
            }

        content = (result.get("content") or "").strip()
        parsed = _parse_json_response(content)

        # Fallback: LLM didn't follow protocol → treat raw as answer
        if parsed is None:
            return {
                "ok": True,
                "answer": content,
                "steps": steps,
                "iterations": iteration + 1,
                "raw_fallback": True,
            }

        # Final answer path
        if "answer" in parsed:
            return {
                "ok": True,
                "answer": str(parsed.get("answer", "")),
                "steps": steps,
                "iterations": iteration + 1,
            }

        # Tool call path
        if "tool" in parsed:
            tool_name = str(parsed.get("tool", ""))
            tool_args = parsed.get("args") or {}
            if not isinstance(tool_args, dict):
                tool_args = {}

            tool = tools_registry.get_tool(tool_name)
            if tool is None:
                tool_result = {"error": f"unknown tool: {tool_name}"}
            else:
                try:
                    tool_result = await tool.run(tool_args)
                    if not isinstance(tool_result, dict):
                        tool_result = {"result": tool_result}
                except Exception as e:
                    tool_result = {"error": f"{type(e).__name__}: {e}"}

            steps.append({
                "iteration": iteration + 1,
                "tool": tool_name,
                "args": tool_args,
                "result": tool_result,
            })

            # Feed back into conversation
            extra_messages.append({"role": "assistant", "content": content})
            extra_messages.append({
                "role": "user",
                "content": f"Tool result: {json.dumps(tool_result)}",
            })
            continue

        # Parsed JSON but no tool/answer key → treat as answer
        return {
            "ok": True,
            "answer": json.dumps(parsed),
            "steps": steps,
            "iterations": iteration + 1,
        }

    # Max iterations reached
    return {
        "ok": True,
        "answer": "Maximum reasoning iterations reached without a final answer.",
        "steps": steps,
        "iterations": MAX_ITERATIONS,
        "truncated": True,
    }
