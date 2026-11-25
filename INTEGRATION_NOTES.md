# Integration Notes

- Python version: 3.11.9
- Dispatch file/function: src/sunnyware/orchestrator.py : _execute_tool (async: yes)
- Dispatch call sites: lines 1908, 2006
- Loop file/function: src/sunnyware/orchestrator.py : run_agent (line 1397)
- Circuit breaker API: is_open(tool_name) -> bool (line 72)
- Browser tools: browser_click, browser_extract, browser_fill_submit, browser_goto, browser_screenshot
- Baseline pytest: 357 passed, 1 failed (test_legal_citation_check_verify_one_routing), 2 skipped
- Task 5 status: APPLICABLE

## Task 2 (Retry Budget) — DEFERRED / ROLLED BACK
- Reason: orchestrator uses pure ReAct loop (LLM-driven), no explicit retry branch to hook into.
- Module deleted (retry_budget.py). Task 1 (tool_errors.py) remains wired.
- Revisit only after trace logs (Task 3) reveal actual retry patterns.

## Task 3 (Trace JSONL) — DONE
- Module: src/sunnyware/trace.py (feature-flagged: SUNNYWARE_TRACE=1)
- Wired: 4 traces (2× tool_started, 2× tool_completed) at orchestrator dispatch sites
- request_id source: session_uuid or "unknown"
- Phase B/C/D/E: all passed against baseline
- Live trace test: /tmp/smoke.jsonl not created (tests don't exercise ReAct loop — expected)

## Task 4 (Tool Cache) — DONE
- Module: src/sunnyware/tool_cache.py (feature-flagged: SUNNYWARE_TOOL_CACHE=1)
- Default allowlist: web_search, fred_economic, weather, url_metadata (all read-only, no mutations)
- Safety guard: static check confirms no write_file/browser_*/delete_file/mkdir in allowlist
- Wired: 2× cache-get/cache-set blocks around both dispatch sites
- Cache stores raw (pre-normalization) result — Task 1 normalization runs identically on hit/miss
- Phase B/C/D/E: all passed against baseline
- TTL: SUNNYWARE_TOOL_CACHE_TTL (default 300s)

## Task 5 (Step Timeout) — DONE
- Module: src/sunnyware/step_timeout.py (feature-flagged: SUNNYWARE_STEP_TIMEOUT=N seconds)
- Wired: 2 dispatch sites now wrap _execute_tool in _with_timeout(coro, tool_name=...)
- Browser tools (browser_click/goto/etc.) bypass the timeout (they're user-driven)
- Default behavior when flag unset: _with_timeout returns await coro immediately (zero overhead)
- Phase B/C/D/E: all passed against baseline

## Task 6 (Sanitizer) — DONE
- Module: src/sunnyware/sanitize.py (feature-flagged: SUNNYWARE_SANITIZE_ARGS=1)
- Strips <script>...</script> blocks, truncates strings > SUNNYWARE_MAX_ARG_LEN (default 10000)
- Wired: 2 sites (before cache lookup, both native and prompt-json paths)
- Idempotent: returns args unchanged when flag off
- Phase B/C/D/E: all passed against baseline

## Section 4 — Final Integration Test — ALL PASSED
- 4.1 Default (all flags off): 1 failed, 357 passed, 2 skipped (matches baseline)
- 4.2 All flags ON: 1 failed, 357 passed, 2 skipped (matches baseline)
- 4.3 Zero-token paths: NO CHANGES to _DIRECT_ANSWER_TOOLS / _LLM_DEPENDENT_TOOLS
- 4.4 Files: 6 new (tool_errors, trace, tool_cache, step_timeout, sanitize + INTEGRATION_NOTES) + orchestrator.py modified. retry_budget.py absent (correctly rolled back).

## Final Tracker
| Task | Precheck | Created | Shadow | Wired | Flag-On | Status |
|------|----------|---------|--------|-------|---------|--------|
| 1 ToolError | Y | Y | Y | Y (2 sites) | Y | DONE |
| 2 Retry Budget | Y | Y | Y | ABORTED (ReAct loop) | - | ROLLED BACK |
| 3 Trace | Y | Y | Y | Y (4 traces) | Y | DONE |
| 4 Cache | Y | Y | Y | Y (2 sites) | Y | DONE |
| 5 Step Timeout | Y | Y | Y | Y (2 sites) | Y | DONE |
| 6 Sanitizer | Y | Y | Y | Y (2 sites) | Y | DONE |
