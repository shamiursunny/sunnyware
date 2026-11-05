"""Regression test for Part 721 — tool.run(**tool_args) must unpack dict args."""
import asyncio
from sunnyware.tools import get_tool


def test_calculator_accepts_kwargs():
    """Calculator tool must accept keyword args, not a single positional dict."""
    calc = get_tool("calculator")
    assert calc is not None
    result = asyncio.run(calc.run(expression="2 + 2"))
    assert result is not None
    assert isinstance(result, dict)


def test_all_tools_have_parameters():
    """Every registered tool must expose a `parameters` attribute as a dict."""
    from sunnyware.tools import _TOOLS
    for name, tool in _TOOLS.items():
        assert hasattr(tool, "parameters"), f"Tool {name} missing .parameters"
        assert isinstance(tool.parameters, dict), f"Tool {name} .parameters is not a dict"
