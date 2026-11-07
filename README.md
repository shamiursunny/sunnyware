---
title: Sunnyware
emoji: ☀️
colorFrom: yellow
colorTo: red
sdk: gradio
app_port: 7860
pinned: false
license: agpl-3.0
---

![Version](https://img.shields.io/badge/version-v1.10.0-blue)


# sunnyware

**Production-grade AI agent orchestrator** -- 112 tools, cross-session memory, multi-step planning, MCP interop, all on Hugging Face free tier.

[![CI](https://github.com/shamiursunny/sunnyware/actions/workflows/smokes.yml/badge.svg)](https://github.com/shamiursunny/sunnyware/actions)

**Live:** https://shamiur-sunnyware.hf.space
**Status dashboard:** https://shamiur-sunnyware.hf.space/status
**Chat UI:** https://shamiur-sunnyware.hf.space/ui
**API docs:** https://shamiur-sunnyware.hf.space/docs
**MCP:** https://shamiur-sunnyware.hf.space/mcp
**Scheduler:** https://shamiur-sunnyware.hf.space/api/schedule
**Usage:** https://shamiur-sunnyware.hf.space/api/usage
**Author:** [Shamiur Rashid Sunny](https://shamiur.com) | shamiur@engineer.com | +880-01737394735

---

## What it is

An autonomous AI agent that plans, calls tools, remembers across sessions, and exposes itself over the **Model Context Protocol** for use from Claude Desktop, Cursor, or any MCP client.

Built from scratch across 166 iterations -- runs 24/7 on HF free tier, no laptop dependency.

---

## Six-layer architecture

| Layer | What it does |
|---|---|
| Safety | rate limit, RBAC, injection guard, recon guard |
| Intelligence | auditor sub-agent, multi-role truth, CFO pipeline |
| Observability | evals, golden dataset, cost, budgets, circuits |
| Reliability | provider routing, cooldowns, circuit breakers |
| Compliance | HMAC audit trail, admin logging |
| Visibility | 10-card status dashboard, markdown chat |

---

## Features

- **Orchestrator** -- ReAct-style loop; supports both native OpenAI tool calling (Groq/OpenAI) and prompt-based JSON protocol (small local models)
- **112 tools** -- see Tools section below
- **Cross-session memory** -- auto-injects relevant past events into every prompt
- **Multi-step planner** -- decompose, execute (parallel), synthesize
- **Session API** -- full history, JSON export, soft rewind
- **Streaming** -- SSE for direct LLM output, tool-aware SSE (real-time tool events)
- **MCP server** -- Claude Desktop, Cursor, Continue, Cline, Zed, Windsurf
- **Observability** -- request IDs, structured logs, persistent metrics
- **Auth + rate limit** -- opt-in via env vars
- **Sandboxed execution** -- AST-validated python_eval, workspace-scoped file ops

---

## Tools (112 total)

Sunnyware ships with **112 registered tools** across **17 categories**. Most requests bypass the LLM entirely — a deterministic keyword router and a ReAct orchestrator dispatch the right tool in milliseconds, so execution is fast, cheap, and reproducible.

### Inventory at a glance

| Category | Tools | What it covers |
|---|---|---|
| **Browser Automation** | 5 | Headless Chromium via Playwright — deterministic, no LLM cost. |
| **Search & Research** | 9 | Web, news, academic, and domain-specific information retrieval. |
| **Retrieval & Memory** | 5 | Semantic search over documents, library, and conversation history. |
| **Financial Data Providers** | 15 | Fundamentals, quotes, filings, economic data — 14+ institutional sources. |
| **Finance & Markets** | 7 | Technical analysis, ML forecasting, and advanced charting. |
| **Data Science & Analytics** | 7 | Deterministic math, stats, dataframes, and sandboxed Python. |
| **Data Quality & ETL** | 6 | Cleaning, profiling, querying, and diffing datasets. |
| **Business Intelligence** | 5 | Tableau / Power BI integration, .pbix parsing, export pipelines. |
| **Reporting & Audit** | 6 | Narrative reporting, batch reports, and audit logging. |
| **Workflow & Automation** | 16 | Scheduled tasks, webhooks, KPI watches, and plan execution. |
| **Documents** | 5 | Read and convert PDFs, Excel, HTML, and BI files. |
| **Legal & Compliance** | 3 | Citation validation and clause extraction. |
| **Communication** | 3 | Email sending, configuration, and audit trail. |
| **Filesystem & Workspace** | 8 | Read, write, list, and delete files in the sandboxed workspace. |
| **Database & SQL** | 6 | Ephemeral SQL sandboxes and external DB queries. |
| **Media & Vision** | 2 | Image generation and vision analysis of charts and documents. |
| **System & Utility** | 4 | Time, weather, and environment utilities. |

### How tools are dispatched

- **Keyword router** (`src/sunnyware/keyword_router.py`) — matches unambiguous patterns like `login on <url> with ...`, `extract text from <url> using selector <css>`, `calculate 25 * 4`, `email <...>` and dispatches directly. **Zero LLM cost, sub-second response.**
- **ReAct orchestrator** (`src/sunnyware/orchestrator.py`) — handles ambiguous prompts by picking the smallest set of tools and formatting results through dedicated formatters. Users see clean markdown tables, never raw JSON.
- **Direct-answer list** (`_DIRECT_ANSWER_TOOLS`) — 60 deterministic tools whose output bypasses the LLM entirely to prevent hallucination on exact values (counts, prices, timestamps, page titles).

### Reliability & safety

- **Timeouts:** browser tools return within a hard budget (25s click, 40s fill/submit) so a slow site can never hang the agent.
- **Fallbacks:** `browser_fill_submit` and `browser_extract` fall back to `requests` + `BeautifulSoup` when Playwright times out on static pages.
- **Permissions:** Hugging Face `EACCES` on Playwright cache fixed by one-time recursive `chmod +x` at launch.
- **Sandboxing:** `python_eval` / `python_session` run in an isolated interpreter; `sql_sandbox_*` spin up ephemeral in-memory DBs; file tools are restricted to `/data/workspace/`.
- **URL validation:** every browser and fetch tool rejects non-`http(s)` schemes before any network I/O.

### Browser Automation (5)

| Tool | Description |
|---|---|
| `browser_click` | Open a URL, click an element (by CSS selector), then return the resulting page HTML + title + URL. Waits for network idle after the click. Use for multi-step navigation… |
| `browser_extract` | Open a URL in headless Chromium, run a CSS selector, and return structured rows. For each matched element, returns its text, href, src, and any requested attributes. Use… |
| `browser_fill_submit` | Open a URL, fill one or more form fields (either CSS selectors or human labels), then submit by clicking a button selector or pressing Enter. Returns the resulting page.… |
| `browser_goto` | Open a URL in a headless Chromium browser, wait for JavaScript to render, and return the final HTML + title + status. Use this instead of web_fetch for JS-heavy sites… |
| `browser_screenshot` | Open a URL in headless Chromium and capture a PNG screenshot. Returns base64 + saves a copy to /data/workspace/. Supports full_page (default true) and a CSS selector to… |

### Search & Research (9)

| Tool | Description |
|---|---|
| `arxiv_search` | Search arXiv for academic papers and preprints (free, no API key). |
| `ddg_news` | Search for general news using DuckDuckGo (free, no API key). |
| `domain_research` | Search free research papers across finance, investment, insurance, and legal domains. |
| `insurance_research` | Insurance-domain research via SEC EDGAR (insurer filings) and FRED (insurance-industry economic series). Uses only public, verified endpoints. Actions: search_filings -… |
| `research_search` | Unified research search across external data sources (no API key required for any source, no LLM calls). Runs the query against SEC EDGAR filings, FRED economic series,… |
| `scrape_webpage` | Scrape tables from a webpage URL and save them as a CSV file. |
| `url_metadata` | Fetch a URL and extract its metadata: <title>, OpenGraph (og:title, og:description, og:image, og:url, og:site_name, og:type), Twitter Card, standard… |
| `web_fetch` | Fetch a URL (http/https) and return a text summary. HTML is stripped to plain text. |
| `web_search` | Search the web for current information. Returns top results with title, URL, and snippet. Use for facts, news, current events. |

### Retrieval & Memory (5)

| Tool | Description |
|---|---|
| `memory_search` | Search past conversation events across all sessions for a keyword or phrase. |
| `rag_list` | List all documents currently uploaded to the RAG store, with page-level source names and chunk counts. Use this FIRST when the user references 'my documents', 'the… |
| `rag_search` | Semantic search over documents the user has uploaded. ALWAYS use this tool when the user asks to check, read, search, or summarize an uploaded file, attachment, or… |
| `recall_history` | Search past conversation events across all sessions. Use when the user asks 'what did we discuss earlier', 'find where I mentioned X', or needs historical context. |
| `search_library` | Search the user's uploaded documents and files in their Library. Use this when the user asks about a document they uploaded, or if you need specific information from… |

### Financial Data Providers (15)

| Tool | Description |
|---|---|
| `aggregate_market_data` | Fetch stock data from multiple providers, unify into a local database, and return a summary. |
| `api_call` | Make an HTTP request to a public REST API. Supports GET, POST, PUT, PATCH, DELETE, HEAD. Pass optional headers and a JSON body. Private and internal hosts are blocked… |
| `earnings_call` | Summarize an earnings-call transcript (raw text). Splits into themes (revenue, margin, guidance, capex, risk, capital_returns, operations, demand), pulls the top… |
| `edgar_fundamentals` | Fetch official financial statements from SEC EDGAR (US public companies only) via the XBRL API. Returns income statement, balance sheet, and cash flow data extracted… |
| `eulerpool_data` | Multi-source financial data via Eulerpool API (447 endpoints). NEW capabilities over other tools: bonds / fixed income, options (Greeks/IV/flow), 13F institutional… |
| `financial_metrics` | Compute standard financial risk + performance metrics from a return or price series: total/annualized return, volatility, Sharpe, Sortino, max drawdown, historical VaR… |
| `finnhub_quote` | Real-time quotes (15-min delayed on free tier), company profiles, company/market news, earnings calendar, and basic fundamentals via Finnhub. Requires FINNHUB_API_KEY… |
| `fmp_fundamentals` | Structured financial statements via Financial Modeling Prep: quote, profile, income statement, balance sheet, cash flow, ratios, key metrics, DCF. Uses FMP's /stable/… |
| `fred_economic` | Query FRED (Federal Reserve Economic Data) for 800k+ economic time series: GDP, CPI, unemployment, interest rates, treasury yields, money supply, sentiment, etc. Also… |
| `govcon_data` | US federal contract + spending data via USAspending.gov (no API key required). Treasury-operated, authoritative source for what federal agencies actually spent. Actions:… |
| `insurance_data` | US state insurance regulator data via Socrata open-data APIs (no key required). Searchable across TX TDI, NY DFS, CT, WA, IL, CO, OR, VT Department of Insurance portals.… |
| `live_market_stream` | Stream live stock prices via REST polling (Finnhub). |
| `risk_metrics` | Deterministic portfolio risk metrics: VaR (historical/parametric/Monte Carlo), CVaR/Expected Shortfall, annualized volatility, Sharpe, Sortino, Calmar, max drawdown,… |
| `tiingo_prices` | Historical OHLCV prices via Tiingo: 9 years of daily data and extended intraday (minute/hourly). Free tier: 1000 req/day, 500 unique symbols/month. Requires… |
| `twelvedata_prices` | Multi-asset market data via Twelve Data: stocks, ETFs, forex, and crypto across 190k+ symbols. Free tier: 800 req/day, 8/min. Requires TWELVEDATA_API_KEY env var. |

### Finance & Markets (7)

| Tool | Description |
|---|---|
| `chart_from_data` | Generate a PNG chart from data. Provide EITHER 'data' (a JSON array of row objects) OR 'file' (a CSV / TSV / JSON file in the workspace). The result includes base64 PNG… |
| `forecast_arima` | Fit an ARIMA model to a numeric time series and forecast N periods ahead. Provide EITHER 'data' (array of numbers) OR 'file' + 'column'. Auto-selects order via AIC if… |
| `generate_chart` | Generate a bar, line, or pie chart from a CSV or Excel file and save it as a PNG. |
| `marketaux_news` | Financial news with entity tagging and sentiment scores across 5000+ sources and 80+ markets. Free tier: 100 req/day, 3 articles per request. Requires MARKETAUX_API_KEY… |
| `ml_forecast` | Use Scikit-Learn to predict future prices or trends from CSV data. |
| `pro_chart` | Generate professional financial (candlestick) or statistical (heatmap) charts. |
| `technical_analysis` | Calculate RSI, MACD, SMA, EMA, and Bollinger Bands from a stock CSV. |

### Data Science & Analytics (7)

| Tool | Description |
|---|---|
| `calculator` | Evaluate a math expression safely (+, -, *, /, %, **, //). Returns the numeric result. |
| `csv_groupby` | Group a CSV/Excel by a column and compute an aggregate on another column. |
| `data_correlation` | Pearson correlation between two numeric arrays or two CSV columns. |
| `data_describe` | Full pandas-style statistical summary of a CSV/Excel file. |
| `data_stats` | Compute statistical summary (mean, median, std, min, max) for a list of numbers or a CSV column. |
| `python_eval` | Execute Python code for data work (pandas, numpy, scipy, sklearn, matplotlib, duckdb, openpyxl preloaded). Set result=... to return a value. Use ws_path('file.csv') for… |
| `python_session` | Run Python code in a persistent session. Variables (like DataFrames) persist across messages. |

### Data Quality & ETL (6)

| Tool | Description |
|---|---|
| `clean_dataset` | Clean a dataset by dropping nulls, filling missing values, and saving to a new file. |
| `csv_query` | Run a SELECT query against a CSV, Parquet, or JSON file in the workspace using DuckDB. Streams from disk so it handles files larger than memory. The file is… |
| `data_quality_report` | Scan a data file (CSV/TSV/XLSX/Parquet/JSON) in the workspace and return a data-quality report: per-column nulls, uniques, min/max/mean/std, IQR outliers, skew, string… |
| `document_diff` | Diff two documents and return a unified diff with summary stats (lines added/removed/same, similarity ratio). Three input modes: (1) two workspace files via left_file +… |
| `document_library` | Persistent text-document library. Save named documents with optional description and tags, list them, retrieve content, keyword-search across… |
| `query_sqlite` | Run a SQL query on a CSV or Excel file. It automatically loads the file into a temporary SQLite database. |

### Business Intelligence (5)

| Tool | Description |
|---|---|
| `add_tableau_filter` | Add a filter to a Tableau worksheet. |
| `edit_tableau_field` | Edit a calculated field formula, filter value, or parameter in a Tableau .twb workbook. Requires file, field_name, and new_value. |
| `export_table` | Export tabular data to a CSV, TSV, or JSON file. Works on BOTH workspace and sandbox (controlled by 'target_kind'). Provide EITHER 'rows' (JSON array of objects) OR… |
| `extract_pbix_assets` | Extract embedded data and images from a Power BI .pbix file. |
| `remove_tableau_field` | Remove a calculated field from a Tableau workbook. |

### Reporting & Audit (6)

| Tool | Description |
|---|---|
| `auditor_full_spec` | Load the extended auditor specification (~4K tokens). Call this ONLY when the compressed prompt is insufficient for a complex audit: multi-layer root cause, benchmark… |
| `generate_report` | Generate a formatted HTML report from a CSV/Excel dataset, including a summary table and a chart. |
| `metrics_batch` | Compute 20+ metrics (Sharpe, Sortino, Calmar, Omega, tail ratio, profit factor, win rate, downside deviation, capture ratios, skew, kurtosis, max drawdown, VaR, CVaR,… |
| `narrate_table` | Generate a plain-English narrative from a JSON array of rows (list of dicts). Pure Python statistics — no LLM, deterministic. Summarizes numeric columns… |
| `pdf_report` | Generate a multi-page PDF report from a structured spec. Each entry in 'pages' can be type='text' (title + body), type='table' (title + headers + rows), or type='chart'… |
| `report_batch` | Run multiple prompts in parallel and return collected results. Useful for FP&A workflows: 'variance for each month', 'KPI for each region', 'summarize each document… |

### Workflow & Automation (16)

| Tool | Description |
|---|---|
| `delegate_to_agent` | Delegate a self-contained sub-task to another specialist agent. The target agent runs with its own role-specific system prompt and tool subset, then returns its final… |
| `execute_plan` | Execute a multi-step plan by running a sequence of tools. Pass a JSON array of steps, where each step has a 'tool' and 'args'. |
| `hitl_config_update` | Update HITL approval settings for a tool. Use when the user asks to auto-approve, require approval, or block a tool — globally or for a specific user. Examples:… |
| `kpi_watch_add` | Register or update a KPI watch. The system will periodically run your check_prompt, extract a number from the answer, and compare it to a threshold. Breaches are logged… |
| `kpi_watch_list` | List all KPI watches. Optionally include recent events per watch (breaches, errors). Use to show the user what KPIs are being monitored and their last status. |
| `kpi_watch_run` | Run all enabled KPI watches right now. Each watch runs its check_prompt, extracts a number, compares to threshold, and logs breaches/errors to Neon. Returns per-watch… |
| `schedule_add` | Register a recurring task that runs an agent prompt on a fixed interval. Optionally email the result. The task persists in Neon and auto-registers with the background… |
| `schedule_delete` | Delete a dynamic schedule by name. Removes it from Neon and from the running scheduler immediately. |
| `schedule_list` | List all dynamic schedules with their last run status, count, result preview, and error if any. Use to show what recurring tasks the agent has running. |
| `schedule_run_now` | Trigger a dynamic schedule to run immediately, regardless of interval. Updates last_run info. Useful for testing or forcing an on-demand execution. |
| `script_registry` | Named Python script registry. Save, list, get, run, or delete reusable scripts. Every script is sandbox-validated on run, executed via the same engine as python_eval.… |
| `webhook_add` | Register a webhook endpoint. External services POST to the returned /webhook/{token} URL. Optionally auto-run an agent prompt on every received payload. Use for… |
| `webhook_delete` | Delete a webhook endpoint by token. Also removes its events. |
| `webhook_events` | List recent events received by a webhook endpoint (payloads, processed status, agent response preview). Newest first. |
| `webhook_list` | List all registered webhook endpoints with their tokens, URLs, hit counts, and last hit timestamps. |
| `workflow_registry` | Named multi-step agent workflows. Save, list, get, run, or delete a workflow composed of sequential (role, task) steps. Running a workflow executes each step via the… |

### Documents (5)

| Tool | Description |
|---|---|
| `excel_read` | Read an .xlsx workbook from the workspace. Returns sheet names and, for each requested sheet, headers (row 1) and rows as JSON objects. Formulas are shown as… |
| `excel_write` | Write an .xlsx workbook with real formatting: multiple sheets, bold headers, freeze panes, column widths, number formats (money/percent/int/date), formulas, and colored… |
| `html_to_text` | Convert HTML (or fetch-and-convert a URL) into clean, readable markdown-style text. Preserves headings, paragraphs, lists, links, code blocks. Better than web_fetch for… |
| `pdf_read` | Read a PDF file from the workspace and extract its text. Returns each page separately with char offsets. Optionally extract tables (if the PDF has them). Use for… |
| `read_bi_file` | Read and inspect any Office or BI file in the workspace or sandbox. Supports: .xlsx/.xls/.xlsm (returns sheets as table data), .docx/.doc (paragraphs + tables),… |

### Legal & Compliance (3)

| Tool | Description |
|---|---|
| `citation_lookup` | Look up full RAG chunk text + sha256 provenance. Two modes: {source, chunk_id} for exact, or {query} for semantic search. MANDATORY OUTPUT RULE: when citing a result,… |
| `clause_extractor` | Extract structured clauses from contract / policy text. Deterministic keyword matching — no LLM, no network. Clause types: termination, indemnification, liability,… |
| `legal_citation_check` | Verify case-law citations against CourtListener's 18M+ citation database (Free Law Project). This is the anti-hallucination guardrail for legal work: it catches… |

### Communication (3)

| Tool | Description |
|---|---|
| `email_configured` | Check whether email sending is configured on the server. Returns {configured: bool, host, port, from, user_set, password_set}. Use before attempting email_send to give… |
| `email_list_sent` | List recent emails sent by sunnyware (from Neon log). Returns recipients, subject, preview, attachments, ok/fail status, and timestamp. Use to audit past sends or… |
| `email_send` | Send an email via the configured Resend API. Supports multiple to/cc/bcc recipients, optional HTML body, and workspace file attachments… |

### Filesystem & Workspace (8)

| Tool | Description |
|---|---|
| `delete_file` | Delete a file or empty directory in the workspace. |
| `list_files` | List files in the workspace or sandbox. Optional path filter. |
| `mkdir` | Create a directory in the workspace (parents created if needed). |
| `read_file` | Read a text file from the server's local workspace (e.g., Python scripts or data files). DO NOT use this for user-uploaded attachments. If the user asks to read or check… |
| `read_sandbox_file` | Read a file from the Sandbox directory. Use this to inspect intermediate data, cleaned CSVs, database dumps, or temporary outputs saved by write_sandbox_file. |
| `workspace_snapshot` | Create a zip archive of the workspace (or a subdirectory) and return its contents as base64 + the file path. Useful for bundling multiple deliverable files (reports,… |
| `write_file` | Write text content to a file in the workspace (creates dirs if needed). |
| `write_sandbox_file` | Write a file to the Sandbox directory. Use this for intermediate data files, cleaned CSVs, database dumps, or temporary outputs. These files appear in the 'Sandbox' tab… |

### Database & SQL (6)

| Tool | Description |
|---|---|
| `query_external_db` | Run a SQL query against an external PostgreSQL or MySQL database using a connection string. |
| `sql_sandbox_create` | Create (or ensure) an isolated SQL sandbox. Returns the internal schema name (sb_<name>). IDEMPOTENT - call ONCE then immediately proceed to sql_sandbox_execute. Do NOT… |
| `sql_sandbox_drop` | Delete a SQL sandbox and its schema. Removes all tables inside it. Use when the user asks to clean up or remove a sandbox. |
| `sql_sandbox_execute` | Run SQL in a sandbox. Use $1..$n placeholders for params. SELECT/WITH return rows (max 5000). DDL/DML return a status string. Search path is forced to the sandbox; main… |
| `sql_sandbox_list` | List all SQL sandboxes with their tables and row counts. Use to see what's already loaded before running queries. |
| `sql_sandbox_load_csv` | Load a workspace CSV/TSV file into a table inside a sandbox. Columns are loaded as TEXT; cast in your SQL (e.g. amount::numeric). Replaces the table if it exists. |

### Media & Vision (2)

| Tool | Description |
|---|---|
| `image_generate` | Generate a NEW image from a text prompt using Pollinations.AI (free tier, no API key). Use whenever the user asks to draw, generate, create, illustrate, or visualize… |
| `vision_analyze` | Analyze an image (e.g., a chart) using a multimodal LLM. |

### System & Utility (4)

| Tool | Description |
|---|---|
| `current_time` | Get the current date and time in UTC. |
| `date_calc` | Date arithmetic. Actions: 'add' (add days to a date), 'diff' (days between two dates), 'weekday' (day of week for a date). Dates must be YYYY-MM-DD format. |
| `echo` | TEST-ONLY tool. Echoes back the provided text. NEVER use this for user requests — it is only for internal smoke tests. If the user says hi/hello/thanks, reply directly… |
| `weather` | Get current weather for a city. Returns temperature, wind, conditions. Uses Open-Meteo (free, no API key). |


## Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | /api/agent/run | Standard agent loop |
| POST | /api/agent/run/stream | Direct LLM SSE stream |
| POST | /api/agent/stream | Tool-aware SSE stream |
| POST | /api/agent/plan | Multi-step planner |
| GET  | /api/tools | List registered tools |
| POST | /api/tools/{name} | Direct tool invocation |
| GET  | /api/sessions | List recent sessions |
| GET  | /api/sessions/{key} | Session detail |
| GET  | /api/sessions/{key}/history | Full event timeline |
| GET  | /api/sessions/{key}/export | JSON export |
| POST | /api/sessions/{key}/rewind | Truncate events |
| GET  | /api/memory/context | Inspect memory injection |
| GET  | /api/eval/cases | List eval cases |
| POST | /api/eval/run | Run full eval suite |
| POST | /api/eval/run/{id} | Run one eval case |
| GET  | /api/auth/status | Auth state |
| POST | /api/metrics/flush | Force-flush metrics |
| GET  | /metrics | Metrics snapshot |
| GET  | /health/live | Liveness |
| GET  | /health/ready | Readiness |
| GET  | /mcp | MCP server info |
| POST | /mcp/rpc | MCP JSON-RPC 2.0 |
| GET  | /docs | OpenAPI UI |

---

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| NEON_DATABASE_URL | - | Postgres connection |
| LLM_BASE_URL | http://localhost:11434/v1 | LLM endpoint |
| LLM_API_KEY | ollama | LLM key |
| LLM_MODEL | gemma2-2b-tuned-stable:latest | Model name |
| SUNNYWARE_API_KEYS | unset | Comma-separated API keys |
| SUNNYWARE_RATE_LIMIT_PER_MINUTE | 0 | Rate limit |
| SUNNYWARE_PERSIST_METRICS | true | Persist counters |
| SUNNYWARE_WORKSPACE | ./data/workspace | File sandbox |

---

## Quickstart

HTTP:

    curl -X POST https://shamiur-sunnyware.hf.space/api/agent/run \
      -H "Content-Type: application/json" \
      -d '{"input":"What is the weather in Dhaka?","session_id":"demo"}'

MCP (Claude Desktop): see docs/mcp.md

---

## Development

    python -m venv .venv
    source .venv/Scripts/activate
    pip install -r requirements.txt
    export PYTHONPATH="$PWD/src"
    python app.py
    pytest tests/ -v
    bash scripts/smoke_test.sh http://localhost:7860

---

## Docs

- docs/mcp.md -- MCP setup guide
- workflow.md -- progress log

---

## License

AGPL-3.0-only (c) 2026 Shamiur Rashid Sunny -- https://shamiur.com