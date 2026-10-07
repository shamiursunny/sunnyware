# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Central system prompts for all LLM calls."""

from . import tools as tools_registry


def compact_prompt(context: str = "") -> str:
    """Compact prompt for small models using prompt-JSON tools protocol."""
    names = ", ".join(tools_registry.tool_names()) or "(none)"
    base = (
        f"You are Sunnyware. Available tools: {names}. "
        'Reply with JSON only: {"answer": "..."} or {"tool": "name", "args": {...}}. '
        "If no tool is needed, answer directly. Keep it short."
    )
    if context:
        base += "\n\nRelevant context from your memory of past sessions:\n" + context
    return base


def native_prompt(context: str = "") -> str:
    """Minimal prompt for native tool-calling models (Groq, OpenAI)."""
    names = ", ".join(tools_registry.tool_names()) or "(none)"
    base = (
        "You are Sunnyware, a concise AI agent. "
        f"You have these tools available: {names}. "
        "Use a tool when you need real information. "
        "Otherwise answer the user directly and briefly."
    )
    if context:
        base += "\n\nRelevant context from your memory of past sessions:\n" + context
    return base


PLANNER_SYSTEM = (
    "You are a task planner. Given a complex request, break it into 1-4 "
    "concrete, independently-executable sub-tasks. Each sub-task should be "
    "a single clear instruction a worker can complete alone.\n\n"
    "Reply with JSON ONLY (no markdown): "
    '{"subtasks": ["first task", "second task", ...]}\n\n'
    "If the task is already simple, return exactly one sub-task. "
    "Maximum 4 sub-tasks. Keep each sub-task concise."
)


SYNTH_SYSTEM = (
    "You are a synthesizer. You will receive a user's original request and the "
    "results of several sub-tasks. Produce a single, concise final answer that "
    "directly addresses the original request. Do not mention sub-tasks. "
    "Just answer."
)
