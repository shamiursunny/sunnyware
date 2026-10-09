# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Simple async scheduler — cron-style background jobs."""

import asyncio
import os
import time


_jobs = {}
_task = None
_running = False


def _enabled() -> bool:
    v = (os.getenv("SUNNYWARE_SCHEDULE_ENABLED", "true") or "").lower()
    return v not in ("false", "0", "no", "off")


def _check_interval() -> int:
    try:
        return max(5, int(os.getenv("SUNNYWARE_SCHEDULE_CHECK_INTERVAL", "30") or 30))
    except Exception:
        return 30


def register_job(name, interval_seconds, handler, description=""):
    _jobs[name] = {
        "name": name,
        "interval_seconds": int(interval_seconds),
        "handler": handler,
        "description": description,
        "last_run": 0.0,
        "last_status": "never",
        "run_count": 0,
    }


def list_jobs():
    return [
        {
            "name": j["name"],
            "interval_seconds": j["interval_seconds"],
            "description": j["description"],
            "last_run": j["last_run"],
            "last_status": j["last_status"],
            "run_count": j["run_count"],
        }
        for j in _jobs.values()
    ]


async def _get_pool():
    try:
        from . import state as app_state
        pool = app_state.get_pool()
        if pool is None:
            try:
                await app_state.init_pool()
                pool = app_state.get_pool()
            except Exception:
                return None
        return pool
    except Exception:
        return None


async def _ensure_table(conn):
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_jobs (
            name TEXT PRIMARY KEY,
            last_run_at TIMESTAMPTZ,
            last_status TEXT,
            run_count BIGINT NOT NULL DEFAULT 0
        )
    """)


async def _load_state():
    pool = await _get_pool()
    if pool is None:
        return
    try:
        async with pool.acquire() as conn:
            await _ensure_table(conn)
            rows = await conn.fetch(
                "SELECT name, last_run_at, last_status, run_count FROM scheduled_jobs"
            )
        for r in rows:
            j = _jobs.get(r["name"])
            if j:
                if r["last_run_at"]:
                    j["last_run"] = r["last_run_at"].timestamp()
                j["last_status"] = r["last_status"] or "never"
                j["run_count"] = int(r["run_count"] or 0)
    except Exception:
        pass


async def _persist_state(job):
    pool = await _get_pool()
    if pool is None:
        return
    try:
        async with pool.acquire() as conn:
            await _ensure_table(conn)
            await conn.execute(
                """
                INSERT INTO scheduled_jobs (name, last_run_at, last_status, run_count)
                VALUES ($1, NOW(), $2, $3)
                ON CONFLICT (name) DO UPDATE
                    SET last_run_at = NOW(),
                        last_status = $2,
                        run_count = $3
                """,
                job["name"], job["last_status"], job["run_count"],
            )
    except Exception:
        pass


async def run_job(name, force=True):
    j = _jobs.get(name)
    if not j:
        return {"ok": False, "error": f"job not found: {name}"}
    t0 = time.time()
    try:
        result = await j["handler"]()
        status = "ok"
    except Exception as e:
        result = {"error": f"{type(e).__name__}: {e}"}
        status = "error"
    j["last_run"] = time.time()
    j["last_status"] = status
    j["run_count"] += 1
    await _persist_state(j)
    return {
        "ok": status == "ok",
        "job": name,
        "status": status,
        "duration_ms": int((time.time() - t0) * 1000),
        "result": result,
        "run_count": j["run_count"],
    }


def _should_run(job):
    return (time.time() - job["last_run"]) >= job["interval_seconds"]


async def _loop():
    global _running
    _running = True
    try:
        await _load_state()
    except Exception:
        pass
    check = _check_interval()
    while _running:
        try:
            for name, j in list(_jobs.items()):
                if _should_run(j):
                    await run_job(name, force=False)
        except Exception:
            pass
        try:
            await asyncio.sleep(check)
        except asyncio.CancelledError:
            break


def start():
    """Start scheduler loop. Only works inside a running event loop."""
    global _task
    if not _enabled():
        return False
    if _task is not None and not _task.done():
        return True
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return False
    try:
        _task = loop.create_task(_loop())
        return True
    except Exception:
        return False


def stop():
    global _task, _running
    _running = False
    if _task and not _task.done():
        _task.cancel()
    _task = None


def status():
    # Lazy start: if we are inside a running loop, start now
    if _enabled() and (_task is None or _task.done()):
        start()
    return {
        "enabled": _enabled(),
        "check_interval_seconds": _check_interval(),
        "jobs": list_jobs(),
        "running": _running,
    }
