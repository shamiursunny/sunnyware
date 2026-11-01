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

def test_finnhub_quote_routing():
    result = keyword_route("get stock quote for AAPL")
    assert result == {"tool": "finnhub_quote", "args": {"action": "quote", "symbol": "AAPL"}}

def test_fmp_income_routing():
    result = keyword_route("get income statement for MSFT")
    assert result == {"tool": "fmp_fundamentals", "args": {"action": "income", "ticker": "MSFT"}}

def test_fmp_balance_routing():
    result = keyword_route("get balance sheet for AAPL")
    assert result == {"tool": "fmp_fundamentals", "args": {"action": "balance", "ticker": "AAPL"}}

def test_fred_series_routing():
    result = keyword_route("get economic data for GDP")
    assert result == {"tool": "fred_economic", "args": {"action": "series", "series_id": "GDP"}}

def test_fred_search_routing():
    result = keyword_route("search economic data for inflation")
    assert result == {"tool": "fred_economic", "args": {"action": "search", "query": "inflation"}}

def test_fred_popular_routing():
    result = keyword_route("list popular economic indicators")
    assert result == {"tool": "fred_economic", "args": {"action": "popular"}}

def test_tiingo_eod_routing():
    result = keyword_route("historical prices for AAPL")
    assert result == {"tool": "tiingo_prices", "args": {"action": "eod", "ticker": "AAPL"}}

def test_tiingo_intraday_routing():
    result = keyword_route("intraday prices for MSFT")
    assert result == {"tool": "tiingo_prices", "args": {"action": "intraday", "ticker": "MSFT"}}

def test_twelvedata_quote_routing():
    result = keyword_route("market quote for BTC/USD")
    assert result == {"tool": "twelvedata_prices", "args": {"action": "quote", "symbol": "BTC/USD"}}

def test_twelvedata_time_series_routing():
    result = keyword_route("time series for AAPL")
    assert result == {"tool": "twelvedata_prices", "args": {"action": "time_series", "symbol": "AAPL"}}

def test_twelvedata_rsi_routing():
    result = keyword_route("rsi for AAPL")
    assert result == {"tool": "twelvedata_prices", "args": {"action": "rsi", "symbol": "AAPL"}}

def test_marketaux_news_routing():
    result = keyword_route("news for AAPL,MSFT")
    assert result == {"tool": "marketaux_news", "args": {"symbols": "AAPL,MSFT"}}

def test_edgar_fundamentals_routing():
    result = keyword_route("get sec financials for AAPL")
    assert result == {"tool": "edgar_fundamentals", "args": {"ticker": "AAPL", "statement": "all"}}

def test_govcon_award_search_routing():
    result = keyword_route("search government contracts for defense")
    assert result == {"tool": "govcon_data", "args": {"action": "award_search", "keyword": "defense"}}

def test_govcon_recipient_search_routing():
    result = keyword_route("search government recipients for Acme")
    assert result == {"tool": "govcon_data", "args": {"action": "recipient_search", "keyword": "Acme"}}

def test_eulerpool_profile_routing():
    result = keyword_route("eulerpool profile for AAPL")
    assert result == {"tool": "eulerpool_data", "args": {"action": "profile", "identifier": "AAPL"}}

def test_mkdir_routing():
    result = keyword_route("create directory reports")
    assert result == {"tool": "mkdir", "args": {"path": "reports"}}

def test_financial_metrics_routing():
    result = keyword_route("financial metrics for [0.01, -0.02, 0.03]")
    assert result == {"tool": "financial_metrics", "args": {"returns": "[0.01, -0.02, 0.03]"}}

def test_recall_history_with_days():
    result = keyword_route("what did we discuss about ai last 30 days")
    assert result == {"tool": "recall_history", "args": {"query": "ai", "days": 30}}

def test_recall_history_with_days_and_limit():
    result = keyword_route("what did we discuss about ai last 30 days limit 5")
    assert result == {"tool": "recall_history", "args": {"query": "ai", "days": 30, "limit": 5}}

def test_fmp_dcf_routing():
    result = keyword_route("get dcf for AAPL")
    assert result == {"tool": "fmp_fundamentals", "args": {"action": "dcf", "ticker": "AAPL"}}

