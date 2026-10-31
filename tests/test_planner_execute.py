# -*- coding: utf-8 -*-
"""
Part 499: Unit tests for planner.plan_and_execute with mocked dependencies.
Covers planning, execution (success/failure), and synthesis.
"""
import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sunnyware import planner


def test_plan_and_execute_success():
    """Planner returns two subtasks, both orchestrator runs succeed."""
    async def fake_chat(prompt, **kwargs):
        if "Decompose this task" in prompt:
            return {"ok": True, "content": '{"subtasks": ["step 1", "step 2"]}'}
        else:  # synthesis
            return {"ok": True, "content": "Final synthesized answer"}

    async def fake_run_agent(task, **kwargs):
        return {"ok": True, "answer": f"Answer for {task}", "steps": [], "iterations": 1}

    with patch.object(planner.llm_client, "chat", AsyncMock(side_effect=fake_chat)), \
         patch.object(planner.orchestrator, "run_agent", AsyncMock(side_effect=fake_run_agent)):
        result = asyncio.run(planner.plan_and_execute("Do something complex", parallel=False))

    assert result["ok"] is True
    assert result["subtasks"] == ["step 1", "step 2"]
    assert len(result["results"]) == 2
    assert all(r["ok"] for r in result["results"])
    assert result["final_answer"] == "Final synthesized answer"


def test_plan_and_execute_planner_failure():
    """If the planner LLM call fails, the function returns an error."""
    async def fake_chat(prompt, **kwargs):
        return {"ok": False, "error": "planner unavailable"}

    with patch.object(planner.llm_client, "chat", AsyncMock(side_effect=fake_chat)):
        result = asyncio.run(planner.plan_and_execute("Do something"))

    assert result["ok"] is False
    assert "planner failed" in result["error"]
    assert result["subtasks"] == []
    assert result["results"] == []


def test_plan_and_execute_one_subtask_fails():
    """If one subtask fails, the final answer is still synthesized from the successful one."""
    async def fake_chat(prompt, **kwargs):
        if "Decompose this task" in prompt:
            return {"ok": True, "content": '{"subtasks": ["good task", "bad task"]}'}
        else:
            return {"ok": True, "content": "Synthesized from partial success"}

    async def fake_run_agent(task, **kwargs):
        if "good" in task:
            return {"ok": True, "answer": "good answer", "steps": [], "iterations": 1}
        else:
            return {"ok": False, "error": "boom"}

    with patch.object(planner.llm_client, "chat", AsyncMock(side_effect=fake_chat)), \
         patch.object(planner.orchestrator, "run_agent", AsyncMock(side_effect=fake_run_agent)):
        result = asyncio.run(planner.plan_and_execute("Do something", parallel=False))

    assert result["ok"] is True
    assert result["subtasks"] == ["good task", "bad task"]
    assert len(result["results"]) == 2
    assert result["results"][0]["ok"] is True
    assert result["results"][1]["ok"] is False
    assert result["final_answer"] == "Synthesized from partial success"


def test_plan_and_execute_empty_task():
    """Empty task returns an error immediately."""
    result = asyncio.run(planner.plan_and_execute(""))
    assert result["ok"] is False
    assert "task is required" in result["error"]
    assert result["subtasks"] == []
