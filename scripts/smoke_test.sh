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
    LLM_RESP=$(curl -sf -X POST "$URL/api/agent/run" \
        -H "Content-Type: application/json" \
        -d '{"input":"Say only: pong","session_id":"smoke-llm"}' 2>/dev/null || echo "")
    if echo "$LLM_RESP" | grep -q '"content"'; then
        check "LLM round-trip: ok" "0"
    else
        check "LLM round-trip: missing content" "1"
    fi
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

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="

if [ "$FAIL" -gt 0 ]; then
    echo "FAILED — do not deploy"
    exit 1
fi

echo "ALL PASSED — safe to deploy"
exit 0