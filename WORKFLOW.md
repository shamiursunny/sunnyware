# Sunnyware — Deploy & Push Workflow

**This is the canonical workflow for every Part (1-25). Locked permanently.**

## Dual-Remote Setup

| Remote | Purpose | URL |
|--------|---------|-----|
| `hf`   | Hugging Face Space (live deployment, auto-rebuild on push) | https://huggingface.co/spaces/shamiur/sunnyware |
| `origin` | GitHub (backup, history, future CI/CD) | https://github.com/shamiursunny/sunnyware |

## The Rule

**After every successful Part — and ONLY when the smoke test passes — push to BOTH remotes.**

Both remotes must end up at the **same commit hash**.

## Canonical Commands

```bash
cd /h/sunnyware

# Verify smoke test passes FIRST (never push broken code)
bash scripts/smoke_test.sh "https://shamiur-sunnyware.hf.space"

# Push to both remotes
git push hf main --force       # HF Space (auto-rebuild)
git push origin main           # GitHub (backup)

### File 2: `README.md` update (link to workflow)

```bash
cd /h/sunnyware

# Add a deployment section to README
cat >> README.md << 'EOF'

## Deployment Workflow

**Every successful Part is pushed to BOTH remotes — Hugging Face + GitHub.**

See [WORKFLOW.md](./WORKFLOW.md) for the locked dual-remote workflow.

- **HF Space:** https://huggingface.co/spaces/shamiur/sunnyware
- **GitHub:** https://github.com/shamiursunny/sunnyware

## Part Progress Log

| Part | Commit  | HF              | GitHub    | Status |
|------|---------|-----------------|-----------|--------|
| 1    | 76fcdde | Live            | Backed up | Done   |
| 2    | a190c3c | Live            | Backed up | Done   |
| 3    | d3b9dc3 | Live (LLM local)| Backed up | Done   |
| 4    | f0fd68e | Live            | Backed up | Done   |
| 5A   | 5802662 | Live            | Backed up | Done   |
| 5B   | dc96bf3 | Live (LLM=Groq) | Backed up | Done   |
| 6    | 84dc484 | Live (tools)    | Backed up | Done   |
| 7    | 7776777 | Live (7 tools)  | Backed up | Done   |
| 8    | 772d646 | Live (memory)   | Backed up | Done   |
| 9    | 462e04e | Live (history)  | Backed up | Done   |
| 10   | e3d38f5 | Live (streaming)| Backed up | Done   |
| 11   | 0cda699 | Live (planning) | Backed up | Done   |
| 12   | 2f674be | Live (parallel) | Backed up | Done   |
| 13   | 1be0a0c | Live (search)   | Backed up | Done   |
| 12alt| ae46031 | Live (refactor) | Backed up | Done   |
| 14   | b982ed2 | Live (10 tools) | Backed up | Done   |
| 15   | acc04fa | Live (11 tools) | Backed up | Done   |
| 16   | b350069 | Live (14 tools) | Backed up | Done   |
| 17   | 45d206f | Live (metrics)  | Backed up | Done   |
| 18   | 65f1f8c | Live (tool-stream) | Backed up | Done   |
| 19   | e603c1a | Live (eval)     | Backed up | Done   |
| 20mcp| be79c3b | Live (MCP)      | Backed up | Done   |
| 21rl | b4f5afe | Live (auth+limit)| Backed up | Done   |
| 22p  | f36e238 | Live (persist)  | Backed up | Done   |
| 23d  | ab39620 | Live (docs)     | Backed up | Done   |
| 24mt | ca23b56 | Live (tenant)   | Backed up | Done   |
| 25t  | 0c3882c | Live (84 tests) | Backed up | Done   |
| 26s  | 74fe10b | Live (scheduler)| Backed up | Done   |
| 27c  | c6c99d2 | Live (web ui)   | Backed up | Done   |
| 28f  | b56b648 | Live (firewall) | Backed up | Done   |
| 29c  | c5dbdd1 | Live (cost)     | Backed up | Done   |
| 31D  | f0107e6 | Live (workbench)| Backed up | Done         |
| 31E  | ca3b9a5 | Live (memory caps + aliases) | Backed up | Done |

