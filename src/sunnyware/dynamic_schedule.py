# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Dynamic schedules — agent-prompt recurring tasks (Part 81).

On app startup, bootstrap() loads dynamic_schedules from Neon and
registers each one as a scheduler job. Each job runs its prompt via
the orchestrator, logs the result, and optionally emails the answer.
"""
import time
from typing import Optional
from . import state as app_state
from . import scheduler as _sched


_MAX_NAME_LEN = 100
_MAX_PROMPT_LEN = 2000
_MIN_INTERVAL = 60
_MAX_INTERVAL = 604800  # 1 week
_RUN_TIMEOUT = 90.0


def _validate(name, prompt, interval_seconds):
    name = (name or "").strip()
    prompt = (prompt or "").strip()
    if not name or len(name) > _MAX_NAME_LEN:
        return None, None, None, "name must be 1-" + str(_MAX_NAME_LEN) + " chars"
    if not prompt or len(prompt) > _MAX_PROMPT_LEN:
        return None, None, None, "prompt must be 1-" + str(_MAX_PROMPT_LEN) + " chars"
    try:
        iv = int(interval_seconds)
    except (TypeError, ValueError):
        return None, None, None, "interval_seconds must be an integer"
    if iv < _MIN_INTERVAL or iv > _MAX_INTERVAL:
        return None, None, None, (
            "interval_seconds must be " + str(_MIN_INTERVAL) + "-" + str(_MAX_INTERVAL)
        )
    return name, prompt, iv, None


def _make_handler(name: str, prompt: str, notify_email: str):
    async def _handler():
        from . import orchestrator as _orch
        from . import email_send as _em
        t0 = time.time()
        status = "ok"
        answer = ""
        err = None
        try:
            import asyncio as _aio
            result = await _aio.wait_for(_orch.run_agent(prompt), timeout=_RUN_TIMEOUT)
            answer = (result.get("answer") or "").strip()
            if not result.get("ok", False):
                status = "error"
                err = result.get("error") or "agent returned ok=False"
        except Exception as e:
            status = "error"
            err = type(e).__name__ + ": " + str(e)[:200]

        # Persist last run info
        pool = app_state.get_pool()
        if pool is not None:
            try:
                async with pool.acquire() as conn:
                    await conn.execute(
                        """UPDATE dynamic_schedules SET
                             last_run_at = NOW(),
                             last_status = $1,
                             last_result_preview = $2,
                             last_error = $3,
                             run_count = run_count + 1
                           WHERE name = $4""",
                        status, (answer or "")[:500], err, name,
                    )
            except Exception:
                pass

        # Optional email
        if notify_email and answer:
            try:
                if _em.is_configured():
                    subject = "[SCHEDULE] " + name
                    body = (
                        "Scheduled task: " + name + "\n"
                        "Prompt:         " + prompt[:300] + "\n"
                        "Status:         " + status + "\n"
                        "Latency:        " + str(int((time.time() - t0) * 1000)) + " ms\n\n"
                        "Result:\n" + answer[:2000]
                    )
                    await _em.send_email(
                        to=[notify_email], subject=subject, body=body,
                    )
            except Exception:
                pass

        return {"name": name, "status": status, "error": err}

    return _handler


async def add(name, prompt, interval_seconds, notify_email=""):
    name, prompt, iv, err = _validate(name, prompt, interval_seconds)
    if err:
        return {"error": err}

    pool = app_state.get_pool()
    if pool is None:
        return {"error": "database unavailable"}

    notify_email = (notify_email or "").strip()
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO dynamic_schedules
                   (name, prompt, interval_seconds, notify_email, enabled)
                   VALUES ($1, $2, $3, $4, TRUE)
                   ON CONFLICT (name) DO UPDATE SET
                     prompt = EXCLUDED.prompt,
                     interval_seconds = EXCLUDED.interval_seconds,
                     notify_email = EXCLUDED.notify_email,
                     enabled = TRUE""",
                name, prompt, iv, notify_email,
            )
    except Exception as e:
        return {"error": type(e).__name__ + ": " + str(e)[:200]}

    # Register with the running scheduler
    try:
        _sched.register_job(
            "dyn:" + name,
            interval_seconds=iv,
            handler=_make_handler(name, prompt, notify_email),
            description="dynamic: " + prompt[:80],
        )
    except Exception as e:
        return {"ok": True, "name": name, "warning": "registered in DB but scheduler reg failed: " + str(e)[:120]}

    return {"ok": True, "name": name, "interval_seconds": iv}


