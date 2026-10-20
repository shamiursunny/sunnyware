# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 221b: Scheduled task management."""

import json
import os
import secrets
import time
from pathlib import Path
from typing import Optional

TASKS_FILE = "scheduled_tasks.json"
RUNS_FILE = "scheduled_task_runs.json"


def _base() -> Path:
    data = Path("/data")
    if data.exists() and os.access(str(data), os.W_OK):
        return data
    return Path("data")


def _load(name: str) -> dict:
    p = _base() / name
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(name: str, data: dict) -> bool:
    p = _base() / name
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(p)
        return True
    except Exception:
        return False


def create_task(name: str, prompt: str, schedule: str, user_email: str = "") -> dict:
    """schedule: 'once', 'hourly', 'daily', 'weekly', 'monthly'"""
    tasks = _load(TASKS_FILE)
    tid = "task_" + secrets.token_hex(6)
    entry = {
        "id": tid,
        "name": (name or "Untitled task").strip()[:100],
        "prompt": (prompt or "").strip()[:4000],
        "schedule": schedule or "daily",
        "user_email": (user_email or "").lower().strip(),
        "enabled": True,
        "created_at": time.time(),
        "last_run": None,
        "next_run": time.time() + 60,  # first run 1 min after creation
        "run_count": 0,
        "fail_count": 0,
    }
    tasks[tid] = entry
    _save(TASKS_FILE, tasks)
    return entry


def list_tasks() -> list:
    tasks = _load(TASKS_FILE)
    return sorted(tasks.values(), key=lambda x: x.get("created_at", 0), reverse=True)


def get_task(tid: str) -> Optional[dict]:
    tasks = _load(TASKS_FILE)
    return tasks.get(tid)


def delete_task(tid: str) -> bool:
    tasks = _load(TASKS_FILE)
    if tid not in tasks:
        return False
    del tasks[tid]
    _save(TASKS_FILE, tasks)
    return True


def toggle_task(tid: str) -> bool:
    tasks = _load(TASKS_FILE)
    if tid not in tasks:
        return False
    tasks[tid]["enabled"] = not tasks[tid].get("enabled", True)
    _save(TASKS_FILE, tasks)
    return True


def _next_run_ts(schedule: str) -> Optional[float]:
    now = time.time()
    if schedule == "once":
        return None
    if schedule == "hourly":
        return now + 3600
    if schedule == "daily":
        return now + 86400
    if schedule == "weekly":
        return now + 86400 * 7
    if schedule == "monthly":
        return now + 86400 * 30
    return now + 86400  # default daily


def record_run(tid: str, ok: bool, output: str = "", error: str = "") -> dict:
    tasks = _load(TASKS_FILE)
    if tid not in tasks:
        return {"ok": False, "error": "task not found"}
    now = time.time()
    tasks[tid]["last_run"] = now
    tasks[tid]["next_run"] = _next_run_ts(tasks[tid].get("schedule", "daily"))
    tasks[tid]["run_count"] = int(tasks[tid].get("run_count", 0)) + 1
    if not ok:
        tasks[tid]["fail_count"] = int(tasks[tid].get("fail_count", 0)) + 1
    _save(TASKS_FILE, tasks)

    runs = _load(RUNS_FILE)
    rid = "run_" + secrets.token_hex(6)
    runs[rid] = {
        "id": rid,
        "task_id": tid,
        "ts": now,
        "ok": ok,
        "output": (output or "")[:2000],
        "error": (error or "")[:500],
    }
    if len(runs) > 5000:
        items = sorted(runs.items(), key=lambda kv: kv[1].get("ts", 0))
        for k, _ in items[:-5000]:
            del runs[k]
    _save(RUNS_FILE, runs)
    return {"ok": True, "run_id": rid}


def list_runs(task_id: str = "", limit: int = 100) -> list:
    runs = _load(RUNS_FILE)
    items = list(runs.values())
    if task_id:
        items = [r for r in items if r.get("task_id") == task_id]
    items.sort(key=lambda x: x.get("ts", 0), reverse=True)
    return items[:limit]


def clear_runs() -> bool:
    return _save(RUNS_FILE, {})
