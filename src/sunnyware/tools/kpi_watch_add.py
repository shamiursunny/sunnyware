# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Register a KPI watch (Part 75)."""


class KpiWatchAddTool:
    name = "kpi_watch_add"
    description = (
        "Register or update a KPI watch. The system will periodically run "
        "your check_prompt, extract a number from the answer, and compare it "
        "to a threshold. Breaches are logged to Neon for later retrieval. "
        "Comparisons: lt, gt, le, ge, eq, ne. Use for 'alert me when X < Y'."
    )
    parameters = {
        "kpi_name": {"type": "string", "required": True,
                     "description": "Short unique name (e.g. 'daily_burn_rate')"},
        "check_prompt": {"type": "string", "required": True,
                         "description": "Prompt to run each check. Must produce a number."},
        "comparison": {"type": "string", "required": True,
                       "description": "lt | gt | le | ge | eq | ne"},
        "threshold_value": {"type": "number", "required": True,
                            "description": "Threshold to compare against"},
        "extract_pattern": {"type": "string", "required": False,
                            "description": "Optional regex to extract number (default: first number in answer)"},
        "interval_seconds": {"type": "integer", "required": False,
                             "description": "Check interval in seconds (60-604800, default 3600)"},
    }

    async def run(self, args: dict) -> dict:
        from .. import kpi_watch as _kw
        return await _kw.add_watch(
            kpi_name=args.get("kpi_name", ""),
            check_prompt=args.get("check_prompt", ""),
            comparison=args.get("comparison", ""),
            threshold_value=args.get("threshold_value", 0),
            extract_pattern=args.get("extract_pattern"),
            interval_seconds=args.get("interval_seconds") or 3600,
        )
