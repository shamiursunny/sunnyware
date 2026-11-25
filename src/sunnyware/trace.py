# SPDX-License-Identifier: AGPL-3.0-only
# Module: trace — feature-flagged, zero-token, opt-in
import json, os, time

_ENABLED = os.getenv("SUNNYWARE_TRACE", "0") == "1"
_FILE = os.getenv("SUNNYWARE_TRACE_FILE", "sunnyware_trace.jsonl")

def emit(request_id: str, event: str, payload: dict = None) -> None:
    if not _ENABLED:
        return
    record = {"ts": time.time(), "request_id": request_id,
              "event": event, "payload": payload or {}}
    try:
        with open(_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
    except Exception:
        pass
