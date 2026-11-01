# -*- coding: utf-8 -*-
"""
Part 496: Direct keyword_route tests for tools that are flaky via /api/agent/stream.
Deterministic and fast.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sunnyware.keyword_router import keyword_route


def test_sql_sandbox_drop_routing():
    """sql_sandbox_drop extracts name from prompt."""
    result = keyword_route("drop sandbox test")
    assert result == {"tool": "sql_sandbox_drop", "args": {"name": "test"}}


def test_api_call_routing():
    """api_call extracts URL and method from prompt."""
    result = keyword_route("make a GET request to https://api.example.com/data")
    assert result is not None
    assert result["tool"] == "api_call"
    assert result["args"] == {"url": "https://api.example.com/data", "method": "GET"}


def test_api_call_post_routing():
    """api_call detects POST method."""
    result = keyword_route("make a POST request to https://api.example.com/data")
    assert result is not None
    assert result["tool"] == "api_call"
    assert result["args"]["method"] == "POST"

def test_date_calc_add_days_routing():
    """'add N days to date' routes to date_calc."""
    result = keyword_route("add 5 days to 2026-11-01")
    assert result == {"tool": "date_calc", "args": {"action": "add", "date": "2026-11-01", "days": 5}}


def test_date_calc_subtract_days_routing():
    """'subtract N days from date' routes to date_calc with negative days."""
    result = keyword_route("subtract 3 days from 2026-11-01")
    assert result == {"tool": "date_calc", "args": {"action": "add", "date": "2026-11-01", "days": -3}}


def test_date_calc_diff_routing():
    """'days between date1 and date2' routes to date_calc diff."""
    result = keyword_route("days between 2026-11-01 and 2026-12-01")
    assert result == {"tool": "date_calc", "args": {"action": "diff", "date": "2026-11-01", "date2": "2026-12-01"}}


def test_date_calc_weekday_routing():
    """'what day of the week is date' routes to date_calc weekday."""
    result = keyword_route("what day of the week is 2026-11-01")
    assert result == {"tool": "date_calc", "args": {"action": "weekday", "date": "2026-11-01"}}

def test_schedule_delete_routing():
    """'delete scheduled task X' routes to schedule_delete."""
    result = keyword_route("delete scheduled task my_task")
    assert result == {"tool": "schedule_delete", "args": {"name": "my_task"}}


def test_schedule_run_now_routing():
    """'run schedule X now' routes to schedule_run_now."""
    result = keyword_route("run schedule my_task now")
    assert result == {"tool": "schedule_run_now", "args": {"name": "my_task"}}

def test_webhook_delete_routing():
    """'delete webhook X' routes to webhook_delete."""
    result = keyword_route("delete webhook wh_12345")
    assert result == {"tool": "webhook_delete", "args": {"token": "wh_12345"}}


def test_webhook_events_routing():
    """'webhook events for X' routes to webhook_events."""
    result = keyword_route("webhook events for wh_12345")
    assert result == {"tool": "webhook_events", "args": {"token": "wh_12345"}}
