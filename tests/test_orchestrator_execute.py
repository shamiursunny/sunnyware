# -*- coding: utf-8 -*-
"""
Part 500: Unit test for orchestrator.run_agent with mocked LLM.
Verifies the direct answer path (no tool calls).
"""
import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sunnyware import orchestrator


def test_run_agent_direct_answer():
    """When the LLM returns a direct answer with no tool calls, run_agent returns it."""
    async def fake_chat(prompt, **kwargs):
        return {"ok": True, "content": "Hello, user!", "tool_calls": None}

    with patch.object(orchestrator.llm_client, "chat", AsyncMock(side_effect=fake_chat)), \
         patch.object(orchestrator, "_execute_tool", AsyncMock()) as mock_exec:
        result = asyncio.run(orchestrator.run_agent("Say hi"))

    assert result["ok"] is True
    assert result["answer"] == "Hello, user!"
    assert result["steps"] == []
    mock_exec.assert_not_called()
