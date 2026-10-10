# AGENTS.md — Briefing for AI Assistants

This file tells any AI assistant how this project works, so it can be
productive from the first message of a new session.

---

## Project in one paragraph

Sunnyware is a FastAPI + Gradio AI agent running on a Hugging Face Space.
It wraps an OpenAI-compatible LLM (Groq by default, Ollama optional locally)
with a ReAct orchestrator, a 15-tool registry, RAG over user documents, and
a sandboxed Python data-science workbench. PostgreSQL (Neon) stores memory
and session history. It is a personal production agent.

**Author:** Shamiur Rashid Sunny — shamiur.com | shamiur@engineer.com
**License:** AGPL-3.0-only
**Live:**   https://shamiur-sunnyware.hf.space/ui

---

## Architecture map

    src/sunnyware/
      main.py                 FastAPI app + middleware + lifespan
      config.py               YAML + env var config loader
      orchestrator.py         ReAct loop (native tools + prompt-JSON fallback)
      llm.py                  OpenAI-compatible client
      memory.py               Append-only event log via Neon
      sessions.py             Session lifecycle
      tenant.py               Per-request tenant context (ContextVar)
      state.py                asyncpg pool
      prompts.py              System prompts
      paths.py                Persistent storage resolver (/data on HF)
      webui.py                Gradio chat UI

      routes/
        agent.py              /api/agent/run + /plan + /stream
        rag.py                /api/rag/{status,upload,query,reset}
        tools.py              /api/tools/{name}
        meta.py               /health/live + /health/ready + /about

      tools/                  Agent tool registry (15 tools)
        __init__.py           Registry - add new tools here
        _sandbox.py           Sandboxed exec runtime
        python_eval.py        Data-science workbench
        rag_search.py         Semantic search over uploaded docs
        (plus echo, calculator, web_search, memory_search, etc.)

      rag/                    Local RAG package
        _threads.py           CPU thread caps (old-laptop safety)
        embeddings.py         bge-small-en-v1.5, 384-dim, CPU
        chunker.py            1024-token windows / 100-token overlap
        extractor.py          PDF / DOCX / TXT / MD / CSV / XLSX
        vector_store.py       Per-tenant FAISS
        report_generator.py   FP&A prompt + Groq narrative

    scripts/                  Smoke tests + utilities
    data/                     Persistent storage (gitignored)
    docs/                     Long-form docs

---

## Conventions

### Deployment (dual-remote, see WORKFLOW.md)
After every successful part, push to BOTH remotes:

    git push origin main           # GitHub backup
    ./push_hf.sh                   # HF Space deploy (auto-rebuild)

Both remotes must end at the same commit hash.

### Commit style
    Part NN: short description

### Testing
- Every feature ships with a scripts/*_smoke.py
- Smoke tests pass before commit
- Numbered checks with PASS/FAIL output

### File writes (bash gotcha)
- Prefer Python heredocs (python - << 'PYEOF') over bash heredocs
- Watch for backslash escaping inside triple-quoted strings
- For long content, use Path(...).write_text() not open()

### Terminal quirks (MINGW on Windows)
- /tmp/ is NOT shared between bash and Windows Python - use relative paths
- `2>&1 | tail` buffers all output until the command finishes
- A stray `]` from a previous prompt can glue to the next command

---

## Hard-won gotchas (do not re-learn)

1. **CPU thread caps are required** for older laptops.
   rag/_threads.py sets OMP/MKL/OPENBLAS before torch import.
   Override via SUNNYWARE_CPU_THREADS.

2. **90s agent wall-clock timeout** guards against looping models.
   Set via SUNNYWARE_AGENT_TIMEOUT. Returns 504 on overflow.

3. **Memory payload caps prevent Groq HTTP 413.**
   log_event caps at 2000 chars; build_context caps replay at 800 chars;
   format_context caps cross-session at 200 chars.

4. **Tool-result truncation in orchestrator.**
   _truncate_tool_result strips base64 + caps stdout/result at 500 chars.
   Applied before appending to messages history.

5. **Tool-name aliases for gpt-oss.**
   _TOOL_ALIASES map + _resolve_tool_name() handle python -> python_eval
   and other abbreviations.

6. **Placeholder retry.**
   _looks_like_placeholder + one-shot retry with hard directive.
   Also handles empty content after a tool call.

7. **Chart base64 injection.**
   _inject_chart_base64 substitutes {{image_base64}} placeholders with the
   real base64 from steps[].result.

8. **Groq tool_use_failed retry.**
   400 with "tool_use_failed" -> retry up to 2x with 0.4s backoff.

9. **polars doesn't run on old CPUs.** Requires AVX2/FMA/BMI.
   Removed from requirements; duckdb covers the same use cases.

10. **HF Space is on ZeroGPU tier.**
    Iframe sometimes shows "refused to connect" while API is fine.
    Use curl /health/ready as ground truth.

---

## How to make changes

1. Read HANDOFF.md first
2. Check state: git log -1, health check
3. Make changes with tests
4. Run smoke tests
5. Commit + push to both remotes
6. Update HANDOFF.md + WORKFLOW.md

---

## Things that MUST NOT change without good reason

- **lifespan=lifespan** in FastAPI(...) - startup logic depends on it
- **Dual-remote workflow** - GitHub + HF must stay in sync
- **Tenant context** - every user-data route scopes by tenant.get_key()
- **CPU thread caps** - protect the dev laptop from thermal shutdown
- **HF Space secrets** - LLM_API_KEY etc. set in HF UI, not committed

---

## Current priorities

1. Real PDF end-to-end test (validate pypdf on actual documents)
2. WebUI file-upload button (UX improvement)
3. Repository cleanup (archive stale .bak.partN files)
4. README refresh for public-facing docs

See HANDOFF.md for the full queue.

---

## Quick reference

    # Health check
    curl -s https://shamiur-sunnyware.hf.space/health/ready | python -m json.tool

    # Local smoke tests
    export SUNNYWARE_CPU_THREADS=2
    python scripts/sandbox_smoke.py
    python scripts/memory_cap_smoke.py
    python scripts/truncation_smoke.py
    python scripts/placeholder_smoke.py
    python scripts/rag_smoke_test.py
    python scripts/rag_narrative_smoke.py
    python scripts/agent_rag_smoke.py

    # Deploy
    git add -A
    git commit -m "Part NN: ..."
    git push origin main
    ./push_hf.sh

    # Check sync
    git ls-remote origin main | awk '{print substr($1,1,7)}'
    git ls-remote hf main | awk '{print substr($1,1,7)}'

---

**Last update:** 2026-10-10 (Part 31F wrap)