async def list_all():
    pool = app_state.get_pool()
    if pool is None:
        return {"error": "database unavailable"}
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT name, prompt, interval_seconds, notify_email, enabled,
                          last_run_at, last_status, last_result_preview,
                          last_error, run_count, created_at
                   FROM dynamic_schedules ORDER BY created_at DESC"""
            )
    except Exception as e:
        return {"error": type(e).__name__ + ": " + str(e)[:200]}

    items = []
    for r in rows:
        items.append({
            "name": r["name"],
            "prompt": r["prompt"],
            "interval_seconds": int(r["interval_seconds"]),
            "notify_email": r["notify_email"] or "",
            "enabled": bool(r["enabled"]),
            "last_run_at": r["last_run_at"].isoformat() if r["last_run_at"] else None,
            "last_status": r["last_status"],
            "last_result_preview": r["last_result_preview"],
            "last_error": r["last_error"],
            "run_count": int(r["run_count"]),
        })
    return {"count": len(items), "schedules": items}


async def delete(name):
    name = (name or "").strip()
    if not name:
        return {"error": "name is required"}
    pool = app_state.get_pool()
    if pool is None:
        return {"error": "database unavailable"}
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM dynamic_schedules WHERE name = $1", name,
            )
    except Exception as e:
        return {"error": type(e).__name__ + ": " + str(e)[:200]}

    # Also remove from running scheduler
    try:
        _sched._jobs.pop("dyn:" + name, None)
    except Exception:
        pass
    return {"ok": True, "name": name}


async def run_now(name):
    name = (name or "").strip()
    if not name:
        return {"error": "name is required"}
    pool = app_state.get_pool()
    if pool is None:
        return {"error": "database unavailable"}
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT name, prompt, notify_email FROM dynamic_schedules WHERE name = $1",
                name,
            )
    except Exception as e:
        return {"error": type(e).__name__ + ": " + str(e)[:200]}
    if row is None:
        return {"error": "schedule not found: " + name}

    handler = _make_handler(row["name"], row["prompt"], row["notify_email"] or "")
    try:
        return await handler()
    except Exception as e:
        return {"error": type(e).__name__ + ": " + str(e)[:200]}


async def bootstrap():
    """Load all enabled schedules from Neon and register with scheduler.
    Called from app lifespan after scheduler.start()."""
    pool = app_state.get_pool()
    if pool is None:
        try:
            await app_state.init_pool()
            pool = app_state.get_pool()
        except Exception:
            return {"ok": False, "error": "no db pool"}
    if pool is None:
        return {"ok": False, "error": "no db pool"}

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT name, prompt, interval_seconds, notify_email FROM dynamic_schedules WHERE enabled = TRUE"
            )
    except Exception as e:
        return {"ok": False, "error": type(e).__name__ + ": " + str(e)[:120]}

    registered = 0
    for r in rows:
        try:
            _sched.register_job(
                "dyn:" + r["name"],
                interval_seconds=int(r["interval_seconds"]),
                handler=_make_handler(r["name"], r["prompt"], r["notify_email"] or ""),
                description="dynamic: " + (r["prompt"] or "")[:80],
            )
            registered += 1
        except Exception:
            continue
    return {"ok": True, "registered": registered, "total": len(rows)}
