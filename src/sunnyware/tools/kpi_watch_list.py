# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""List KPI watches (Part 75)."""


class KpiWatchListTool:
    name = "kpi_watch_list"
    description = (
        "List all KPI watches. Optionally include recent events per watch "
        "(breaches, errors). Use to show the user what KPIs are being "
        "monitored and their last status."
    )
    parameters = {
        "include_events": {"type": "boolean", "required": False,
                           "description": "Include recent events per watch (default false)"},
        "events_limit": {"type": "integer", "required": False,
                         "description": "How many events per watch (default 5, max 50)"},
    }

    async def run(self, args: dict) -> dict:
        from .. import kpi_watch as _kw
        try:
            limit = int(args.get("events_limit") or 5)
        except (TypeError, ValueError):
            limit = 5
        limit = max(1, min(limit, 50))
        return await _kw.list_watches(
            include_events=bool(args.get("include_events", False)),
            events_limit=limit,
        )
