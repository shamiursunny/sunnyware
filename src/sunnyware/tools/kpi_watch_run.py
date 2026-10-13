# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Run KPI watches (Part 75)."""


class KpiWatchRunTool:
    name = "kpi_watch_run"
    description = (
        "Run all enabled KPI watches right now. Each watch runs its "
        "check_prompt, extracts a number, compares to threshold, and logs "
        "breaches/errors to Neon. Returns per-watch status. Use to force "
        "an immediate check instead of waiting for the schedule."
    )
    parameters = {
        "enabled_only": {"type": "boolean", "required": False,
                         "description": "Only run enabled watches (default true)"},
    }

    async def run(self, args: dict) -> dict:
        from .. import kpi_watch as _kw
        return await _kw.run_all(
            enabled_only=bool(args.get("enabled_only", True))
        )
