# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Current time tool — real utility."""

from datetime import datetime, timezone


class CurrentTimeTool:
    name = "current_time"
    description = "Get the current time or clock for a specific location or timezone (e.g., Tokyo, London, UTC). Triggers: time, clock, current time, what time is it. Returns the current timestamp."
    parameters = {}  # no args

    async def run(self, args: dict) -> dict:
        now = datetime.now(timezone.utc)
        return {
            "utc_iso": now.isoformat(),
            "utc_human": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "epoch_seconds": int(now.timestamp()),
            "day_of_week": now.strftime("%A"),
        }
