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

## Current state (last session: 2026-10-12, Part 63)
- Commit:  run `git log -1 --oneline` for current hash
- Health:  /health/ready -> status ok, tools: 33
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
- workspace_snapshot tool (Part 71) — zip workspace to retrievable archive
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

## What's next (priority order)
1. NVIDIA NIM integration — pending support verification
2. Part 64 — next feature (define together)
3. Optional: voice input, session rename, chart rendering polish

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
- qwen/qwen3.8-27b (Groq, retired Part 46): reasoning models do not reliably
  call tools + hit 7000 ITPM rate limit. Do NOT re-enable as primary.
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
