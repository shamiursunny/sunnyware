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


## Multi-Tenant Architecture

Sunnyware is a **true multi-tenant SaaS**. Every organization is isolated by `org_id` across identity, data, workspace, and memory. Built for land-and-expand: start with one user, scale to enterprise teams without re-architecture.

| Layer | Isolation |
|---|---|
| Identity | WorkOS AuthKit (`org_id` + `user_id`) |
| RAG Data | FAISS indices partitioned by `org_id` |
| Workspace | `/data/workspace/{org_id}/{user_id}/` |
| Memory | Sessions keyed by `(org_id, session_id)` |

**RBAC:** Owner / Admin / User / Viewer.
**Quotas:** Per-tenant token budgets, tool execution caps, storage limits.
**Enterprise:** SSO (SAML 2.0 / OIDC), SCIM roadmap Q1 2027.

See [`MULTI_TENANT.md`](./MULTI_TENANT.md) for the full architecture.

---

<!-- ATTESTATIONS:START -->

## Verifiable Quality Reports

**Version:** `v1.57.0` · **Commit:** `bbfad8a` · **Generated:** `2026-11-09T15-29-15Z`

Every commit ships 7 **tamper-evident** quality reports.

| Report | Exit | SHA-256 (first 16) | What it proves |
|---|---|---|---|
| `system_monitor` | ✅ 0 | `f1d41eec262b8a04…` | Full system health + 54 production checks |
| `pre_push_check` | ✅ 0 | `257039299207b5bf…` | Pre-push gate: syntax, HTML sanity, smoke test |
| `smoke_local` | ✅ 0 | `406f5d6c9b51c9e2…` | Local HTML/structure validation |
| `security_pre_deploy` | ✅ 0 | `7699f3f3dbc69514…` | Static security: secrets, imports, CVEs, bandit |
| `smoke_remote` | ✅ 0 | `ba6a3e8e391ccda6…` | Live HF Space deployment health |
| `security_post_deploy` | ✅ 0 | `0c96f1aa6d12881e…` | Runtime security: headers, auth, CORS |
| `diagnostics` | ✅ 0 | `69244c0a70b87695…` | Automatic error detection: registry/schema integrity, recursive-name guard |

**Verify integrity in 1 second:**
```bash
python scripts/verify_attestations.py
```

Full reports + hashes: [`reports/latest/MANIFEST.json`](./reports/latest/MANIFEST.json). Each report is timestamped and linked to this git commit — anyone can re-run and reproduce.

<!-- ATTESTATIONS:END -->
## ⛓️ Attestation Blockchain (Enterprise Trust Chain)

_Auto-generated by `scripts/attest_all.py` on every ship. Do not edit manually._

<!-- CHAIN:START -->
### Trust Summary

| Property | Value |
|----------|-------|
| **Chain length** | 43 blocks |
| **Latest block hash** | `9ced3281c4a9c5212138cb3961385914b0f669bf720869b71c975c1bce86b78c` |
| **Latest commit** | `bbfad8a` |
| **Latest version** | 1.57.0 |
| **Genesis hash** | `0000000000000000000000000000000000000000000000000000000000000000` |

### Full Blockchain

