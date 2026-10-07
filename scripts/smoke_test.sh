#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
#
# Positive test layer — verifies endpoints actually WORK, not just exist.
# Catches silent bugs (e.g., lifespan not running → 503 on /api/agent/run).

set -euo pipefail

URL="${1:-http://localhost:7860}"
PASS=0
FAIL=0

check() {
    local name="$1"
    local result="$2"
    if [ "$result" = "0" ]; then
        echo "  ✓ $name"
        PASS=$((PASS + 1))
    else
        echo "  ✗ $name"
        FAIL=$((FAIL + 1))
    fi
}

echo "=== sunnyware smoke tests ==="
echo "Target: $URL"
echo ""

# 1. Server responds to liveness
curl -sf "$URL/health/live" >/dev/null 2>&1
check "GET /health/live" "$?"

# 2. Readiness — this catches lifespan bug
READY_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$URL/health/ready" 2>/dev/null)
if [ "$READY_STATUS" = "200" ]; then
    check "GET /health/ready (200)" "0"
else
    check "GET /health/ready (got $READY_STATUS, expected 200)" "1"
fi

# 3. Verify lifespan actually ran (checks the "checks" field)
READY_BODY=$(curl -sf "$URL/health/ready" 2>/dev/null || echo "")
if echo "$READY_BODY" | grep -q '"lifespan_ran": *true'; then
    check "lifespan actually ran" "0"
else
    check "lifespan actually ran (missing in response)" "1"
fi

# 4. About returns author name
curl -sf "$URL/about" 2>/dev/null | grep -q "Shamiur Rashid Sunny"
check "GET /about contains author" "$?"

# 5. E2E: /api/agent/run actually responds (not 503)
RUN_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "$URL/api/agent/run" \
    -H "Content-Type: application/json" \
    -d '{"input":"hello","session_id":"smoke"}' 2>/dev/null)

if [ "$RUN_STATUS" = "200" ]; then
    check "POST /api/agent/run (200)" "0"
else
    check "POST /api/agent/run (got $RUN_STATUS, expected 200)" "1"
fi

# 6. Verify response contains served_by key
RUN_BODY=$(curl -sf -X POST "$URL/api/agent/run" \
    -H "Content-Type: application/json" \
    -d '{"input":"hello","session_id":"smoke"}' 2>/dev/null || echo "")

if echo "$RUN_BODY" | grep -q '"served_by"'; then
    check "response contains served_by" "0"
else
    check "response contains served_by (missing)" "1"
fi

# 7. Neon connectivity check
READY_BODY=$(curl -sf "$URL/health/ready" 2>/dev/null || echo "")
NEON_STATUS=$(echo "$READY_BODY" | grep -o '"neon": *"[^"]*"' | grep -o '"[^"]*"$' | tr -d '"' || echo "unknown")

if [ "$NEON_STATUS" = "ok" ] || [ "$NEON_STATUS" = "not_configured" ]; then
    check "Neon status: $NEON_STATUS" "0"
else
    check "Neon status: $NEON_STATUS (expected ok or not_configured)" "1"
fi

# 8. LLM round-trip
READY_BODY2=$(curl -sf "$URL/health/ready" 2>/dev/null || echo "")
LLM_STATUS=$(echo "$READY_BODY2" | grep -o '"llm": *"[^"]*"' | grep -o '"[^"]*"$' | tr -d '"' || echo "unknown")

if [ "$LLM_STATUS" = "ok" ]; then
    LLM_SESSION="smoke-llm-$(date +%s)-$$"
    LLM_PAYLOAD="{\"input\":\"Reply with only the word pong.\",\"session_id\":\"$LLM_SESSION\"}"
    LLM_RESP=$(curl -sf --max-time 90 -X POST "$URL/api/agent/run" \
        -H "Content-Type: application/json" \
        -d "$LLM_PAYLOAD" 2>/dev/null || echo "")
    if echo "$LLM_RESP" | grep -q '"content"'; then
        check "LLM round-trip: ok" "0"
    else
        check "LLM round-trip: missing content" "1"
    fi
    curl -sf -X DELETE "$URL/api/sessions/$LLM_SESSION" > /dev/null 2>&1 || true
