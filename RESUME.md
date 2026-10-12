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

## Current state (last session: 2026-10-12, Part 42)
- Commit:  run `git log -1 --oneline` for current hash
- Health:  /health/ready -> status ok, tools: 16
- LLM:     multi-provider (groq, gemini, openrouter) with auto-failover
  - Groq:       qwen/qwen3.8-27b       (primary, ~200ms)
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
- 16 agent tools including rag_search + python_eval workbench
- Streaming WebUI — tokens appear as generated via SSE (Part 34)
- Chat history persistence + sidebar with multi-session (Part 35)
- Multi-file upload (Part 36) — drag 10+ files at once
- Neon fallback for session history (Part 38) — browser-wipe proof
- JSON export/import for sessions (Part 39) — belt & suspenders
- Token usage dashboard (Part 40) — Stats button + modal
- System monitor + baseline (Part 41) — 57 checks, A+ grade
- Markdown rendering for assistant messages (Part 42) — marked.js
- `via <provider>` badge on header (Part 42)

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
2. Part 43 — next feature (define together)
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
- scripts/smoke_test_part42.py         19 checks (markdown + provider badge)
- scripts/smoke_test_part41.py         15 checks (monitor wrapper)
- scripts/probe_all_providers.py       Scan all provider /models endpoints

## Model selection (real mechanism)

Provider order — env LLM_PROVIDERS (comma-separated priority order).
  Current: groq,gemini,openrouter
  Config lives in: src/sunnyware/providers.py (load_providers)

Model per provider — env <NAME>_MODEL
  Groq:       qwen/qwen3.8-27b       (swapped in Part 37, was gpt-oss-20b)
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
- qwen/qwen3.8-27b on Groq: needs max_tokens >= 900 (reasoning model)
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

## Full docs in repo (fetch or ask owner to paste)
- HANDOFF.md  — detailed state + full queue
- AGENTS.md   — architecture + briefing for AI assistants
- WORKFLOW.md — dual-remote workflow + per-part progress log

## Session-end ritual
Ask the AI: "Update RESUME.md and HANDOFF.md with what we did, and give
me the exact git commands to commit + push both remotes."
