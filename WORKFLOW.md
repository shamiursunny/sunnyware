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
| 31F  | 272f98a | Live (tool retry + chart inject) | Backed up | Done |

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
\n

## Tool Reliability + Chart Injection (Part 31F)

### Bugs fixed
1. gpt-oss-20b made the tool call but returned placeholder text
   ("What would you like to do next?") without the numeric answer
2. gpt-oss-20b sometimes returned empty content after a tool call
3. gpt-oss emitted malformed JSON args -> Groq rejected with 400
   "tool_use_failed" before our server saw the request
4. gpt-oss wrote ![chart](data:image/png;base64,{{image_base64}})
   as a literal placeholder instead of the actual chart data

### Fixes

**prompts.py (directive system prompt)**
- Rewrote native_prompt() with non-negotiable rules:
  "MUST call the appropriate tool when the request involves
   computation, data, search, documents"
  "After a tool result, MUST compose a final answer using that result"
  "Never respond with placeholders like 'What would you like to do next?'"

**orchestrator.py (placeholder + empty retry)**
- _looks_like_placeholder(): detects ~9 known phrases and short non-answers
  (has-digit check ensures numeric answers are never flagged)
- If model returns placeholder after a tool call -> retry once with hard
  directive "Deliver the concrete numeric/textual answer in one short reply"
- If model returns empty content after a tool call -> retry once with
  "Write a short final answer that uses that result"

**llm.py (Groq tool_use_failed retry)**
- On HTTP 400 with "tool_use_failed" -> retry up to 2x with 0.4s backoff
- Uses _retry_depth parameter (not a global) so nested calls are safe

**tools/python_eval.py (schema shrink)**
- Description trimmed from 872 -> 245 chars
- Total tool schema 5006 -> 4492 chars
- Reduces prompt token pressure + lowers malformed-JSON chance

**orchestrator.py (chart base64 injection)**
- _inject_chart_base64(): detects ~10 placeholder forms
  ({{image_base64}}, {{ base64 }}, <IMAGE_BASE64>, etc.)
  and substitutes the real base64 from steps[].result.image_base64
- Also handles the case where the model emitted syntactically-correct
  but truncated base64 characters (heuristic: content <200 chars)
- Wired into both native and prompt-JSON answer return paths

### Smoke tests
- scripts/placeholder_smoke.py -> 8/8 PASS

### Verified live in WebUI
- Compute average -> "Average = 24,666.67" (was: placeholder)
- Bar chart -> real PNG rendered inline (was: {{image_base64}})
- Line + pie charts -> inline
- RAG search -> correct figures + citation
- Multi-turn, multi-chart session -> no 413, no 400, no placeholder

## Part 87 — Reasoning-model token budget (2026-10-14)
- max_tokens 900 -> 2048 in llm.py
- Symptom fixed: empty content after tool calls on reasoning models
- Commit: 3e33c28

## Part 88 — Orchestrator token economy (2026-10-14)
- MAX_ITERATIONS 7 -> 3
- Greeting rule, ONE TOOL PER STEP, NO PREFLIGHT LISTS (rules 1, 3, 3a)
- echo tool marked TEST-ONLY
- Commit: 273b7bf (88b), d271167 (88c), 896570a (88d)

## Part 88b/88c/88d — Tool-call dedup & preflight removal
- Exact-match + subset/superset dedup in orchestrator
- Hard-stop after 2 duplicate calls
- Skip sql_sandbox_list when resource is named
- Combined effect: 10-50x token reduction

## Part 89 — Self-host marked.js, no CDN dependency (2026-10-14)
- Root cause of InPrivate '(empty response)': tracking protection + VPN blocked cdn.jsdelivr.net
- marked@12 -> src/sunnyware/static/marked.min.js (35 KB) + __init__.py
- main.py: /static mounted via FastAPI StaticFiles after include_router block
- webui.py: <script src="/static/marked.min.js"> (was CDN)
- scripts/smoke_test_part89.py: 8 checks (ASCII-safe for cp1252 Windows stdout)
- Verified live: HTTP 200 | 35479 bytes on /static/marked.min.js
- Verified live: InPrivate Firefox loads UI clean + chat works
- Commit: 3732fb5

