#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
# Periodic system monitor runner.
# Usage:
#   bash scripts/monitor_watch.sh            # every 300s (5 min)
#   bash scripts/monitor_watch.sh 60         # every 60s
#   bash scripts/monitor_watch.sh 900 --offline
set -euo pipefail
INTERVAL="${1:-300}"
shift || true
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
cd "$ROOT"
if [ ! -f .venv/Scripts/activate ]; then
    echo "ERROR: .venv not found"
    exit 1
fi
source .venv/Scripts/activate
echo "Watching: interval=${INTERVAL}s, args=$*"
echo "Reports: reports/system_health.md, reports/system_health.json"
echo "Press Ctrl+C to stop."
echo ""
python scripts/system_monitor.py --watch "$INTERVAL" "$@"
