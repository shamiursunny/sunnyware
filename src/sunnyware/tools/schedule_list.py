# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""List recurring agent tasks (Part 81)."""


class ScheduleListTool:
    name = "schedule_list"
    description = (
        "List all dynamic schedules with their last run status, count, "
        "result preview, and error if any. Use to show what recurring "
        "tasks the agent has running."
    )
    parameters = {}

    async def run(self, args: dict) -> dict:
        from .. import dynamic_schedule as _ds
        return await _ds.list_all()