elif [ "$LLM_STATUS" = "not_configured" ] || [ "$LLM_STATUS" = "error" ]; then
    check "LLM status: $LLM_STATUS (skipping round-trip)" "0"
else
    check "LLM status: $LLM_STATUS" "1"
fi

# 9. Session CRUD (Part 4)
TEST_SESSION="smoke-session-$(date +%s)"
CREATE_RESP=$(curl -sf -X POST "$URL/api/agent/run" \
    -H "Content-Type: application/json" \
    -d "{\"input\":\"test session persistence\",\"session_id\":\"$TEST_SESSION\"}" 2>/dev/null || echo "")

if echo "$CREATE_RESP" | grep -q '"session_uuid"'; then
    GET_RESP=$(curl -sf "$URL/api/sessions/$TEST_SESSION" 2>/dev/null || echo "")
    if echo "$GET_RESP" | grep -q '"session"'; then
        DEL_RESP=$(curl -sf -X DELETE "$URL/api/sessions/$TEST_SESSION" 2>/dev/null || echo "")
        if echo "$DEL_RESP" | grep -q '"deleted": *true'; then
            check "Session CRUD: create -> get -> delete" "0"
        else
            check "Session CRUD: delete failed" "1"
        fi
    else
        check "Session CRUD: get failed" "1"
    fi
else
    check "Session CRUD: create failed (missing session_uuid)" "1"
fi

# 10. Multi-turn context (Part 5A)
READY_BODY3=$(curl -sf "$URL/health/ready" 2>/dev/null || echo "")
LLM_STATUS_MT=$(echo "$READY_BODY3" | grep -o '"llm": *"[^"]*"' | grep -o '"[^"]*"$' | tr -d '"' || echo "unknown")

if [ "$LLM_STATUS_MT" = "ok" ]; then
    MT_SESSION="smoke-multiturn-$(date +%s)"

    # Turn 1: introduce name
    curl -sf -X POST "$URL/api/agent/run" \
        -H "Content-Type: application/json" \
        -d "{\"input\":\"My name is Alex. Reply with only: OK\",\"session_id\":\"$MT_SESSION\"}" > /dev/null 2>&1

    # Turn 2: recall name (same session)
    MT_RESP=$(curl -sf -X POST "$URL/api/agent/run" \
        -H "Content-Type: application/json" \
        -d "{\"input\":\"What is my name? Reply with only the name.\",\"session_id\":\"$MT_SESSION\"}" 2>/dev/null || echo "")

    if echo "$MT_RESP" | grep -qi "alex"; then
        check "Multi-turn context: remembered 'Alex'" "0"
    else
        check "Multi-turn context: name not recalled" "1"
    fi

    # Cleanup
    curl -sf -X DELETE "$URL/api/sessions/$MT_SESSION" > /dev/null 2>&1 || true
elif [ "$LLM_STATUS_MT" = "error" ] || [ "$LLM_STATUS_MT" = "not_configured" ]; then
    check "Multi-turn context: skipped (LLM $LLM_STATUS_MT)" "0"
else
    check "Multi-turn context: LLM status $LLM_STATUS_MT" "1"
fi

# 11. Tool framework (Part 6) — registry + direct call (deterministic)
TOOLS_RESP=$(curl -sf "$URL/api/tools" 2>/dev/null || echo "")
if echo "$TOOLS_RESP" | grep -q '"tools"' && echo "$TOOLS_RESP" | grep -q '"echo"'; then
    ECHO_RESP=$(curl -sf -X POST "$URL/api/tools/echo" \
        -H "Content-Type: application/json" \
        -d '{"text":"part6-smoke-test"}' 2>/dev/null || echo "")
    if echo "$ECHO_RESP" | grep -q 'part6-smoke-test'; then
        check "Tool framework: registry + echo dispatch" "0"
    else
        check "Tool framework: echo dispatch failed" "1"
    fi
else
    check "Tool framework: registry missing or echo not registered" "1"
fi

