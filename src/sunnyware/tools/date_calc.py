# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Date arithmetic tool — deterministic, no LLM needed."""

from datetime import datetime, timedelta, timezone


def _parse_date(s: str):
    """Parse YYYY-MM-DD (returns naive datetime)."""
    return datetime.strptime(s.strip(), "%Y-%m-%d")


class DateCalcTool:
    name = "date_calc"
    description = (
        "Date arithmetic. Actions: 'add' (add days to a date), "
        "'diff' (days between two dates), 'weekday' (day of week for a date). "
        "Dates must be YYYY-MM-DD format."
    )
    parameters = {
        "action": {
            "type": "string",
            "description": "One of: add, diff, weekday",
            "required": True,
        },
        "date": {
            "type": "string",
            "description": "Primary date (YYYY-MM-DD)",
            "required": True,
        },
        "days": {
            "type": "integer",
            "description": "Days to add (positive or negative) — required for 'add'",
            "required": False,
        },
        "date2": {
            "type": "string",
            "description": "Second date for 'diff' (YYYY-MM-DD)",
            "required": False,
        },
    }

    async def run(self, args: dict) -> dict:
        action = str(args.get("action", "")).strip().lower()
        date_str = str(args.get("date", "")).strip()

        if not action:
            return {"error": "action is required"}
        if not date_str:
            return {"error": "date is required"}

        try:
            d1 = _parse_date(date_str)
        except Exception:
            return {"error": f"invalid date (expected YYYY-MM-DD): {date_str}"}

        if action == "add":
            try:
                days = int(args.get("days", 0))
            except Exception:
                return {"error": "days must be an integer"}
            if abs(days) > 100000:
                return {"error": "days out of range (max 100000)"}
            result = d1 + timedelta(days=days)
            return {
                "action": "add",
                "date": date_str,
                "days": days,
                "result": result.strftime("%Y-%m-%d"),
                "result_weekday": result.strftime("%A"),
            }

        if action == "diff":
            date2_str = str(args.get("date2", "")).strip()
            if not date2_str:
                return {"error": "date2 is required for 'diff'"}
            try:
                d2 = _parse_date(date2_str)
            except Exception:
                return {"error": f"invalid date2: {date2_str}"}
            delta = (d2 - d1).days
            return {
                "action": "diff",
                "date": date_str,
                "date2": date2_str,
                "days_between": delta,
                "absolute_days": abs(delta),
            }

        if action == "weekday":
            return {
                "action": "weekday",
                "date": date_str,
                "weekday": d1.strftime("%A"),
                "iso_weekday": d1.isoweekday(),
            }

        return {"error": f"unknown action: {action} (use: add, diff, weekday)"}