## LLM Backend Configuration

Same codebase supports multiple OpenAI-compatible backends via env vars:

| Env var | Purpose | Example |
|---------|---------|---------|
| `LLM_BASE_URL` | OpenAI-compatible endpoint | `https://api.groq.com/openai/v1` |
| `LLM_API_KEY` | API key | `gsk_...` or `ollama` |
| `LLM_MODEL` | Model name | `openai/gpt-oss-20b` |

### Backends

- **Local (dev):** Ollama — `http://localhost:11434/v1`, key `ollama`
- **HF Space (prod):** Groq — `https://api.groq.com/openai/v1`, model `openai/gpt-oss-20b`
- **Fallback:** OpenAI, HF Inference API

### Deployment Matrix

| Env | LLM_BASE_URL | Model |
|-----|--------------|-------|
| Local .env | `http://localhost:11434/v1` | `gemma2-2b-tuned-stable:latest` |
| HF Space secrets | `https://api.groq.com/openai/v1` | `openai/gpt-oss-20b` |

### Why Groq for HF?

- Cloudflare Tunnel blocked by BD ISP (verified 2026-10-04)
- Groq: 14,400 req/day free, ~200-300ms latency
- No laptop dependency — HF Space always-on
- Same OpenAI-compatible client code

## Orchestrator + Tools (Part 6)

### Architecture
- `orchestrator.py` — ReAct loop: think → tool call → observe → answer
- `tools/` — modular tool framework (registry pattern)
- Max iterations: 5

### Hybrid protocol (auto-detected)
| Backend | Protocol | Detection |
|---------|----------|-----------|
| Groq / OpenAI | Native tool calling (`tools=` param) | URL contains groq.com/openai.com |
| Ollama / small models | Prompt-based JSON | default |

Override with `LLM_NATIVE_TOOLS=true|false`.

### Available tools
- `echo` — sanity check
- `current_time` — UTC time

### Endpoints
- `GET /api/tools` — list tools
- `POST /api/tools/{name}` — direct invocation
- `POST /api/agent/run` — full agent loop

### Debug
Response `steps[].protocol` shows `native` or `prompt-json`.

## Tool Inventory (7 total)

| Tool | Purpose | Notes |
|------|---------|-------|
| `echo` | sanity check | deterministic |
| `current_time` | UTC time | deterministic |
| `read_file` | read text file | sandbox: `./data/workspace/` |
| `write_file` | write text file | sandbox: `./data/workspace/` |
| `calculator` | math eval | AST-based, no `eval()` |
| `web_fetch` | URL → text | http/https only |
| `memory_search` | search events | ILIKE on payload |

### Endpoints
- `GET  /api/tools` — list all
- `POST /api/tools/{name}` — direct invoke (deterministic tests)

### Prompt sizing note
- Small models (gemma2-2b): compact prompt (tool names only) + `max_tokens=500`
- Large models (gpt-oss-20b): native tool schemas via `tools=` param

## Memory-Enhanced Context (Part 8)

### Auto-injection
- Every `/api/agent/run` call fetches **3 relevant past events** from OTHER sessions
- Injected into system prompt (native + prompt-JSON modes)
- Ranking: keyword hits (desc) → recency (desc)
- Stopword filter + length>=4 keyword extraction

### Endpoint
- `GET /api/memory/context?q=<text>[&session_id=<id>]`
  - Shows what memory would be injected for a query
  - Debug tool: "what does the agent remember about X?"

### Files
- `memory.select_relevant_events(query, exclude_session_uuid, limit)` — query events
- `memory.format_context(events)` — format as text block
- `_build_system_prompt(context)` / `_build_native_system_prompt(context)` — prompt with context

### Health
- `/health/ready` includes `memory_context: "ok"` check

