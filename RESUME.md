# RESUME — Sunnyware (paste this into a new AI tab)



Copy everything below the line into a fresh chat, then ask any question.



---



## Project

Sunnyware — a FastAPI + custom HTML/JS WebUI AI agent running on a Hugging

Face Space. Multi-provider LLM router (Groq/Gemini/OpenRouter with auto

model resolver), ReAct orchestrator, 16 agent tools, RAG over uploaded

docs, sandboxed Python data-science workbench. PostgreSQL (Neon) stores

memory + sessions + historical chat. Streaming SSE WebUI, multi-session

sidebar, JSON export/import, token usage dashboard, markdown rendering.



## Live

- WebUI:   https://shamiur-sunnyware.hf.space/ui

- GitHub:  https://github.com/shamiursunny/sunnyware

- Space:   https://huggingface.co/spaces/shamiur/sunnyware



## Current state (last session: 2026-10-16, Part 140)

- Commit:  run `git log -1 --oneline` for current hash

- Health:  /health/ready -> status ok, tools: 58

- LLM:     multi-provider (groq, gemini, openrouter) with auto-failover

  - Groq:       openai/gpt-oss-120b      (primary, ~200ms)

  - Gemini:     gemini-2.5-flash        (backup, ~500ms)

  - OpenRouter: liquid/lfm-2.5-2.6b:free (backup, ~700ms)

  - Auto-resolver: /api/models/resolve (self-heals when providers retire models)

- Vector store: per-tenant FAISS in /data/vector_store/{org_id}/

- Neon DB:    PostgreSQL, sessions + events + metrics + usage

- WebUI header badge: `via <provider>` shows last-serving provider
  (Part 139: response now also carries result.resolved_model so the
   model name always matches the provider that actually served)

## Sub-agents

- auditor ("AI Evaluation Auditor", U+1F50D): forensic audit of
  AI outputs. ~430-token prompt (compressed from the 30K V15.0
  spec). Tools: calculator, python_eval, read_file, rag_search.
  Returns structured JSON verdict. User-only invocation.

## Recent additions (Parts 157-163)

- Golden dataset (Part 158): src/sunnyware/golden.py + static/
  golden_dataset.json. 5 seeded cases, 5 match modes. Endpoints:
  /api/golden/{status,latest,trends,run,promote,delete}. Frozen
  baseline separate from evals; detects behavior drift.

- Budget tracking (Part 159): usage.py extended with
  budget_status / check_budget / fire_alerts / rollup / reset_alerts.
  Endpoints: /api/usage/{budget,rollup,alerts/reset}.
  Config: SUNNYWARE_BUDGET_USD_{DAILY,MONTHLY}, SUNNYWARE_BUDGET_ALERT_PCT
  (all opt-in; default 0 = disabled).

- Legacy smokes archived (Part 157b): 9 stale tests moved to
  scripts/_archive/legacy/ with README. 93 active smokes all pass.

- Tool circuit breakers (Part 160): src/sunnyware/circuit_breaker.py.
  Per-tool failure tracking. N consecutive fails -> breaker opens for
  M seconds; calls return synthetic circuit_open. Endpoints:
  /api/tools/circuits{,/reset}. Env: SUNNYWARE_TOOL_BREAKER_{ENABLED,
  FAILS,COOLDOWN_S} (defaults: on, 5, 60).

- Audit trail (Part 161): src/sunnyware/audit.py. HMAC-signed,
  hash-chained JSONL. _check_admin wrapped to log every admin
  decision. Endpoints: /api/audit/{recent,stats,verify,export,clear}.
  Env: SUNNYWARE_AUDIT_{ENABLED,KEY,PATH} (default on).

- Recon-path guard (Part 162): src/sunnyware/recon_guard.py +
  middleware in main.py. Blocks common scanner probes with 403. Always
  allows /api/, /health, /static/, /docs, /.well-known/. Endpoints:
  /api/recon/{stats,reset}. Env: SUNNYWARE_RECON_GUARD_ENABLED,
  SUNNYWARE_RECON_LOG_TO_AUDIT, SUNNYWARE_RECON_RECENT_MAX
  (defaults: on, on, 50).

- Status dashboard (Part 163): static/status.html, served at GET
  /status. Self-contained (no CDN, no build). Auto-refreshes 5s.
  Aggregates health, budget, golden, evals, circuits, recon, audit,
  providers into one color-coded page.

- CI/CD (Part 164a-k): .github/workflows/smokes.yml runs two
  jobs on every push/PR: gate (pre_push_check.py + system_monitor.py
  --offline, deterministic, <1 min) and smoke (auto-detected from
  diff/commit-message, runs only the smokes the change touches).
  requirements-ci.txt = minimal CI dep set. scripts/run_all_smokes.py
  is the local full-sweep runner with --verbose + env-skip classifier.
  Status: GREEN on both jobs.

- Status page - Neon + CI cards (Part 165): /status now shows
  Neon DB health (SELECT 1 probe with latency + region) and the last
  3 GitHub Actions runs (status, duration, clickable link). Cached
  90s on the CI probe to respect the unauthenticated rate limit.

- README refresh (Part 168): stale "14 tools / 22 iterations"
  fixed to 81 tools / 166 iterations. Added status dashboard
  link, CI badge, and six-layer architecture table. HF Space
  frontmatter preserved.

- Structured outputs (Part 167): src/sunnyware/schema.py
  validates every tool call against its declared parameters
  spec. Coercion first, strict mode rejects unresolvable
  mismatches. Violations logged to audit, don't trip breaker.
  Env: SUNNYWARE_SCHEMA_{ENABLED,STRICT,ALLOW_EXTRA}.

## Production safety layers (Parts 134-140)

