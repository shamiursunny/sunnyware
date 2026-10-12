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
\n

## WebUI PDF Validation (2026-10-10, session end)

Verified end-to-end in the browser at https://shamiur-sunnyware.hf.space/ui:

- User typed natural-language query asking for Q3 audit Marketing ad spend
- Agent chose rag_search tool (native protocol)
- Retrieved test.pdf (page 2) at 0.36 distance
- LLM extracted: 20% overrun, CFO review required, Oct 20 action item
- Multi-turn follow-up ("Sales variance?") returned $4,000 F correctly

Conclusion: full document-intelligence pipeline is production-validated
via both API and WebUI. Drag-drop upload button is the only remaining
UX gap (next session — Part 31H).
\n

## Part 31H + 31I + 31J (2026-10-10, extended session)

### Part 31H - WebUI upload button
- File picker in header (paperclip icon next to new session)
- Chat shows progress + result (e.g. "uploaded test.pdf - 16 chunks - 12652 ms")
- Header badge tracks doc count (docs: N)
- No curl needed for uploading

### Part 31I - Token budget hardening
- rag_search k default 3 -> 2
- Chunk preview cap 400 -> 1200 chars
- 429 rate-limit auto-retry (20s backoff, up to 2 retries)
- Prompt prefers rag_search over web_search for doc references
- Fixed: chat() signature missing _retry_depth param

### Part 31J - Iteration headroom
- MAX_ITERATIONS 5 -> 7 for complex multi-tool queries

### Known limitation
- gpt-oss-20b sometimes hits "analysis paralysis" on complex multi-hop
  queries - uses all iterations evaluating without committing.

### Verified live in browser
- Upload: attention paper (2.1 MB PDF) -> 16 chunks in 12.6 sec
- Query: BLEU score 28.4 (correct)
- Query: layers/heads/dim (6/8/512 correct)
- Rate limit: 429 auto-recovers silently in ~20s
\n

## Part 31K + 31K-ext (2026-10-10, late session)

### Part 31K — Stronger prompt rules
- RAG FIRST: if any document is uploaded, prefer rag_search for all
  factual questions about its content (not just explicit 'in my docs')
- TOOL OBEDIENCE: if user says 'use X tool', MUST call it, no mental simulation

### Part 31K-ext — Groq hallucinated-tool-name retry
- On HTTP 400 'Model called <X> tool which was not enabled', retry with
  an injected system hint: "The only Python tool is named exactly
  'python_eval'. Never use 'python' or abbreviations."
- Verified: fixes the multi-tool chain case (512 x 8 x 6 = 24,576)

