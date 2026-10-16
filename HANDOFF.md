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
\n

## Part 38 - Neon Fallback for Session History (2026-10-12)

### The problem
Browser cache clear (Ctrl+Shift+Delete with "Cookies and other site data"
checked) wiped localStorage -> all WebUI chat history appeared lost.
BUT: every message is also logged to Neon DB by the backend.
The WebUI just never read from Neon.

### The fix
WebUI now uses a two-tier session store:
1. localStorage (fast, offline-friendly) - primary
2. Neon DB (durable, browser-wipe proof) - fallback

On page load:
- If localStorage has sessions -> use them
- If localStorage is EMPTY -> call /api/sessions, then for each web-*
  session, call /api/sessions/{key}/history -> rebuild localStorage

On session click:
- If session in localStorage -> load directly
- If session NOT in localStorage (but exists on Neon) -> fetch
  history, save to localStorage, then load

### Functions added to webui.py
- fetchSessionsFromNeon()          - GET /api/sessions
- fetchHistoryFromNeon(key)        - GET /api/sessions/{key}/history
- hydrateFromNeon()                - bulk load all web-* sessions
- loadSessionWithFallback(id)      - single session fetch + load

### UI feedback
- "Restored N session(s) from database." message at top of chat
  when hydration runs

### Verified live
- Wiped localStorage via F12 console
- Page reloaded -> all historical sessions reappeared in sidebar
- Clicking any restored session loaded full conversation from Neon
- Auto-titles, markdown, active highlighting all working

### Backend endpoints used (already existed from Part 9)
- GET /api/sessions                       -> list all sessions
- GET /api/sessions/{key}/history?limit=N -> events for a session

### Reliability improvement
Browser wipes, cache clears, private mode, or a different browser
device -> history can now be restored. Only total Neon DB deletion
would lose data (in which case JSON export feature is the safety net
for a future session).

### Next session
1. NVIDIA NIM integration (pending verification)
2. Optional: Export/Import JSON button (extra belt & suspenders)
3. Part 39 - define next
\n

## Part 40 - Token Usage Dashboard (2026-10-12)

### What shipped
- Stats button in sidebar header opens modal dashboard
- Modal shows:
  - 4 summary cards: total calls, input tokens, output tokens, cost USD
  - "By model" table: per-model calls/tokens/cost breakdown
  - "Pricing" table: USD per 1M input/output tokens
- Data source: existing /api/usage + /api/usage/pricing (Part 29)
- Rendering: pure DOM API (createElement) - zero string-escape risk
- Close methods: X button OR click outside modal backdrop

### Files changed
- src/sunnyware/webui.py: +modal CSS, +Stats button, +modal HTML, +JS functions
- scripts/smoke_test_part40.py: 26-check verification

### Bugs caught by pre-push gate
- Part 40 first attempt: 5 CSS rules (.modal-overlay, .modal-panel,
  .usage-grid, .usage-card, .usage-table) were silently missing because
  an earlier patch aborted before write_text. Gate detected them.
- This is exactly the value of scripts/pre_push_check.py - keeps history
  clean and rollback-safe.

### Verified live
- Stats button visible next to sidebar icons
- Modal shows real data (585 calls, $0.2403 cost, per-model breakdown)
- All 4 providers tracked: qwen3.8-27b, gpt-oss-20b, lfm-2.5-2.6b, gemini-2.5-flash
- Both close methods (X button, backdrop click) work

### Cumulative live features now (Parts 31-40)
- Multi-provider LLM router (Groq/Gemini/OpenRouter)
- Auto model resolver (self-healing)
- Streaming WebUI (SSE)
- Multi-session sidebar with browser-wipe-proof Neon fallback
- JSON export/import for sessions
- Multi-file upload
- Token usage dashboard
- Pre-push DevSecOps gate (5 stages)

### Next session
1. NVIDIA NIM integration (pending verification)
2. Part 41 - define next
3. Optional: use pre-push gate as the standard workflow going forward

## 2026-10-14 — Part 87-88d
- Token economy fixes: max_tokens 900->2048, MAX_ITERATIONS 7->3, dedup, preflight rules.
- Token burn: 6 iterations / 10k tokens for "hi" -> 1 iteration / 200 tokens.
- SQL query: 3 tool calls -> 1 tool call.
- Confirmed: Firefox InPrivate mode + tracking protection + VPN blocks cdn.jsdelivr.net,
  causing (empty response). Normal window works. Part 89 will self-host marked.js.
- Next: Part 89 (self-host marked.js), Part 90 (token budget guard), cleanup old sandboxes.
- Current HEAD: ac66e30

## 2026-10-14 — Part 90 + 90b
- Per-request token budget guard: MAX_REQUEST_TOKENS = 8000
- _estimate_tokens helper (char-based, ~4 chars/token)
- Trips on cumulative >= 8000, returns friendly message + budget_exceeded flag
- SSE event 'budget_exceeded' emitted
- Part 90b fix: excluded tools_schema (~8700 tokens) from estimate
- routes/agent.py: propagates budget_exceeded + tokens_used to client
- NEW: scripts/smoke_test_part90.py (11 checks, ASCII-safe)
- Verified: hi -> ~700 tokens, budget_exceeded False
- Verified: 67k chars -> trips at 34837/8000, budget_exceeded True
- HEAD: 65ad114
- NEXT: monitor 429s; NVIDIA NIM integration; optional WebUI budget styling

