# Sunnyware — Handoff Document

**For future sessions. Read this first.**

## What this is

Sunnyware is a production-grade AI agent orchestrator built incrementally
across 30 iterations. It runs 24/7 on Hugging Face Spaces (free tier),
uses Neon Postgres for persistence, and exposes itself via HTTP, SSE,
MCP, and a web chat UI.

## Live URLs

- **Chat UI:**   https://shamiur-sunnyware.hf.space/ui
- **API docs:**  https://shamiur-sunnyware.hf.space/docs
- **MCP:**       https://shamiur-sunnyware.hf.space/mcp
- **Scheduler:** https://shamiur-sunnyware.hf.space/api/schedule
- **Usage:**     https://shamiur-sunnyware.hf.space/api/usage
- **Metrics:**   https://shamiur-sunnyware.hf.space/metrics
- **Firewall:**  https://shamiur-sunnyware.hf.space/api/firewall/status

## Repos (both at same commit)

- HF:     https://huggingface.co/spaces/shamiur/sunnyware
- GitHub: https://github.com/shamiursunny/sunnyware

## Local development

```bash
cd /h/sunnyware
source .venv/Scripts/activate      # Windows Git Bash
export PYTHONPATH="$PWD/src"
taskkill //F //IM python.exe 2>/dev/null || true
python app.py                       # foreground, :7860

## Deploy to HF (dual-remote workflow)

    cd /h/sunnyware
    git add .
    git commit -m "Part N: description"
    ./push_hf.sh                # HF (helper script, token embedded)
    git push origin main        # GitHub

Wait ~3 min for HF rebuild, then run:
    bash scripts/smoke_test.sh "https://shamiur-sunnyware.hf.space"

## Architecture

    Clients (HTTP, SSE, MCP, Web UI)
             |
       FastAPI (gradio.Server) + ASGI middleware
             |  - auth (opt-in API keys)
             |  - rate limit (per-key)
             |  - firewall (IP allowlist, opt-in)
             |  - security headers
             |  - metrics (in-memory + Neon persist)
             |  - request IDs
             |  - scheduler lazy-start
             |  - tenant context (contextvars)
             |
       Routes:      Orchestrator    MCP handler   Scheduler
       /agent       (ReAct loop)    tools/list    jobs
       /tools       - native        tools/call    - heartbeat
       /sessions    - prompt-JSON                 - session_cleanup
       /memory      - LLM (Groq/Ollama)
       /eval        - Tools (14)
       /mcp
       /auth
       /schedule
             |
       Neon Postgres
       - sessions (owner_key for tenants)
       - events (memory)
       - metrics_counters
       - scheduled_jobs
       - llm_usage

## Key facts / gotchas

### HF quirks
- emoji: field in README must be a real Extended_Pictographic char, not text
- HF skips FastAPI lifespan on its launch path -> state also init'd at import
- BaseHTTPMiddleware (the decorator) buffers SSE -> use ASGI middleware class
- First request after cold start may be slow (Neon pool init ~30s)
- HF build takes ~3 min for full rebuild

### Local quirks
- Up-arrow key on this laptop auto-fires -> run: bind '"\e[A":""' at session start
- Large heredocs can get cut off -> use notepad file.md for markdown files
- Always source .venv/Scripts/activate before running python

### Test flakiness
- Local Ollama flakes on tests #8 (LLM round-trip) and #10 (multi-turn)
  -> HF with Groq passes them reliably
- Tests #21 and #22 (planner) may take 60-90s locally

## What is implemented (Parts 1-30)

### Infrastructure (Parts 1-5B)
- FastAPI on HF via gradio.Server
- Neon Postgres (sessions, events, migrations)
- LLM client (Groq native + Ollama prompt-JSON fallback)
- Multi-turn + cross-session memory

### Agent (Parts 6-16)
- Orchestrator (ReAct, hybrid tool calling)
- 14 tools (see README)
- Multi-step planner (parallel-capable via asyncio.gather)
- Session history API (history/export/rewind)

### Production (Parts 17-30)
- Metrics + request IDs + structured logs
- Persistent metrics in Neon (write-through, throttled)
- SSE streaming (direct + tool-aware)
- Evaluation suite (8 cases, 4 scoring modes)
- MCP server (HTTP JSON-RPC + stdio runner)
- API key auth (opt-in)
- Rate limiting (per-key, sliding window)
- Multi-tenant session isolation (contextvars)
- Background scheduled jobs (heartbeat + session cleanup)
- Web chat UI at /ui
- CORS (opt-in)
- IP allowlist + security headers
- Per-tenant LLM usage + cost tracking

### Quality
- 84 pytest unit tests
- 42 E2E smoke tests
- README + OpenAPI docs + WORKFLOW.md

## Environment variables

| Var | Default | Purpose |
|---|---|---|
| NEON_DATABASE_URL | - | Postgres (required) |
| LLM_BASE_URL | http://localhost:11434/v1 | LLM endpoint |
| LLM_API_KEY | ollama | LLM key |
| LLM_MODEL | gemma2-2b-tuned-stable:latest | Model |
| LLM_NATIVE_TOOLS | auto | Force native vs prompt-JSON |
| SUNNYWARE_API_KEYS | unset | API keys (enables auth) |
| SUNNYWARE_RATE_LIMIT_PER_MINUTE | 0 | Rate limit |
| SUNNYWARE_PERSIST_METRICS | true | Persist counters |
| SUNNYWARE_PERSIST_USAGE | true | Persist token usage |
| SUNNYWARE_IP_ALLOWLIST | unset | IP/CIDR list (enables firewall) |
| SUNNYWARE_SECURITY_HEADERS | true | Security headers |
| SUNNYWARE_CORS_ORIGINS | unset | CORS allowlist |
| SUNNYWARE_SCHEDULE_ENABLED | true | Background jobs |
| SUNNYWARE_SESSION_TTL_DAYS | 30 | Cleanup TTL |
| SUNNYWARE_WORKSPACE | ./data/workspace | File sandbox |

## How to resume

    cd /h/sunnyware
    source .venv/Scripts/activate
    git fetch hf && git fetch origin
    git log --oneline -5
    pytest tests/ -q

Then read WORKFLOW.md for the full part-by-part history.

## Adding a new Part N

1. Read WORKFLOW.md -> see last commit + part number
2. Pattern: file -> wire into main.py -> smoke test -> commit -> push both remotes
3. Update WORKFLOW.md with the new row
4. Never push if smoke test fails
5. Both remotes must end at the same commit hash

## Author

Shamiur Rashid Sunny -- shamiur@engineer.com -- https://shamiur.com