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

# sunnyware

**Production-grade AI agent orchestrator** -- 14 tools, cross-session memory, multi-step planning, MCP interop, all on Hugging Face free tier.

**Live:** https://shamiur-sunnyware.hf.space
**MCP:** https://shamiur-sunnyware.hf.space/mcp
**Author:** [Shamiur Rashid Sunny](https://shamiur.com) | shamiur@engineer.com | +880-01737394735

---

## What it is

An autonomous AI agent that plans, calls tools, remembers across sessions, and exposes itself over the **Model Context Protocol** for use from Claude Desktop, Cursor, or any MCP client.

Built from scratch across 22 iterations -- runs 24/7 on HF free tier, no laptop dependency.

---

## Features

- **Orchestrator** -- ReAct-style loop; supports both native OpenAI tool calling (Groq/OpenAI) and prompt-based JSON protocol (small local models)
- **14 tools** -- see Tools section below
- **Cross-session memory** -- auto-injects relevant past events into every prompt
- **Multi-step planner** -- decompose, execute (parallel), synthesize
- **Session API** -- full history, JSON export, soft rewind
- **Streaming** -- SSE for direct LLM output, tool-aware SSE (real-time tool events)
- **MCP server** -- Claude Desktop, Cursor, Continue, Cline, Zed, Windsurf
- **Observability** -- request IDs, structured logs, persistent metrics
- **Auth + rate limit** -- opt-in via env vars
- **Sandboxed execution** -- AST-validated python_eval, workspace-scoped file ops

---

## Tools

| Tool | Purpose |
|---|---|
| echo | sanity check |
| current_time | UTC time |
| read_file / write_file | sandboxed workspace files |
| list_files / delete_file / mkdir | workspace management |
| calculator | AST-based math |
| python_eval | sandboxed Python execution |
| web_fetch | URL to text |
| web_search | DuckDuckGo search |
| weather | Open-Meteo (no key) |
| date_calc | date arithmetic |
| memory_search | search past events |

Plus virtual agent_query in MCP (routes through the full orchestrator).

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
- WORKFLOW.md -- progress log

---

## License

AGPL-3.0-only (c) 2026 Shamiur Rashid Sunny -- https://shamiur.com