import asyncio
from sunnyware.tools.calculator import CalculatorTool

tool = CalculatorTool()


def run(expr):
    return asyncio.run(tool.run({"expression": expr}))


def test_add():
    assert run("2 + 3")["result"] == 5


def test_multiply():
    assert run("4 * 5")["result"] == 20


def test_parens():
    assert run("2 * (3 + 4)")["result"] == 14


def test_power():
    assert run("2 ** 8")["result"] == 256


def test_rejects_code():
    r = run("__import__('os')")
    assert "error" in r


def test_empty():
    r = run("")
    assert "error" in r
