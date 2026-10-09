# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Built-in job registrations."""

from .. import scheduler
from . import cleanup, heartbeat


def register_all():
    scheduler.register_job(
        "heartbeat",
        interval_seconds=300,
        handler=heartbeat.run,
        description="Periodic heartbeat log — proves scheduler is alive",
    )
    scheduler.register_job(
        "session_cleanup",
        interval_seconds=3600,
        handler=cleanup.run,
        description="Delete sessions older than SUNNYWARE_SESSION_TTL_DAYS (default 30)",
    )
