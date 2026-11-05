"""Regression test for Part 721 — tool.run(**tool_args) must unpack dict args."""
import asyncio
from sunnyware.tools import get_tool


def test_calculator_accepts_args_dict():
    """Calculator tool uses Style A (args: dict) — must accept a single dict."""
    calc = get_tool("calculator")
    assert calc is not None
    result = asyncio.run(calc.run({"expression": "2 + 2"}))
    assert result is not None
    assert isinstance(result, dict)


def test_call_tool_handles_both_styles():
    """The _call_tool helper must auto-detect Style A vs Style B."""
    from sunnyware.orchestrator import _call_tool
    calc = get_tool("calculator")
    result = asyncio.run(_call_tool(calc, {"expression": "2 + 2"}))
    assert isinstance(result, dict)


def test_all_tools_have_parameters():
    """Every registered tool must expose a `parameters` attribute as a dict."""
    from sunnyware.tools import _TOOLS
    for name, tool in _TOOLS.items():
        assert hasattr(tool, "parameters"), f"Tool {name} missing .parameters"
        assert isinstance(tool.parameters, dict), f"Tool {name} .parameters is not a dict"
