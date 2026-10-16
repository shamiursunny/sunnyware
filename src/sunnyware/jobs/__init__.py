# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Built-in job registrations."""

import os

from .. import scheduler
from . import cleanup, heartbeat, evals


def register_all():
    scheduler.register_job(
        "heartbeat",
        interval_seconds=300,
        handler=heartbeat.run,
        description="Periodic heartbeat log — proves scheduler is alive",
    )
    # Part 137c: scheduled eval suite (opt-in via env var)
    try:
        _ivl = float(os.getenv("SUNNYWARE_EVAL_INTERVAL_HOURS", "0") or "0")
    except Exception:
        _ivl = 0.0
    if _ivl > 0:
        scheduler.register_job(
            "evals_suite",
            interval_seconds=int(_ivl * 3600),
            handler=evals.run,
            description=f"Run eval suite every {_ivl}h (Part 137c)",
        )
    scheduler.register_job(
        "session_cleanup",
        interval_seconds=3600,
        handler=cleanup.run,
        description="Delete sessions older than SUNNYWARE_SESSION_TTL_DAYS (default 30)",
    )
