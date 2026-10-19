#!/bin/bash
# Usage: ./safe_deploy.sh "commit message"
set -euo pipefail
MSG="${1:-}"
if [ -z "$MSG" ]; then
  echo "Usage: ./safe_deploy.sh \"commit message\""
  exit 1
fi
cd "$(dirname "$0")"

echo ""
echo "============================================================"
echo " STEP 1/4: Local smoke test"
echo "============================================================"
python scripts/smoke_local.py || { echo ""; echo "ABORTING — fix local errors first"; exit 1; }

echo ""
echo "============================================================"
echo " STEP 2/4: Git commit + push"
echo "============================================================"
git add -A
git commit -m "$MSG" || echo "(no changes to commit)"
git push origin main
./push_hf.sh

echo ""
echo "============================================================"
echo " STEP 3/4: Waiting for HF rebuild (max 6 min)"
echo "============================================================"
LOCAL_SHA=$(git rev-parse HEAD)
for i in $(seq 1 24); do
  sleep 15
  INFO=$(curl -s "https://huggingface.co/api/spaces/shamiur/sunnyware" || echo '{}')
  REMOTE_SHA=$(echo "$INFO" | python -c "import sys,json; print(json.load(sys.stdin).get('sha',''))" 2>/dev/null || echo "")
  STAGE=$(echo "$INFO" | python -c "import sys,json; print(json.load(sys.stdin).get('runtime',{}).get('stage','?'))" 2>/dev/null || echo "?")
  if [ "$REMOTE_SHA" = "$LOCAL_SHA" ] && [ "$STAGE" = "RUNNING" ]; then
    echo "  HF running at $LOCAL_SHA ($((i*15))s elapsed)"
    break
  fi
  echo "  [${i}/24] stage=$STAGE sha=${REMOTE_SHA:0:12} (want ${LOCAL_SHA:0:12})"
  if [ $i -eq 24 ]; then
    echo "  TIMEOUT waiting for HF rebuild"
    exit 1
  fi
done

echo ""
echo "============================================================"
echo " STEP 4/4: Remote smoke test"
echo "============================================================"
python scripts/smoke_remote.py

echo ""
echo "============================================================"
echo " DEPLOYMENT SUCCESSFUL"
echo "============================================================"
