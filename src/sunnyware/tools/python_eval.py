# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Sandboxed Python executor — best-effort isolation for agent use.

Restrictions:
- No imports (AST-rejected)
- No eval/exec/compile/__import__/open/input
- No dunder attribute access
- Restricted builtins (~40 functions only)
- 5-second timeout, 4KB code limit
- Output capped at 4KB

Not bulletproof against every exploit — suitable for an internal agent
that runs code from its own LLM (not arbitrary untrusted users).
"""

import ast
import asyncio
import io
from contextlib import redirect_stdout, redirect_stderr


MAX_CODE_LENGTH = 4000
MAX_OUTPUT_LENGTH = 4000
EXEC_TIMEOUT = 5.0


BANNED_NAMES = frozenset({
    "eval", "exec", "compile", "__import__", "open", "input",
    "globals", "locals", "vars", "dir", "getattr", "setattr", "delattr",
    "breakpoint", "help", "exit", "quit",
    "__builtins__", "__loader__", "__spec__", "__file__",
})


class _SafeVisitor(ast.NodeVisitor):
    """Reject imports, banned names, and dunder attribute access."""

    def __init__(self):
        self.errors = []

    def visit_Import(self, node):
        self.errors.append(f"import not allowed (line {node.lineno})")

    def visit_ImportFrom(self, node):
        self.errors.append(f"from-import not allowed (line {node.lineno})")

    def visit_Name(self, node):
        if node.id in BANNED_NAMES:
            self.errors.append(f"banned name '{node.id}' (line {node.lineno})")
        self.generic_visit(node)

    def visit_Attribute(self, node):
        if node.attr.startswith("__") and node.attr.endswith("__"):
            self.errors.append(
                f"dunder attribute '{node.attr}' not allowed (line {node.lineno})"
            )
        self.generic_visit(node)


def _validate(code: str) -> list:
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as e:
        return [f"syntax error: {e.msg} (line {e.lineno})"]
    v = _SafeVisitor()
    v.visit(tree)
    return v.errors


def _safe_builtins() -> dict:
    import builtins as _b
    allowed = [
        "abs", "all", "any", "ascii", "bin", "bool", "bytearray", "bytes",
        "callable", "chr", "complex", "dict", "divmod", "enumerate", "filter",
        "float", "format", "frozenset", "hash", "hex", "id", "int",
        "isinstance", "issubclass", "iter", "len", "list", "map", "max",
        "min", "next", "oct", "ord", "pow", "print", "range", "repr",
        "reversed", "round", "set", "slice", "sorted", "str", "sum",
        "tuple", "type", "zip",
        "True", "False", "None",
        "Exception", "ValueError", "TypeError", "KeyError", "IndexError",
        "ZeroDivisionError", "ArithmeticError", "StopIteration",
        "AttributeError", "RuntimeError", "NameError",
    ]
    return {name: getattr(_b, name) for name in allowed if hasattr(_b, name)}


def _exec_sync(code: str) -> dict:
    out = io.StringIO()
    namespace = {"__builtins__": _safe_builtins()}
    try:
        with redirect_stdout(out), redirect_stderr(out):
            compiled = compile(code, "<python_eval>", "exec")
            exec(compiled, namespace)
    except Exception as e:
        return {
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
            "stdout": out.getvalue()[:MAX_OUTPUT_LENGTH],
            "result": namespace.get("result"),
        }
    return {
        "ok": True,
        "stdout": out.getvalue()[:MAX_OUTPUT_LENGTH],
        "result": namespace.get("result"),
    }


class PythonEvalTool:
    name = "python_eval"
    description = (
        "Execute Python code in a restricted sandbox. Returns captured stdout "
        "and the value of a `result` variable if set. No imports, no file/"
        "network access. Use for math, data transforms, string operations."
    )
    parameters = {
        "code": {
            "type": "string",
            "description": "Python code. Set `result = ...` to return a value.",
            "required": True,
        }
    }

    async def run(self, args: dict) -> dict:
        code = str(args.get("code", "")).strip()
        if not code:
            return {"error": "code is required"}
        if len(code) > MAX_CODE_LENGTH:
            return {"error": f"code too long (max {MAX_CODE_LENGTH} chars)"}

        errors = _validate(code)
        if errors:
            return {"error": "code rejected", "reasons": errors}

        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(_exec_sync, code),
                timeout=EXEC_TIMEOUT,
            )
        except asyncio.TimeoutError:
            return {"error": f"execution timed out ({EXEC_TIMEOUT}s)"}

        return result
