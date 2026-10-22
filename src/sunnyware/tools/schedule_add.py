# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Register a recurring agent task (Part 81)."""


class ScheduleAddTool:
    name = "schedule_add"
    description = "Schedule a recurring task at a fixed interval. Triggers: schedule task, run every, set reminder, recurring job. Input: name and interval hours. Returns schedule ID."."
    )
    parameters = {
        "name": {"type": "string", "required": True,
                 "description": "Unique short name (e.g. 'weekly_fpa_summary')"},
        "prompt": {"type": "string", "required": True,
                   "description": "Agent prompt to run each interval"},
        "interval_seconds": {"type": "integer", "required": True,
                             "description": "Seconds between runs (60-604800)"},
        "notify_email": {"type": "string", "required": False,
                         "description": "Email to send results to (optional)"},
    }

    async def run(self, args: dict) -> dict:
        from .. import dynamic_schedule as _ds
        return await _ds.add(
            name=args.get("name", ""),
            prompt=args.get("prompt", ""),
            interval_seconds=args.get("interval_seconds", 0),
            notify_email=args.get("notify_email", ""),
        )