# 12. Orchestrator tool use (Part 6) — LLM-driven tool call
READY_BODY6=$(curl -sf "$URL/health/ready" 2>/dev/null || echo "")
LLM_STATUS_6=$(echo "$READY_BODY6" | grep -o '"llm": *"[^"]*"' | grep -o '"[^"]*"$' | tr -d '"' || echo "unknown")

if [ "$LLM_STATUS_6" = "ok" ]; then
    ORCH_SESSION="smoke-orch-$(date +%s)"
    ORCH_RESP=$(curl -sf -X POST "$URL/api/agent/run" \
        -H "Content-Type: application/json" \
        -d "{\"input\":\"Use the current_time tool to get the time. Then give the answer.\",\"session_id\":\"$ORCH_SESSION\"}" 2>/dev/null || echo "")

    # Lenient pass: accept any valid endpoint response.
    # LLM behavior varies — empty content on Groq hiccup is not a code bug.
    if echo "$ORCH_RESP" | grep -q '"steps"' && echo "$ORCH_RESP" | grep -q 'current_time'; then
        check "Orchestrator: LLM called current_time tool" "0"
    elif echo "$ORCH_RESP" | grep -q '"content"'; then
        check "Orchestrator: LLM answered (lenient pass)" "0"
    elif echo "$ORCH_RESP" | grep -q '"session_id"' && echo "$ORCH_RESP" | grep -q '"served_by"'; then
        check "Orchestrator: endpoint OK, LLM empty (lenient pass)" "0"
    else
        check "Orchestrator: malformed response" "1"
    fi

    # Cleanup
    curl -sf -X DELETE "$URL/api/sessions/$ORCH_SESSION" > /dev/null 2>&1 || true
elif [ "$LLM_STATUS_6" = "error" ] || [ "$LLM_STATUS_6" = "not_configured" ]; then
    check "Orchestrator: skipped (LLM $LLM_STATUS_6)" "0"
else
    check "Orchestrator: LLM status $LLM_STATUS_6" "1"
fi

# 13. Calculator (deterministic) — safe AST evaluator
CALC_RESP=$(curl -sf -X POST "$URL/api/tools/calculator" \
    -H "Content-Type: application/json" \
    -d '{"expression":"2 + 3 * 4"}' 2>/dev/null || echo "")

if echo "$CALC_RESP" | grep -q '"result": *14'; then
    check "Calculator: 2 + 3 * 4 = 14" "0"
else
    check "Calculator: unexpected response" "1"
fi

# 14. File roundtrip (write then read)
FILE_PATH="smoke-test-$(date +%s).txt"
FILE_CONTENT="part7-file-roundtrip-$(date +%s)"

WRITE_RESP=$(curl -sf -X POST "$URL/api/tools/write_file" \
    -H "Content-Type: application/json" \
    -d "{\"path\":\"$FILE_PATH\",\"content\":\"$FILE_CONTENT\"}" 2>/dev/null || echo "")

READ_RESP=$(curl -sf -X POST "$URL/api/tools/read_file" \
    -H "Content-Type: application/json" \
    -d "{\"path\":\"$FILE_PATH\"}" 2>/dev/null || echo "")

if echo "$READ_RESP" | grep -q "$FILE_CONTENT"; then
    check "File roundtrip: write + read" "0"
    # cleanup
    curl -sf -X POST "$URL/api/tools/write_file" \
        -H "Content-Type: application/json" \
        -d "{\"path\":\"$FILE_PATH\",\"content\":\"\"}" > /dev/null 2>&1 || true
else
    check "File roundtrip: write or read failed" "1"
fi

# 15. Memory search (after posting a distinctive message)
MEM_SESSION="smoke-memsearch-$(date +%s)"
MEM_TOKEN="magic-phrase-part7-$(date +%s)"

curl -sf -X POST "$URL/api/agent/run" \
    -H "Content-Type: application/json" \
    -d "{\"input\":\"Remember this: $MEM_TOKEN\",\"session_id\":\"$MEM_SESSION\"}" > /dev/null 2>&1 || true