## Part 90 + 90b — Per-request token budget guard (2026-10-14)
- MAX_REQUEST_TOKENS = 8000 in orchestrator.py
- _estimate_tokens(*parts): char-based heuristic (~4 chars/token)
- _tokens_used accumulator + trip check each iteration
- Friendly message on trip: 'Token budget reached (X / 8,000 tokens)...'
- SSE event type 'budget_exceeded' emitted to WebUI
- Response flags: budget_exceeded, tokens_used (propagated via routes/agent.py)
- Part 90b fix: excluded tools_schema (~8700 tokens for 58 tools) from
  estimate; otherwise 'hi' tripped the guard
- Smoke test: scripts/smoke_test_part90.py (11 checks, ASCII-safe)
- Verified: hi -> ~700 tokens, budget_exceeded False
- Verified: 67k chars -> trips at 34837 / 8000, budget_exceeded True
- Commits: 0bebe62 (initial), 65ad114 (Part 90b fix)

## Part 91 — WebUI budget_exceeded styling (2026-10-14)
- budgetExceeded flag declared per-request in webui.py stream handler
- SSE event 'budget_exceeded' sets the flag
- 'final' event also reads data.budget_exceeded as fallback
- Class 'budget' added to assistant bubble on trip
- CSS .msg.agent.budget: amber bg + #ffb020 left border
- ::before prefix 'BUDGET LIMIT:' (ASCII-only)
- Verified: 90k-char prompt -> amber bubble + friendly message
- Smoke test: scripts/smoke_test_part91.py (8 checks, ASCII-safe)
- Commit: e09abd3

