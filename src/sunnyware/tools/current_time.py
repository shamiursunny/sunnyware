# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Current time tool — real utility."""

from datetime import datetime, timezone


class CurrentTimeTool:
    name = "current_time"
    description = "Get the current date and time in UTC."
    parameters = {}  # no args

    async def run(self, args: dict) -> dict:
        now = datetime.now(timezone.utc)
        return {
            "utc_iso": now.isoformat(),
            "utc_human": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "epoch_seconds": int(now.timestamp()),
            "day_of_week": now.strftime("%A"),
        }
