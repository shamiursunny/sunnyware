# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Evaluation suite endpoints."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .. import eval_runner


router = APIRouter()


@router.get("/api/eval/cases")
async def list_cases():
    """List available evaluation cases (metadata only — no execution)."""
    cases = eval_runner.case_summary()
    return {"count": len(cases), "cases": cases}


@router.post("/api/eval/run")
async def run_suite_endpoint(req: Request):
    """Run the full evaluation suite (or a subset by case_ids).

    Body (optional):
      {"case_ids": ["echo_1", "math_simple"]}
    Empty body runs all cases.
    """
    try:
        body = await req.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}

    case_ids = body.get("case_ids")
    if case_ids is not None and not isinstance(case_ids, list):
        return JSONResponse({"error": "case_ids must be a list"}, status_code=400)

    report = await eval_runner.run_suite(case_ids=case_ids)
    return report


@router.post("/api/eval/run/{case_id}")
async def run_single_case(case_id: str):
    """Run one evaluation case by ID."""
    cases = eval_runner.load_cases()
    match = next((c for c in cases if c.get("id") == case_id), None)
    if not match:
        return JSONResponse({"error": f"case not found: {case_id}"}, status_code=404)
    return await eval_runner.run_case(match)
