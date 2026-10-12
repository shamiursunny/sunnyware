# RESUME — Sunnyware (paste this into a new AI tab)

Copy everything below the line into a fresh chat, then ask any question.

---

## Project
Sunnyware — a FastAPI + custom HTML/JS WebUI AI agent running on a Hugging
Face Space. Multi-provider LLM router (Groq/Gemini/OpenRouter with auto
model resolver), ReAct orchestrator, 16 agent tools, RAG over uploaded
docs, sandboxed Python data-science workbench. PostgreSQL (Neon) stores
memory + sessions + historical chat. Now includes streaming SSE WebUI,
multi-session sidebar, JSON export/import, and a token usage dashboard.

## Live
- WebUI:   https://shamiur-sunnyware.hf.space/ui
- GitHub:  https://github.com/shamiursunny/sunnyware
- Space:   https://huggingface.co/spaces/shamiur/sunnyware

## Current state (last session: 2026-10-12)
- Commit:  run `git log -1 --oneline` in repo for current hash
- Health:  /health/ready -> status ok, tools: 16
- LLM:     multi-provider (groq,gemini,openrouter) with auto-failover
  - Groq:       openai/gpt-oss-20b (primary, ~200ms)
  - Gemini:     gemini-2.5-flash (backup, ~500ms)
  - OpenRouter: liquid/lfm-2.5-2.6b:free (backup, ~700ms)
  - Auto-resolver: /api/models/resolve (self-heals when providers retire models)
- Vector store: per-tenant FAISS in /data/vector_store/{org_id}/
- Neon DB:    PostgreSQL, 85+ sessions, 1000+ events logged
- Usage:      585+ LLM calls, 1.2M input tokens, 122k output, ~$0.24 cost

## What's working (verified live)

### Core features (Parts 32-40)
- Multi-provider LLM router with auto-failover
- Auto model resolver — self-heals when providers retire models
- 429 fast-fail (0.2s instead of 40s waste per broken provider)
- 16 agent tools including rag_search + python_eval workbench
- Streaming WebUI — tokens appear as generated via SSE (Part 34)
- Chat history persistence + sidebar with multi-session (Part 35)
- Multi-file upload (Part 36) — drag 10+ files at once
- Neon fallback for session history (Part 38) — browser-wipe proof
- JSON export/import for sessions (Part 39) — belt & suspenders
- Token usage dashboard (Part 40) — Stats button + modal
- WebUI `via <provider>` badge shows serving provider

### RAG over documents
- Upload: /api/rag/upload (PDF/DOCX/CSV/XLSX/TXT/MD; 20 MB max; multi-file)
- Retrieval: /api/rag/query (with optional FP&A narrative via LLM)
- Page-level citations for PDFs
- XLSX extractor: title-row tolerant + formula fallback + raw-cell dump
- Empty-file error includes diagnostics (blocks/rows/hint)

### Data science workbench (python_eval)
- Preloaded: np, pd, plt, sns, scipy, stats, sklearn, sqlite3, duckdb,
  sql_on, pa, openpyxl, tabulate, Path, ws_path
- Sandboxed: no os/subprocess/socket/network; workspace-jailed
- Inline matplotlib charts returned as base64 in responses
- DataFrame/Series results auto-converted to JSON records

## Pre-push workflow (DevSecOps gate)
Before every commit + push, run:
    python scripts/pre_push_check.py
It runs 5 stages:
  1. Python syntax check (all src/**/*.py)
  2. Served HTML/JS sanity (catches escape-bug pattern)
  3. Latest smoke_test_partNN.py (numbered PASS/FAIL checks)
  4. Git working-tree check (rejects secrets/junk)
  5. Live HF Space health (soft check)
Exit 0 = READY TO PUSH. Any failure = fix before pushing.

## What's next (priority order)
1. NVIDIA NIM integration — pending support verification (Bangladesh
   not in phone dropdown, manual verification requested)
2. Part 41 — next feature (define together)
3. Optional: voice input, markdown rendering polish, session rename

