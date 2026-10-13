# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Run a dynamic schedule immediately (Part 81)."""


class ScheduleRunNowTool:
    name = "schedule_run_now"
    description = (
        "Trigger a dynamic schedule to run immediately, regardless of "
        "interval. Updates last_run info. Useful for testing or forcing "
        "an on-demand execution."
    )
    parameters = {
        "name": {"type": "string", "required": True,
                 "description": "Schedule name to run"},
    }

    async def run(self, args: dict) -> dict:
        from .. import dynamic_schedule as _ds
        return await _ds.run_now(args.get("name", ""))
