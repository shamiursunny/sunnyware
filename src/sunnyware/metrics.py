# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""In-memory metrics + optional Neon persistence (write-through throttled)."""

import os
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

# Persistence state
_dirty: set = set()
_last_flush: float = 0.0
_load_attempted: bool = False
_load_ok: bool = False
_flush_interval: float = 10.0


def _persist_enabled() -> bool:
    v = (os.getenv("SUNNYWARE_PERSIST_METRICS", "true") or "").lower()
    return v not in ("false", "0", "no", "off")


def incr(key: str, by: int = 1) -> None:
    _counters[key] = _counters.get(key, 0) + by
    _dirty.add(key)


def incr_labeled(bucket: str, label: str, by: int = 1) -> None:
    b = _labeled.setdefault(bucket, {})
    b[label] = b.get(label, 0) + by
    _dirty.add(f"{bucket}:{label}")


def snapshot() -> dict:
    out = dict(_counters)
    for k, v in _labeled.items():
        out[k] = dict(v)
    out["uptime_seconds"] = int(time.time() - _started_at)
    out["persist"] = {
        "enabled": _persist_enabled(),
        "last_flush_unix": _last_flush,
        "dirty_keys": len(_dirty),
        "loaded_from_db": _load_ok,
        "flush_interval_sec": _flush_interval,
    }
    return out


def reset() -> None:
    global _started_at, _last_flush
    _started_at = time.time()
    _last_flush = 0.0
    for k in _counters:
        _counters[k] = 0
    for k in _labeled:
        _labeled[k] = {}
    _dirty.clear()


# ── Persistence ────────────────────────────────────────────────────────────

async def _get_pool():
    """Return pool, initializing if needed."""
    try:
        from . import state as app_state
        pool = app_state.get_pool()
        if pool is None:
            try:
                await app_state.init_pool()
                pool = app_state.get_pool()
            except Exception:
                return None
        return pool
    except Exception:
        return None


async def _ensure_table(conn):
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS metrics_counters (
            key TEXT PRIMARY KEY,
            value BIGINT NOT NULL DEFAULT 0,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)


async def load_from_db() -> bool:
    global _load_ok
    pool = await _get_pool()
    if pool is None:
        _load_ok = False
        return False
    try:
        async with pool.acquire() as conn:
            await _ensure_table(conn)
            rows = await conn.fetch("SELECT key, value FROM metrics_counters")
        for r in rows:
            k = r["key"]
            v = int(r["value"])
            if ":" in k:
                bucket, label = k.split(":", 1)
                if bucket in _labeled:
                    _labeled[bucket][label] = v
                    continue
            _counters[k] = v
        _load_ok = True
        return True
    except Exception:
        _load_ok = False
        return False


async def ensure_loaded() -> None:
    """Load once per process. Retries if pool wasn't ready on first try."""
    global _load_attempted
    if _load_attempted and _load_ok:
        return
    if not _persist_enabled():
        _load_attempted = True
        return
    ok = await load_from_db()
    _load_attempted = True
    # If load failed, allow a retry on a later request
    if not ok:
        _load_attempted = False


async def flush_now() -> int:
    """Force-write all dirty counters to DB. Returns keys written."""
    global _last_flush
    if not _persist_enabled():
        return 0
    pool = await _get_pool()
    if pool is None:
        return 0

    keys = list(_dirty)
    if not keys:
        _last_flush = time.time()
        return 0

    writes = []
    for k in keys:
        if ":" in k:
            bucket, label = k.split(":", 1)
            v = _labeled.get(bucket, {}).get(label, 0)
            writes.append((k, int(v)))
        elif k in _counters:
            writes.append((k, int(_counters[k])))

    try:
        async with pool.acquire() as conn:
            await _ensure_table(conn)
            async with conn.transaction():
                for key, value in writes:
                    await conn.execute("""
                        INSERT INTO metrics_counters (key, value, updated_at)
                        VALUES ($1, $2, NOW())
                        ON CONFLICT (key) DO UPDATE
                            SET value = $2, updated_at = NOW()
                    """, key, value)
        for k, _ in writes:
            _dirty.discard(k)
        _last_flush = time.time()
        return len(writes)
    except Exception:
        return 0


async def flush_if_due(interval: float = None) -> int:
    """Called from middleware — flushes at most once per interval."""
    if not _persist_enabled():
        return 0
    if not _dirty:
        return 0
    iv = interval if interval is not None else _flush_interval
    if (time.time() - _last_flush) < iv:
        return 0
    return await flush_now()


def persistence_status() -> dict:
    return {
        "enabled": _persist_enabled(),
        "last_flush_unix": _last_flush,
        "dirty_keys": len(_dirty),
        "loaded_from_db": _load_ok,
        "flush_interval_sec": _flush_interval,
    }
