# RESUME — Sunnyware (paste this into a new AI tab)

Copy everything below the line into a fresh chat, then ask any question.

---

## Project
Sunnyware — a FastAPI + Gradio AI agent running on a Hugging Face Space.
Wraps an OpenAI-compatible LLM (Groq) with a ReAct orchestrator, a 15-tool
registry, RAG over user documents, and a sandboxed Python data-science
workbench. PostgreSQL (Neon) stores memory + sessions.

## Live
- WebUI:  https://shamiur-sunnyware.hf.space/ui
- GitHub: https://github.com/shamiursunny/sunnyware
- Space:  https://huggingface.co/spaces/shamiur/sunnyware

## Current state (last session: 2026-10-10)
- Commit: e34f27d (both GitHub + HF in sync)
- Health: /health/ready -> status ok, llm ok, python_eval ok, 15 tools
- Model: openai/gpt-oss-20b on Groq (LLM_BASE_URL=https://api.groq.com/openai/v1)
- Vector store: 4 chunks (2 CSV + 2 PDF) in per-tenant FAISS

## What's working (verified live)
- Document upload: /api/rag/upload (PDF, DOCX, CSV, XLSX, TXT, MD; 20 MB max)
- Retrieval: /api/rag/query (with optional FP&A narrative via LLM)
- Agent tool rag_search: callable from WebUI chat with natural language
- Agent tool python_eval: pandas, duckdb, matplotlib, scipy, sklearn, etc.
- Inline matplotlib charts in the WebUI
- Native tool calling via Groq
- Multi-turn sessions without token overflow

## What's next (priority order)
1. WebUI drag-drop upload button (Part 31H) — close last UX gap
2. Archive stale scripts/*.bak.partN* files
3. README refresh for public docs
4. Part 32 — next feature (define together)

## Key files
- src/sunnyware/main.py               FastAPI app + lifespan
- src/sunnyware/orchestrator.py       ReAct loop + tool aliases + retries
- src/sunnyware/llm.py                Groq client (max_tokens=2000)
- src/sunnyware/memory.py             Event log (payload caps at 2000 chars)
- src/sunnyware/prompts.py            Directive system prompt
- src/sunnyware/webui.py              Gradio chat UI
- src/sunnyware/routes/rag.py         /api/rag/* endpoints
- src/sunnyware/rag/                  RAG package (7 modules)
- src/sunnyware/tools/                Agent tools (15 total)
  - _sandbox.py                      Sandboxed exec runtime
  - python_eval.py                   Data-science workbench
  - rag_search.py                    Semantic search over uploaded docs

## Conventions
- Dual-remote deploy: git push origin main && ./push_hf.sh
- Every feature ships with scripts/*_smoke.py (numbered PASS/FAIL checks)
- Commit style: "Part NN: short description"
- Prefer Python heredocs over bash heredocs

## Key gotchas (do not re-learn)
- gpt-oss-20b is a REASONING model — needs max_tokens >= 1500 (uses 60-75% on internal reasoning)
- Memory payloads capped at 2000 chars to avoid Groq TPM 413 errors
- Tool-result truncation in orchestrator: strips base64 + caps at 500 chars
- Tool-name aliases: python -> python_eval, rag -> rag_search (gpt-oss shortens)
- Placeholder retry: if model returns "What next?" after a tool call, auto-retry
- Chart base64 injection: replaces {{image_base64}} placeholder with real data
- polars is REMOVED (requires AVX2/FMA; crashes on 3rd-gen i7)
- HF Space rebuild: ~1 min for code, ~10 min if requirements.txt changes

## Full docs in repo (fetch or ask owner to paste)
- HANDOFF.md  — detailed state + full queue
- AGENTS.md   — architecture + briefing for AI assistants
- WORKFLOW.md — dual-remote workflow + per-part progress log

## Session-end ritual
Ask the AI: "Update HANDOFF.md with what we did and commit + push both remotes."
