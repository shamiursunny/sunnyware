# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Shared runtime state and helpers."""

import os
import time
from pathlib import Path

from .config import load_config
from .logging_config import configure_logging
from . import state as app_state


log = configure_logging()  # uses paths.logs_dir() internally


state = {
    "ready": False,
    "started_at": None,
    "config": None,
}


def init_state() -> None:
    """Initialize application state. Idempotent."""
    if state["ready"]:
        return
    log.info("sunnyware initializing")
    state["started_at"] = time.time()
    try:
        cfg = load_config()
        state["config"] = cfg
        log.info("Config loaded", agent_path=cfg.generic_agent_path)
        # Part 31: use persistent paths (falls back to ./data if no /data)
        from . import paths as _paths
        _paths.workspace()   # ensures workspace dir exists
        _paths.logs_dir()    # ensures logs dir exists
        state["ready"] = True

        # Part 26: register jobs + try starting scheduler (only if loop is running)
        try:
            from .jobs import register_all as _register_jobs
            from . import scheduler as _sched
            _register_jobs()
            _ok = _sched.start()
            try:
                log.info("scheduler_start_attempted", ok=_ok)
            except Exception:
                pass
        except Exception as _e:
            try:
                log.error("scheduler_start_failed", err=f"{type(_e).__name__}: {_e}")
            except Exception:
                pass
        log.info("sunnyware ready")
    except Exception as e:
        log.error("Startup failed", error=str(e), exc_info=True)
        state["ready"] = False


async def ensure_pool():
    """Lazy-init Neon pool. Idempotent."""
    if app_state.get_pool() is None:
        try:
            await app_state.init_pool()
        except Exception as e:
            log.error("Pool init failed", error=str(e))
