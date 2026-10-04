# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Tool registry — all agent tools live in this package.

Each tool is a class with:
  - name: str
  - description: str
  - parameters: dict (JSON-schema-ish)
  - async run(args: dict) -> dict
"""

from .echo import EchoTool
from .current_time import CurrentTimeTool


# Central registry
_TOOLS = {
    EchoTool.name: EchoTool(),
    CurrentTimeTool.name: CurrentTimeTool(),
}


def list_tools() -> list:
    """Return metadata for all registered tools."""
    return [
        {
            "name": t.name,
            "description": t.description,
            "parameters": t.parameters,
        }
        for t in _TOOLS.values()
    ]


def get_tool(name: str):
    """Return tool instance, or None."""
    return _TOOLS.get(name)


def tool_names() -> list:
    return list(_TOOLS.keys())