| # | Block Hash | Prev Hash | Commit | Version | Timestamp (UTC) |
|---|-----------|-----------|--------|---------|-----------------|
| 42 | `9ced3281c4a9c521...` | `538a7e6ff8e506e5...` | `bbfad8a` | 1.57.0 | 2026-11-09T15-29-15Z |
| 41 | `538a7e6ff8e506e5...` | `6ef6f755b0d15085...` | `2d35860` | 1.56.0 | 2026-11-09T15-16-53Z |
| 40 | `6ef6f755b0d15085...` | `a654aa66e070df69...` | `758623e` | 1.55.0 | 2026-11-09T15-02-02Z |
| 39 | `a654aa66e070df69...` | `ca8c604fc8ec2027...` | `47555cd` | 1.54.0 | 2026-11-09T14-36-23Z |
| 38 | `ca8c604fc8ec2027...` | `cdfb804bb211e15e...` | `3367593` | 1.53.0 | 2026-11-09T14-09-29Z |
| 37 | `cdfb804bb211e15e...` | `baa6e7a8ef36e504...` | `ba7fca1` | 1.52.0 | 2026-11-09T13-56-51Z |
| 36 | `baa6e7a8ef36e504...` | `883fe20332683953...` | `2bd23b0` | 1.51.0 | 2026-11-09T13-40-42Z |
| 35 | `883fe20332683953...` | `a41cd8b914db9a7c...` | `612b8c3` | 1.50.0 | 2026-11-09T13-20-08Z |
| 34 | `a41cd8b914db9a7c...` | `8bcd63fe5dcae21f...` | `3ed0bfe` | 1.49.0 | 2026-11-09T12-47-17Z |
| 33 | `8bcd63fe5dcae21f...` | `22b53714406c578b...` | `91356f0` | 1.48.0 | 2026-11-09T12-32-11Z |
| 32 | `22b53714406c578b...` | `6ebaf3e7851726e2...` | `b87d230` | 1.47.0 | 2026-11-09T12-10-03Z |
| 31 | `6ebaf3e7851726e2...` | `2c5d2f861b8a2a5d...` | `41fb189` | 1.46.0 | 2026-11-09T11-50-25Z |
| 30 | `2c5d2f861b8a2a5d...` | `c95eb57bc496a915...` | `37df907` | 1.45.0 | 2026-11-09T11-33-41Z |
| 29 | `c95eb57bc496a915...` | `f91cec1fdf0bbdf6...` | `9c1b69c` | 1.44.0 | 2026-11-09T11-23-34Z |
| 28 | `f91cec1fdf0bbdf6...` | `c0da48ca36851141...` | `3dee9f3` | 1.43.0 | 2026-11-09T11-09-32Z |
| 27 | `c0da48ca36851141...` | `af6fe9e1161599a5...` | `685de80` | 1.42.0 | 2026-11-09T10-50-58Z |
| 26 | `af6fe9e1161599a5...` | `08192836320a0eb0...` | `c1f3ca3` | 1.41.0 | 2026-11-09T10-21-30Z |
| 25 | `08192836320a0eb0...` | `b2ceab833cc959b2...` | `232fbda` | 1.40.0 | 2026-11-09T09-44-47Z |
| 24 | `b2ceab833cc959b2...` | `e4316c8507f72e0f...` | `5c61105` | 1.39.0 | 2026-11-09T09-07-24Z |
| 23 | `e4316c8507f72e0f...` | `b010f3cfb3345c01...` | `fbba4d1` | 1.38.0 | 2026-11-09T08-56-34Z |
| 22 | `b010f3cfb3345c01...` | `843c717828d001b4...` | `a28fb9b` | 1.37.0 | 2026-11-09T08-42-07Z |
| 21 | `843c717828d001b4...` | `5ff77e21fb51bae4...` | `b740fed` | 1.36.0 | 2026-11-09T08-30-24Z |
| 20 | `5ff77e21fb51bae4...` | `9a23dcf6b36d7826...` | `32c4aed` | 1.35.0 | 2026-11-09T08-07-48Z |
| 19 | `9a23dcf6b36d7826...` | `f54c20d46dc9e497...` | `383cd36` | 1.34.0 | 2026-11-09T07-54-56Z |
| 18 | `f54c20d46dc9e497...` | `4c3406a79969a125...` | `f59467e` | 1.33.0 | 2026-11-08T19-18-58Z |
| 17 | `4c3406a79969a125...` | `967d2625e651bbd4...` | `a6e18c6` | 1.32.0 | 2026-11-08T18-11-12Z |
| 16 | `967d2625e651bbd4...` | `8ff81c5d1fd727e6...` | `ac847f0` | 1.31.0 | 2026-11-08T17-46-47Z |
| 15 | `8ff81c5d1fd727e6...` | `a385d6c549384080...` | `d5770ef` | 1.30.0 | 2026-11-08T17-17-56Z |
| 14 | `a385d6c549384080...` | `8d8c2f59238b8044...` | `7823bb1` | 1.29.0 | 2026-11-08T16-17-04Z |
| 13 | `8d8c2f59238b8044...` | `1bfdde3786561ce1...` | `a16cc46` | 1.28.0 | 2026-11-08T15-20-27Z |
| 12 | `1bfdde3786561ce1...` | `2cf1163df0029915...` | `341b117` | 1.27.0 | 2026-11-08T13-18-51Z |
| 11 | `2cf1163df0029915...` | `f2fc4f50fcd3c7fa...` | `1b46635` | 1.26.0 | 2026-11-08T13-13-08Z |
| 10 | `f2fc4f50fcd3c7fa...` | `e4854523cc8f4ee8...` | `b8acc01` | 1.25.0 | 2026-11-08T12-54-37Z |
| 9 | `e4854523cc8f4ee8...` | `11d2d6fd257f7dfc...` | `712f19d` | 1.24.0 | 2026-11-08T12-33-23Z |
| 8 | `11d2d6fd257f7dfc...` | `7633ad295c4bbae7...` | `df10e70` | 1.23.0 | 2026-11-08T12-07-34Z |
| 7 | `7633ad295c4bbae7...` | `b783b2eeadefd106...` | `906d76a` | 1.22.0 | 2026-11-08T11-36-07Z |
| 6 | `b783b2eeadefd106...` | `c409a61fb19ef697...` | `bc3c495` | 1.21.0 | 2026-11-08T11-27-47Z |
| 5 | `c409a61fb19ef697...` | `995a3f49b95acb13...` | `5593676` | 1.20.0 | 2026-11-08T11-05-18Z |
| 4 | `995a3f49b95acb13...` | `dfe223fc95822681...` | `b17a9b1` | 1.19.0 | 2026-11-08T09-54-09Z |
| 3 | `dfe223fc95822681...` | `2ea4dce00324a1a9...` | `02e9f0a` | 1.18.0 | 2026-11-08T09-44-42Z |
| 2 | `2ea4dce00324a1a9...` | `91243ccf6b8401ee...` | `7437974` | 1.17.0 | 2026-11-08T09-24-35Z |
| 1 | `91243ccf6b8401ee...` | `ad91fff085838c87...` | `52b7bfd` | 1.16.0 | 2026-11-08T09-14-07Z |
| 0 | `ad91fff085838c87...` | `0000000000000000...` | `52b7bfd` | 1.16.0 | 2026-11-08T09-10-05Z |