## 2026-10-14 — Part 91
- WebUI styling for budget_exceeded SSE event
- webui.py: budgetExceeded flag, SSE handler case, classList.add('budget')
- webui.py: new .msg.agent.budget CSS (amber, #ffb020 border)
- webui.py: 'BUDGET LIMIT:' ::before prefix (ASCII-safe)
- NEW: scripts/smoke_test_part91.py (8 checks, ASCII-safe)
- Verified: 90k-char prompt renders amber bubble + friendly abort message
- HEAD: e09abd3
- NEXT: monitor 429s; NVIDIA NIM; optional exact token counts via llm.py usage

## 2026-10-14 — Parts 93, 93b, 94, 95, 95b
- Professional WebUI redesign (5 iterations):
  - Part 93: header (gradient S + session pill + icon buttons + menu)
  - Part 93b: paperclip inside composer (ChatGPT-style)
  - Part 94: doc count badge = just a number; overflow button visible
  - Part 95: menu moved to sidebar bottom-left, opens upward
  - Part 95b: null-safe clearBtn (fix JS crash from removed #clear)
- NEW: scripts/smoke_test_part93.py (52 checks)
- Verified live: sidebar menu opens, no Console errors, paperclip works
- HEAD: a984bcb
- LESSON: always grep for getElementById + addEventListener before
  removing an id from HTML. Part 95 removed #clear and it crashed
  every subsequent init call silently.

## 2026-10-14 — Parts 96 + 96b
- Real token counts from provider usage (replaces char/4 heuristic)
- llm.py: returns tokens_in / tokens_out / tokens_total
- orchestrator.py: prefers real tokens; subtracts tools_schema overhead;
  fallback heuristic no longer double-counts prompt
- MAX_REQUEST_TOKENS: 8000 -> 15000 (real counts made 8000 tight)
- NEW: scripts/smoke_test_part96.py (13 checks)
- Verified: 12k prompt -> tokens_used 10022, budget_exceeded True
- Known limit: Groq rejects very large prompts (HTTP 413); failover
  routes to OpenRouter/Gemini
- HEAD: ae65d27
- NEXT: monitor 429s; NVIDIA NIM; optional long-prompt routing tweak

## 2026-10-14 — Parts 97 + 97b
- Pollinations AI added as 4th fallback provider (free tier)
- Base URL: https://text.pollinations.ai/openai (OpenAI-compatible)
- Model: 'openai' (GPT-OSS-20b); fallbacks registered in resolver
- HF Space config:
  - LLM_PROVIDERS = variable (was colliding with secret)
  - POLLINATIONS_* = secrets
- LIVE PROOF: 'POLLINATIONS WORKS' via /api/agent/run with
  provider=pollinations, iterations=1
- NEW: scripts/smoke_test_part97.py (10 checks)
- LESSON: LLM_PROVIDERS on HF must be a variable, not a secret --
  duplicate name -> 'Collision on variables and secrets names' -> crash
- HEAD: 97d7123
- NEXT: monitor status; NVIDIA NIM; optional Pollinations image gen tool

## 2026-10-15 — Parts 98 + 98b + 98c
- New tool: image_generate (free text-to-image via Pollinations.AI)
- Models: flux (default), turbo, gptimage, qwen-image, kontext, nanobanana
- Returns {image_base64, image_format} — same contract as chart_from_data
- 128-2048px clamp, 45s timeout, 2 MB size cap, magic-byte detection
- Part 98b: 'call EXACTLY ONCE' (rate limit 1/15s)
- Part 98c: WebUI 'tool_result' SSE case + .msg-image CSS — renders
  any tool's image_base64 result inline (also benefits chart_from_data
  and browser_screenshot)
- Part 98c: tool description says 'Do NOT include base64 in reply'
- Tools count: 58 -> 59
- Verified: photorealistic orange cat JPEG @ 1024x1024, model=flux,
  rendered inline in WebUI (screenshot proof)
- NEW: scripts/smoke_test_part98.py (24 checks)
- HEAD: e27a541
- NEXT: monitor 429s; NVIDIA NIM; video gen; long-prompt routing; TTS

## 2026-10-15 — Part 99
- Long-prompt routing: skip providers that can't fit the prompt
- Provider.max_prompt_tokens field (defaults per provider)
- Env override: {PREFIX}_MAX_PROMPT_TOKENS
- llm.py: _estimate_prompt_tokens() + skip logic in multi-provider loop
- status() exposes max_prompt_tokens
- FIXES: 30k-char prompt now routes to openrouter (Groq auto-skipped)
- NEW: scripts/smoke_test_part99.py (17 checks)
- HEAD: 20ed50b
- NEXT: monitor 429s; NVIDIA NIM; video gen; TTS; learn real limits

## 2026-10-15 — Parts 100 + 100b
- Auto-learn provider prompt limits from 413 errors
- New module: provider_limits.py
- learn_limit(name, sent_tokens) -> max(500, sent - 200)
- Persisted to /data/provider_limits.json (HF bucket)
- POSIX-only /data detection (Windows falls back to ./data)
- Observable writes (returns bool, logs failures, verifies round-trip)
- Precedence: env > learned (if lower) > hardcoded default
- llm.py: _is_too_large_error() + learn call + 60s cooldown
- Debug endpoints:
  GET  /api/providers/limits
  POST /api/providers/limits/reset
- NEW: scripts/smoke_test_part100.py (44 checks)
- Verified: learned={'groq': 8403} persisted across HF restart
- HEAD: ad38fcf
- NEXT: empty-response handling; NVIDIA NIM; TTS
- KNOWN ISSUE: provider returning ok=True with empty content returns
  "Agent failed" instead of trying next provider (surfaced during Part
  100 test when Groq 413'd). Deferred to a future part.

## 2026-10-15 — Part 101
- Empty-response fallback in multi-provider chain
- _is_empty_response(r): ok=True + no content + no tool_calls
- Both HTTP and local paths: cooldown + metric + continue
- Fixes "Agent failed | empty LLM response" bug (surfaced in Part 100)
- Verified: 30k prompt -> openrouter -> 3,850-char real answer
- NEW: scripts/smoke_test_part101.py (22 checks)
- HEAD: 1214276
- NEXT: monitor 429s; NVIDIA NIM; video gen; TTS; possible retry cycle

## 2026-10-15 — Part 102
- Retry policy for full failover cycle
- When all providers cooling AND recovery imminent (<= 20s):
  wait min(min_cool + 0.5, 8.0)s then retry once
- _retry_depth=1 guard prevents infinite retries
- Metric llm_request_retried + diagnostic print lines
- NEW: scripts/smoke_test_part102.py (18 checks)
- HEAD: 0da91ab
- NEXT: monitor 429s; NVIDIA NIM; video gen; TTS; provider metrics dashboard

## 2026-10-15 — Part 103
- Provider health metrics dashboard
- New endpoint: GET /api/providers/metrics
- Aggregates session stats + lifetime counters + storage diag
- Uses _sum_prefix() over metrics.snapshot() for extensibility
- NEW: scripts/smoke_test_part103.py (33 checks)
- Verified: 4 providers, learned=8403 for groq, storage=hf:/data
- HEAD: b48173f
- NEXT: monitor metrics; NVIDIA NIM; video gen; TTS; WebUI health panel

## 2026-10-15 — Part 104
- WebUI provider health panel in the Stats modal
- Renders /api/providers/metrics: table + summary + footers
- Auto-refresh 10s while open
- Modal title: 'Stats & Provider Health'
- NEW: scripts/smoke_test_part104.py (36 checks)
- HEAD: f6160ce
- NEXT: monitor metrics; NVIDIA NIM; video gen; TTS; per-message provider badge

## 2026-10-15 — Part 105
- Per-message provider chip in chat
- 'via groq · 1.2s' appears under each assistant bubble
- lastProvider tracked per-request, set in 'final' + 'done' SSE handlers
- .provider-chip CSS: muted, aligned, non-selectable
- NEW: scripts/smoke_test_part105.py (18 checks)
- HEAD: a640a80
- NEXT: NVIDIA NIM (waiting on user activation); video gen (deferred);
  TTS; streaming-provider attribution for instant chip display

## 2026-10-15 — Parts 106 + 106b/c/d
- Persistent image attachments
- New module: src/sunnyware/attachments.py
- Serving: GET /api/attachments/{id}.{ext} + /stats
- Tools save base64 to /data/attachments on HF bucket
- Orchestrator returns attachments in all success paths
- routes/agent.py strips broken base64 markdown from history
- WebUI renders from history + persists to localStorage
- 106d handles LLM-returns-no-text case
- NEW: scripts/smoke_test_part106.py (38 checks)
- Verified: image survives refresh + navigation
- HEAD: c558e78
- NEXT: monitor attachments/stats; NVIDIA NIM (waiting); TTS; video gen

## 2026-10-15 — Parts 107 + 108 + 109
- Added 7 financial data tools for FP&A + quant roles:
  - edgar_fundamentals (SEC EDGAR XBRL, no key)
  - fred_economic (FRED macro, free key)
  - finnhub_quote (quotes + news, free key)
  - tiingo_prices (9y daily + intraday)
  - marketaux_news (news + sentiment)
  - twelvedata_prices (multi-asset)
  - fmp_fundamentals (structured statements, /stable/ API)
- All 7 API keys on HF Space secrets (verified working)
- Tools: 59 -> 66
- Fixes during integration:
  - EDGAR: UA format + /companyfacts single request
  - Tiingo: /daily/{sym}/prices suffix
  - FMP: /stable/ prefix + symbol query param
- NEW: scripts/smoke_test_part107.py (73 checks)
- Live verified: all 7 tools return real data on HF
- HEAD: ff2054f
- NEXT: FP&A/Quant role prompts; NVIDIA NIM; options data (Polygon)

## 2026-10-15 — Part 110
- Eulerpool multi-source financial data tool (8th data source)
- Curated 70 endpoints over Eulerpool's 447-endpoint API
- NEW capabilities over other tools: bonds / yield curves / fixed income,
  options chains + Greeks + IV + flow, 13F holdings, superinvestors,
  congressional trading, insider trades, economic calendar, Google Trends,
  Reddit, Fear & Greed, Wikipedia views, commodity futures, risk models,
  Fama-French factors, CFTC COT, earnings call transcripts
- Single 'action' parameter; optional 'identifier' and 'params' (JSON)
- 1h TTL cache
- Verified live: 10/10 actions return real data on HF
- Tools: 66 -> 67
- EULERPOOL_API_KEY on HF Space secrets
- HEAD: d26718f
- NEXT: FP&A / Quant role personas; NVIDIA NIM (waiting); options caching

## 2026-10-15 — Part 111
- Actuarial / insurance / risk libraries
- Added to requirements.txt + python_eval sandbox allowlist:
  * chainladder 0.10.1 (P&C IBNR)
  * lifelib 0.17.2 (life/pension models)
  * solvency2-data 0.5.0 (EIOPA RFR curves)
- haute rejected — requires Python 3.11+, HF runs 3.10.13
- Sandbox ALLOWED_MODULES extended with 12 modules (incl. transitive deps
  sparse, numba, llvmlite, modelx, libcst, asttokens, bs4, configparser,
  diskcache)
- Verified live: chainladder IBNR on RAA sample = 52,135.23
- Smoke test: scripts/smoke_test_part111.py (11 checks)
- HEAD: 3c927ce
- NEXT: role personas (FP&A / Quant / Actuary); NVIDIA NIM; insurance
  data sources (AmericasSuretyBonds MCP, NAIC API)

## 2026-10-15 — Part 112
- Role personas + per-role tool subsetting
- New module: src/sunnyware/roles.py (5 roles: general, fpa, quant, actuary, tax)
- Backend wiring: orchestrator + routes/agent (both /run and /stream)
- New endpoint: GET /api/roles
- WebUI: roleSelect dropdown in header, localStorage-persisted
- Verified: 28/28 smoke checks + 6/6 pre-push gate
- NEXT: NVIDIA NIM; per-session role; role-specific result formatting

## 2026-10-15 — Part 113A
- Per-session role persistence
- Stored in existing sessions.metadata JSONB (no migration)
- New endpoints: GET/PUT /api/sessions/{key}/role
- /run + /stream auto-persist role on first message
- WebUI syncs role on session open; PUTs role on selector change
- NEXT: role-specific result rendering (Part 113B)

### Part 113B hotfix
- /api/agent/stream (WebUI's route) now passes role to orchestrator
- orchestrator._emit start event carries accent + chip
- Fixes accent=None / chip=None in the live SSE start event

## 2026-10-15 — Part 113C
- Options-cache TTL differentiation
- In-memory cache now differentiated per action (60s / 300s / 24h / 1h)
- Metrics: eulerpool_cache_hit_<action>, eulerpool_cache_miss_<action>, eulerpool_api_calls_total
- Endpoints: GET /api/cache/stats, POST /api/cache/clear
- Smoke test: scripts/smoke_test_part113c.py (24 checks)
- NEXT: Part 113D insurance data sources (AmericasSuretyBonds, NAIC, state TDI)

## 2026-10-15 — Part 114
- CFO + CDO supervisor hierarchy
- New tool: delegate_to_agent (bounded, max depth 3, cycle-safe)
- New roles: cfo (user-facing PM), cdo (internal orchestrator)
- Delegation matrix: cfo→cdo; cdo→{actuary,quant,fpa,tax,general}
- WebUI: dropdown + borders + chips for cfo/cdo
- Bonus fix: 113B chip emoji now render correctly
- Smoke test: scripts/smoke_test_part114.py (49 checks)
- NEXT: NVIDIA NIM (blocked on account); NAIC JSON:API; AmericasSuretyBonds

### Part 114b-e — Pipeline hardening
- 114b CFO tool trim + 114c CDO tool trim + 600s timeout
- 114d compact_prompt(allowed_tools) + _execute_tool guard
- 114e STRICT PIPELINE RULE overrides base prompt
- Live-verified: User → CFO → CDO → workers → CDO → CFO → User
  on trivial task; correct answer, single delegation, no local tools
- HEAD: 16e1462

## 2026-10-15 — Parts 115, 116, 117
- Part 115: role-specific content CSS (tables/code/lists/headings)
- Part 116: role config export/import (GET /api/roles/export,
  POST /api/roles/import)
- Part 117: insurance_research tool (EDGAR + FRED)
  Verified live: 2,082 IBNR filings, 4,330 FRED series, CCSA obs.
- HEAD: 79eaaf0
- NEXT: NVIDIA NIM (blocked); optional SAM.gov federal surety
  (needs free API key from api.data.gov/signup)

## 2026-10-15 — Part 118
- govcon_data tool (71st, USAspending.gov keyless federal contracts)
- Honest replacement for SAM.gov plan
- Live: NAICS 524126 P&C insurer contracts, AIG UEI lookup,
  $48.5B Direct Health & Medical Insurance federal contracts
- Fix: spending_by_category needs category in URL path
- HEAD: d2cdf9c
- NEXT: NVIDIA NIM (blocked on account activation)

## 2026-10-15 — Parts 119-128 (roadmap complete)
- 10 of 10 multi-platform roadmap features shipped
- 78 tools total (was 71 at start of roadmap)
- All zero-LLM deterministic, except 119 (metrics wrapper around
  existing calls) and 123 (chart capture only)
- Live-verified each part on HF before moving to next
- HEAD: 2179f16
- NEXT: NVIDIA NIM (blocked on account); add roadmap tools to
  quant role for full symmetry

## 2026-10-15 — Phase A + C-2 (specialist sub-agents)
- 2 new roles: legal (Financial Legal Assistant) + risk_ins
  (Financial Risk & Insurance)
- Extended cdo delegation to include legal + risk_ins
- New tool #79: risk_metrics (12 deterministic actions)
- Zero orchestrator changes — pure registry extension
- VERIFIED live: 9 roles in /api/roles, both new roles answer
  correctly, risk_ins autonomously calls risk_metrics end-to-end
- HEAD: 85beac3
- NEXT: Phase C-1 (legal_citation_check via CourtListener) if pursued;
        NVIDIA NIM (blocked); tool-to-role symmetry cleanup

## 2026-10-16 - Parts 132-133 (production readiness)
- Part 132: execution tracing (trace_id per run, span per tool call)
- Part 133: prompt externalization (static/prompts.json, reloadable)
- Both live-verified on HF
- HEAD: 73d0a87
- NEXT: Part 134 (per-tenant rate limiting); RBAC; injection guard

## 2026-10-16 - Parts 134-141 (production safety + observability)

One long session. 21 commits. Five production features shipped and
live-verified. Eight real bugs found + fixed. Six of those bugs were
found by the observability built during the same session.

### Part 134 - Per-tenant rate limiting (5 commits)
- 134    : sliding-window limiter (auth.py), middleware hook
- 134b   : _eff_key propagation into tenant contextvar
- 134c   : detached rate gate from auth gate (was nested inside
           `if auth_enabled():` so it never ran when auth off)
- 134d   : admin endpoints (/api/rate_limit/*) bypass the bucket
- hotfix : missing `Request` import in routes/meta.py (Space crash)
- Config : SUNNYWARE_RATE_LIMIT_PER_MINUTE=60 on HF
- Endpoints: /api/rate_limit/{status,tenants,reset,evict}
- Live-verified: 60/min per IP; admin endpoints stay at used=0

### Part 135 - RBAC layer
- 3-role hierarchy: admin(3) > analyst(2) > readonly(1)
- SUNNYWARE_API_ROLES="key1:admin,key2:analyst,..."
- SUNNYWARE_DEFAULT_ROLE=admin (unmapped keys)
- Permissive when auth is off (no behavior change until keys added)
- Endpoints: GET /api/auth/whoami
- Admin guards on: /api/rate_limit/{reset,evict,tenants}

### Part 136 - Prompt injection guard (3 commits)
- 136a : guardrails.py - 18 regex patterns across 6 categories
         (instruction_override, system_prompt_leak,
          role_play_jailbreak, delimiter_injection,
          exfiltration, encoded_override)
- 136b : wired into all 4 /api/agent/* routes as _guard_check()
- 136c : routed guardrail_hit events through the structured logger
- Modes: off / warn / block (SUNNYWARE_INJECTION_GUARD)
- HF setting: SUNNYWARE_INJECTION_GUARD=block
- Endpoints: /api/guardrails/{status,scan,self_test}
- Live-verified: high-severity attack -> HTTP 400; clean -> 200

### Part 137 - Continuous evals (5 commits)
- 137a  : evals.py framework (cases, assertions, storage, trends)
- 137b  : 4 endpoints (status/latest/trends/run)
- 137a-f: dry_run_call_fn simulates safe refusals
- 137c  : scheduler job (jobs/evals.py) - opt-in via env var
- 137d  : guard runs inside default_call_fn (fixed a SECURITY gap
           where the scheduler bypassed the HTTP injection guard)
- Built-in corpus: 5 cases (echo, math, one_word, leak, injection)
- HF setting: SUNNYWARE_EVAL_INTERVAL_HOURS=6
- Live-verified: first scheduler run found 3 real bugs (see below)

### Part 138 - Cost attribution (3 commits)
- 138   : admin surface (/api/usage/{all,tenant,trends,reset,export.csv})
          + Gemini pricing + tenant fallback to rate_limit_key
- 138b  : added gemini-2.5-flash / 2.5-pro / 2.5-flash-lite pricing
          (was falling back to a cheap default)
- 138c  : /api/providers/limits/reset now reloads the provider cache

### Part 139 - resolved_model propagation
- Bug: /api/agent/run returned {provider: gemini, model:
  openai/gpt-oss-20b} -- model came from legacy LLM_MODEL env var,
  not from the router's response.
- Fix: orchestrator tracks _last_model from r["resolved_model"] and
  includes it in every return block; route prefers it over
  state["config"].llm_model.
- Live-verified: provider=openrouter, model=liquid/lfm-2.5-2.6b:free

### Part 140 - Sunnyware identity in prompts
- Bug: Gemini answered "I'm LFM by Liquid AI" to "which model are you".
  Hallucinated pretrained persona.
- Fix: _IDENTITY_CLAUSE in prompts.py, prepended to both
  compact_prompt() and native_prompt(). Forbids claiming to be
  Gemini/GPT/Claude/Llama/LFM/Liquid AI.
- Live-verified: 3 identity questions -> "Sunnyware" each time.

### Bugs found + fixed this session
1.  Missing `Request` import -> HF Space down for ~4 min (hotfix)
2.  Rate limiter nested inside auth gate -> never ran when auth off
3.  Status endpoint showed wrong tenant (empty string bucket)
4.  SECURITY: injection guard bypassed on scheduler calls
5.  groq learned limit = 500 (stale 413) -> silently skipped every
    request that exceeded 500 tokens
6.  Provider cache not reloaded after limits reset
7.  result.model leaked legacy LLM_MODEL env value
8.  Gemini hallucinated identity as LFM

Bugs 2, 4, 5, 7, 8 were surfaced by the observability built this
same session (rate_limit/status, evals scheduler, /api/providers/*,
usage CSV).

### Config - all HF secrets now set
- SUNNYWARE_RATE_LIMIT_PER_MINUTE=60
- SUNNYWARE_INJECTION_GUARD=block
- SUNNYWARE_EVAL_INTERVAL_HOURS=6
- (plus all existing provider keys)

### Pre-push gate grew from 6 to 6 (unchanged) but now covers
12 smoke test files: 112, 114, 131, 132, 133, 134, 135, 136, 137,
137b, 137c, 138, 139, 140.

### NEXT
- NVIDIA NIM (still blocked on account activation)
- Optional: Part 141 recon-path hardening (.env probes seen in logs)
- Optional: WebUI provider chip should read result.resolved_model
  instead of the mirrored dropdown value (cosmetic)

### Part 142a - Auditor role (token-minimized)
- New role: "auditor" / "AI Evaluation Auditor" / U+1F50D icon
- Forensic audit of AI outputs (math, logic, code, proofs, agent
  trajectories, benchmarks, rubrics)
- Compressed prompt (~1986 chars / ~430 tokens) replaces the full
  30K-token V15.0 spec; still enforces:
    - 11-step pipeline (Spec -> Domain -> Artifact -> ... -> Verdict)
    - 7 hard rules (no agreement-as-proof, no requirement invention,
      no fabrication, independent arithmetic, static vs runtime,
      defect vs coverage confidence, severity independence)
    - Exact 5-label canonical taxonomy + no-defect phrase
    - Structured JSON output (10 keys)
- Tool allowlist: calculator, python_eval, read_file, rag_search
- NOT delegatable (no other role can call it; user-only invocation)
- Tool allowlist enforced by existing Part 114d guard
- Smoke: scripts/smoke_test_part142a.py (26/26)

### Part 143 - Rate-limit detection (Pollinations 402)
- Bug: Pollinations returns HTTP 402 FREE_LIMIT ("1 reply every 30s
  per IP") when free-tier quota exhausted. The router's
  _is_rate_limit_error only checked 429/rate limit/tpd/tpm and never
  matched 402/FREE_LIMIT/Retry-after, so the provider never cooled
  down and the request ended with "all providers failed".
- Fix:
  1. Extend _is_rate_limit_error to match 402, free_limit,
     "retry after", and "retry_after".
  2. New _parse_retry_after() extracts "Retry after Ns" /
     "retry_after: N" / "Retry-After N" hints (1..600 s).
  3. Cooldown duration now uses that hint (+5s safety) instead of
     always 60s when the provider tells us exactly how long to wait.
- Regex initially missed the hyphen in "Retry-After"; fixed to
  retry[\s_\-]*after.
- HF secret POLLINATIONS_API_KEY is already set (1 req/sec with key,
  vs 1 req/30s free tier).
- Smoke: scripts/smoke_test_part143.py (24/24)

### Parts 144-145 - Tool-aware eligibility + reset-aware cooldown
- 144: tool-schema tokens now counted in provider eligibility.
      Before: groq 413'd every multi-tool request because the
      ~8700-token tool schema alone exceeds its 7500-token cap and
      the router didn't know. Now: _estimate_tools_tokens() adds the
      tool payload to _required_tokens; providers whose max_prompt_tokens
      can't fit prompt+tools are skipped cleanly.
- 144: new POST /api/providers/test/{name} endpoint for direct
      provider testing (bypasses router). Returns _key_present,
      _key_prefix (masked), _provider_host, _cooling.
- 145: provider + error-aware cooldown. Replaces fixed 60s with:
      1. Provider-supplied retry hint (Part 143 _parse_retry_after) wins
      2. Per-day quota exhausted -> wait until next daily reset
         (Groq 00:00 UTC, Gemini midnight Pacific, OpenRouter 00:00 UTC)
      3. Per-minute quota -> 65s rolling window
      4. Fallback 60s
- 145: new provider_limits_config.py with verified free-tier limits
      (Groq 30 RPM / 1000 RPD, Gemini 15 RPM / 1500 RPD (Pacific reset),
      OpenRouter 20 RPM / 50 RPD, Pollinations unlimited with sk_ key)
- 143-fix: smoke test 143 updated to accept Part 145's replacement
      marker ("Part 143 + 145: provider + error-type aware cooldown").
- Smoke: 144 (14/14), 145 (37/37)

### Part 146 - Auditor JSON extraction + tool policy
- Live test of the auditor role (Part 142a) revealed two real issues:
    1. Large models (groq gpt-oss-120b) return clean JSON.
       Small models (Liquid LFM 2.6B via openrouter) wrap the JSON in
       a markdown code fence and prepend prose — so the API consumer
       couldn't reliably parse the verdict.
    2. The auditor was misusing rag_search for logic-fallacy names
       ("post hoc ergo propter hoc") which are general knowledge,
       not user-documents.
- Fixes:
    - roles.extract_auditor_json() handles 4 shapes: pure JSON,
      ```json-fenced, bare-fenced, prose + {bare object}. Falls back
      to None on failure. Never raises.
    - roles._AUDITOR_PROMPT gains a TOOL POLICY block:
        * calculator/python_eval for numeric verification
        * read_file/rag_search for user's submitted materials only
        * DO NOT use rag_search for logic names / audit methodology
        * prefer one clear call over multiple redundant ones
    - routes/agent.py adds _auditor_verdict_or_none(role, content)
      helper; response now carries an "auditor_verdict" field for
      the auditor role (parsed dict or null).
- Smoke: 146 (18/18)

### Part 147 - Auditor refinements (a/b/c)
- Follow-up to the 3 live auditor tests that partially failed:
- 147a: removed rag_search from auditor tool allowlist.
    Reason: LFM 2.6B used rag_search to look up logic-fallacy names
    ("post hoc ergo propter hoc") in the user's documents, burning
    3 calls + returning irrelevant CV content. Auditor verifies claims;
    it does not research terminology. If a user names a source
    document, read_file still works.
    Allowlist now: calculator, python_eval, read_file (3 tools).
- 147b: added EXAMPLES block to auditor prompt with 3 canonical
    input/output pairs (miscalculated %, no defect, logic gap).
    Positive examples work better than negative rules on small models.
    TOOL POLICY rewritten without naming rag_search (it's gone).
- 147c: extract_auditor_json() gains a regex field-extraction
    fallback. When JSON is malformed (missing braces, trailing comma)
    but "key": "value" pairs are present, the fields are recovered
    via _AUDITOR_FIELD_RE. Handles LFM's prose-heavy responses.
- Smoke: 147 (16/16); 142a and 146 updated for new allowlist/prompt.

### Part 146 (already shipped) recap
- extract_auditor_json() with 4 parse paths
- auditor_verdict field added to /api/agent/run response
- TOOL POLICY block (superseded by 147b)

### Part 148 - Extended auditor spec sidecar
- Adds an on-demand "sidecar" for the auditor role:
    - static/auditor_prompt_full.txt (~6.6 KB / ~1.6K tokens):
      extended spec covering specification extraction, requirement
      provenance, defect discipline, canonical taxonomy, math
      verification, logic verification, code verification, evidence
      hierarchy, static-vs-runtime, confidence separation, multi-layer
      root cause, claim-evidence-scope, severity, security, anti-overreach,
      anti-underreach, full 42-step pipeline, top-15 final self-check.
    - tools/auditor_full_spec.py (new, 82nd tool): returns the extended
      spec on demand.
    - roles.py: auditor allowlist grows to 4 tools
      (calculator, python_eval, read_file, auditor_full_spec).
    - Prompt hint added: "Call calculator ONCE per unique expression"
      (reduces duplicate compute) + "call auditor_full_spec ONCE" for
      nuanced tasks.
- Design: routine audits cost ~2.4K tokens (base prompt);
  complex audits load the sidecar only when needed, adding ~1.6K
  tokens for that specific call. Zero overhead for simple cases.
- The sidecar replaces the full V15.0 spec as a mechanical translation.
  Swapping in the verbatim 30K V15.0 later is a one-file change.
- Smoke: 148 (27/27); 142a and 147 updated for new allowlist.

### Part 149 - Mandatory tool-use rules in auditor prompt
- Follow-up to the Part 148 live test on a complex multi-layer audit:
  the auditor answered correctly (17.0% weighted average) but made
  two subtle misses:
    1. Called ZERO tools - the model computed 0.5*10 + 0.3*20 + 0.2*30
       mentally, violating the "recompute every number independently"
       rule. The output was right, but no auditable evidence.
    2. Ignored the "identify all layers of error" instruction - it
       only blamed the Candidate, missing that the Evaluator and the
       Benchmark key both agreed with the wrong answer. The sidecar
       (multi-layer root cause) was not loaded.
- Fixes in _AUDITOR_PROMPT:
    1. Calculator rule is now MANDATORY: "ALWAYS call calculator for
       ANY numeric claim - even trivial arithmetic. Mental math is
       NOT auditable evidence." Includes a concrete example.
    2. Added SIDECAR TRIGGERS block. If the task mentions any of:
       'layers', 'end-to-end', 'all sources of error', 'multi-layer',
       'benchmark', 'evaluator', 'rubric', 'evidence hierarchy' -
       the auditor MUST call auditor_full_spec FIRST.
       "Skipping this when trigger words are present is a defect."
- Prompt grew from ~3.6KB to ~3.9KB (+~80 tokens). Still well under
  the 4.5KB cap and safely within Groq's 7500-token limit.
- Smoke: 149 (19/19). Regressions: 148 (27/27), 147 (16/16),
  146 (18/18), 145 (37/37), 144 (14/14), 142a (26/26),
  143 (24/24), 137 (57/57), 112 (28/28).
- Smoke 146, 147, 148 caps bumped 3500 -> 4500 to match new prompt size.

### Part 150 - Forced JSON retry on extraction failure
- Follow-up to the Part 149 live test. On LFM 2.6B (via openrouter):
    tools_used: ['auditor_full_spec', 'calculator', 'calculator']  <- both rules fired
    but auditor_verdict: None  <- JSON extraction failed
- LFM wrote prose that none of the 5 extraction paths (pure JSON,
  fenced, bare-fenced, prose+obj, regex field) could recover.
- Fix: _auditor_verdict_with_retry() in routes/agent.py.
    1. Try the normal extract_auditor_json() first (fast path).
    2. If it fails, send the model its own response back with a
       strict "return ONLY the JSON verdict object, no prose, no
       fences, start with { end with }" instruction.
    3. Use the retry's response if extraction succeeds.
- Both return blocks in /api/agent/run now call the async retry
  helper (`await _auditor_verdict_with_retry(...)`).
- The sync _auditor_verdict_or_none() helper is retained for
  reference/back-compat, but is no longer called.
- Retry is a single round-trip, only when the initial parse fails.
  Well-behaved models (Groq gpt-oss-120b, pollinations) never hit it.
- Smoke: 150 (9/9). Regressions: 149 (19/19), 148 (27/27),
  147 (16/16), 146 (18/18), 145 (37/37), 144 (14/14),
  142a (26/26), 143 (24/24), 137 (57/57), 112 (28/28).

### Part 151 - Universal truthfulness + orchestration hardening
- New module: src/sunnyware/role_truthfulness.py
    - TRUTHFULNESS_CLAUSE: 5-rule universal prefix. Applied to every
      role's prompt automatically.
        - Never state live facts without a tool call
        - 'I could not retrieve X' when a tool fails
        - Every numeric claim cites tool + timestamp
        - Prefer 'no data' over 'approximately'/'probably'
        - Name the specific tool/source needed when unverifiable
    - MANDATORY_TOOLS dict: per-role tool-first guidance
        - fpa -> edgar_*, fmp_*, fred_*, eulerpool_bonds_*
        - quant -> tiingo_*, twelvedata_*, eulerpool_options_*,
          eulerpool_alt_*, finnhub_*, fred_*
        - actuary -> insurance_*, edgar_*, fred_*
        - tax -> web_search (yearly rules), edgar_*
        - legal -> legal_citation_check, web_search, clause_extractor
        - risk_ins -> risk_metrics, insurance_*, fred_*
        - cfo -> orchestration rules + CDO cross-check requirement
        - cdo -> CROSS-CHECK RULE (2+ independent specialists for
          financial/legal/tax/insurance/regulatory claims)
    - clause_for(role): returns combined clause. Unknown roles get
      only the base TRUTHFULNESS_CLAUSE.
- roles.py: prompt_addon() now wraps _prompt_addon_base() and
  prepends clause_for(role). Existing role prompts unchanged except
  for the appended clauses.
- Effective per-role prompt sizes after Part 151:
    general   704c   (was 0)
    fpa      1461c   (was  416)
    quant    1505c   (was  424)
    actuary  1809c   (was  709)
    tax      1423c   (was  416)
    cfo      2923c   (was 1808)
    cdo      2871c   (was 1371)
    legal    2005c   (was  938)
    risk_ins 1956c   (was  958)
    auditor  4358c   (was 3654 - only gained base truthfulness)
- CFO workflow: must cite "verified by CDO cross-check" or
  "CDO unable to verify X" in the final answer.
- CDO workflow: must cross-check financial/legal/tax/insurance/
  regulatory claims against at least TWO independent specialists.
- Smoke: 151 (31/31). Regressions: 150 (9/9), 149 (19/19),
  148 (27/27), 147 (16/16), 146 (18/18), 145 (37/37), 144 (14/14),
  142a (26/26), 143 (24/24), 137 (57/57), 112 (28/28).

### Part 152 - Provider tool-support flag
- Root cause found during Part 151 live verify: the CFO->CDO->worker
  pipeline returned "all providers failed" with pollinations 402
  FREE_LIMIT. The debug endpoint /api/providers/test/pollinations
  returned ok=True with the sk_ key. Same key, same URL, same
  _chat_single -- only difference: tools were attached.
- Discovery: Pollinations free tier REJECTS requests containing
  OpenAI-style tool schemas with HTTP 402 FREE_LIMIT (the same
  message it uses for anonymous rate limiting). It is not a rate
  limit -- it is a capability limit disguised as a rate limit.
- Fix:
    - providers.py: Provider dataclass gains `supports_tools: bool = True`.
    - providers.load_providers(): sets supports_tools=False for
      pollinations. All other providers stay True.
    - providers.Provider.status(): exposes `supports_tools` for
      the /api/providers/status endpoint.
    - llm.py: _chat_single() is now called with
      `tools=(tools if getattr(p, "supports_tools", True) else None)`
      from both the single-provider fast path and the multi-provider
      router loop. Non-tool providers automatically get tools=None.
- Impact: pollinations now serves tool-less requests successfully
  (chat, RAG lookups, simple queries). Tool-bearing requests route
  to groq/gemini/openrouter as before. Zero regression.
- Smoke: 152 (9/9). Regressions: 151 (31/31), 150 (9/9),
  144 (14/14), 137 (57/57), 112 (28/28).
