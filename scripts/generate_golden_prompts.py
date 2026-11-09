#!/usr/bin/env python3
"""Phase 1: Auto-generate golden prompts from tool inventory."""
import sys, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

PROMPT_OVERRIDES = {
    "calculator": "what is 12 times 34",
    "current_time": "what time is it",
    "time_now": "what time is it",
    "date_calc": "what is 30 days from today",
    "sql_sandbox_create": "create sql sandbox test",
    "sql_sandbox_list": "list sql sandboxes",
    "sql_sandbox_load_csv": "load csv data.csv into sql sandbox",
    "sql_sandbox_execute": "execute sql select * from t in sandbox",
    "sql_sandbox_drop": "drop sql sandbox test",
    "email_send": "send an email to user@example.com saying hello",
    "email_configured": "is email configured",
    "email_list_sent": "list sent emails",
    "web_search": "search the web for python tutorials",
    "web_fetch": "fetch https://example.com",
    "read_file": "read file test.txt",
    "write_file": "write hello to test.txt",
    "list_files": "list files in current directory",
    "delete_file": "delete file test.txt",
    "mkdir": "create directory testdir",
    "pdf_read": "read test.pdf",
    "excel_read": "read test.xlsx",
    "excel_write": "write data to test.xlsx",
    "generate_chart": "generate a bar chart of sales data",
    "pro_chart": "generate a pro chart of revenue",
    "advanced_chart": "create an advanced chart of profit",
    "generate_report": "generate a report of sales",
    "export_table": "export table to csv",
    "narrate_table": "narrate the table data",
    "arxiv_search": "search arxiv for transformers",
    "ddg_news": "search news for AI",
    "research_search": "research quantum computing",
    "marketaux_news": "get market news for AAPL",
    "finnhub_quote": "what is AAPL stock price",
    "fred_economic": "get GDP data from FRED",
    "tiingo_prices": "get historical prices for AAPL",
    "twelvedata_prices": "get intraday prices for AAPL",
    "fmp_fundamentals": "get fundamentals for AAPL",
    "eulerpool_data": "get eulerpool data for AAPL",
    "edgar_fundamentals": "get SEC fundamentals for AAPL",
    "insurance_data": "get insurance data states",
    "insurance_research": "insurance research filings for AIG",
    "govcon_data": "get government contract data",
    "live_market_stream": "live market stream for AAPL",
    "aggregate_market_data": "aggregate market data for tech stocks",
    "legal_citation_check": "check legal citation for 123 F.3d 456",
    "citation_lookup": "lookup citation 123 F.3d 456",
    "rag_search": "search documents for contract terms",
    "rag_list": "list all documents",
    "memory_search": "recall our previous conversation",
    "recall_history": "what did we discuss before",
    "search_library": "search the library for AI papers",
    "vision_analyze": "analyze this image",
    "image_generate": "generate an image of a cat",
    "browser_goto": "go to https://example.com",
    "browser_screenshot": "take a screenshot of example.com",
    "browser_click": "click the login button",
    "browser_fill_submit": "fill the form and submit",
    "browser_extract": "extract text from the page",
    "scrape_webpage": "scrape https://example.com",
    "url_metadata": "get metadata for https://example.com",
    "html_to_text": "convert html to text",
    "domain_research": "research example.com domain",
    "data_stats": "calculate stats for [1,2,3,4,5]",
    "data_describe": "describe the dataset",
    "data_correlation": "correlation between x and y",
    "csv_groupby": "group csv data by category",
    "ml_forecast": "forecast next 7 days sales",
    "forecast_arima": "arima forecast for sales",
    "technical_analysis": "technical analysis of AAPL",
    "python_eval": "calculate 2+2 in python",
    "python_session": "start python session",
    "query_external_db": "query external database for users",
    "query_sqlite": "query sqlite for users",
    "kpi_watch_add": "add kpi watch for revenue",
    "kpi_watch_list": "list kpi watches",
    "kpi_watch_run": "run kpi watch for revenue",
    "schedule_add": "schedule daily report",
    "schedule_list": "list schedules",
    "schedule_delete": "delete schedule 123",
    "schedule_run_now": "run schedule 123 now",
    "webhook_add": "add webhook for alerts",
    "webhook_list": "list webhooks",
    "webhook_delete": "delete webhook 123",
    "webhook_events": "list webhook events",
    "workspace_snapshot": "snapshot workspace",
    "document_diff": "diff two documents",
    "pdf_report": "generate pdf report",
    "data_quality_report": "data quality report for sales",
    "chart_from_data": "chart from data.csv",
    "financial_metrics": "financial metrics for AAPL",
    "api_call": "call https://api.example.com/data",
    "delegate_to_agent": "delegate to researcher: find AI papers",
    "execute_plan": "execute plan step 1: search",
    "workflow_registry": "list workflows",
    "script_registry": "list scripts",
    "echo": "echo hello",
    "weather": "weather in London",
}

SKIP_EXEC = {
    "email_send", "delete_file", "webhook_add", "webhook_delete",
    "schedule_add", "schedule_delete", "schedule_run_now",
    "sql_sandbox_drop", "write_file", "mkdir", "execute_plan",
    "delegate_to_agent", "image_generate", "browser_fill_submit",
    "browser_click", "browser_goto", "webhook_events", "excel_write",
}

NO_KEY = {
    "finnhub_quote", "fred_economic", "tiingo_prices", "twelvedata_prices",
    "fmp_fundamentals", "eulerpool_data", "edgar_fundamentals",
    "insurance_data", "govcon_data", "live_market_stream", "api_call",
    "image_generate",
}

def main():
    inv_path = Path("reports/tool_inventory.json")
    inv = json.loads(inv_path.read_text(encoding="utf-8"))

    out = []
    for item in inv["tools"]:
        name = item["name"]
        prompt = PROMPT_OVERRIDES.get(name, "use " + name.replace("_", " "))

        entry = {
            "tool": name,
            "prompt": prompt,
            "expected_args_subset": {},
            "category": item["category"],
            "mode": "keyword",
            "skip_exec": name in SKIP_EXEC if not (name in NO_KEY) else "no_key",
        }
        if name in NO_KEY:
            entry["skip_exec"] = "no_key"

        out.append(entry)

    out_path = Path("tests/fixtures/tool_golden.jsonl")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for entry in out:
            f.write(json.dumps(entry) + "\n")

    print("Generated %d golden prompts -> %s" % (len(out), out_path))
    print("  skip_exec=true: %d" % sum(1 for e in out if e["skip_exec"] is True))
    print("  skip_exec=no_key: %d" % sum(1 for e in out if e["skip_exec"] == "no_key"))
    print("  fully testable: %d" % sum(1 for e in out if not e["skip_exec"]))

if __name__ == "__main__":
    main()