### Security Properties

- **Tamper-evident** — modifying any historical report or block breaks all subsequent hashes
- **Append-only** — blocks cannot be inserted or reordered without breaking the chain
- **Deterministic** — `diagnostics --attest` produces byte-identical output across runs
- **Idempotent** — re-running attestation on unchanged code does not create duplicate blocks

### Verification (Source of Truth)

```bash
python scripts/verify_chain.py           # verify full chain integrity
python scripts/verify_attestations.py    # verify individual report hashes
cat reports/CHAIN.json | python -m json.tool  # inspect raw chain
```

### Trust Model

**Cryptographically guaranteed:**
1. Every shipped version was attested by all 7 independent scripts
2. Each attestation run is linked to its predecessor via SHA-256
3. Historical reports cannot be silently rewritten without breaking the chain
4. Anyone can independently verify the chain from `reports/CHAIN.json`

**Not guaranteed:**
- Absence of bugs (certifies process integrity, not code perfection)
- Maintainer trustworthiness (chain records what was signed, not whether it should be trusted)

<!-- CHAIN:END -->








































## 🚀 Deployment Trust Log

_Auto-generated by `scripts/attest_all.py` from `reports/DEPLOYMENTS.json`. Do not edit manually._

<!-- DEPLOYMENTS:START -->
**17/19 deployments verified**

| Timestamp (UTC) | Version | Block | Chain Hash | Result |
|-----------------|---------|-------|------------|--------|
| 2026-11-08T18:15:38Z | v1.32.0 | #17 | `4c3406a79969a125...` | PASS |
| 2026-11-08T17:52:31Z | v1.31.0 | #16 | `967d2625e651bbd4...` | PASS |
| 2026-11-08T17:22:20Z | v1.30.0 | #15 | `8ff81c5d1fd727e6...` | PASS |
| 2026-11-08T17:00:12Z | v1.29.0 | #14 | `a385d6c549384080...` | PASS |
| 2026-11-08T16:31:22Z | v? | #14 | `a385d6c549384080...` | FAIL |
| 2026-11-08T15:27:22Z | v1.28.0 | #13 | `8d8c2f59238b8044...` | PASS |
| 2026-11-08T13:16:46Z | v1.26.0 | #11 | `2cf1163df0029915...` | PASS |
| 2026-11-08T12:58:49Z | v1.25.0 | #10 | `f2fc4f50fcd3c7fa...` | PASS |
| 2026-11-08T12:37:45Z | v1.24.0 | #9 | `e4854523cc8f4ee8...` | PASS |
| 2026-11-08T12:11:57Z | v1.23.0 | #8 | `11d2d6fd257f7dfc...` | PASS |
| 2026-11-08T11:43:05Z | v1.22.0 | #7 | `7633ad295c4bbae7...` | PASS |
| 2026-11-08T11:39:25Z | v1.22.0 | #7 | `7633ad295c4bbae7...` | PASS |
| 2026-11-08T11:08:40Z | v1.20.0 | #5 | `c409a61fb19ef697...` | PASS |
| 2026-11-08T10:34:16Z | v1.19.0 | #4 | `995a3f49b95acb13...` | PASS |
| 2026-11-08T10:27:22Z | v1.19.0 | #4 | `995a3f49b95acb13...` | PASS |
| 2026-11-08T10:03:20Z | v1.19.0 | #4 | `995a3f49b95acb13...` | PASS |
| 2026-11-08T09:58:25Z | v1.19.0 | #4 | `995a3f49b95acb13...` | PASS |
| 2026-11-08T09:52:14Z | v1.18.0 | #3 | `dfe223fc95822681...` | PASS |
| 2026-11-08T09:35:01Z | v? | #2 | `2ea4dce00324a1a9...` | FAIL |

