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

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="

if [ "$FAIL" -gt 0 ]; then
    echo "FAILED — do not deploy"
    exit 1
fi

echo "ALL PASSED — safe to deploy"
exit 0