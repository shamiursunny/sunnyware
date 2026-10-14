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



## Current state (last session: 2026-10-15, Part 98c)

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
1. Monitor /api/providers/status over next few days — 429s should
   now be rare because of Parts 87-96b token economy fixes.
2. NVIDIA NIM integration — pending support verification
3. Future: secondary long-prompt path (Groq's 8k input limit rejects
   very large prompts; could route big-prompt requests to Gemini first)

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

