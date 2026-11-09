#!/usr/bin/env python3
"""Phase 0: Generate tool inventory with categories, env needs, and test coverage."""
import sys, json, re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

def main():
    from sunnyware.tools import list_tools
    tools = list_tools()
    print(f"Loaded {len(tools)} tools")

    # Category heuristics
    def categorize(name, desc):
        n = name.lower()
        if any(k in n for k in ("sandbox", "sql_sandbox", "csv_groupby", "calculator",
                                 "python_eval", "date_calc", "current_time", "time_now",
                                 "data_stats", "data_describe", "data_correlation",
                                 "ml_forecast", "forecast_arima", "technical_analysis")):
            return "deterministic"
        if any(k in n for k in ("read_file", "write_file", "list_files", "delete_file",
                                 "mkdir", "excel_read", "excel_write", "pdf_read",
                                 "read_bi_file", "read_sandbox_file", "write_sandbox_file",
                                 "document_diff", "pdf_report")):
            return "file"
        if any(k in n for k in ("email_send", "email_list", "webhook_add", "webhook_delete",
                                 "schedule_add", "schedule_delete", "delete_file")):
            return "side-effect"
        if any(k in n for k in ("web_search", "web_fetch", "browser_", "scrape_webpage",
                                 "arxiv_search", "ddg_news", "marketaux_news", "research_search",
                                 "url_metadata", "domain_research", "html_to_text")):
            return "network"
        if any(k in n for k in ("finnhub", "fred", "tiingo", "twelvedata", "fmp", "eulerpool",
                                 "edgar", "insurance_data", "govcon", "insurance_research",
                                 "live_market_stream", "aggregate_market")):
            return "api-key"
        if any(k in n for k in ("chart", "pro_chart", "advanced_chart", "generate_chart",
                                 "generate_report", "export_table", "bi_export", "narrate_table")):
            return "visual"
        if any(k in n for k in ("rag_", "memory_search", "recall_history", "search_library",
                                 "citation_lookup", "legal_citation_check")):
            return "rag"
        if any(k in n for k in ("delegate", "execute_plan", "workflow_registry", "script_registry")):
            return "meta"
        return "other"

    # Env detection: scan each tool file for os.getenv
    src = Path("src/sunnyware/tools")
    env_by_tool = {}
    for tool_file in src.glob("*.py"):
        text = tool_file.read_text(encoding="utf-8")
        envs = re.findall(r'os\.getenv\(["\']([A-Z_][A-Z0-9_]+)["\']', text)
        if envs:
            # Map file name to tool names
            for t in tools:
                # heuristic: tool name roughly matches file stem
                if t["name"].replace("_", "") in tool_file.stem.replace("_", ""):
                    env_by_tool[t["name"]] = list(set(envs))

    # Test coverage: check if tool name appears in any test file
    test_dir = Path("tests")
    coverage = {}
    for t in tools:
        name = t["name"]
        found = False
        for test_file in test_dir.glob("test_*.py"):
            if name in test_file.read_text(encoding="utf-8"):
                found = True
                break
        coverage[name] = "covered" if found else "uncovered"

    # Build inventory
    inventory = []
    for t in tools:
        name = t["name"]
        desc = t.get("description", "")
        inventory.append({
            "name": name,
            "description": desc[:200],
            "category": categorize(name, desc),
            "requires_env": env_by_tool.get(name, []),
            "test_coverage": coverage.get(name, "uncovered"),
            "has_parameters": bool(t.get("parameters")),
        })

    # Summary
    by_cat = {}
    for item in inventory:
        by_cat.setdefault(item["category"], []).append(item["name"])

    by_coverage = {"covered": 0, "uncovered": 0}
    for item in inventory:
        by_coverage[item["test_coverage"]] += 1

    out = {
        "total": len(inventory),
        "by_category": {k: len(v) for k, v in by_cat.items()},
        "by_coverage": by_coverage,
        "tools": inventory,
    }

    out_path = Path("reports/tool_inventory.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    print(f"\nInventory written: {out_path}")
    print(f"\nCategories:")
    for cat, count in sorted(out["by_category"].items(), key=lambda x: -x[1]):
        print(f"  {cat:<20} {count}")
    print(f"\nTest coverage: {by_coverage['covered']} covered, {by_coverage['uncovered']} uncovered")
    print(f"\nTools with env requirements:")
    for item in inventory:
        if item["requires_env"]:
            print(f"  {item['name']:<25} requires {item['requires_env']}")

if __name__ == "__main__":
    main()
