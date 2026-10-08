# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""In-memory metrics counters (simple, single-process)."""

import time


_started_at = time.time()
_counters = {
    "requests_total": 0,
    "tool_calls_total": 0,
    "llm_calls_total": 0,
    "llm_errors_total": 0,
    "errors_total": 0,
}
_labeled = {
    "requests_by_endpoint": {},
    "tool_calls_by_name": {},
}


def incr(key: str, by: int = 1) -> None:
    _counters[key] = _counters.get(key, 0) + by


def incr_labeled(key: str, label: str, by: int = 1) -> None:
    bucket = _labeled.setdefault(key, {})
    bucket[label] = bucket.get(label, 0) + by


def snapshot() -> dict:
    out = dict(_counters)
    for k, v in _labeled.items():
        out[k] = dict(v)
    out["uptime_seconds"] = int(time.time() - _started_at)
    return out


def reset() -> None:
    global _started_at
    _started_at = time.time()
    for k in _counters:
        _counters[k] = 0
    for k in _labeled:
        _labeled[k] = {}