def test_fmp_ratios_routing():
    result = keyword_route("get financial ratios for MSFT")
    assert result == {"tool": "fmp_fundamentals", "args": {"action": "ratios", "ticker": "MSFT"}}

def test_memory_search_with_limit():
    result = keyword_route("search memory for python limit 5")
    assert result == {"tool": "memory_search", "args": {"query": "python", "limit": 5}}

def test_memory_search_with_top():
    result = keyword_route("memory search for python top 10")
    assert result == {"tool": "memory_search", "args": {"query": "python", "limit": 10}}

def test_webhook_add_named_routing():
    result = keyword_route("create webhook named myhook")
    assert result == {"tool": "webhook_add", "args": {"name": "myhook"}}

def test_webhook_add_simple_routing():
    result = keyword_route("add webhook myhook")
    assert result == {"tool": "webhook_add", "args": {"name": "myhook"}}

def test_webhook_add_no_name_returns_none():
    result = keyword_route("create a webhook")
    assert result is None

def test_schedule_add_hourly_routing():
    result = keyword_route("schedule a task named daily_check every hour to check email")
    assert result["tool"] == "schedule_add"
    assert result["args"]["name"] == "daily_check"
    assert result["args"]["interval_seconds"] == 3600

def test_schedule_add_minutes_routing():
    result = keyword_route("schedule task for test every 5 minutes")
    assert result["tool"] == "schedule_add"
    assert result["args"]["name"] == "test"
    assert result["args"]["interval_seconds"] == 300

def test_schedule_add_daily_routing():
    result = keyword_route("set reminder named daily every day to review reports")
    assert result["tool"] == "schedule_add"
    assert result["args"]["name"] == "daily"
    assert result["args"]["interval_seconds"] == 86400

def test_memory_search_with_days():
    result = keyword_route("search memory for python last 30 days")
    assert result == {"tool": "memory_search", "args": {"query": "python", "days": 30}}

def test_memory_search_with_days_and_limit():
    result = keyword_route("search memory for python last 30 days limit 5")
    assert result == {"tool": "memory_search", "args": {"query": "python", "days": 30, "limit": 5}}

def test_email_configured_setup_routing():
    result = keyword_route("check email setup")
    assert result == {"tool": "email_configured", "args": {}}

def test_email_configured_working_routing():
    result = keyword_route("is my email working")
    assert result == {"tool": "email_configured", "args": {}}

def test_chart_histogram_routing():
    result = keyword_route("make a histogram with 5, 10, 15")
    assert result["tool"] == "chart_from_data"
    assert result["args"]["chart_type"] == "bar"

def test_chart_donut_routing():
    result = keyword_route("plot a donut chart with 1, 2, 3")
    assert result["tool"] == "chart_from_data"
    assert result["args"]["chart_type"] == "pie"

def test_webhook_events_with_limit_routing():
    result = keyword_route("webhook events for wh_12345 limit 5")
    assert result == {"tool": "webhook_events", "args": {"token": "wh_12345", "limit": 5}}

def test_webhook_events_with_top_routing():
    result = keyword_route("events for webhook wh_abc top 10")
    assert result == {"tool": "webhook_events", "args": {"token": "wh_abc", "limit": 10}}

def test_list_files_default_routing():
    result = keyword_route("list files")
    assert result == {"tool": "list_files", "args": {}}

def test_list_files_subpath_routing():
    result = keyword_route("list files in reports")
    assert result == {"tool": "list_files", "args": {"path": "reports"}}

def test_list_files_under_routing():
    result = keyword_route("show files under /data")
    assert result == {"tool": "list_files", "args": {"path": "/data"}}

def test_email_send_body_stripped():
    import os
    os.environ['RESEND_API_KEY'] = 'dummy'
    result = keyword_route("send an email to bob@example.com about lunch saying hello")
    assert result["tool"] == "email_send"
    assert result["args"]["to"] == "bob@example.com"
    assert "hello" in result["args"]["body"]

def test_email_send_to_extracted():
    import os
    os.environ['RESEND_API_KEY'] = 'dummy'
    result = keyword_route("send email to alice@test.com regarding project update")
    assert result["tool"] == "email_send"
    assert result["args"]["to"] == "alice@test.com"
