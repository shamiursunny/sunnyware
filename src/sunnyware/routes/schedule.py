# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Scheduler inspection + manual run endpoints."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from .. import scheduler


router = APIRouter()


@router.get("/api/schedule")
async def schedule_status():
    """Scheduler status + registered jobs."""
    return scheduler.status()


@router.post("/api/schedule/{job_name}/run")
async def schedule_run(job_name: str):
    """Manually trigger a job (bypasses interval)."""
    return await scheduler.run_job(job_name, force=True)