### Known limitation (documented, not fixed)
- For generic factual questions about a document ('What BLEU score did
  the Transformer achieve?'), gpt-oss-20b sometimes still chooses
  web_search instead of rag_search, even with 'RAG FIRST' rule.
- Root cause: model treats those as general-knowledge queries.
- Mitigation attempts tried: prompt rules (partial help).
- Real fix would need server-side tool_choice enforcement or a
  different model.
\n

## Part 32 Phase 1 + Phase 3 (2026-10-11, multi-provider router)

### Phase 1 - Multi-provider router
- New: src/sunnyware/providers.py (Provider dataclass + cooldown tracking)
- Rewrote: src/sunnyware/llm.py as 2-layer router
  - _chat_single(): all Part-31 retries preserved
  - chat(): iterates providers, falls through on error
  - Rate-limit cooldown = 60s, generic error cooldown = 10s
- LLM_PROVIDERS env var (comma-separated priority list)
- Legacy single-provider mode preserved when LLM_PROVIDERS unset

Configured providers (priority order):
1. Groq          - openai/gpt-oss-20b           - 200K tokens/day
2. Gemini        - gemini-2.0-flash             - 1.5K requests/day
3. OpenRouter    - llama-3.2-3b-instruct:free   - 50 requests/day

Combined free budget: ~1,900 requests/day

### Phase 3 - Monitoring
- New: GET /api/providers/status
  - Returns per-provider: name, model, base_url host, cooling status,
    cooldown_remaining_s, success_count, fail_count, last_error
- Updated: /health/ready now includes providers count
- WebUI: "via <provider>" badge in header, updates after each message

### Verified live
- mode: "multi" with 3 providers listed
- Groq served first test request (success_count = 1)
- WebUI badge shows "via groq" after response
- API returns provider at top level + inside result dict

### Config (HF Space secrets)
- LLM_PROVIDERS=groq,gemini,openrouter (Variable)
- GROQ_BASE_URL, GROQ_API_KEY, GROQ_MODEL
- GEMINI_BASE_URL, GEMINI_API_KEY, GEMINI_MODEL
- OPENROUTER_BASE_URL, OPENROUTER_API_KEY, OPENROUTER_MODEL
- Legacy LLM_BASE_URL/LLM_API_KEY/LLM_MODEL kept as fallback

### Phase 2 - TODO next session
- Local MiniCPM5-2B fallback in HF Space
- Constraint: HF Spaces Docker SDK requires PRO ($9/mo)
- Workaround: run llama.cpp as subprocess inside existing Gradio Space
- Bucket: shamiur/minicpm5-2b-bucket (to create)
- GGUF: MiniCPM5-2B-Q4_K_M.gguf (1.56 GB)
- Speed expectation: ~8-15 tok/s on 2 vCPU (~30-50 sec response)
\n

## Part 32 Phase 2 - Local model deployed (parked as fallback)

### Current status
- Code deployed: commit 6e8d734
- Local MiniCPM5-2B provider registered in the router (type=local)
- Parked LAST in priority: LLM_PROVIDERS=groq,gemini,openrouter,local
- Cloud-first for production (fast, no GIL issues)

### HF Space config (all set)
- Variable: LLM_PROVIDERS=groq,gemini,openrouter,local
- Variable: LOCAL_MODEL_ENABLED=1
- Variable: SUNNYWARE_AGENT_TIMEOUT=300
- Secret: LOCAL_MODEL_PATH=/models/shamiur/MiniCPM5-2B-GGUF-bucket/MiniCPM5-2B-Q4_K_M.gguf
- Secret: LOCAL_BASE_URL=http://localhost:8080/v1
- Secret: LOCAL_MODEL=minicpm5-2b
- Bucket mounted at /models (read-only)

### Known limitation - GIL blocking
Local model runs in-process via llama-cpp-python. During inference on 2 vCPU:
- llama.cpp holds the GIL
- Python event loop is blocked
- Entire FastAPI Space freezes (all endpoints return empty / timeout)
- Health check also frozen until inference completes

Confirmed by: 129+ sec WebUI hang, empty /health/live response during local call.

### Fix for next session - pick one
1. Run local model in multiprocessing.Process (GIL isolated)
2. Spawn llama-server as subprocess on port 8080 (HTTP isolation)
3. Accept as "slow batch-only fallback" - invoke only via direct API, never in chat

### What's working today
- 3 cloud providers (Groq, Gemini, OpenRouter) with auto-failover
- WebUI badge shows serving provider
- Local model is deployed and loadable - just not chat-friendly yet

### Files added for Phase 2
- src/sunnyware/local_llm.py - in-process llama.cpp wrapper
- providers.py: added provider_type field ("http" | "local")
- llm.py: router handles local provider type
- main.py: preload task (runs at startup if lifespan fires)
- requirements.txt: llama-cpp-python + prebuilt wheel index
\n

## Part 32 Phase 2 - VERDICT: MiniCPM5-2B not viable on 2 vCPU

### Smoke test result (2026-10-11)
- Test ran: /api/local-model/smoke (7 sub-tests)
- Outcome: HTTP 502 after 490 sec (8.2 min)
- Cause: HF gateway killed the connection because the Space was
  unresponsive for too long

### Root cause (confirmed)
1. CPU: 2 vCPU shared cannot run a 2.5B model interactively
2. GIL: llama-cpp-python holds Python GIL during inference, blocking
   the entire FastAPI event loop (even /health/live froze)
3. HF gateway timeout: ~8 min max before returning 502

### Decision
- Local model REMOVED from LLM_PROVIDERS priority list
- LLM_PROVIDERS=groq,gemini,openrouter (cloud-only, stable)
- Local code stays deployed but dormant (reactivate by adding "local"
  back to LLM_PROVIDERS if infrastructure changes)

### Future paths (if local becomes a hard requirement)
a) HF PRO ($9/mo) -> 8 vCPU -> ~4x faster -> 2-3 min/response
   (still slow but usable for non-chat batch tasks)
b) Swap to Granite 4.0-H-1B (840 MB) or Qwen2.5-0.5B (350 MB) ->
   actually runs on 2 vCPU in 30-60 sec, but tool-calling quality drops
c) Own GPU server (out of scope for HF Space)

### What's deployed but dormant
- src/sunnyware/local_llm.py (in-process llama.cpp wrapper)
- src/sunnyware/providers.py (supports type=local)
- src/sunnyware/llm.py (routes local provider)
- Bucket mount at /models (read-only)
- /api/local-model/smoke endpoint (for future testing)
- HF secrets: LOCAL_MODEL_PATH, LOCAL_BASE_URL, LOCAL_MODEL
- HF variable: LOCAL_MODEL_ENABLED=1

### Verified working today
- 3 cloud providers (Groq, Gemini, OpenRouter) with auto-failover
- WebUI "via <provider>" badge
- ~1,900 free requests/day combined
- Zero more daily token exhaustion
\n

