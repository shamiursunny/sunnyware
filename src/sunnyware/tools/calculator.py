# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Safe calculator — AST-based evaluation, no arbitrary code."""

import ast
import operator


_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.FloorDiv: operator.floordiv,
}

_ALLOWED_UNARYOPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _eval(node):
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"unsupported constant: {node.value!r}")
    if isinstance(node, ast.BinOp):
        op = _ALLOWED_BINOPS.get(type(node.op))
        if op is None:
            raise ValueError(f"unsupported operator: {type(node.op).__name__}")
        return op(_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp):
        op = _ALLOWED_UNARYOPS.get(type(node.op))
        if op is None:
            raise ValueError(f"unsupported unary operator: {type(node.op).__name__}")
        return op(_eval(node.operand))
    raise ValueError(f"unsupported node: {type(node).__name__}")


class CalculatorTool:
    name = "calculator"
    description = "Evaluate a math expression safely (+, -, *, /, %, **, //). Returns the numeric result."
    parameters = {
        "expression": {
            "type": "string",
            "description": "Math expression, e.g. '2 + 3 * 4'",
            "required": True,
        }
    }

    async def run(self, args: dict) -> dict:
        expr = str(args.get("expression", "")).strip()
        if not expr:
            return {"error": "expression is required"}
        if len(expr) > 500:
            return {"error": "expression too long"}
        try:
            tree = ast.parse(expr, mode="eval")
            result = _eval(tree)
        except SyntaxError as e:
            return {"error": f"syntax error: {e.msg}"}
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}
        return {"expression": expr, "result": result}