## Key files
- src/sunnyware/main.py                FastAPI app + lifespan + preload hooks
- src/sunnyware/orchestrator.py        ReAct loop + tool aliases + retries
- src/sunnyware/llm.py                 2-layer router (chat + _chat_single)
- src/sunnyware/providers.py           Multi-provider registry + cooldown
- src/sunnyware/model_resolver.py      Auto-detect available models
- src/sunnyware/memory.py              Event log (payload caps at 2000 chars)
- src/sunnyware/prompts.py             Directive system prompt (7 rules)
- src/sunnyware/webui.py               Custom HTML/JS chat UI
- src/sunnyware/routes/rag.py          /api/rag/* endpoints
- src/sunnyware/routes/sessions.py     /api/sessions/* endpoints
- src/sunnyware/routes/meta.py         /health/* + /api/providers/* + /api/models/*
- src/sunnyware/rag/                   RAG package (7 modules)
- src/sunnyware/tools/                 Agent tools (16 total)

## Key scripts
- scripts/pre_push_check.py            Master DevSecOps gate (5 stages)
- scripts/smoke_test_part39.py         13 checks (JSON export/import)
- scripts/smoke_test_part40.py         26 checks (usage dashboard)
- scripts/probe_all_providers.py       Scan all provider /models endpoints
- scripts/providers_smoke.py           Per-provider health test
- scripts/rag_smoke_test.py            RAG retrieval e2e
- scripts/rag_narrative_smoke.py       FP&A narrative via LLM

## Conventions
- Dual-remote deploy: git push origin main && ./push_hf.sh
- Every feature ships with scripts/smoke_test_partNN.py
- Commit style: "Part NN: short description"
- Prefer Python heredocs over bash heredocs
- When adding JS strings in webui.py HTML triple-quote:
  **double the backslashes** (\\n -> \\\\n in source) or Python interprets
  them as newlines and breaks the served JS
- Always run scripts/pre_push_check.py before push

## Key gotchas (do not re-learn)
- gpt-oss-20b is a REASONING model — needs max_tokens >= 900
- Memory payloads capped at 2000 chars to avoid Groq TPM 413 errors
- Tool-result truncation in orchestrator: strips base64 + caps at 500 chars
- Tool-name aliases: python -> python_eval, rag -> rag_search
- Placeholder retry: if model returns "What next?" after tool call, retry
- Chart base64 injection: replaces {{image_base64}} placeholder
- polars is REMOVED (requires AVX2/FMA; crashes on 3rd-gen i7)
- Local GGUF model (MiniCPM5-2B) on 2 vCPU: not viable (502 timeout)
- Groq qwen3.8-27b OTPM = 1000/min (tight); gpt-oss-20b has 8000 TPM
- HF Space rebuild: ~1 min code, ~10 min if requirements.txt changes
- JS escape bug: Python triple-quoted HTML strings interpret \\n -> real newline
- localStorage wipe: happens if user clears "Cookies and other site data"
  (not "Cached images and files") - use Ctrl+Shift+R for hard refresh only
- Emoji in heredocs: use chr(0xHEX) not literal emoji (MINGW mangles UTF-8)

## Full docs in repo (fetch or ask owner to paste)
- HANDOFF.md  — detailed state + full queue (744 lines)
- AGENTS.md   — architecture + briefing for AI assistants
- WORKFLOW.md — dual-remote workflow + per-part progress log

## Backend endpoints (current)
### Chat + agent
- POST /api/agent/run             — full agent loop (non-streaming)
- POST /api/agent/run/stream      — SSE streaming version
- POST /api/agent/plan            — multi-step planning
### RAG
- GET  /api/rag/status
- POST /api/rag/upload            — single or multi-file
- POST /api/rag/query             — with/without narrative
- POST /api/rag/reset
### Sessions
- GET  /api/sessions
- GET  /api/sessions/{key}/history?limit=N
- GET  /api/sessions/{key}/export
- POST /api/sessions/{key}/rewind
### Providers + models
- GET  /api/providers/status
- POST /api/providers/smoke       — per-provider test
- GET  /api/models/resolve        — auto-resolver cache state
- POST /api/models/resolve/refresh
### Tools
- GET  /api/tools
- POST /api/tools/{name}
### Usage
- GET  /api/usage                 — token/cost stats (window_days=7)
- GET  /api/usage/pricing         — cost table per model
### Health + meta
- GET  /health/live
- GET  /health/ready
- GET  /about

## WebUI structure (current)
- Sidebar (240px):
  - "+ New chat" button
  - Down-arrow button (export sessions JSON)
  - Up-arrow button (import sessions JSON)
  - "Stats" button (opens token usage modal)
  - Session list (auto-titled from first user message)
- Header: session ID, API docs link, about, upload, new session,
  docs:N badge, via:<provider> badge
- Chat area: streaming tokens, tool call indicators, markdown text
- Footer: latency display
- Modals: token usage dashboard (Stats button)
- Persistent: localStorage (primary) + Neon DB (fallback for browser wipes)

## Session-end ritual
Ask the AI: "Update RESUME.md and HANDOFF.md with what we did, and give
me the exact git commands to commit + push both remotes."