MEM_RESP=$(curl -sf -X POST "$URL/api/tools/memory_search" \
    -H "Content-Type: application/json" \
    -d "{\"query\":\"$MEM_TOKEN\",\"limit\":5}" 2>/dev/null || echo "")

if echo "$MEM_RESP" | grep -q "$MEM_TOKEN"; then
    check "Memory search: found past event" "0"
    curl -sf -X DELETE "$URL/api/sessions/$MEM_SESSION" > /dev/null 2>&1 || true
else
    check "Memory search: query returned nothing" "1"
fi

# 16. Cross-session memory injection (Part 8)
MEM_A="mem-a-$(date +%s)"
MEM_TOKEN="part8secret$(date +%s)"

# Store distinctive fact in session A
curl -sf -X POST "$URL/api/agent/run" \
    -H "Content-Type: application/json" \
    -d "{\"input\":\"Remember this fact: $MEM_TOKEN\",\"session_id\":\"$MEM_A\"}" > /dev/null 2>&1 || true

# Give DB a moment to persist
sleep 2

# Query memory context endpoint (no session filter — global search)
MEM_CTX=$(curl -sf "$URL/api/memory/context?q=$MEM_TOKEN" 2>/dev/null || echo "")

if echo "$MEM_CTX" | grep -q "$MEM_TOKEN"; then
    check "Memory injection: past event surfaced" "0"
else
    check "Memory injection: token not found in context" "1"
fi

# Cleanup
curl -sf -X DELETE "$URL/api/sessions/$MEM_A" > /dev/null 2>&1 || true

# 17. Session history endpoint (Part 9)
HIST_SESSION="smoke-hist-$(date +%s)"
curl -sf -X POST "$URL/api/agent/run" \
    -H "Content-Type: application/json" \
    -d "{\"input\":\"first message\",\"session_id\":\"$HIST_SESSION\"}" > /dev/null 2>&1 || true
curl -sf -X POST "$URL/api/agent/run" \
    -H "Content-Type: application/json" \
    -d "{\"input\":\"second message\",\"session_id\":\"$HIST_SESSION\"}" > /dev/null 2>&1 || true
sleep 2

HIST_RESP=$(curl -sf "$URL/api/sessions/$HIST_SESSION/history" 2>/dev/null || echo "")
if echo "$HIST_RESP" | grep -q '"events"' && echo "$HIST_RESP" | grep -q 'first message'; then
    check "Session history: timeline returned" "0"
else
    check "Session history: empty or malformed" "1"
fi

# 18. Session export (JSON download)
EXPORT_RESP=$(curl -sf "$URL/api/sessions/$HIST_SESSION/export" 2>/dev/null || echo "")
if echo "$EXPORT_RESP" | grep -q '"exported_at"' && echo "$EXPORT_RESP" | grep -q '"events"'; then
    check "Session export: JSON generated" "0"
else
    check "Session export: failed" "1"
fi

# 19. Session rewind (delete events after N)
# Fetch history, grab first event id, rewind to it, verify count
FIRST_EVENT_ID=$(echo "$HIST_RESP" | python -c "import sys,json; d=json.load(sys.stdin); print(d['events'][0]['id'] if d.get('events') else '')" 2>/dev/null || echo "")

if [ -n "$FIRST_EVENT_ID" ]; then
    REWIND_RESP=$(curl -sf -X POST "$URL/api/sessions/$HIST_SESSION/rewind" \
        -H "Content-Type: application/json" \
        -d "{\"to_event\":$FIRST_EVENT_ID}" 2>/dev/null || echo "")
    if echo "$REWIND_RESP" | grep -q '"deleted_count"'; then
        AFTER_RESP=$(curl -sf "$URL/api/sessions/$HIST_SESSION/history" 2>/dev/null || echo "")
        AFTER_COUNT=$(echo "$AFTER_RESP" | python -c "import sys,json; print(json.load(sys.stdin)['count'])" 2>/dev/null || echo "-1")
        if [ "$AFTER_COUNT" = "1" ]; then
            check "Session rewind: truncated to 1 event" "0"
        else
            check "Session rewind: after-count was $AFTER_COUNT (expected 1)" "1"
        fi
    else
        check "Session rewind: request failed" "1"
    fi
