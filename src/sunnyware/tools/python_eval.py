# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Data-science workbench for the agent.

Preloaded (no import needed): np, pd, plt, sns, scipy, stats, sklearn,
sqlite3, duckdb, pl, pa, openpyxl, tabulate, Path, ws_path.

Allowed imports: whitelist in _sandbox.py (numpy, pandas, scipy, sklearn,
statsmodels, polars, pyarrow, duckdb, matplotlib, seaborn, plotly,
openpyxl, xlsxwriter, tabulate + safe stdlib).

Blocked: os, sys, subprocess, socket, urllib.request, requests, ctypes,
importlib, and any file I/O outside the workspace jail.

Threat model: semi-trusted (agent's own LLM). Not a bulletproof
adversarial sandbox.
"""

import asyncio

from . import _sandbox


class PythonEvalTool:
    name = "python_eval"
    description = (
        "Execute Python code for data work (pandas, numpy, scipy, sklearn, "
        "matplotlib, duckdb, openpyxl preloaded). Set result=... to return "
        "a value. Use ws_path('file.csv') for workspace files."
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
        if len(code.encode("utf-8")) > _sandbox.MAX_CODE_BYTES:
            return {
                "error": "code too long (max "
                         + str(_sandbox.MAX_CODE_BYTES) + " bytes)"
            }

        errors = _sandbox.validate(code)
        if errors:
            try:
                from .. import metrics as _m
                _m.incr("python_eval_rejected_total")
            except Exception:
                pass
            return {"error": "code rejected", "reasons": errors}

        try:
            from .. import metrics as _m
            _m.incr("python_eval_calls_total")
        except Exception:
            pass

        g = _sandbox.build_globals()
        timeout = _sandbox.DEFAULT_TIMEOUT

        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(_sandbox.exec_code, code, g),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            return {"error": "execution timed out (" + str(timeout) + "s)"}

        # Capture any open matplotlib figure as base64 PNG
        chart = _sandbox.capture_chart(g.get("plt"))
        if chart:
            result.update(chart)

        return result
