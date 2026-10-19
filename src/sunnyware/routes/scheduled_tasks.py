# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 221b: Scheduled tasks routes."""

import time
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from .. import scheduled_tasks_store as _sts

router = APIRouter(tags=["scheduled_tasks"])


def _admin_only(req: Request):
    from .. import auth as _auth
    key = req.headers.get("x-api-key") or ""
    if not key:
        authz = req.headers.get("authorization") or ""
        if authz.lower().startswith("bearer "):
            key = authz[7:].strip()
    if not _auth.auth_enabled():
        return None
    if not key or not _auth.is_valid_key(key):
        return JSONResponse({"error": "auth_required"}, status_code=401)
    if not _auth.has_role(_auth.role_for_key(key), "admin"):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return None


@router.get("/api/scheduled-tasks")
async def list_tasks(req: Request):
    d = _admin_only(req)
    if d: return d
    tasks = _sts.list_tasks()
    return {"count": len(tasks), "tasks": tasks}


@router.post("/api/scheduled-tasks")
async def create_task(req: Request):
    d = _admin_only(req)
    if d: return d
    try:
        body = await req.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    name = (body.get("name") or "").strip()
    prompt = (body.get("prompt") or "").strip()
    schedule = (body.get("schedule") or "daily").strip()
    user_email = (body.get("user_email") or "").strip()
    if not name:
        return JSONResponse({"error": "name required"}, status_code=400)
    if not prompt:
        return JSONResponse({"error": "prompt required"}, status_code=400)
    if schedule not in ("once", "hourly", "daily", "weekly", "monthly"):
        return JSONResponse({"error": "invalid schedule"}, status_code=400)
    task = _sts.create_task(name, prompt, schedule, user_email)
    return {"ok": True, "task": task}


@router.delete("/api/scheduled-tasks/{tid}")
async def delete_task(tid: str, req: Request):
    d = _admin_only(req)
    if d: return d
    return {"ok": _sts.delete_task(tid)}


@router.post("/api/scheduled-tasks/{tid}/toggle")
async def toggle_task(tid: str, req: Request):
    d = _admin_only(req)
    if d: return d
    return {"ok": _sts.toggle_task(tid)}


@router.post("/api/scheduled-tasks/{tid}/test-run")
async def test_run(tid: str, req: Request):
    d = _admin_only(req)
    if d: return d
    task = _sts.get_task(tid)
    if not task:
        return JSONResponse({"error": "task not found"}, status_code=404)
    try:
        _sts.record_run(tid, ok=True, output=f"[Test run] Prompt: {task['prompt'][:100]}")
        return {"ok": True, "message": "Test run recorded"}
    except Exception as e:
        _sts.record_run(tid, ok=False, error=str(e))
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/scheduled-tasks/runs")
async def list_runs(req: Request, task_id: str = "", limit: int = 100):
    d = _admin_only(req)
    if d: return d
    runs = _sts.list_runs(task_id=task_id, limit=min(limit, 500))
    return {"count": len(runs), "runs": runs}


@router.delete("/api/scheduled-tasks/runs/clear")
async def clear_runs(req: Request):
    d = _admin_only(req)
    if d: return d
    return {"ok": _sts.clear_runs()}