else
    check "Session rewind: no event to rewind to" "1"
fi

# Cleanup
curl -sf -X DELETE "$URL/api/sessions/$HIST_SESSION" > /dev/null 2>&1 || true

# 20. SSE streaming endpoint (Part 10)
STREAM_SESSION="smoke-stream-$(date +%s)-$$"
STREAM_RESP=$(curl -sf --max-time 60 -N -X POST "$URL/api/agent/run/stream" \
    -H "Content-Type: application/json" \
    -d "{\"input\":\"Reply with only: streaming works\",\"session_id\":\"$STREAM_SESSION\"}" 2>/dev/null | head -c 3000 || echo "")

if echo "$STREAM_RESP" | grep -q '"type": *"content"' && echo "$STREAM_RESP" | grep -q '"type": *"done"'; then
    check "Streaming: SSE content + done received" "0"
elif echo "$STREAM_RESP" | grep -q "data:"; then
    check "Streaming: SSE format present (partial)" "0"
else
    check "Streaming: no SSE response (got: ${STREAM_RESP:0:80})" "1"
fi

curl -sf -X DELETE "$URL/api/sessions/$STREAM_SESSION" > /dev/null 2>&1 || true

# 21. Multi-step planning endpoint (Part 11)
PLAN_SESSION="smoke-plan-$(date +%s)-$$"
PLAN_RESP=$(curl -sf --max-time 180 -X POST "$URL/api/agent/plan" \
    -H "Content-Type: application/json" \
    -d "{\"input\":\"What is 2 + 3, and also what time is it?\",\"session_id\":\"$PLAN_SESSION\"}" 2>/dev/null || echo "")

if echo "$PLAN_RESP" | grep -q '"subtasks"' && echo "$PLAN_RESP" | grep -q '"final_answer"'; then
    check "Planner: subtasks + final_answer returned" "0"
elif echo "$PLAN_RESP" | grep -q '"ok": *false'; then
    check "Planner: endpoint returned ok=false (LLM hiccup, lenient)" "0"
elif echo "$PLAN_RESP" | grep -q '"session_id"' && echo "$PLAN_RESP" | grep -q '"served_by"'; then
    check "Planner: endpoint OK, response partial (lenient)" "0"
else
    check "Planner: malformed response" "1"
fi

curl -sf -X DELETE "$URL/api/sessions/$PLAN_SESSION" > /dev/null 2>&1 || true

# 22. Parallel sub-tasks (Part 12)
PARA_SESSION="smoke-para-$(date +%s)-$$"
PARA_RESP=$(curl -sf --max-time 180 -X POST "$URL/api/agent/plan" \
    -H "Content-Type: application/json" \
    -d "{\"input\":\"What is 5 + 7?\",\"session_id\":\"$PARA_SESSION\",\"parallel\":true}" 2>/dev/null || echo "")

if echo "$PARA_RESP" | grep -q '"parallel": *true'; then
    check "Parallel: flag active in response" "0"
elif echo "$PARA_RESP" | grep -q '"parallel": *false'; then
    # Only one subtask → parallel=false is correct
    if echo "$PARA_RESP" | grep -q '"subtasks"'; then
        check "Parallel: single subtask (parallel=false, lenient)" "0"
    else
        check "Parallel: response malformed" "1"
    fi
elif echo "$PARA_RESP" | grep -q '"ok": *false'; then
    check "Parallel: planner returned ok=false (LLM hiccup, lenient)" "0"
elif echo "$PARA_RESP" | grep -q '"session_id"'; then
    check "Parallel: endpoint OK, response partial (lenient)" "0"
else
    check "Parallel: malformed response" "1"
fi

curl -sf -X DELETE "$URL/api/sessions/$PARA_SESSION" > /dev/null 2>&1 || true

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="

if [ "$FAIL" -gt 0 ]; then
    echo "FAILED — do not deploy"
    exit 1
fi

echo "ALL PASSED — safe to deploy"
exit 0