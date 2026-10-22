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
import multiprocessing as mp

from . import _sandbox




def _worker_proc(code, q):
    try:
        import sys
        g = _sandbox.build_globals()
        res = _sandbox.exec_code(code, g)
        
        # Add chart captures in the subprocess
        chart = _sandbox.capture_chart(g.get("plt"))
        if chart: res.update(chart)
        try:
            pl_cap = _sandbox.capture_plotly(g)
            if pl_cap: res.update(pl_cap)
        except Exception:
            pass

        q.put(res)
    except Exception as e:
        q.put({"ok": False, "error": str(e)})

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
        },
        "save_as": {
            "type": "string",
            "description": "Optional script name. On success, saves the code into the script registry for reuse.",
            "required": False,
        },
        "description": {
            "type": "string",
            "description": "Optional description stored alongside a saved script.",
            "required": False,
        },
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

        timeout = _sandbox.DEFAULT_TIMEOUT
        ctx = mp.get_context("spawn")
        q = ctx.Queue()
        p = ctx.Process(target=_worker_proc, args=(code, q))
        
        p.start()
        p.join(timeout)
        
        if p.is_alive():
            p.terminate()
            p.join()
            return {"error": "execution timed out (" + str(timeout) + "s) and was killed"}
            
        try:
            result = q.get_nowait()
        except Exception:
            return {"error": "process failed without output"}

        # Part 120: optional save-as-script (best-effort, never fatal)
        save_as = str(args.get("save_as", "")).strip()
        if save_as and not result.get("error"):
            try:
                from .script_registry import save_script_internal
                _meta120 = save_script_internal(
                    save_as, code, args.get("description") or ""
                )
                result["_saved_as"] = _meta120
            except Exception as e:
                result["_save_error"] = type(e).__name__ + ": " + str(e)

        return result
