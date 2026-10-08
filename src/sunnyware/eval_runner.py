# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Agent evaluation runner — ground-truth test set scoring."""

import json
import time
from pathlib import Path
from typing import Optional

from . import orchestrator


_CASES_CACHE = None


def _cases_path() -> Path:
    # Try repo-root/eval/cases.json
    here = Path(__file__).resolve()
    # src/sunnyware/eval_runner.py → ../../.. → repo root
    root = here.parent.parent.parent
    return root / "eval" / "cases.json"


def load_cases(reload: bool = False) -> list:
    global _CASES_CACHE
    if _CASES_CACHE is not None and not reload:
        return _CASES_CACHE
    path = _cases_path()
    if not path.exists():
        _CASES_CACHE = []
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        _CASES_CACHE = data if isinstance(data, list) else []
    except Exception:
        _CASES_CACHE = []
    return _CASES_CACHE


def _check_expectations(case: dict, answer: str, steps: list, error: Optional[str]) -> dict:
    """Return {passed: bool, reasons: [str], failures: [str]}."""
    reasons = []
    failures = []

    if error:
        return {"passed": False, "reasons": reasons, "failures": [f"error: {error}"]}

    answer_lc = (answer or "").lower()

    # expect_contains — all must appear
    exp_all = case.get("expect_contains") or []
    for kw in exp_all:
        if str(kw).lower() in answer_lc:
            reasons.append(f"contains '{kw}'")
        else:
            failures.append(f"missing '{kw}'")

    # expect_any — at least one
    exp_any = case.get("expect_any") or []
    if exp_any:
        found = [kw for kw in exp_any if str(kw).lower() in answer_lc]
        if found:
            reasons.append(f"any-of matched: {found}")
        else:
            failures.append(f"none of {exp_any} present")

    # expect_tool_called — tool with that name appears in steps
    tool = case.get("expect_tool_called")
    if tool:
        called = [s.get("tool") for s in (steps or []) if isinstance(s, dict)]
        if tool in called:
            reasons.append(f"tool '{tool}' called")
        else:
            failures.append(f"tool '{tool}' not called (saw: {called})")

    # expect_no_tools
    if case.get("expect_no_tools"):
        if not steps:
            reasons.append("no tools called (as required)")
        else:
            failures.append(f"expected no tools but got {len(steps)}")

    passed = not failures
    return {"passed": passed, "reasons": reasons, "failures": failures}


async def run_case(case: dict) -> dict:
    """Run one case, return scored result."""
    cid = case.get("id", "unnamed")
    t0 = time.time()
    try:
        result = await orchestrator.run_agent(case.get("input", ""))
    except Exception as e:
        return {
            "id": cid,
            "passed": False,
            "error": f"{type(e).__name__}: {e}",
            "latency_ms": int((time.time() - t0) * 1000),
        }
    latency_ms = int((time.time() - t0) * 1000)

    answer = result.get("answer", "") if result.get("ok") else ""
    steps = result.get("steps", []) or []
    error = None if result.get("ok") else result.get("error", "agent failed")

    scoring = _check_expectations(case, answer, steps, error)

    return {
        "id": cid,
        "passed": scoring["passed"],
        "reasons": scoring["reasons"],
        "failures": scoring["failures"],
        "answer_snippet": (answer or "")[:200],
        "steps_count": len(steps),
        "iterations": result.get("iterations", 0),
        "latency_ms": latency_ms,
        "tags": case.get("tags", []),
    }


async def run_suite(case_ids: Optional[list] = None) -> dict:
    """Run all cases (or a subset by id). Return summary report."""
    all_cases = load_cases()
    if case_ids:
        want = set(case_ids)
        all_cases = [c for c in all_cases if c.get("id") in want]

    if not all_cases:
        return {
            "total": 0, "passed": 0, "failed": 0,
            "score": 0.0, "results": [], "error": "no cases",
        }

    t0 = time.time()
    results = []
    for c in all_cases:
        results.append(await run_case(c))
    suite_ms = int((time.time() - t0) * 1000)

    passed = sum(1 for r in results if r.get("passed"))
    total = len(results)
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "score": round(passed / total, 3) if total else 0.0,
        "suite_latency_ms": suite_ms,
        "results": results,
    }


def case_summary() -> list:
    """Lightweight view of loaded cases (no execution)."""
    return [
        {
            "id": c.get("id"),
            "input": c.get("input", "")[:100],
            "tags": c.get("tags", []),
        }
        for c in load_cases()
    ]