## Parts 93, 93b, 94, 95, 95b — Professional WebUI redesign (2026-10-14)
- Part 93: header redesign (gradient S, session pill, icon buttons, dropdown)
- Part 93b: paperclip inside composer (ChatGPT-style)
- Part 94: doc badge shows number only; overflow menu always visible
- Part 95: menu moved to sidebar bottom-left, opens upward; header minimal
- Part 95b: null-safe clearBtn (removed #clear crashed init script)
- SVG icons only (no CDN, no emoji), responsive at 760/640/480px
- Smoke test: scripts/smoke_test_part93.py (52 checks)
- Commits: 13585fc (93), 2574dcc (93b), dcd32f3 (94), 54e29e5 (95), a984bcb (95b)

## Parts 96 + 96b — Real token counts from provider usage (2026-10-14)
- llm.py: return tokens_in / tokens_out / tokens_total in result dict
  (previously only written to usage DB)
- orchestrator.py: prefer result['tokens_total'] - _tools_overhead over
  char/4 heuristic; fallback no longer double-counts 'prompt'
- Part 96b: MAX_REQUEST_TOKENS 8000 -> 15000 (accurate counts made
  8000 too tight)
- Verified: 12k prompt -> tokens_used 10022 (real, not inflated),
  budget_exceeded True
- Note: Groq has hard 8k input limit (HTTP 413 for very large prompts);
  the orchestrator's provider-failover handles it
- Smoke test: scripts/smoke_test_part96.py (13 checks)
- Commits: b9342d4 (96), ae65d27 (96b)

## Parts 97 + 97b — Pollinations AI fallback provider (2026-10-14)
- Added Pollinations as 4th provider (after groq, gemini, openrouter)
- Free anonymous tier, no API key needed (dummy 'pollinations')
- Base URL: https://text.pollinations.ai/openai (OpenAI-compatible)
- Model: 'openai' (GPT-OSS-20b class); fallbacks in model_resolver.py
- HF Space config managed via huggingface_hub API:
  - LLM_PROVIDERS as VARIABLE (not secret -- fixes collision)
  - POLLINATIONS_BASE_URL / API_KEY / MODEL as secrets
- LIVE PROOF: 'POLLINATIONS WORKS' returned with provider=pollinations
- Note: developer's VPN DNS-blocks pollinations.ai; HF cloud reaches it
- Smoke test: scripts/smoke_test_part97.py (10 checks)
- Commits: 46a5a25 (97), 97d7123 (97b)

## Parts 98 + 98b + 98c — Image generation tool (2026-10-15)
- New tool: image_generate (Pollinations.AI free text-to-image)
- Models: flux (default), turbo, gptimage, qwen-image, kontext, nanobanana
- Returns {image_base64, image_format} — same contract as chart_from_data
- Part 98b: 'call EXACTLY ONCE' instruction (free tier rate-limit 1/15s)
- Part 98c: WebUI 'tool_result' SSE case renders images inline as
  <img class='msg-image'> — also benefits chart_from_data / browser_screenshot
- Tools: 58 -> 59
- Verified live: 52 KB JPEG @ 1024x1024, model=flux, rendered inline
- Smoke test: scripts/smoke_test_part98.py (24 checks)
- Commits: 6498e3d (98), a0a0df8 (98b), e27a541 (98c)

## Part 99 — Long-prompt routing (2026-10-15)
- Provider dataclass: max_prompt_tokens field (0 = no limit)
- Defaults: groq=7500, gemini=1M, openrouter/pollinations=32000,
  mistral=32000, nvidia=8000, local=0
- Env override: {PREFIX}_MAX_PROMPT_TOKENS
- llm.py: _estimate_prompt_tokens() char/4 over prompt + system + history
- Router skips providers that can't fit the prompt; falls through if
  no eligible provider (safety)
- status() exposes max_prompt_tokens
- FIXES earlier 'empty LLM response' on 30k-char prompts (Groq 413)
- Verified live: 30k chars -> openrouter (Groq auto-skipped)
- Smoke test: scripts/smoke_test_part99.py (17 checks)
- Commit: 20ed50b

## Parts 100 + 100b — Auto-learn provider limits (2026-10-15)
- New module: src/sunnyware/provider_limits.py
- On 413: learn_limit(name, sent_tokens) -> max(500, sent - 200)
- Never raises existing lower limit; persists to disk
- Storage path resolution (Part 100b):
  1. SUNNYWARE_DATA_DIR
  2. /data (HF persistent bucket, POSIX only)
  3. ./data
- Verified: learned={'groq': 8403} survived HF restart at
  /data/provider_limits.json
- providers.py: applies learned limits (env override > learned < default)
- llm.py: _is_too_large_error() detects 413, marks cooldown 60s, learns,
  continues to next provider
- Debug endpoints:
  GET  /api/providers/limits
  POST /api/providers/limits/reset  {name} | {all: true}
- Smoke test: scripts/smoke_test_part100.py (44 checks)
- Commits: 91bf676 (100), ad38fcf (100b)

## Part 101 — Empty-response fallback (2026-10-15)
- llm.py: _is_empty_response(r) detects ok=True with blank content
  AND empty tool_calls
- Both HTTP and local provider paths treat empty as failure:
  record failure, cooldown 15s HTTP / 10s local, metric
  llm_provider_empty_response, continue to next provider
- FIXES: 'Agent failed | empty LLM response' when a provider
  returned HTTP 200 with no actionable content
- Verified live: 30k prompt -> openrouter -> 3,850-char real answer
- Smoke test: scripts/smoke_test_part101.py (22 checks)
- Commit: 1214276

## Part 102 — Retry policy for full failover cycle (2026-10-15)
- llm.py: after failover loop, if _retry_depth == 0
- Reload providers to see fresh cooldown state
- If all cooling AND soonest cooldown <= 20s:
  wait min(min_cool + 0.5, 8.0)s, recurse once with _retry_depth=1
- Exactly ONE retry (guarded by _retry_depth)
- Wait capped at 8s (never stalls interactive requests)
- Metric llm_request_retried + diagnostic print lines
- Smoke test: scripts/smoke_test_part102.py (18 checks)
- Commit: 0da91ab

## Part 103 — Provider health metrics dashboard (2026-10-15)
- New endpoint: GET /api/providers/metrics
- Aggregates three sources:
  1. Session stats (per-process): success/fail counts, cooldowns
  2. Lifetime counters (persistent): attempts, empty-responses,
     learned-limits, retries (from metrics.py / Neon)
  3. Storage diagnostics (from provider_limits)
- _sum_prefix() helper over metrics.snapshot() for extensibility
- Verified live: groq learned=8403 but max_pt=7500 (tighter wins)
- Smoke test: scripts/smoke_test_part103.py (33 checks)
- Commit: b48173f

## Part 104 — WebUI provider health panel (2026-10-15)
- Renders /api/providers/metrics in the Stats modal
- Modal title: 'Stats & Provider Health'
- Table: Provider | Model | Status(dot) | Success Rate
- Summary: N providers | N ready | N cooling | session rate
- Footer: storage source + learned limits + lifetime counters
- Auto-refresh every 10s while open (clears on close)
- New .ph-* CSS classes
- Smoke test: scripts/smoke_test_part104.py (36 checks)
- Commit: f6160ce

## Part 105 — Per-message provider chip (2026-10-15)
- Small 'via groq · 1.2s' chip appears under each assistant bubble
- lastProvider tracked per-request, set from data.provider in
  both 'final' and 'done' SSE events
- Inserted via agentBubble.insertAdjacentElement('afterend', chip)
- New .provider-chip CSS: 11px muted, aligned with agent padding
- Failover chain now visible message-by-message
- Smoke test: scripts/smoke_test_part105.py (18 checks)
- Commit: a640a80

## Parts 106 + 106b/c/d — Persistent image attachments (2026-10-15)
- Bug: images rendered live but disappeared after browser refresh /
  session navigation. Base64 only lived in the SSE stream.
- New module: src/sunnyware/attachments.py
  save_base64() / resolve_path() / stats()
  Storage: /data/attachments (HF bucket) > ./data/attachments
- Serving: GET /api/attachments/{id}.{ext} + /stats
- Tools (image_generate, chart_from_data) save to disk and return
  attachment_url/id/ext
- Orchestrator collects + returns attachments in ALL success returns
- routes/agent.py strips broken base64 markdown from history
- WebUI loadSession renders <img class=msg-image> from stored attachments
- WebUI sendMessage persists to localStorage (Part 106d handles the
  LLM-returns-no-text case)
- Verified: image survives browser refresh + session navigation
- Smoke test: scripts/smoke_test_part106.py (38 checks)
- Commits: 0587c1f, c1a3845, c558e78

## Parts 107-109 + 108b/109b — Financial data tools (2026-10-15)
7 new tools for FP&A and quantitative finance roles:

- edgar_fundamentals: SEC EDGAR /companyfacts (no key, US public cos)
  UA: 'Sunnyware Financial Research shamiur@engineer.com'
  Company: 'CIK{cik}.json' single-request pattern
- fred_economic: FRED macro (free key, 120/min), popular presets + search
- finnhub_quote: quote, profile, company_news, market_news, earnings, metrics
- tiingo_prices: eod (/daily/{sym}/prices), intraday, meta
- marketaux_news: entity tagging + sentiment
- twelvedata_prices: multi-asset (stocks/forex/crypto), RSI, MACD
- fmp_fundamentals: /stable/ API (v3 legacy retired Sept 2025)

Shared helper: _financial_http.py (get_json + env_required + TTL cache)

Fixes along the way:
- 107b: EDGAR UA format + /companyfacts single request (was 15+ calls)
- 108b: Tiingo EOD needs /daily/{sym}/prices suffix (not /daily/{sym})
- 109b: FMP /stable/ prefix + symbol as query param

All 7 API keys pushed to HF Space secrets (verified working).

Tools: 59 -> 66.
Smoke test: scripts/smoke_test_part107.py (73 checks)
pre_push_check.py: whitelist .env.example / .env.sample / .env.template

Verified live on HF: all 8 endpoints return real data
  - EDGAR: Apple Inc. revenue $109.4B
  - FRED:  GDP $32,563.03B
  - Finnhub: AAPL $342.96 + 245 news articles
  - Tiingo: 7 OHLCV bars
  - MarketAux: AAPL $5T cap headline
  - TwelveData: AAPL/EUR-USD/BTC-USD
  - FMP: quote + income statement

Commits: c180d24 (initial), b881954 (107b EDGAR fix), 1f6c789 (109b FMP fix),
ff2054f (108b Tiingo fix)

## Part 110 — Eulerpool multi-source data (2026-10-15)
- New tool: eulerpool_data (curated 70 endpoints of 447-endpoint API)
- Base URL: https://api.eulerpool.com/api/1 (query-param auth ?token=)
- Fills gaps not covered by other tools:
  * Bonds / Treasury yields / interest rate spreads
  * Fixed income analytics / spot + forward curves
  * Options chains / Greeks / IV surface / flow
  * 13F institutional holdings (per ticker + per CIK)
  * Superinvestor tracking
  * Congressional trading (STOCK Act)
  * Insider trades (Form 4) + sentiment
  * Economic calendar (macro, earnings, dividends, IPO, M&A)
  * Google Trends / Reddit / Fear & Greed / Wikipedia views
  * Commodity prices + futures curves
  * Crypto global + candles + fear/greed
  * Risk models (covariance, factors, portfolio risk)
  * Fama-French factors + CFTC COT
  * Earnings call transcripts
- Uses 'action' + optional 'identifier' + optional 'params' (JSON string)
- 1-hour TTL cache to preserve free tier budget
- Path fix: /fundamentals/company/ was 500 — correct is /equity/profile/
  (and /equity/overview/ as bonus with description)
- Verified live on HF: 10/10 actions return real data
  profile, overview, bonds_yield_curve, options_greeks, macro_fred,
  congress_trades, fama_french, institutional_holders, crypto_global,
  commodity_prices
- Tools: 66 -> 67
- EULERPOOL_API_KEY on HF Space secrets (len 32)
- Commit: d26718f

## Part 111 — Actuarial / insurance / risk libraries (2026-10-15)
- Added 3 PyPI packages to requirements.txt:
  * chainladder 0.10.1   — P&C IBNR reserving
  * lifelib     0.17.2   — Life/pension actuarial models
  * solvency2-data 0.5.0 — EIOPA risk-free rate curves
- haute removed (requires Python 3.11+, HF runs 3.10.13)
- Sandbox ALLOWED_MODULES extended with 12 modules (top-level + transitive deps)
- Verified live on HF:
    chainladder IBNR on RAA = 52,135.23
    lifelib v0.17.2 imports instantly
    solvency2_data imports cleanly
- Smoke test: scripts/smoke_test_part111.py (11 checks)
- Commits: a2bef46 (111), b37dd00 (111b haute removal), 3c927ce (111c allowlist)

## Part 112 — Role personas + tool subsetting (2026-10-15)
- New module src/sunnyware/roles.py (5 roles)
- Backend:
  * orchestrator._build_tools_schema(role=None) — filters by role
  * orchestrator.run_agent(..., role=None) — injects role prompt addon
  * routes/agent.py: /run + /stream read `role` field
  * NEW endpoint: GET /api/roles
- WebUI:
  * <select id="roleSelect"> in header-right
  * getRole()/setRole() helpers, ROLE_KEY='sunnyware.role'
  * initRoleSelector() fetches /api/roles on boot
  * fetch body includes `role: getRole()`
- Token savings: 4-6K/request in non-general roles
- Smoke test: scripts/smoke_test_part112.py (28 checks)

## Part 113A — Per-session role persistence (2026-10-15)
- sessions.py: set_role + get_role (stored in existing metadata JSONB)
- routes/sessions.py:
    GET  /api/sessions/{key}/role  -> {role}
    PUT  /api/sessions/{key}/role  -> validated, 400 on unknown
- routes/agent.py: /run + /stream auto-persist role on send
- roles.py: canonical() now public alias
- WebUI: persistRoleToSession + syncRoleFromSession, hooked into loadSession
- No schema migration (reuses sessions.metadata)
- Smoke test: scripts/smoke_test_part113a.py (18 checks)

## Part 113B — Role-specific result rendering (2026-10-15)
- roles.py: style(role) returns {accent, chip} per role
  general #8899aa | fpa #4a90e2 | quant #a855f7 | actuary #10b981 | tax #f59e0b
- routes/agent.py /stream: start event carries role + accent + chip
- routes/agent.py /run: response includes role
- WebUI CSS: #chat[data-role=X] .msg.agent gets colored border + ::before chip
- WebUI JS:
    SSE handler reads data.role / data.accent
    initRoleSelector sets chat.dataset.role on boot
    persistRoleToSession + syncRoleFromSession keep it in sync
- Session-level: switching role re-colors ALL bubbles in the active chat
- Smoke test: scripts/smoke_test_part113b.py (25 checks)

### Part 113B hotfix — orchestrator + agent_stream
- orchestrator._emit start event now includes accent + chip (from roles.style)
- routes/agent.py agent_stream() reads role from body + passes role=role to orchestrator
- agent_stream "session" SSE event also enriched with role/accent/chip
- Root cause: WebUI calls /api/agent/stream (not /api/agent/run/stream); that
  route goes through orchestrator, which previously emitted only {type, role}

## Part 113C — Options-cache TTL differentiation (2026-10-15)
- _financial_http.py: cache_stats() + cache_clear() helpers
- eulerpool_data.py: _TTL_OVERRIDES per action
    options_greeks/chain/iv/flow → 60s
    candles                     → 300s
    profile/overview/dividends/esg/analyst_grades → 24h
    everything else             → 1h default
- eulerpool_data.py: metrics counters (hit/miss per action, api_calls_total)
- routes/meta.py: GET /api/cache/stats, POST /api/cache/clear
- Smoke test: scripts/smoke_test_part113c.py (24 checks)

## Part 113D — Insurance data sources (2026-10-15)
- New tool: tools/insurance_data.py — Socrata state-DOI portals (no key)
- 8 portals: TX TDI, NY DFS, CT, WA, IL, CO, OR, VT
- Actions: states / discover / inspect / fetch
- Tool registry: 68 tools total (was 67)
- Roles: actuary prefix now includes insurance_; active tools = 11
- Cache: discovery 24h, inspect 24h, fetch 1h
- Smoke test: scripts/smoke_test_part113d.py (20 checks)

## Part 114 — CFO + CDO supervisor delegation (2026-10-15)
- New tool: delegate_to_agent (69th tool)
  - contextvars: role / depth / path
  - max depth 3; cycle detection by path
  - permission matrix: cfo→cdo; cdo→workers; workers→nothing
- New roles: cfo (Chief Financial Officer), cdo (Chief Delivery Officer)
- orchestrator.run_agent wrapped: sets _CURRENT_ROLE contextvar
- routes/agent.py: timeout for cfo/cdo bumped to 300s
- WebUI: cfo + cdo options, borders, chips (with real emoji)
- Bonus fix: 113B chip emoji now render correctly (were literal \U escapes)
- Smoke test: scripts/smoke_test_part114.py (49 checks)

### Part 114b-e — Pipeline hardening (2026-10-15)
- 114b: CFO tools trimmed to 8 (delegate/email/pdf/read/current_time);
        MANDATORY-first delegation; 300s timeout
- 114c: CDO tools 6→2 (delegate_to_agent + read_file);
        CDO prompt hardened FORBIDDEN ACTIONS; timeout 300s→600s
- 114d: compact_prompt(allowed_tools=) filters prompt tool list
        by role; orchestrator guards _execute_tool at runtime
- 114e: STRICT PIPELINE RULE in CFO prompt overrides base
        'answer simple questions directly' clause
- VERIFIED: '15% of $2400' → 1 delegation → '360' in 12.3s

## Part 115 — Role-specific content styling (2026-10-15)
- Per-role CSS on agent-bubble content (tables, code, lists, headings)
- FP&A blue | Quant purple | Actuary emerald | Tax amber | CFO violet | CDO cyan
- Smoke: smoke_test_part115.py (22 checks)

## Part 116 — Role config export/import (2026-10-15)
- roles.export_roles() / roles.import_roles(payload)
- GET /api/roles/export, POST /api/roles/import (validate-only)
- Smoke: smoke_test_part116.py (25 checks)

## Part 117 — insurance_research tool (2026-10-15)
- 70th tool: SEC EDGAR (search_filings, company_filings) + FRED
  (fred_search, fred_series)
- Honest reframe: NAIC (no API) + AmericasSuretyBonds (blocks bots)
  were dropped; real sources are EDGAR + FRED (verified live)
- Live: 'IBNR' 10-K search = 2,082 filings; health-insurance FRED
  search = 4,330 series; CCSA = 1.71M insured unemployment
- actuary role now includes insurance_research
- Smoke: smoke_test_part117.py (23 checks)

## Part 118 — govcon_data tool (USAspending.gov) (2026-10-15)
- 71st tool: federal contracts + spending (Treasury, keyless)
- Honest replacement for SAM.gov (OTP never arrived)
- Actions: award_search / recipient_search / spending_by_category
- Live verified:
    NAICS 524126 P&C insurers hold federal contracts
    AIG recipient lookup (real UEI)
    Direct Health & Medical Insurance = $48.5B in federal contracts
- Cache TTLs: awards 15m, recipients 1h, category 15m
- Fix: spending_by_category requires category in URL path (404 otherwise)
- cfo role now has govcon_data in its subset
- Smoke: smoke_test_part118.py (20 checks)

## Parts 119-128 — Multi-platform feature roadmap (2026-10-15)
Sourced from verified research of high-value platforms (Bloomberg,
Kensho, AlphaSense, Hebbia, ServiceNow, Workday).

- 119: per-role agent monitoring metrics + GET /api/agents/metrics
- 120: save-as-script on python_eval + script_registry tool
- 121: lexicon sentiment on insurance_research (Part 121 _sentiment.py)
- 122: workflow_registry tool (named multi-step workflows)
- 123: interactive Plotly charts (capture_plotly + WebUI renderer)
- 124: narrate_table tool (deterministic table-to-narrative)
- 125: research_search tool (parallel edgar+fred+govcon)
- 126: document_library tool (persistent text docs w/ tags + search)
- 127: earnings_call tool (8-theme transcript summarizer)
- 128: clause_extractor tool (14-type contract clause extraction)

Tools: 71 → 78. Zero regressions across all 10 parts.

## Phase A + C-2 — Specialist sub-agents (2026-10-15)
- Added 2 new roles to the supervisor hierarchy:
  * legal    (14 tools)  slate #64748b  LEGAL
  * risk_ins (22 tools)  red   #ef4444  RISK/INS
- Extended _DELEGATION_MATRIX.cdo with legal + risk_ins
- Aliases: attorney/counsel/compliance -> legal;
           risk/insurance_risk/investment_risk -> risk_ins
- WebUI dropdown: 2 new <option> entries
- Compliance guardrails baked into role prompts:
  * legal    -- no legal advice + [PRIVILEGED] + citation verify
  * risk_ins -- methodology + confidence + holding + human sign-off
- New tool #79: risk_metrics (12 actions, pure numpy/scipy, deterministic)
  - VaR (historical/parametric/Monte Carlo with seed=42)
  - CVaR, volatility, Sharpe, Sortino, Calmar, max drawdown
  - stress_test, correlation, beta, from_prices
  - Every result carries 'methodology' field
- Zero changes to orchestrator.py or delegate_to_agent.py
- Smoke: 129 (48/48), 130 (47/47), 114 (50/50), 112 (28/28)

## Phase C-1 — legal_citation_check (2026-10-16)
- New tool #80: legal_citation_check (CourtListener REST API v4)
- Actions: verify_one / verify_text / search_cases / get_opinion
- Status codes: 200 found | 404 valid-not-found | 400 invalid reporter
                | 300 ambiguous | 429 throttled
- Free tier: 5 req/min, 50 req/hr, 125 req/day
- Requires COURTLISTENER_API_KEY (HF Space secret) - graceful fallback
- Smart caching: 1w for cites, SHA-256 for text blobs
- Legal role now has 15 tools
- VERIFIED live:
  * Obergefell v. Hodges (576 U.S. 644) verified=True
  * Miranda v. Arizona (384 U.S. 436) verified=True
  * Fabricated citation 9999 F.99d 99999 verified=False
- Smoke: smoke_test_part131.py (32 checks)
