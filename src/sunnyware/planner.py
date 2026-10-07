# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Multi-step planner — decompose complex task into sub-tasks and synthesize.

Flow:
  1. Planner LLM call → list of 1-4 sub-tasks (JSON)
  2. Execute each sub-task via orchestrator.run_agent()
  3. Synthesizer LLM call → combine sub-results into final answer
"""

import asyncio
import json
import re
from typing import Optional

from . import llm as llm_client
from . import orchestrator
from . import prompts


MAX_SUBTASKS = 4
PLANNER_TIMEOUT = 45.0
SYNTH_TIMEOUT = 45.0







def _parse_subtasks(content: str) -> list:
    """Extract subtasks from LLM output (JSON with markdown tolerance)."""
    if not content:
        return []
    s = content.strip()
    # Strip code fences
    if s.startswith("```"):
        lines = s.split("\n")
        if len(lines) >= 3 and lines[-1].strip().startswith("```"):
            s = "\n".join(lines[1:-1])
        else:
            s = "\n".join(lines[1:])
        s = s.strip()

    # Direct JSON
    try:
        obj = json.loads(s)
        if isinstance(obj, dict) and "subtasks" in obj:
            return _clean_list(obj["subtasks"])
        if isinstance(obj, list):
            return _clean_list(obj)
    except Exception:
        pass

    # Fallback: find first {...}
    m = re.search(r"\{.*\}", s, re.DOTALL)
    if m:
        try:
            obj = json.loads(m.group())
            if isinstance(obj, dict) and "subtasks" in obj:
                return _clean_list(obj["subtasks"])
        except Exception:
            pass

    return []


def _clean_list(items) -> list:
    if not isinstance(items, list):
        return []
    out = []
    for item in items:
        s = str(item).strip()
        if s:
            out.append(s)
    return out[:MAX_SUBTASKS]


async def _run_one_subtask(st: str, session_uuid: Optional[str], model: Optional[str]) -> dict:
    """Execute a single sub-task via orchestrator, normalize result."""
    try:
        r = await orchestrator.run_agent(st, session_uuid=session_uuid, model=model)
        if r.get("ok"):
            return {
                "subtask": st,
                "ok": True,
                "answer": r.get("answer", ""),
                "steps_count": len(r.get("steps", [])),
                "iterations": r.get("iterations", 0),
            }
        return {
            "subtask": st,
            "ok": False,
            "error": r.get("error", "unknown"),
            "answer": "",
            "steps_count": 0,
            "iterations": 0,
        }
    except Exception as e:
        return {
            "subtask": st,
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
            "answer": "",
            "steps_count": 0,
            "iterations": 0,
        }


async def plan_and_execute(
    task: str,
    session_uuid: Optional[str] = None,
    model: Optional[str] = None,
    parallel: bool = True,
) -> dict:
    """Decompose task, run each sub-task (sequential or parallel), synthesize.

    Returns:
      {
        ok: bool,
        task: str,
        subtasks: [str, ...],
        results: [{subtask, ok, answer, error?, steps_count, iterations}, ...],
        final_answer: str,
        latency_ms: int,
        error?: str
      }
    """
    import time
    t0 = time.time()

    if not task or not task.strip():
        return {
            "ok": False,
            "task": task,
            "error": "task is required",
            "subtasks": [],
            "results": [],
            "final_answer": "",
            "latency_ms": 0,
        }

    # ── Step 1: Plan ──
    plan_result = await llm_client.chat(
        f"Decompose this task into sub-tasks: {task}",
        model=model,
        system=prompts.PLANNER_SYSTEM,
        timeout=PLANNER_TIMEOUT,
    )

    if not plan_result.get("ok"):
        return {
            "ok": False,
            "task": task,
            "error": f"planner failed: {plan_result.get('error')}",
            "subtasks": [],
            "results": [],
            "final_answer": "",
            "latency_ms": int((time.time() - t0) * 1000),
        }

    subtasks = _parse_subtasks(plan_result.get("content", ""))

    # Fallback: if planner fails protocol, treat whole task as single sub-task
    if not subtasks:
        subtasks = [task]

    # ── Step 2: Execute sub-tasks (parallel or sequential) ──
    if parallel and len(subtasks) > 1:
        # asyncio.gather — run all subtasks concurrently
        gathered = await asyncio.gather(
            *[_run_one_subtask(st, session_uuid, model) for st in subtasks],
            return_exceptions=False,
        )
        results = list(gathered)
    else:
        results = []
        for st in subtasks:
            results.append(await _run_one_subtask(st, session_uuid, model))

    # ── Step 3: Synthesize final answer ──
    results_text = "\n\n".join(
        f"Sub-task {i+1}: {r['subtask']}\n"
        f"Result: {'OK — ' + r['answer'] if r['ok'] else 'FAILED — ' + r.get('error', '')}"
        for i, r in enumerate(results)
    )

    synth_prompt = (
        f"Original user request:\n{task}\n\n"
        f"Sub-task results:\n{results_text}\n\n"
        "Write the final answer for the user."
    )

    synth_result = await llm_client.chat(
        synth_prompt,
        model=model,
        system=prompts.SYNTH_SYSTEM,
        timeout=SYNTH_TIMEOUT,
    )

    final_answer = ""
    if synth_result.get("ok"):
        final_answer = synth_result.get("content", "").strip()
    else:
        # Fallback: concatenate sub-answers
        final_answer = " ".join(
            r["answer"] for r in results if r["ok"] and r.get("answer")
        ).strip()
        if not final_answer:
            final_answer = "(no answer could be synthesized)"

    return {
        "ok": True,
        "task": task,
        "subtasks": subtasks,
        "parallel": parallel and len(subtasks) > 1,
        "results": results,
        "final_answer": final_answer,
        "latency_ms": int((time.time() - t0) * 1000),
    }
