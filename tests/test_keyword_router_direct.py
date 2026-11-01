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

def test_kpi_watch_add_routing_lt():
    """'alert me when X < Y' routes to kpi_watch_add with lt."""
    result = keyword_route("alert me when daily_burn_rate < 1000")
    assert result["tool"] == "kpi_watch_add"
    assert result["args"] == {
        "kpi_name": "daily_burn_rate",
        "check_prompt": "What is the current daily_burn_rate?",
        "comparison": "lt",
        "threshold_value": 1000.0,
    }


def test_kpi_watch_add_routing_gt():
    """'add kpi watch X > Y' routes to kpi_watch_add with gt."""
    result = keyword_route("add kpi watch revenue > 50000")
    assert result["tool"] == "kpi_watch_add"
    assert result["args"]["comparison"] == "gt"
    assert result["args"]["threshold_value"] == 50000.0


def test_kpi_watch_add_routing_ge():
    """'watch kpi X >= Y' routes to kpi_watch_add with ge."""
    result = keyword_route("watch kpi user_count >= 100")
    assert result["tool"] == "kpi_watch_add"
    assert result["args"]["comparison"] == "ge"
    assert result["args"]["threshold_value"] == 100.0

def test_email_list_sent_default_routing():
    """'list sent emails' routes to email_list_sent with empty args."""
    result = keyword_route("list sent emails")
    assert result == {"tool": "email_list_sent", "args": {}}


def test_email_list_sent_with_limit_routing():
    """'show recent 10 sent emails' routes to email_list_sent with limit=10."""
    result = keyword_route("show recent 10 sent emails")
    assert result == {"tool": "email_list_sent", "args": {"limit": 10}}


def test_email_list_sent_what_routing():
    """'what emails have i sent' routes to email_list_sent."""
    result = keyword_route("what emails have i sent")
    assert result == {"tool": "email_list_sent", "args": {}}

def test_delete_file_routing():
    """'delete file X' routes to delete_file."""
    result = keyword_route("delete file report.txt")
    assert result == {"tool": "delete_file", "args": {"path": "report.txt"}}


def test_remove_file_routing():
    """'remove file X' routes to delete_file."""
    result = keyword_route("remove file data.csv")
    assert result == {"tool": "delete_file", "args": {"path": "data.csv"}}

def test_recall_history_routing():
    """'what did we discuss about X' routes to recall_history."""
    result = keyword_route("what did we discuss about ai")
    assert result == {"tool": "recall_history", "args": {"query": "ai"}}


def test_memory_search_routing():
    """'search memory for X' routes to memory_search."""
    result = keyword_route("search memory for python")
    assert result == {"tool": "memory_search", "args": {"query": "python"}}


def test_recall_history_conversation_routing():
    """'recall our last conversation about X' routes to recall_history."""
    result = keyword_route("recall our last conversation about weather")
    assert result == {"tool": "recall_history", "args": {"query": "weather"}}


def test_recall_history_discussion_routing():
    """'recall our last discussion about X' routes to recall_history."""
    result = keyword_route("recall our last discussion about taxes")
    assert result == {"tool": "recall_history", "args": {"query": "taxes"}}

def test_workspace_snapshot_routing():
    """'workspace snapshot' routes to workspace_snapshot."""
    result = keyword_route("workspace snapshot")
    assert result == {"tool": "workspace_snapshot", "args": {}}


def test_zip_workspace_routing():
    """'zip the workspace' routes to workspace_snapshot."""
    result = keyword_route("zip the workspace")
    assert result == {"tool": "workspace_snapshot", "args": {}}


def test_archive_workspace_routing():
    """'archive the workspace' routes to workspace_snapshot."""
    result = keyword_route("archive the workspace")
    assert result == {"tool": "workspace_snapshot", "args": {}}


def test_workspace_snapshot_subpath_routing():
    """'snapshot of the workspace for X' extracts subpath."""
    result = keyword_route("snapshot of the workspace for /data/reports")
    assert result == {"tool": "workspace_snapshot", "args": {"subpath": "/data/reports"}}

def test_citation_lookup_routing():
    """'look up citation X' routes to citation_lookup."""
    result = keyword_route("look up citation 42 U.S.C. 1983")
    assert result == {"tool": "citation_lookup", "args": {"query": "42 U.S.C. 1983"}}


def test_clause_extractor_list_types_routing():
    """'list clause types' routes to clause_extractor."""
    result = keyword_route("list clause types")
    assert result == {"tool": "clause_extractor", "args": {"action": "list_types"}}


def test_legal_citation_check_verify_one_routing():
    """'verify citation 576 U.S. 644' routes to legal_citation_check."""
    result = keyword_route("verify citation 576 U.S. 644")
    assert result == {
        "tool": "legal_citation_check",
        "args": {
            "action": "verify_one",
            "volume": "576",
            "reporter": "U.S.",
            "page": "644",
        }
    }

def test_risk_metrics_summary_routing():
    result = keyword_route("calculate risk metrics for returns [0.01, -0.02, 0.03]")
    assert result == {"tool": "risk_metrics", "args": {"action": "summary", "returns": "[0.01, -0.02, 0.03]"}}

def test_risk_metrics_sharpe_routing():
    result = keyword_route("calculate sharpe ratio for returns [0.01, -0.02, 0.03]")
    assert result == {"tool": "risk_metrics", "args": {"action": "sharpe", "returns": "[0.01, -0.02, 0.03]"}}

def test_forecast_arima_routing():
    result = keyword_route("forecast arima for [1, 2, 3, 4, 5]")
    assert result == {"tool": "forecast_arima", "args": {"data": [1, 2, 3, 4, 5], "periods": 6}}

def test_forecast_arima_periods_routing():
    result = keyword_route("forecast 10 periods for [1, 2, 3, 4, 5]")
    assert result == {"tool": "forecast_arima", "args": {"data": [1, 2, 3, 4, 5], "periods": 10}}

def test_auditor_full_spec_routing():
    result = keyword_route("auditor full spec")
    assert result == {"tool": "auditor_full_spec", "args": {}}

def test_insurance_data_states_routing():
    result = keyword_route("insurance data states")
    assert result == {"tool": "insurance_data", "args": {"action": "states"}}

def test_insurance_data_discover_routing():
    result = keyword_route("discover insurance data for complaints")
    assert result == {"tool": "insurance_data", "args": {"action": "discover", "query": "for complaints"}}

def test_insurance_research_filings_routing():
    result = keyword_route("insurance research filings IBNR")
    assert result == {"tool": "insurance_research", "args": {"action": "search_filings", "query": "IBNR"}}

def test_insurance_fred_search_routing():
    result = keyword_route("insurance fred search premium")
    assert result == {"tool": "insurance_research", "args": {"action": "fred_search", "query": "premium"}}

def test_insurance_fred_series_routing():
    result = keyword_route("insurance fred series CCSA")
    assert result == {"tool": "insurance_research", "args": {"action": "fred_series", "series_id": "CCSA"}}
