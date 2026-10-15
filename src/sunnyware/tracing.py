# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 132: execution tracing.

In-memory ring-buffer of traces. Each trace is a full agent run with
nested spans for tool calls, delegations, and (when instrumented)
LLM calls. Uses OTel gen_ai semantic conventions where applicable.

No external dependencies. No persistence (traces survive until the
buffer wraps or the process restarts).
"""
import threading
import time
import uuid
from collections import deque
from contextvars import ContextVar

_MAX_TRACES = 200
_CURRENT_TRACE = ContextVar("sunnyware_trace_id", default=None)

_lock = threading.Lock()
_traces = deque(maxlen=_MAX_TRACES)
_by_id = {}


def start_trace(role=None, session_uuid=None, prompt=None,
                parent_trace_id=None):
    tid = uuid.uuid4().hex[:16]
    now = time.time()
    trace = {
        "trace_id": tid,
        "parent_trace_id": parent_trace_id,
        "role": role or "general",
        "session_uuid": session_uuid,
        "started_at": now,
        "finished_at": None,
        "duration_ms": None,
        "status": "running",
        "prompt_preview": (prompt or "")[:200],
        "spans": [],
    }
    with _lock:
        if len(_traces) >= _MAX_TRACES and _traces:
            old = _traces[0]
            _by_id.pop(old.get("trace_id"), None)
        _traces.append(trace)
        _by_id[tid] = trace
    _CURRENT_TRACE.set(tid)
    return tid


def finish_trace(status="ok", result_summary=None):
    tid = _CURRENT_TRACE.get()
    if not tid:
        return False
    with _lock:
        t = _by_id.get(tid)
        if not t:
            return False
        now = time.time()
        t["finished_at"] = now
        t["duration_ms"] = int((now - t["started_at"]) * 1000)
        t["status"] = status
        if result_summary:
            t["result_summary"] = result_summary
    _CURRENT_TRACE.set(None)
    return True


def current_trace_id():
    return _CURRENT_TRACE.get()


def add_span(kind, name, attributes=None):
    tid = _CURRENT_TRACE.get()
    if not tid:
        return None
    span = {
        "span_id": uuid.uuid4().hex[:12],
        "trace_id": tid,
        "kind": kind,
        "name": name,
        "started_at": time.time(),
        "finished_at": None,
        "duration_ms": None,
        "status": "running",
        "attributes": dict(attributes or {}),
    }
    with _lock:
        t = _by_id.get(tid)
        if not t:
            return None
        t["spans"].append(span)
    return span


def finish_span(span, status="ok", extra=None):
    if span is None:
        return False
    now = time.time()
    span["finished_at"] = now
    span["duration_ms"] = int((now - span["started_at"]) * 1000)
    span["status"] = status
    if extra:
        span["attributes"].update(extra)
    return True


def get_recent_traces(limit=20, role=None):
    try:
        lim = max(1, min(int(limit or 20), 100))
    except Exception:
        lim = 20
    with _lock:
        items = list(_traces)
    if role:
        items = [t for t in items if t.get("role") == role]
    return list(reversed(items))[:lim]


def get_trace(trace_id):
    with _lock:
        return _by_id.get(trace_id)


def clear_traces():
    with _lock:
        n = len(_traces)
        _traces.clear()
        _by_id.clear()
        return n


def stats():
    with _lock:
        items = list(_traces)
    return {
        "trace_count": len(items),
        "max_traces": _MAX_TRACES,
        "running": sum(1 for t in items if t.get("status") == "running"),
        "total_spans": sum(len(t.get("spans") or []) for t in items),
    }
