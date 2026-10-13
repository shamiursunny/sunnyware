# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Batch prompt runner (Part 74).

Runs N prompts in parallel via asyncio.gather. Returns collected results
with per-prompt tool calls + latency. For FP&A workflows like 'variance
for each of 12 months' or 'KPI for each of 8 regions'.
"""
import asyncio
import time


_MAX_PROMPTS = 10
_MAX_PROMPT_CHARS = 4000
_PER_PROMPT_TIMEOUT = 90.0


class ReportBatchTool:
    name = "report_batch"
    description = (
        "Run multiple prompts in parallel and return collected results. "
        "Useful for FP&A workflows: 'variance for each month', 'KPI for "
        "each region', 'summarize each document section'. Each result "
        "includes the answer, tool calls made, and latency. Max 10 "
        "prompts per call, 90s per prompt."
    )
    parameters = {
        "prompts": {
            "type": "array",
            "description": "Array of prompt strings (max 10)",
            "required": True,
        },
        "parallel": {
            "type": "boolean",
            "description": "Run in parallel (default true)",
            "required": False,
        },
    }

    async def run(self, args: dict) -> dict:
        prompts = args.get("prompts")
        if not isinstance(prompts, list) or not prompts:
            return {"error": "prompts must be a non-empty array"}
        if len(prompts) > _MAX_PROMPTS:
            return {"error": f"too many prompts (max {_MAX_PROMPTS})"}
        cleaned = []
        for p in prompts:
            if not isinstance(p, str) or not p.strip():
                return {"error": "each prompt must be a non-empty string"}
            if len(p) > _MAX_PROMPT_CHARS:
                return {"error": f"prompt too long (max {_MAX_PROMPT_CHARS} chars)"}
            cleaned.append(p.strip())

        parallel = bool(args.get("parallel", True))

        try:
            from .. import orchestrator as _orch
        except Exception as e:
            return {"error": "orchestrator import failed: " + type(e).__name__ + ": " + str(e)}

        async def run_one(idx, prompt):
            t0 = time.time()
            try:
                result = await asyncio.wait_for(
                    _orch.run_agent(prompt),
                    timeout=_PER_PROMPT_TIMEOUT,
                )
                return {
                    "index": idx,
                    "prompt": prompt,
                    "ok": bool(result.get("ok", False)),
                    "answer": result.get("answer", "") or "",
                    "error": result.get("error"),
                    "steps_count": len(result.get("steps", []) or []),
                    "tools_used": [s.get("tool") for s in (result.get("steps") or []) if s.get("tool")],
                    "provider": result.get("provider"),
                    "iterations": result.get("iterations", 0),
                    "latency_ms": int((time.time() - t0) * 1000),
                }
            except asyncio.TimeoutError:
                return {
                    "index": idx, "prompt": prompt, "ok": False,
                    "answer": "", "error": f"timeout after {_PER_PROMPT_TIMEOUT}s",
                    "steps_count": 0, "tools_used": [],
                    "latency_ms": int((time.time() - t0) * 1000),
                }
            except Exception as e:
                return {
                    "index": idx, "prompt": prompt, "ok": False,
                    "answer": "", "error": type(e).__name__ + ": " + str(e),
                    "steps_count": 0, "tools_used": [],
                    "latency_ms": int((time.time() - t0) * 1000),
                }

        t_start = time.time()
        if parallel:
            results = await asyncio.gather(*[run_one(i, p) for i, p in enumerate(cleaned)])
            results = list(results)
        else:
            results = []
            for i, p in enumerate(cleaned):
                results.append(await run_one(i, p))

        total_ms = int((time.time() - t_start) * 1000)
        ok_count = sum(1 for r in results if r.get("ok"))

        return {
            "count": len(cleaned),
            "parallel": parallel,
            "ok_count": ok_count,
            "fail_count": len(cleaned) - ok_count,
            "total_latency_ms": total_ms,
            "avg_latency_ms": total_ms // max(1, len(cleaned)),
            "results": results,
        }