## NVIDIA NIM Provider - PENDING SUPPORT VERIFICATION

### Status
- NVIDIA Cloud Account created: sunnyware (account #1068493506984984, ACTIVE)
- build.nvidia.com still shows "API Access Unavailable - contact support"
- Cause: Bangladesh not available in phone verification dropdown

### Action taken (2026-10-11)
- Sent manual verification request via build.nvidia.com/settings/api-keys
  -> Contact Support button
- Duplicate email to help@build.nvidia.com
- Attached screenshots: verification page, country dropdown, live Space

### Awaiting
- NVIDIA support response (24-72 hours typical)

### Once verified
1. Get API key from https://build.nvidia.com/settings/api-keys
2. Run: export NVIDIA_API_KEY=nvapi-...
3. Run: python scripts/probe_nvidia.py
   (discovers which tool-calling models are available)
4. Add 3 HF secrets:
   NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
   NVIDIA_API_KEY=nvapi-...
   NVIDIA_MODEL=meta/llama-4-maverick-17b-128e-instruct  (or best from probe)
5. Edit LLM_PROVIDERS variable:
   groq,gemini,openrouter,nvidia
6. Verify with /api/providers/status -> should show 4 providers

### Why this matters
NVIDIA NIM free tier: ~40 requests/minute (no daily token cap)
Effectively ~57,600 requests/day. Adds huge resilience to the router.

### Files ready
- scripts/probe_nvidia.py (key verifier + model discovery)
\n

## Part 33 FINAL (2026-10-11) - 3/3 providers PASS

### Live status
| Priority | Provider | Model | Latency | Status |
|---|---|---|---|---|
| 1 | Groq | qwen/qwen3.8-27b | 233ms | PASS |
| 2 | Gemini | gemini-2.5-flash | 574ms | PASS |
| 3 | OpenRouter | liquid/lfm-2.5-2.6b:free | 6230ms | PASS |
| - | Mistral | (removed from priority) | - | IP throttled |

### Mistral decision
Two separate accounts tested (old + new key), both got HTTP 429
"Rate limit exceeded" from Bangladesh network. Confirmed pattern:
- Mistral throttles by IP/region, not just by account
- HF Space + local dev IPs both hit the same upstream throttle
- Even brand-new accounts don't bypass it from this region

Decision: REMOVED `mistral` from LLM_PROVIDERS.
Secrets kept dormant - reactivate with one HF variable change if
Mistral ever lifts the throttle, or if deploying from a different
network region.

### Current HF config
Variables:
- LLM_PROVIDERS=groq,gemini,openrouter
- MODEL_AUTORESOLVE=1
- SUNNYWARE_AGENT_TIMEOUT=300
- SUNNYWARE_CPU_THREADS=2

Secrets (all kept):
- GROQ_* (qwen/qwen3.8-27b, primary)
- GEMINI_* (gemini-2.5-flash)
- OPENROUTER_* (liquid/lfm-2.5-2.6b:free)
- MISTRAL_* (dormant)
- LOCAL_* (dormant)
- LLM_* legacy fallback
- NEON_DATABASE_URL

### Auto-resolver live
- /api/models/resolve shows per-provider cache state
- /api/models/resolve/refresh invalidates cache
- Preference lists in src/sunnyware/model_resolver.py
- Self-heals when any provider retires a model (e.g. OpenRouter's
  earlier gemma-4-26b:free retirement)

### Scripts for future probes
- scripts/probe_all_providers.py - scan all provider /models
- scripts/providers_smoke.py - per-provider health test

### Next session
1. NVIDIA NIM integration (pending support verification)
2. Optional: re-test Mistral in 1-2 weeks
3. Part 34 - define next feature
\n

## Part 34 - Streaming WebUI (2026-10-12)

### What shipped
- WebUI now streams tokens live via SSE (Server-Sent Events)
- Backend already had /api/agent/run/stream (Part 10) - frontend now uses it
- Replaced fetch().then() with ReadableStream + TextDecoder
- Tokens appear in real-time as they are generated
- Tool call indicators show as tools fire
- Provider badge updates on 'done' event

### Files changed
- src/sunnyware/webui.py - replaced sendMessage() with streaming version

### Bugs fixed during build
- Python triple-quoted HTML string was interpreting \n as actual newlines
  in served JS - fixed by doubling backslashes (\\n -> literal \n)
- Multi-line comment with embedded newlines broke JS parser - joined to one line

### Verified live
- 3-sentence story: 750ms
- 10-sentence essay: 1003ms
- No JS console errors
- Streaming visible on longer responses (first token <1s)

### Next
1. Chat history persistence + sidebar (Part 35?)
2. Multi-file upload
3. NVIDIA NIM (pending verification)
\n

## Part 35 - Chat History Persistence + Sidebar (2026-10-12)

### What shipped
- Left sidebar (240px) with session list
- "+ New chat" button creates fresh session (doesn't wipe old ones)
- Auto-titling: first user message becomes session title (40 char cap)
- Multi-session localStorage: sunnyware_sessions_v2 (JSON)
- Click session -> loads full conversation history
- Hover session -> shows X to delete
- Active session highlighted with green border
- Mobile: sidebar hides at <720px (media query)

### Storage schema
localStorage['sunnyware_sessions_v2'] = {
  "web-xxxxx": {
    id: "web-xxxxx",
    title: "first user message (truncated to 40 chars)",
    created: <unix_ms>,
    messages: [{role, text, ts}, ...]
  },
  ...
}
localStorage['sunnyware_active_v2'] = "web-xxxxx"

### Caps
- MAX_SESSIONS = 20 (oldest pruned by created time)
- MAX_MSGS_PER = 200 per session
- Only user/agent/error messages persisted (tool markers skipped)

### Files changed
- src/sunnyware/webui.py: +265 lines (CSS, HTML layout, JS logic)
- Old single-session key 'sunnyware_session' abandoned (fresh start)

### Bugs fixed during build
- f-string backslash issue (Python 3.10 restriction) — split into concatenation
- CSS/HTML structure needed two-pass patch (CSS first, JS later)

### Verified live
- Sidebar renders with session list
- Conversations persist across browser refresh
- "+ New chat" creates new session, keeps old
- Session switch loads history correctly
- Auto-titles work

### Next session
1. Multi-file upload
2. NVIDIA NIM (pending verification)
3. Part 36 - define next
\n

## Part 36 - Multi-file Upload (2026-10-12)

### What shipped
- File picker accepts multiple files (Ctrl+Click or Shift+Click)
- Sequential upload with per-file progress: [1/N] filename.pdf...
- Per-file result: ✓ for success, ✗ for failure
- Continues after failures (doesn't stop the batch)
- Summary line at end: "Done: N uploaded (M chunks) · K failed"
- docs:N badge refreshes after batch completes
- Zero backend changes (loop of existing /api/rag/upload calls)

### Files changed
- src/sunnyware/webui.py (file input gets 'multiple', handler loops)

### Verified live
- 4-file batch uploaded: 1 OK, 3 failed cleanly with error messages
- Progress markers [1/4]..[4/4] shown correctly
- Failure didn't block subsequent uploads
- Summary line accurate

### Known issue (investigate later)
- 3 XLSX files returned "no extractable text found in file"
- Likely: empty workbooks, header-only sheets, or formula-only cells
- The extractor uses data_only=True; if XLSX never opened in Excel,
  cached formula values may be missing
- Not a bug in multi-file upload - the failure was reported correctly

### Next session
1. Investigate XLSX extractor edge cases (optional)
2. NVIDIA NIM integration (pending verification)
3. Part 37 - define next
\n

## Part 37 - XLSX hardening + diagnostics + Groq swap (2026-10-12)

### What shipped
1. XLSX extractor hardened:
   - Scans first 10 rows to find header row (title-row tolerant)
   - Falls back to data_only=False (formula strings) if cached values empty
   - Last-resort: dumps every non-empty cell as text block
   - Column-letter fallback (col_A, col_B) when header cell blank

2. Upload error diagnostics:
   - Empty-file error now includes blocks_returned, total_rows,
     total_text_chars, per_block breakdown, and per-extension hint
   - WebUI displays these diagnostics inline on failure

3. max_tokens reduced 2000 -> 900:
   - Groq qwen3.8-27b free tier has 1000 OTPM cap - our old requests
     exceeded it, causing HTTP 429
   - 900 leaves headroom under all providers' limits

4. GROQ_MODEL reverted to openai/gpt-oss-20b:
   - qwen3.8-27b OTPM too tight for our usage pattern
   - gpt-oss-20b has 8000 TPM (8x more headroom)
   - Proven reliable across Parts 31-34

### Bug fixed (regression)
- JS escape bug: single \n in Python triple-quoted HTML -> real newline
  in served JS -> syntax error. Doubled backslash in source -> fixed.
- Same pattern as Part 34; needs to be a habit when adding JS strings.

### Verified live
- WebUI fully restored (session ID, docs badge, sidebar, chat all work)
- Session persistence working across 3+ sessions
- gpt-oss-20b chat responds in ~1-2s
- Auto-titles, active session highlighting, markdown all working

### Next session
1. Retest the 4 XLSX files with new extractor (may fix 2-3 now)
2. NVIDIA NIM integration (pending verification)
3. Part 38 - define next