### What this proves

- Each entry was created **after** the HF Space reported the same version
- Every script hash on the server was compared to the local chain
- Every blockchain block was compared to the local chain
- Tampering with either the server or the repo breaks the comparison

### Verification command

```bash
python scripts/verify_deployed.py --skip-wait   # compare current state
```

<!-- DEPLOYMENTS:END -->













































## Automatic Error Detection (Diagnostics)

Sunnyware ships with a self-diagnostic subsystem that observes every layer of the request pipeline and records structured error reports — without ever mutating tool behavior.

| Layer | Detection |
|-------|-----------|
| **Startup** | Registry integrity (duplicate/recursive names), wiring integrity (run_agent, _build_tools_schema), schema determinism |
| **Preflight** | Router/LLM-suggested tool names verified against the live registry |
| **Per-call** | Tool result classified: auth (401), rate_limit (429), timeout, empty, malformed |
| **Post-response** | LLM self-report contradictions ("I don't have X" while X exists) |

### CLI

    python scripts/diagnostics.py           # human-readable report
    python scripts/diagnostics.py --attest  # deterministic SHA-256 for attestation

### API

    GET /api/diagnostics/report   ->  grouped by severity (info / warn / error / fatal)

### Attested Hash

diagnostics is the 7th attested script. Its deterministic SHA-256 (first 16) is pinned as 806060aa9fe1f97b and recorded in reports/latest/MANIFEST.json.

### Tests

    pytest -q tests/test_diagnostics.py    # 5 seeded error classes


## Versioning & Rollback

Every successful push to `main` **automatically bumps the minor version** and creates an immutable git tag. The current version is displayed at the top of the **Verifiable Quality Reports** table above.

### Versioning scheme

| Change | Version bump | Example |
|---|---|---|
| Every push to `main` | `+0.1.0` (minor) | `v1.10.0` → `v1.11.0` |
| Manual hotfix | `+0.0.1` (patch) | `python scripts/bump_version.py --patch` |

### Rollback to any previous version

List all released versions:

    git tag -l 'v*' --sort=-version:refname

View a previous version (read-only, safe):

    git checkout v1.10.0
    git checkout main

Full rollback of main (destructive):

    git checkout main
    git reset --hard v1.10.0
    git push origin main --force
    git push hf main --force

### How it works

1. Push lands on `main` -> CI triggers
2. CI runs `python scripts/bump_version.py` -> writes new version to `src/sunnyware/__init__.py`
3. CI runs the 6 quality checks -> generates reports
4. CI commits as `chore(release): vX.Y.Z [skip ci]`
5. CI creates git tag `vX.Y.Z` on that commit
6. CI pushes the commit + tag to both GitHub and Hugging Face

The `[skip ci]` flag prevents the bump commit from re-triggering the workflow.

---


## Production Readiness

<!-- PRODUCTION_READINESS:START -->
Sunnyware is monitored continuously and scored against 54 production-readiness checks. Current score: **100.0 / 100 (Grade A+)**.

| Area | Status |
|---|---|
| Tools loaded | 112 registered, 0 degraded, 0 broken |
| Providers online | 5 / 5 |
| Audit chain | `CHAIN OK` (1,484+ entries) |
| Recon guard | 34 patterns active |
| CI pipeline | pytest (55/55 checks passed), pre-push gate, smoke tests |
<!-- PRODUCTION_READINESS:END -->

**Security:** WorkOS AuthKit + 2FA, RBAC, audit chain, sandboxing, TLS 1.2+.
**Compliance:** Controls aligned with SOC 2 — formal audits on roadmap (see [`SECURITY.md`](./SECURITY.md)).
**Admin:** Full admin panel documented in [`ADMIN.md`](./ADMIN.md).

---

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