- Rate limiting: SUNNYWARE_RATE_LIMIT_PER_MINUTE=60 (per-tenant, IP
  or session fallback). Admin endpoints at /api/rate_limit/* are
  exempt. Endpoints: /api/rate_limit/{status,tenants,reset,evict}.

- RBAC: admin > analyst > readonly. Set SUNNYWARE_API_ROLES=
  'key1:admin,key2:analyst'. Permissive when auth is off. Endpoint:
  /api/auth/whoami.

- Injection guard: SUNNYWARE_INJECTION_GUARD=block. 18 regex patterns
  across 6 categories. Blocks high-severity attacks with HTTP 400.
  Endpoints: /api/guardrails/{status,scan,self_test}.

- Continuous evals: SUNNYWARE_EVAL_INTERVAL_HOURS=6. 5-case corpus
  (echo, math, one_word, leak, injection) runs on the scheduler.
  Endpoints: /api/evals/{status,latest,trends,run}.

- Cost attribution: per-tenant LLM usage + cost tracked to Neon
  (llm_usage table). Endpoints: /api/usage, /api/usage/all,
  /api/usage/trends, /api/usage/export.csv.

- Identity: prompts.py enforces 'You are Sunnyware' so the underlying
  LLM never claims to be Gemini/GPT/Claude/Llama/LFM.



## What's working (verified live)



### Core features (Parts 32-42)

- Multi-provider LLM router with auto-failover

- Auto model resolver — self-heals when providers retire models

- 429 fast-fail (0.2s instead of 40s waste per broken provider)

- 33 agent tools: rag_search, python_eval, recall_history, csv_query,

  chart_from_data, citation_lookup, forecast_arima, financial_metrics,

  api_call, document_diff, pdf_report, workspace_snapshot, excel_write,

  excel_read, browser_goto, browser_screenshot, browser_extract,

  browser_click, browser_fill_submit (+ 14 core)

- Streaming WebUI — tokens appear as generated via SSE (Part 34)

- Chat history persistence + sidebar with multi-session (Part 35)

- Multi-file upload (Part 36) — drag 10+ files at once

- Neon fallback for session history (Part 38) — browser-wipe proof

- JSON export/import for sessions (Part 39) — belt & suspenders

- Token usage dashboard (Part 40) — Stats button + modal

- System monitor + baseline (Part 41) — 57 checks, A+ grade

- Markdown rendering for assistant messages (Part 42) — marked.js

- `via <provider>` badge on header (Part 42)

- Chart rendering + click-to-zoom (Part 43)

- Session rename — pencil icon or double-click title (Part 43)

- Voice input — Web Speech API (Part 43; Chrome/Edge/Safari only, not Firefox)

- WebUI hits tool-aware /api/agent/stream (Part 47) — tools work on mobile + desktop

- Tool audit trail in Neon (Part 48) — tool_invocations table

- recall_history tool (Part 49) — cross-session memory search

- csv_query tool (Part 50) — DuckDB over workspace files

- chart_from_data tool (Part 51) — inline PNG from JSON/CSV

- citation_lookup tool (Part 52) — full chunk text + sha256 provenance

- forecast_arima tool (Part 53-54) — trend-aware ARIMA forecasting

- financial_metrics tool (Part 55) — Sharpe/Sortino/VaR/CVaR/drawdown

- api_call tool (Part 56) — generic REST client w/ SSRF guard

- Streaming provider fallback (Part 57) — stream_chat tries all providers

- document_diff tool (Part 58) — diff files/RAG chunks/inline text

- pdf_report tool (Part 59) — multi-page PDF (text/table/chart pages)

- pdf_read tool (Part 72) — extract text from workspace PDFs

- citation_lookup strengthened (Part 73) — citation_string + cite_these

- report_batch tool (Part 74) — parallel multi-prompt runner

- kpi_watch_add/list/run (Part 75) — log-only KPI monitoring

  (Neon tables: kpi_watches, kpi_watch_events; email deferred to Part 82)

- workspace_snapshot tool (Part 60) — zip workspace to retrievable archive

- Full UI redesign (Parts 65-71): responsive, Inter font, SVG icons,

  neutral palette, glass drawer, ChatGPT/Claude message layout, session search

- excel_write tool (Part 61) — formatted .xlsx (sheets, formulas, formats)

- excel_read tool (Part 62) — read .xlsx (sheets, headers, formulas)

- Playwright browser automation (Part 63/63.3) — 5 tools:

  browser_goto, browser_screenshot, browser_extract,

  browser_click, browser_fill_submit. Part 63.1 fixes:

  chmod +x after install + retry on EACCES. Chromium caches to

  /data/playwright-browsers; first call 3-5 min, then ~3 sec.

- Full responsive UI — mobile drawer, tablet, TV mode (Part 44)

- Mic permission UX — getUserMedia preflight + state badge (Part 44)

- TV user-agent detection with larger fonts + focus outlines (Part 44)



- url_metadata tool (Part 78) — OpenGraph / Twitter Card / favicon extractor

- html_to_text tool (Part 78) — HTML -> clean markdown (structure preserved)

- data_quality_report tool (Part 80) — nulls/outliers/dups on CSV/XLSX

- schedule_add/list/delete/run_now (Part 81) — recurring agent prompts

  (Neon: dynamic_schedules; auto-registered on app start)

- metrics_batch tool (Part 82 + 85a) — 20+ ratios for 25 series per call

  (numpy engine; empyrical-reloaded BUILD_ERROR reverted)

- webhook receiver (Part 83) — POST /webhook/{token} external triggers

  (Neon: webhook_endpoints + webhook_events; 4 tools)

- sql_sandbox (Part 84) — isolated sb_<name> schemas for ad-hoc SQL

  (Part 84-fix: explicit transaction for SET LOCAL; blocks DROP SCHEMA,

   cross-schema reads, main tables)

- RESEND PRODUCTION (Part 86) — shamiur.com verified via DKIM

  (noreply@shamiur.com sends to ANY recipient; verified end-to-end)

- Token budget raised (Part 87) — max_tokens 900 -> 2048 in llm.py.
  Reasoning models (gpt-oss-120b) were consuming the entire 900-token
  budget on hidden reasoning after a tool call, leaving nothing for
  the visible answer (symptom: empty content).
- Orchestrator token economy (Parts 88, 88b, 88c, 88d):
  • MAX_ITERATIONS 7 -> 3 (was 6 LLM calls for "hi")
  • System prompt rule 1: greetings/chit-chat answer directly, no tools
  • System prompt rule 3: ONE TOOL PER STEP; never repeat same tool
  • System prompt rule 3a: NO PREFLIGHT LISTS when resource is named
  • echo tool description marked TEST-ONLY (was inviting abuse)
  • Tool-call dedup: (tool_name, canonical_args) tracked in _seen_calls
  • Subset/superset match: {name,sql} vs {sql} treated as duplicate
  • Hard-stop after 2 consecutive duplicates with cached answer
  • Applied to both native tool-call path AND prompt-JSON path
  Combined effect: 10-50x reduction in tokens per typical prompt.
  Greeting: 6 iterations/~10k tokens -> 1 iteration/~200 tokens.
  SQL query: 7 iterations/3 calls -> 2 iterations/1 call.
- Self-hosted marked.js (Part 89) — no more CDN dependency:
  • marked@12 -> src/sunnyware/static/marked.min.js (35 KB)
  • src/sunnyware/static/__init__.py makes static/ a shippable package
  • main.py: /static mounted via FastAPI StaticFiles (after include_router)
  • webui.py: <script src="/static/marked.min.js"> (was cdn.jsdelivr.net)
  • Fixes '(empty response)' in InPrivate Firefox when tracking
    protection + VPN blocked the jsdelivr CDN
  • Verified live: HTTP 200 | 35479 bytes | uvicorn; 0 CDN refs in src/
  • InPrivate Firefox loads clean (0 Console errors) + chat works
  • Smoke test: scripts/smoke_test_part89.py (8 checks, ASCII-safe)
- Per-request token budget guard (Part 90 + 90b):
  • MAX_REQUEST_TOKENS = 8000 (top of orchestrator.py)
  • _estimate_tokens(*parts): ~4 chars/token, provider-agnostic
  • _tokens_used accumulator incremented each LLM iteration
  • Trips at cumulative >= 8000 -> friendly message + break
  • Response flags: budget_exceeded: True, tokens_used: N
  • SSE event type 'budget_exceeded' emitted to WebUI
  • tools_schema (~8700 tokens for 58 tools) EXCLUDED from count
    (Part 90b - otherwise every request tripped on 'hi')
  • routes/agent.py propagates both flags to the client
  • Smoke test: scripts/smoke_test_part90.py (11 checks)
- WebUI budget_exceeded styling (Part 91):
  • budgetExceeded flag declared per-request in streaming handler
  • SSE case for 'budget_exceeded' event type
  • Reads data.budget_exceeded from 'final' event as fallback
  • Applies class 'budget' to assistant bubble
  • CSS .msg.agent.budget: amber bg + left border #ffb020
  • ::before prefix 'BUDGET LIMIT:' (ASCII-only, cp1252 safe)
  • Verified live: 90k-char prompt renders amber bubble with label
  • Smoke test: scripts/smoke_test_part91.py (8 checks)
- Professional HTML /about page (Parts 92, 92b, 92c):
  • Was raw JSON dump -> now styled HTML matching WebUI dark theme
  • src/sunnyware/static/about.html (7.6 KB, inline CSS, no CDN)
  • Hero with gradient S mark, version + license badges, 4-card grid
  • Responsive: 4 cards desktop -> stacked mobile
  • meta.py /about returns HTMLResponse with %%KEY%% substitution
  • Part 92b: fixed HF crash (missing top-level HTMLResponse import)
  • Part 92c: smoke test AST-verifies top-level import (not substring)
  • Smoke test: scripts/smoke_test_part92.py (20 checks)
- Professional WebUI redesign (Parts 93, 93b, 94, 95, 95b):
  • Part 93: header redesign — gradient S brand mark, session pill
    with green dot, icon buttons, overflow dropdown menu
  • Part 93b: paperclip moved INSIDE composer (ChatGPT-style),
    input padding-left 46px, id='upload' preserved
  • Part 94: doc count badge = just the number (15px circle),
    no 'docs: N' label; overflow button always visible
  • Part 95: overflow menu moved to sidebar bottom-left, opens
    UPWARD ('⚙ Settings & more'); header stripped to just
    provider pill; removed redundant + and ... from header
  • Part 95b: null-safe clearBtn lookup (JS crash fix)
  • Full SVG icons, no CDN, no emoji
  • Responsive: brand name hides <760px, session pill <480px,
    menu label hides <640px
  • Smoke test: scripts/smoke_test_part93.py (52 checks)
- Real token counts from provider usage (Part 96 + 96b):
  • llm.py now returns tokens_in / tokens_out / tokens_total
    (was only written to usage DB, not passed to orchestrator)
  • orchestrator prefers result['tokens_total'] over the
    char/4 heuristic; subtracts _tools_overhead (schema size)
  • fallback heuristic no longer double-counts 'prompt'
  • Part 96b: MAX_REQUEST_TOKENS 8000 -> 15000 (accurate counts
    make 8000 too tight; 12k-char prompt tripped at 10,022 real)
  • Verified: 12k prompt -> tokens_used 10022, budget_exceeded True
  • Smoke test: scripts/smoke_test_part96.py (13 checks)
- Pollinations AI fallback provider (Parts 97 + 97b):
  • 4th provider after groq, gemini, openrouter
  • Free anonymous tier, no API key (dummy 'pollinations')
  • Base URL: https://text.pollinations.ai/openai (OpenAI-compat)
  • Model: 'openai' (GPT-OSS-20b class) with fallbacks
    (gemini, mistral, deepseek, llama)
  • Rate limit: 1 req/15s anonymous — last-resort fallback only
  • Files: model_resolver.py PREFERENCES, .env.example
  • HF Space secrets: LLM_PROVIDERS (variable, not secret!),
    POLLINATIONS_BASE_URL / API_KEY / MODEL
  • Gotcha: LLM_PROVIDERS must be a VARIABLE not SECRET on HF
    (collision error 'Collision on variables and secrets names')
  • Verified live: 'POLLINATIONS WORKS' returned with
    provider=pollinations, iterations=1
  • Smoke test: scripts/smoke_test_part97.py (10 checks)
- Image generation tool (Parts 98 + 98b + 98c):
  • New tool: image_generate — free text-to-image via Pollinations.AI
  • Returns {image_base64, image_format, ...} — same contract as
    chart_from_data
  • Models: flux (default), turbo, gptimage, qwen-image, kontext,
    nanobanana (free tier)
  • Parameters: prompt, model, width, height, seed
  • Size clamp: 128-2048px (default 1024), 45s timeout, 2 MB cap
  • Magic-byte detection: JPEG / PNG / WebP
  • Part 98b: 'call EXACTLY ONCE' instruction (free tier 1/15s limit)
  • Part 98c: WebUI 'tool_result' SSE case renders image_base64 inline
    as <img class='msg-image'> — works for image_generate,
    chart_from_data, browser_screenshot (any tool returning image_base64)
  • Part 98c: tool description says 'Do NOT include base64 in reply'
  • Tools: 58 -> 59
  • Verified live: 'Draw a cute orange cat' -> 52 KB JPEG rendered inline
  • Smoke test: scripts/smoke_test_part98.py (24 checks)
- Long-prompt routing (Part 99):
  • Per-provider max_prompt_tokens field on Provider dataclass
  • Defaults: groq=7500, gemini=1M, openrouter/pollinations=32000,
    mistral=32000, nvidia=8000, local=0 (no limit)
  • Override per-provider via {PREFIX}_MAX_PROMPT_TOKENS env
  • llm.py: _estimate_prompt_tokens() char/4 heuristic over
    prompt + system + history
  • Router skips providers where estimated tokens > their limit
  • Safety: if NO provider eligible, tries all anyway (avoid total fail)
  • status() exposes max_prompt_tokens for each provider
  • Fixes earlier 'empty LLM response' on 30k-char prompts
  • Verified live: 30k chars -> openrouter (Groq auto-skipped)
  • Smoke test: scripts/smoke_test_part99.py (17 checks)
- Auto-learn provider limits (Parts 100 + 100b):
  • New module: src/sunnyware/provider_limits.py
  • On 413 (or 'request too large'), learns actual limit from
    tokens just sent — steps down 200, clamps to 500 minimum
  • Never raises an existing lower limit
  • Storage path (Part 100b):
    1. SUNNYWARE_DATA_DIR env (explicit override)
    2. /data HF persistent bucket — POSIX only (os.name == 'posix')
    3. ./data (local dev)
  • Persists to provider_limits.json — verified surviving HF restart
  • Precedence: env override > learned < default (uses tighter)
  • llm.py: _is_too_large_error() detects 413, 'request too large',
    'payload too large', 'context length', 'maximum context',
    'too many tokens'
  • Part 100b: observable writes (returns bool, logs failures)
  • Debug endpoints:
    GET  /api/providers/limits         — diagnostics
    POST /api/providers/limits/reset   — {name: 'groq'} or {all: true}
  • Verified live: learned={'groq': 8403} persisted at
    /data/provider_limits.json on HF
  • Smoke test: scripts/smoke_test_part100.py (44 checks)
- Empty-response fallback (Part 101):
  • llm.py: _is_empty_response(r) detects ok=True with no content
    AND no tool_calls
  • Both HTTP and local provider paths treat empty as failure:
    record failure, cooldown (15s HTTP / 10s local), metric
    llm_provider_empty_response, continue to next provider
  • Safety: only triggers when BOTH content and tool_calls are empty
    — when LLM makes a tool call, check returns False
  • Fixes 'Agent failed | empty LLM response' when a provider
    returned success HTTP with hollow body
  • Verified live: 30k prompt -> openrouter -> 3,850-char real answer
  • Smoke test: scripts/smoke_test_part101.py (22 checks)
- Retry policy for full failover cycle (Part 102):
  • llm.py: after the failover loop, if _retry_depth == 0
  • Reload providers to see fresh cooldown state
  • If NO provider is ready AND soonest cooldown <= 20s:
    wait min(min_cool + 0.5, 8.0)s then recurse once with
    _retry_depth=1
  • Guard ensures exactly ONE retry (no infinite loop)
  • Wait capped at 8s to never stall an interactive request
  • Metric llm_request_retried + diagnostic print lines
  • Only fires when ALL providers cooling AND recovery imminent
    — if any provider is ready, first pass used it
  • Smoke test: scripts/smoke_test_part102.py (18 checks)
- Provider health metrics dashboard (Part 103):
  • New endpoint: GET /api/providers/metrics
  • Aggregates three sources:
    1. Session stats (per-process): success/fail counts,
       success_rate, cooldowns, last_error, last_success_ts
    2. Lifetime counters (persistent via metrics.py / Neon):
       attempts, empty-responses, learned-limits, retries
    3. Storage diagnostics (from provider_limits)
  • _sum_prefix() helper auto-includes future labeled counters
  • Verified live: groq learned=8403 but max_pt=7500 (tighter wins)
  • Smoke test: scripts/smoke_test_part103.py (33 checks)
- WebUI provider health panel (Part 104):
  • Renders /api/providers/metrics inside the Stats modal
  • Modal renamed: 'Stats & Provider Health'
  • Table: Provider | Model | Status(dot) | Success Rate
  • Summary: N providers | N ready | N cooling | session rate
  • Footer: storage source + learned limits + lifetime counters
  • Auto-refresh every 10s while modal open (clears on close)
  • New .ph-* CSS classes matching existing dark theme
  • Smoke test: scripts/smoke_test_part104.py (36 checks)
- Per-message provider chip (Part 105):
  • Small 'via groq · 1.2s' chip appears under each
    assistant bubble in chat
  • Tracks lastProvider per-request (reset each sendMessage)
  • Set from data.provider in both 'final' and 'done' SSE events
  • Appended via agentBubble.insertAdjacentElement('afterend', chip)
  • CSS .provider-chip: 11px muted, aligned with agent padding
  • Failover chain now visible message-by-message
  • Smoke test: scripts/smoke_test_part105.py (18 checks)
- Persistent image attachments (Parts 106, 106b, 106c, 106d):
  • New module: src/sunnyware/attachments.py
  • save_base64(b64, ext) -> {id, ext, url, bytes}
  • Storage: SUNNYWARE_DATA_DIR/attachments > /data/attachments
    (POSIX) > ./data/attachments
  • Serving: GET /api/attachments/{att_id}.{ext} (immutable cache)
  • Diagnostics: GET /api/attachments/stats
  • image_generate + chart_from_data save base64 to disk
  • Orchestrator collects attachment URLs from tool results
    (native + prompt-json paths) and returns them in ALL success
    paths (10 return sites)
  • routes/agent.py: _strip_broken_b64_md() removes unusable
    '![..](data:image/..,base64,[image: N bytes base64])' markdown
    before saving to history
  • WebUI: loadSession renders <img class='msg-image'> from
    stored attachments; sendMessage persists to localStorage
  • Part 106d: handles empty-text case (LLM returns nothing after
    tool call) by forcing ensureBubble + placeholder text
  • Verified: image survives browser refresh + session navigation
  • Smoke test: scripts/smoke_test_part106.py (38 checks)
- Financial data tools for FP&A and quant roles (Parts 107-109):
  • edgar_fundamentals: SEC EDGAR XBRL (no key, authoritative US filings)
    — /companyfacts endpoint (ONE request returns all tags)
    — UA format: '<Company Name> <email>' (no version, no parens)
    — Verified: Apple Inc., FY2025 revenue $416.16B, net $112.01B
  • fred_economic: FRED macro (free key, 120 req/min)
    — 800k+ series: GDP, CPI, unemployment, treasury yields
    — 'popular' preset + search + series observations
  • finnhub_quote: Quotes + news + earnings (free key, 60/min)
    — quote, profile, company_news, market_news, earnings, metrics
  • tiingo_prices: 9-year daily + intraday (free key, 1000/day)
    — eod (uses /daily/{sym}/prices), intraday, meta
  • marketaux_news: News + sentiment (free key, 100 req/day)
    — entity tagging, sentiment scores, 80+ markets
  • twelvedata_prices: Multi-asset (free key, 800/day)
    — stocks, forex, crypto; quote, time_series, rsi, macd
  • fmp_fundamentals: /stable/ API (v3 legacy retired Sept 2025)
    — quote, profile, income, balance, cashflow, ratios, metrics, dcf
    — symbol is query param (?symbol=AAPL) not path segment
  • Shared helper: _financial_http.py (retry + cache + env checks)
  • Tools: 59 -> 66
  • All 7 API keys on HF Space secrets (FRED, FINNHUB, TIINGO,
    MARKETAUX, TWELVEDATA, FMP, SEC_USER_AGENT)
  • Smoke test: scripts/smoke_test_part107.py (73 checks)
- Actuarial / insurance / risk libraries (Part 111):
  • chainladder 0.10.1, lifelib 0.17.2, solvency2-data 0.5.0
  • All in requirements.txt + python_eval sandbox allowlist
  • haute rejected (Py3.11+ only)
  • chainladder IBNR on RAA verified = 52,135.23 on HF
  • Smoke test: scripts/smoke_test_part111.py (11 checks)
- Role personas with per-role tool subsetting (Part 112):
  • New module src/sunnyware/roles.py defines 5 roles:
    — general   (all 67 tools, no addon)
    — fpa       FP&A Analyst     12 tools, statements/ratios/forecasting
    — quant     Quant Researcher  12 tools, time series/backtests/options
    — actuary   Actuarial Analyst 10 tools, chainladder/lifelib/solvency2
    — tax       Tax Accountant    10 tools, filings/insider/RFR
  • Tool filtering: prefix-based (e.g. edgar_*, fmp_*) + curated extras
  • Per-role prompt addon prepended to system prompt (persona + guidance)
  • Saves ~4-6K tokens/request in non-general roles; improves tool pick
  • Backend: orchestrator._build_tools_schema(role), run_agent(role=...)
  • API: both /api/agent/run and /api/agent/stream accept 'role' field
  • New endpoint: GET /api/roles — returns {roles:[{key,label,icon}],default}
  • WebUI: <select id="roleSelect"> in header-right, persists to
    localStorage ('sunnyware.role'), synced from /api/roles on boot
  • Smoke test: scripts/smoke_test_part112.py (28 checks)
  • WebUI is served at /ui (chat UI); / returns metadata JSON
- Per-session role persistence (Part 113A):
  • sessions.py: set_role(session_key, role) + get_role(session_key)
    — role stored in existing metadata JSONB column (no migration)
  • routes/sessions.py:
    — GET /api/sessions/{key}/role  -> {"role": "actuary"} or "general"
    — PUT /api/sessions/{key}/role  -> {role}, validated, 400 on unknown
  • routes/agent.py: /run + /stream persist role to session on send
  • roles.py: canonical() now public alias
  • WebUI:
    — persistRoleToSession() PUTs on selector change
    — syncRoleFromSession(id) reads role on session open
    — loadSession + loadSessionWithFallback hook the sync
  • Behavior: switching Actuary on chat A stores actuary on A;
    opening chat B restores B's own role (or general)
  • Smoke test: scripts/smoke_test_part113a.py (18 checks)
- Role-specific result rendering (Part 113B):
  • roles.py: style(role) helper — per-role accent color + chip label
    — general #8899aa  fpa #4a90e2  quant #a855f7
    — actuary #10b981  tax #f59e0b
  • routes/agent.py /stream: 'start' event now includes role + accent + chip
  • routes/agent.py /run: response includes role
  • WebUI:
    — #chat[data-role="X"] CSS rules set agent-bubble border-left accent
    — role chip via .msg.agent::before (e.g. 📊 FP&A, 🧮 QUANT)
    — orchestrator._emit start event carries role + accent + chip
    — agent_stream reads role from body + passes to orchestrator
    — SSE handler reads data.role + data.accent from start event
    — initRoleSelector sets chat.dataset.role on boot
    — persistRoleToSession + syncRoleFromSession keep it in sync
  • Session-level styling: switching role re-colors whole chat (old + new msgs)
  • Smoke test: scripts/smoke_test_part113b.py (25 checks)
- Options-cache TTL differentiation (Part 113C):
  • _financial_http.py: cache_stats() + cache_clear() helpers
    — cache_stats: {total_keys, live_keys, expired_keys, default_ttl}
    — cache_clear: wipe the in-memory cache (admin escape hatch)
  • eulerpool_data.py: per-action TTL table (_TTL_OVERRIDES)
    — options_greeks/chain/iv/flow → 60s (live derivatives)
    — candles                     → 300s
    — profile/overview/dividends/esg/analyst_grades → 24h
    — everything else              → 1h (default _TTL)
  • eulerpool_data.py: metrics hooks
    — eulerpool_cache_hit_<action>   (labeled)
    — eulerpool_cache_miss_<action>  (labeled)
    — eulerpool_api_calls_total
  • routes/meta.py: NEW endpoints
    — GET  /api/cache/stats — cache + per-action hit rates
    — POST /api/cache/clear — wipe cache, returns count
  • Effect: 2nd options_greeks call within 60s is instant (0 API quota)
  • Smoke test: scripts/smoke_test_part113c.py (24 checks)
- Insurance data sources (Part 113D):
  • New tool: tools/insurance_data.py (68th tool)
    — Socrata open-data APIs — NO API key required
    — 8 state DOI portals: TX TDI, NY DFS, CT, WA, IL, CO, OR, VT
    — actions: states, discover, inspect, fetch
    — returns datasets, column metadata, raw rows
  • Registry: tools/__init__.py imports + registers InsuranceDataTool
  • Roles: actuary tool_prefixes now include insurance_
    — actuary active tools: 11 (was 10)
    — actuary prompt addon mentions insurance_data usage
  • Cache: discovery 24h, inspect 24h, fetch 1h (via existing cache_get/set)
  • Smoke test: scripts/smoke_test_part113d.py (20 checks)
- CFO + CDO supervisor hierarchy (Part 114):
  • New tool: delegate_to_agent (69th tool)
    — contextvars track current role / depth / path (async-safe)
    — max depth 3 (CFO → CDO → worker), cycle detection by path
  • New roles:
    — cfo (Chief Financial Officer)  accent #8b5cf6, chip 💼 CFO
    — cdo (Chief Delivery Officer)   accent #06b6d4, chip 📋 CDO
  • Delegation matrix (enforced in roles.py):
    — cfo → {cdo}
    — cdo → {actuary, quant, fpa, tax, general}
    — workers → nothing
  • orchestrator.run_agent wrapped to set role contextvar (nested calls)
  • routes/agent.py extends timeout to 300s for cfo + cdo roles
  • WebUI: CFO + CDO in role dropdown; borders + chips
  • Bonus fix: Part 113B chip emoji were literal \U escapes in CSS
    (never rendered) — replaced with real emoji bytes
  • Smoke test: scripts/smoke_test_part114.py (50 checks)
  • Part 114b-e: pipeline hardening (5 commits)",
  "    — 114b: trimmed CFO tools (rag_search, list_files, write_file,",
  "      calculator removed); MANDATORY-first-action prompt",
  "    — 114c: CDO tools 6→2 (delegate_to_agent + read_file only);",
  "      CDO prompt hardened; timeout 300s→600s for cfo/cdo roles",
  "    — 114d: compact_prompt(allowed_tools=...) enforces role subset",
  "      on the default (non-native-tools) path; orchestrator guards",
  "      _execute_tool to reject out-of-role tool calls",
  "    — 114e: STRICT PIPELINE RULE in CFO prompt overrides the base",
  "      'answer simple questions directly' clause — every user request",
  "      goes through delegate_to_agent(cdo), no exceptions",
  "    — VERIFIED live: '15% of $2400' → 1 delegation to CDO → '360'",
  "      in 12.3s, no local calculator/rag_search abuse
- UI + role tooling (Parts 115–117):
  • Part 115 — role-specific content styling (22 checks)
    — CSS per role on tables / code / list markers / headings
    — FP&A blue, Quant purple, Actuary emerald, Tax amber,
      CFO violet, CDO cyan
  • Part 116 — role config export/import (25 checks)
    — GET /api/roles/export  → shareable JSON snapshot
    — POST /api/roles/import → validated (version, keys, fields)
    — export_roles() / import_roles() helpers in roles.py
  • Part 117 — insurance_research tool (70th tool, 23 checks)
- Multi-platform feature roadmap (Parts 119–128):
  • 10 features from verified high-value platforms, all shipped:
    1. 119 — agent monitoring dashboard (runs/success/failure/latency)
    2. 120 — save-as-script on python_eval (Bloomberg BQL-style)
    3. 121 — lexicon sentiment on filings (AlphaSense-style)
    4. 122 — workflow registry (Bloomberg ASKB-style)
    5. 123 — interactive Plotly charts in chat (Kensho MCP Apps)
    6. 124 — narrate_table (Hebbia Matrix-style)
    7. 125 — research_search (edgar+fred+govcon parallel)
    8. 126 — document_library (Bloomberg Drive-style)
    9. 127 — earnings_call transcript summarizer
    10. 128 — clause_extractor (Hebbia ISD-style)
- Specialist sub-agents + risk computation (Phase A + C-2):
  • Phase A — two new roles added to the supervisor hierarchy:
    — legal    Financial Legal Assistant   slate #64748b  chip LEGAL
    — risk_ins Financial Risk & Insurance  red   #ef4444  chip RISK/INS
  • legal (14 tools): clause_extractor, research_search,
    document_library, narrate_table, earnings_call, python_eval,
    sql_sandbox_execute, read/write/list, rag_search, web_search,
    calculator, delegate_to_agent
  • risk_ins (22 tools): python_eval, risk_metrics, sql_sandbox,
    duckdb_query, insurance_research, insurance_data, govcon_data,
    research_search, narrate_table, clause_extractor,
    earnings_call, + tiingo/twelvedata/fred/finnhub/edgar/eulerpool
  • Delegation: cdo → {actuary, quant, fpa, tax, general, legal, risk_ins}
    cfo → {cdo}  (unchanged)  |  legal, risk_ins → {} (workers)
  • Aliases: attorney/counsel/compliance → legal;
    risk/insurance_risk/investment_risk → risk_ins
  • Compliance baked into prompts: legal has [PRIVILEGED] markers
    + no-legal-advice disclaimer + citation verification; risk_ins
    requires methodology + confidence + holding period + human
    sign-off flagging + no autonomous execution
  • Phase C-2 — new tool #79 risk_metrics (pure numpy/scipy):
    — 12 actions: summary, var (historical/parametric/MC), cvar,
      volatility, sharpe, sortino, drawdown, calmar, stress_test,
      correlation, beta, from_prices
    — Every result carries a 'methodology' field (audit-ready)
    — Monte Carlo reproducible (seed=42)
    — Assigned to risk_ins + quant roles
  • VERIFIED live on HF:
    — 9 roles in /api/roles
    — Legal answered indemnification vs liability distinction
    — risk_ins computed VaR/Sharpe via risk_metrics end-to-end
  • Zero changes to orchestrator.py or delegate_to_agent.py
  • Smoke tests: 129 (48/48), 130 (47/47)
  • Tools: 71 → 78 (+7 new tools)
  • New endpoints:
    — GET  /api/agents/metrics
    — GET  /api/cache/stats
    — POST /api/cache/clear
  • WebUI: Plotly CDN + auto-render pipeline
  • Roles updated: fpa, actuary, cfo, tax gain new tools
  • All zero-LLM, zero-network (pure Python) except 119/123
    which only instrument existing paths — no new LLM calls
    — honest reframe: NAIC (404) + AmericasSuretyBonds (403)
      had no public APIs, so we shipped real verified sources
    — SEC EDGAR full-text: https://efts.sec.gov/LATEST/search-index
      query='IBNR' forms='10-K' returned 2,082 real filings
    — SEC EDGAR submissions by CIK: data.sec.gov/submissions/
    — FRED search + observations (existing FRED_API_KEY)
      'health' insurance query returned 4,330 real series
    — CCSA (insured unemployment) = 1.71M, 2026-10-03
    — actuary role now includes insurance_research
  • Part 118 — govcon_data tool (71st tool, 20 checks)
    — honest replacement for SAM.gov plan (no OTP delivery)
    — source: USAspending.gov API v2 (Treasury, keyless)
    — actions: award_search / recipient_search /
      spending_by_category
    — VERIFIED live on HF:
      award_search NAICS 524126 → real P&C insurer contracts
      recipient_search 'American International Group' → real UEIs
      spending_by_category naics → Direct Health & Medical
      Insurance = $48.5B in federal contracts
    — cfo role extra_tools now include govcon_data
- Eulerpool multi-source data (Part 110) — 8th financial data source:
  • New tool: eulerpool_data — curated 70-endpoint wrapper over
    Eulerpool's 447-endpoint API
  • NEW capabilities (not in any other tool):
    — Bonds / Treasury yields / interest rate spreads
    — Fixed income analytics / spot & forward curves
    — Options chains / Greeks / IV surface / flow
    — 13F institutional holdings (per ticker + per CIK)
    — Superinvestor tracking (holdings, recent activity, top)
    — Congressional trading (STOCK Act)
    — Insider trades (Form 4) + insider sentiment
    — Economic calendar (macro, earnings, dividends, IPO, M&A)
    — Google Trends / Reddit / Fear & Greed / Wikipedia views
    — Commodity prices + futures curves
    — Crypto global stats + candles + fear/greed
    — Risk models (covariance, factors, portfolio risk)
    — Fama-French factors + CFTC COT
    — Earnings call transcripts
  • SUPPLEMENTS: FRED/IMF/BIS/ECB/Eurostat/World Bank via same key
  • Single unified tool: action + optional identifier + optional params
  • 1-hour TTL cache to preserve free tier budget
  • Verified live: 10/10 actions return real data on HF
  • Tools: 66 -> 67
  • EULERPOOL_API_KEY on HF Space secrets


### RAG over documents

- Upload: /api/rag/upload (PDF/DOCX/CSV/XLSX/TXT/MD; 20 MB max; multi-file)

- Retrieval: /api/rag/query (with optional FP&A narrative via LLM)

- Page-level citations for PDFs

- XLSX extractor: title-row tolerant + formula fallback + raw-cell dump



### Data science workbench (python_eval)

- Preloaded: np, pd, plt, sns, scipy, stats, sklearn, sqlite3, duckdb,

  sql_on, pa, openpyxl, tabulate, Path, ws_path

- Sandboxed: no os/subprocess/socket/network; workspace-jailed

- Inline matplotlib charts returned as base64 in responses



## Pre-push workflow (DevSecOps gate)

Before every commit + push, run:

    python scripts/pre_push_check.py

5 stages: syntax, HTML/JS sanity, latest part smoke test, git tree, live HF.

Exit 0 = READY TO PUSH.
When running pre_push_check.py, if HF push times out, retry
  ./push_hf.sh standalone — the GitHub push already succeeded.



## What's next (priority order)
1. Monitor the 80-tool stack + 9-role supervisor pipeline in production.
2. NVIDIA NIM integration — WAITING on user to activate account.
3. Future: add Phase A + roadmap tools to remaining roles (general)
   for full symmetry.
4. Future: legal/risk_ins metrics in /api/agents/metrics — they
   automatically appear since Part 119 instruments every run_agent.
5. Future: expand legal_citation_check actions (get_cluster detail,
   cited_by graph) if the free tier proves sufficient.
3. Future: NAIC Content JSON:API + AmericasSuretyBonds MCP (6,900+ bonds)
   — additional insurance sources beyond the state-DOI Socrata portals
   shipped in Part 113D.
4. Future: per-role result-rendering defaults (FP&A → tables,
   Quant → charts, Actuary → assumption blocks).
5. Future: role selection import/export — save a role's tool subset
   to a shareable JSON so teams can standardize workflows.

## Key files

- src/sunnyware/main.py                FastAPI app + lifespan + preload

- src/sunnyware/orchestrator.py        ReAct loop + tool aliases + retries

- src/sunnyware/llm.py                 2-layer router (chat + _chat_single)

- src/sunnyware/providers.py           Multi-provider registry + cooldown

- src/sunnyware/model_resolver.py      Auto-detect available models

- src/sunnyware/memory.py              Event log (payloads capped at 2000)

- src/sunnyware/prompts.py             Directive system prompt (7 rules)

- src/sunnyware/webui.py               Custom HTML/JS chat UI (markdown)

- src/sunnyware/routes/rag.py          /api/rag/* endpoints

- src/sunnyware/routes/sessions.py     /api/sessions/* endpoints

- src/sunnyware/routes/meta.py         /health/* + /api/providers/*

- src/sunnyware/routes/agent.py        /api/agent/run[/stream]

- src/sunnyware/rag/                   RAG package (7 modules)

- src/sunnyware/tools/                 Agent tools (16 total)



## Key scripts

- scripts/pre_push_check.py            Master DevSecOps gate (5 stages)

- scripts/system_monitor.py            System health snapshot + baseline

- scripts/smoke_test_part63.py         31 checks (browser tools)

- scripts/smoke_test_part62.py         35 checks (excel_read)

- scripts/smoke_test_part61.py         29 checks (excel_write)

- scripts/smoke_test_part60.py         25 checks (workspace_snapshot)

- scripts/smoke_test_part59.py         21 checks (pdf_report)

- scripts/smoke_test_part58.py         29 checks (document_diff)

- scripts/smoke_test_part57.py         14 checks (streaming fallback)

- scripts/smoke_test_part56.py         33 checks (api_call)

- scripts/smoke_test_part55.py         30 checks (financial_metrics)

- scripts/smoke_test_part53.py         27 checks (forecast_arima)

- scripts/smoke_test_part52.py         13 checks (citation_lookup)

- scripts/smoke_test_part51.py         22 checks (chart_from_data)

- scripts/smoke_test_part50.py         19 checks (csv_query)

- scripts/smoke_test_part49.py         16 checks (recall_history)

- scripts/smoke_test_part48.py          9 checks (audit trail)

- scripts/smoke_test_part47.py         14 checks (tool-aware streaming)

- scripts/smoke_test_part45.py         14 checks (/openapi.json fix)

- scripts/smoke_test_part44.py         26 checks (responsive + mic + TV)

- scripts/smoke_test_part43.py         24 checks (charts + rename + voice)

- scripts/smoke_test_part42.py         19 checks (markdown + provider badge)

- scripts/js_syntax_check.py           node --check on served JS (regression guard)

- scripts/smoke_test_part41.py         15 checks (monitor wrapper)

- scripts/probe_all_providers.py       Scan all provider /models endpoints



## Model selection (real mechanism)



Provider order — env LLM_PROVIDERS (comma-separated priority order).

  Current: groq,gemini,openrouter

  Config lives in: src/sunnyware/providers.py (load_providers)



Model per provider — env <NAME>_MODEL

  Groq:       openai/gpt-oss-120b    (Part 46 swap; llama-3.3-70b not in tier)

  Gemini:     gemini-2.5-flash

  OpenRouter: liquid/lfm-2.5-2.6b:free



Auto-resolver (src/sunnyware/model_resolver.py)

  - Probes /models on each provider (1h success cache, 5m failure cache)

  - Falls back to static PREFERENCES list if configured model gone

  - Env MODEL_AUTORESOLVE=0 to disable



No runtime latency racing. "Lowest ping" was a manual config pick hardcoded

in .env. Dynamic latency-based selection does not exist today.



## Conventions

- Dual-remote deploy: git push origin main && ./push_hf.sh

- Every feature ships with scripts/smoke_test_partNN.py

- Commit style: "Part NN: short description"

- Prefer Python heredocs over bash heredocs

- When adding JS strings in webui.py HTML triple-quote:

  double the backslashes (\\n -> \\\\n) or Python interprets them

- Always run scripts/pre_push_check.py before push

- pre_push_check auto-discovers highest-numbered smoke_test_partNN.py



## Key gotchas (do not re-learn)

- /docs Schemas section shows 7 orphan Gradio Pydantic models

  (PredictBody, CancelBody, EstimationMessage, VibeCodeBody, etc).

  All 43 tools work. COSMETIC ONLY.

  TRUE ROOT CAUSE: `from gradio import Server` subclasses FastAPI

  and Gradio's Server overrides openapi() AT THE CLASS LEVEL. Python

  method resolution order means instance-level `app.openapi = ...`

  and route overrides and ASGI middleware all lose to the class method.

  FIX ATTEMPTS (all failed on live, succeeded locally):

    Part 77:      ref-based schema whitelist (local only)

    Part 77-fix:  cache-aware override  (local only)

    Part 77d:     /openapi.json route re-registration (local only)

    Part 79:      ASGI middleware (local only — Gradio's response wins)

  WON'''T FIX without replacing Gradio Server with our own subclass —

  major refactor, risk to /ui endpoint. Status: accepted limitation.

- qwen/qwen3.8-27b (Groq, retired Part 46): reasoning models do not reliably

  call tools + hit 7000 ITPM rate limit. Do NOT re-enable as primary.

- Token budget is TIGHT for reasoning models. gpt-oss-120b consumes
  its entire max_tokens on hidden reasoning before emitting visible
  content. If a tool call is followed by an empty answer, first check
  that max_tokens >= 2048 in llm.py. Part 87 raised it from 900.
- LLM WILL re-call the same tool with slightly different args (e.g.
  dropping 'name' from {name, sql}). Exact-hash dedup misses this.
  Use subset/superset matching in orchestrator._find_duplicate().
  Part 88c installed this; keep it in mind if you change tool schemas.
- LLM WILL call sql_sandbox_list / list_files as a preflight even
  when the user named the resource. Rule 3a in prompts.py tells it
  not to. If you see extra iterations, check rule 3a survived edits.
- ALL frontend deps are SELF-HOSTED (Part 89). marked.js lives at
  src/sunnyware/static/marked.min.js and serves from /static/marked.min.js
  via StaticFiles mount in main.py. DO NOT re-add CDN <script src> tags.
  New frontend dep: download to src/sunnyware/static/ + reference /static/<file>.
- If '(empty response)' reappears: check browser Console for blocked
  network requests. Pre-Part-89 it was InPrivate tracking protection +
  VPN blocking cdn.jsdelivr.net; now it would mean /static/marked.min.js
  is not served (check main.py mount + restart).
- Token budget guard (Part 90) trips at 8000 estimated tokens. The
  estimate is char-based (~4 chars/token) and deliberately over-counts
  long prompts (counts prompt twice: once as 'prompt', once inside
  'messages'). Safe direction — never trips late. tools_schema is
  EXCLUDED: 58 tool definitions = ~8700 tokens of fixed infra cost;
  including them tripped every request. DO NOT re-add tools_schema
  to the estimator without raising MAX_REQUEST_TOKENS to 20000+.
- Memory payloads capped at 2000 chars (Groq TPM 413 protection)

- Tool-result truncation in orchestrator: strips base64 + caps at 500 chars

- Tool-name aliases: python -> python_eval, rag -> rag_search

- Placeholder retry: if model returns "What next?" after tool call, retry

- polars is REMOVED (requires AVX2/FMA; crashes on 3rd-gen i7)

- Local GGUF not viable on HF 2 vCPU (502 timeout)

- HF Space rebuild: ~1 min code, ~10 min if requirements.txt changes

- JS escape bug: Python triple-quoted HTML strings interpret \\n as newline

- HTML gate false-positive on regex char-classes: use charCode approach

- Emoji in heredocs: use chr(0xHEX) not literal emoji (MINGW mangles UTF-8)

- forecast_arima explicit order=(p,d,q) with d>0 uses trend='n'

  (statsmodels rejects trend='c' when d>0). Auto-order path prefers

  trend='t' when a linear trend is detected (|r|>0.55).

- NEVER use regex literals inside Python triple-quoted HTML:

  Python's escaping mangles them and breaks the served JS parser.

  Use string-based scanners instead (see wrapBareBase64 in webui.py).

- scripts/js_syntax_check.py runs `node --check` on served JS.

  Must pass before push (wired into pre_push_check.py stage 2b).



## Full docs in repo (fetch or ask owner to paste)

- HANDOFF.md  — detailed state + full queue

- AGENTS.md   — architecture + briefing for AI assistants

- WORKFLOW.md — dual-remote workflow + per-part progress log



## Session-end ritual

Ask the AI: "Update RESUME.md and HANDOFF.md with what we did, and give

me the exact git commands to commit + push both remotes."