## Session History API (Part 9)

### Endpoints
- `GET  /api/sessions/{key}/history?limit=N` — chronological event timeline
- `GET  /api/sessions/{key}/export` — JSON download (with Content-Disposition)
- `POST /api/sessions/{key}/rewind` — soft truncate (body: {"to_event": <id>})

### Helpers
- `memory.get_all_events(uuid, max_limit)` — all events ASC
- `memory.delete_events_after(uuid, event_id)` — returns deleted count

### Pool init fix (critical)
- `_ensure_pool()` helper added to `main.py`
- Called at start of every DB-touching endpoint
- Fixes cold-start race where pool wasn't ready on first request
- Endpoints covered: /api/agent/run, /api/memory/context, /api/sessions/*

### Smoke tests added
- #17: Session history returns events
- #18: Session export returns JSON
- #19: Session rewind deletes events after given ID

### Test #8 fix
- Previously used fixed `smoke-llm` session → history buildup over runs → timeout
- Now: unique session per run (`smoke-llm-{ts}-{pid}`), 90s curl timeout, auto-cleanup

## SSE Streaming (Part 10)

### Endpoint
- POST /api/agent/run/stream

### SSE event types
- start    -> session_uuid
- content  -> text chunk
- done     -> session_uuid
- error    -> error message

### llm.stream_chat()
Async generator yielding text chunks via OpenAI-compatible SSE.
Direct LLM only (no tool orchestration).
Tool-aware streaming is deferred (Part 10.5).

### Smoke
Test #20 verifies SSE content + done events received.


## Local RAG + Groq LLM + Agent Tool (Part 31)

### Files added
- `src/sunnyware/rag/` — 7-module RAG package
  - `embeddings.py`       — BAAI/bge-small-en-v1.5, CPU, 384-dim
  - `chunker.py`          — 1024-token windows / 100-token overlap + row-based for CSV/XLSX
  - `extractor.py`        — PDF, DOCX, TXT/MD, CSV, XLSX/XLS
  - `vector_store.py`     — per-tenant FAISS at `data/vector_store/{org_id}/`
  - `report_generator.py` — FP&A prompt + async narrative + stub fallback
  - `_threads.py`         — env-var thread caps (OMP/MKL/OPENBLAS + torch + faiss)
- `src/sunnyware/routes/rag.py` — 4 endpoints
- `src/sunnyware/tools/rag_search.py` — agent-callable search (15th tool)

### Endpoints
- `GET  /api/rag/status`
- `POST /api/rag/upload`   (multipart: file, reset)
- `POST /api/rag/query`    (query, k, with_prompt, with_narrative)
- `POST /api/rag/reset`
- `POST /api/tools/rag_search` — direct tool invocation

### Env vars added
| Var | Purpose | Default |
|-----|---------|---------|
| `SUNNYWARE_CPU_THREADS` | cap BLAS/torch/faiss threads | half of logical cores, max 4 |
| `SUNNYWARE_AGENT_TIMEOUT` | 504 wall-clock cap on /api/agent/run | 90 |
| `SUNNYWARE_TEST_AGENT` | enable agent loop in smoke tests | 0 |

### Safety
- CPU thread caps protect old laptops from thermal shutdown
- 90s agent timeout guard: 504 on infinite loop instead of freeze
- Graceful LLM fallback to stub markdown when Groq unreachable

### Groq switch (production)
- `.env`: `LLM_BASE_URL=https://api.groq.com/openai/v1`
- `.env`: `LLM_MODEL=openai/gpt-oss-120b`
- Ollama retained as local dev option
- Cloud LLM = zero local heat during LLM calls

### Smoke tests
- `scripts/rag_smoke_test.py`      — 10-step retrieval e2e
- `scripts/rag_narrative_smoke.py` — full pipeline + Groq narrative
- `scripts/agent_rag_smoke.py`     — direct tool + opt-in agent loop

### Verified (all PASS)
- Retrieval e2e: 10/10 checks
- Narrative on Groq: 2.3s latency, correct figures, citations
- Agent tool call: rag_search invoked by gpt-oss-120b on natural prompt

### Commit
- `f7d5531` — 17 files, +1352/-3

### Rollback
- `.env.bak.20261010-171322` — pre-Groq Ollama config
\n

## Data Science Workbench for python_eval (Part 31D)

### Deliverable
Agent's `python_eval` tool upgraded from a 40-builtin calculator into
a full data science workbench - safe sandbox, rich libraries, chart
capture, DuckDB SQL helpers.

### Preloaded (no import needed)
np, pd, plt, sns, scipy, stats, sklearn, sqlite3, duckdb, sql_on, pa,
openpyxl, tabulate, Path, ws_path

### Import whitelist (via import statement)
- Data: numpy, pandas, scipy, scikit-learn, statsmodels
- SQL: duckdb, sqlite3
- Columnar: pyarrow
- Viz: matplotlib, seaborn, plotly
- Excel: openpyxl, xlsxwriter
- Utils: tabulate, + safe stdlib (json, csv, math, datetime, re, etc.)

### Always banned
os, subprocess, socket, ctypes, importlib, multiprocessing + the
sys.modules / dunder introspection escapes.

### Features
- sql_on(df, "SELECT ...") - DuckDB SQL over any DataFrame
- matplotlib Agg forced; open figures auto-captured as base64 PNG (200 KB cap)
- DataFrame / Series results auto-convert to JSON records
- ws_path() - jailed relative paths, blocks ../ traversal
- JailedPath subclass rejects read_text/read_bytes > 50 MB
- 30s wall-clock timeout, 32 KB code cap, 64 KB output cap
- Health check: /health/ready reports python_eval: ok|partial|unavailable

### Verified live on HF Space
- 27 ms pandas + DuckDB GROUP BY
- 11 KB PNG chart from matplotlib
- 13/13 local smoke tests passing (scripts/sandbox_smoke.py)

### Requirements added
matplotlib, seaborn, plotly, duckdb, pyarrow, xlsxwriter, tabulate,
statsmodels

### Known limits
- No polars (AVX2/FMA required; crashes on 3rd-gen i7)
- Timeout is soft (threads can't always be interrupted)
- Not a hardened adversarial sandbox - enable API auth before public use
\n

## Memory Caps + Tool Aliases (Part 31E)

### Bug
WebUI hit Groq HTTP 413 after 2-3 tool calls because the memory layer
replayed full prior events (including 15 KB base64 charts from
python_eval) into every subsequent prompt, blowing the 8K TPM budget.

### Fixes
**memory.py** (payload caps):
- _sanitize_content(): redacts 500+ char base64 runs, truncates to cap
- log_event(): caps payload.content at 2000 chars before DB write
- build_context(): caps replayed messages at 800 chars each
- format_context(): caps cross-session context at 200 chars each
- build_context max_turns: 10 -> 6

**orchestrator.py** (tool-result truncation):
- _truncate_tool_result(): strips base64 image fields, caps stdout/result
  at 500 chars each, final JSON cap at 1500 chars
- Native tool_result messages: truncated before append to history
- Prompt-JSON fallback: truncated before append
- build_context max_turns: 5 -> 4 (belt & suspenders)

**orchestrator.py** (tool name aliases):
- _TOOL_ALIASES map: python -> python_eval, rag -> rag_search, etc.
- _resolve_tool_name(): case-insensitive, strips -/_ before lookup
- Called at top of _execute_tool() with metrics tracking

### Smoke tests
- scripts/memory_cap_smoke.py    -> 9/9 PASS
- scripts/truncation_smoke.py    -> 6/6 PASS
- alias resolution inline test   -> 8/8 PASS

### Verified live on HF WebUI
- Bar chart rendered inline (turn 1)
- Line chart rendered inline (turn 2)
- Pie chart rendered inline (turn 3)
- 3 base64 images + 4 turns in one session, zero 413 / 400 errors
