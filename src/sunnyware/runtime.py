# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Shared runtime state and helpers."""

import os
import time
from pathlib import Path

from .config import load_config
from .logging_config import configure_logging
from . import state as app_state


log = configure_logging("/data/logs" if os.path.exists("/data") else "./data/logs")


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
        data_dir = Path("./data")
        (data_dir / "workspace").mkdir(parents=True, exist_ok=True)
        (data_dir / "logs").mkdir(parents=True, exist_ok=True)
        state["ready"] = True
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
