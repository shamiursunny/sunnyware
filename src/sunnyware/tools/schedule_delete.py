# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Delete a recurring agent task (Part 81)."""


class ScheduleDeleteTool:
    name = "schedule_delete"
    description = (
        "Delete a dynamic schedule by name. Removes it from Neon and from "
        "the running scheduler immediately."
    )
    parameters = {
        "name": {"type": "string", "required": True,
                 "description": "Schedule name to delete"},
    }

    async def run(self, args: dict) -> dict:
        from .. import dynamic_schedule as _ds
        return await _ds.delete(args.get("name", ""))
