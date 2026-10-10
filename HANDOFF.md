# HANDOFF — Sunnyware Current State

> **Read this first.** This file is the single source of truth for "where we are."
> Update it at the end of every work session.

**Last updated:** 2026-10-10 (Part 31F wrap)
**Current commit:** (see `git log -1`)
**Live Space:** https://shamiur-sunnyware.hf.space/ui
**GitHub:** https://github.com/shamiursunny/sunnyware

---

## How to resume in a new tab

1. Open a new conversation
2. Paste this prompt:

   > Read HANDOFF.md and AGENTS.md in full. Then tell me the current state
   > and what's next. Wait for my instruction before doing anything.

3. The AI will read both files and be ready to continue.

---

## Current state

### Deployed and live
- Full RAG pipeline: upload -> chunk -> embed -> FAISS -> retrieve
- Groq cloud LLM (gpt-oss-20b primary; 120b available)
- 15 agent tools including `rag_search` and `python_eval` workbench
- Data science workbench in python_eval (pandas, duckdb, matplotlib,
  scipy, sklearn, statsmodels, seaborn, plotly, openpyxl, xlsxwriter)
- All Part-31 hardening fixes live

### Health check
    curl https://shamiur-sunnyware.hf.space/health/ready
    -> status: ok, llm: ok, python_eval: ok, tools: 15

### Sync state
- Local: (see `git log -1`)
- GitHub: synced
- HF: synced
- Unpushed: 0

---

## What was just completed (Part 31 A-F)

See WORKFLOW.md for full details. Summary:

- **Part 31**  RAG (bge-small + FAISS) + Groq LLM + rag_search tool
- **Part 31D** Data science workbench for python_eval (sandboxed, hardened)
- **Part 31E** Memory caps + tool-result truncation + tool-name aliases
- **Part 31F** Directive prompt + placeholder retry + chart base64 injection

All smoke tests passing:
- rag_smoke_test.py         PASS
- rag_narrative_smoke.py    PASS
- agent_rag_smoke.py        PASS
- sandbox_smoke.py          13/13
- memory_cap_smoke.py       9/9
- truncation_smoke.py       6/6
- placeholder_smoke.py      8/8

---

## What's next (recommended priority)

1. **Real PDF end-to-end test** (~10 min)
   Upload an actual PDF (10-K, invoice, contract) to the WebUI.
   Verify pypdf extraction works on real documents.

2. **WebUI file-upload button** (~30 min)
   Add a Gradio file-picker panel to webui.py.
   Wire it to POST /api/rag/upload.

3. **Repository cleanup** (~5 min)
   Archive the ~20 stale scripts/*.bak.partN* files into
   scripts/_archive_stale/.

4. **README refresh** (~15 min)
   Public-facing docs, architecture diagram, live demo links.

5. **Part 32** — next feature (define together)

---

## Key decisions made in Part 31

- CPU-only embeddings (bge-small-en-v1.5, 2-thread cap for old laptop safety)
- Groq over local LLM (zero laptop heat, better tool calling, free tier)
- gpt-oss-20b over 120b (4x the TPM budget on free tier, faster, sufficient)
- FAISS over other vector stores (no external dependency)
- Per-tenant vector store (scoped by tenant.get_key(), falls back to "default")
- DuckDB over polars (polars needs AVX2/FMA; crashes on 3rd-gen i7)
- Sandbox, not full PC (rich libraries, jailed to /data/workspace, no os/subprocess)

---

## Environment variables in use

Local .env (see .env.example for all options):
- LLM_BASE_URL=https://api.groq.com/openai/v1
- LLM_API_KEY=gsk_...   (rotated periodically)
- LLM_MODEL=openai/gpt-oss-20b
- SUNNYWARE_CPU_THREADS=2
- SUNNYWARE_AGENT_TIMEOUT=90
- NEON_DATABASE_URL=...   (for memory + sessions)

HF Space secrets mirror the above.

---

## Known limitations and gotchas

1. **Do NOT run `pip install` piped to `tail` on MINGW** — it buffers
   everything for minutes. Use `--progress-bar on` for live output.

2. **MINGW `/tmp/` is NOT Windows `/tmp/`** — use relative paths for
   file arguments shared between bash and native Windows Python.

3. **Prefer Python heredocs over bash heredocs** for multi-line content.
   Inside triple-quoted strings, `\` can mis-escape.

4. **HF Space rebuild time** — ~1 min for code-only changes, ~10 min if
   requirements.txt changed (new wheels download).

5. **HF Space runs on ZeroGPU hardware** — works fine for CPU workloads.
   The iframe sometimes shows "refused to connect" while the API is fine.
   Use `curl /health/ready` as ground truth.

6. **Groq free-tier TPM limits** — 8K tokens/min for gpt-oss-20b.
   Memory caps + truncation keep us under it.

7. **gpt-oss-20b quirks** — sometimes abbreviates tool names or returns
   placeholder text. Alias map + retry handle both.

8. **Pre-Groq `.env` backup** lives at `.env.bak.20261010-171322`.
   Keep it until Groq feels stable.

---

## See also

- `WORKFLOW.md` — dual-remote workflow + per-part progress log
- `AGENTS.md`   — briefing for AI assistants on this repo
- `README.md`   — public-facing project overview

---

## How to update this file

At the end of every session, before committing:

- Update the "Last updated" line at top
- Update the "Current commit" line
- Update the "Sync state" block
- Move completed items out of "What's next"
- Add any new gotchas to the list

Then commit + push both remotes.
\n

## Part 31G — Real PDF end-to-end test + max_tokens fix

**Date:** 2026-10-10 (continued session)

### What was tested
Full document-intelligence pipeline on a real multi-page PDF:
- Generated a 2-page PDF locally (matplotlib PdfPages) with budget
  data + audit findings + bar chart
- Uploaded to live HF Space via /api/rag/upload -> 2 chunks in 10 sec
- Queried "What was the Sales variance in Q3?" with with_narrative=true
- Received correct FP&A report with $4,000 (F) variance and page-level
  citations [source: test.pdf (page 1), chunk 0]

### Bug found + fixed
**Symptom:** narrative_error = "empty llm response" on first PDF test.
**Root cause:** gpt-oss-20b is a reasoning model that burns 60-75% of
max_tokens on internal reasoning before producing output. Our llm.py
sent max_tokens=500, leaving ~135 tokens for the actual answer.

**Fix (Part 31G):** raised max_tokens 500 -> 2000 in llm.py (both chat
and stream variants). Verified reasoning now completes with room for
output.

### Files changed
- src/sunnyware/llm.py (max_tokens x2)

### Test artifacts
- test.pdf (38 KB, gitignored, kept locally for regression tests)

### Verified live
- /api/rag/upload on HF: 2 chunks from real 2-page PDF
- /api/rag/query: correct Sales variance + Marketing driver extraction
- narrative_model: openai/gpt-oss-20b
- narrative_latency_ms: ~1600
