# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Tool-call audit trail (Part 48).

Fire-and-forget logging of every tool invocation to Neon. Never raises —
audit failures must never break tool execution.
"""
import asyncio
import hashlib
import json
from typing import Optional
from . import state as app_state


MAX_ERROR_CHARS = 300


def _hash_args(args: dict) -> str:
    try:
        blob = json.dumps(args or {}, sort_keys=True, default=str).encode()
        return hashlib.sha256(blob).hexdigest()[:16]
    except Exception:
        return ""


def _size_of(obj) -> int:
    try:
        return len(json.dumps(obj, default=str))
    except Exception:
        return 0


async def _write(tool_name, args_hash, ok, error, result_size, latency_ms):
    pool = app_state.get_pool()
    if pool is None:
        return
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO tool_invocations
                   (tool_name, args_hash, ok, error, result_size, latency_ms)
                   VALUES ($1, $2, $3, $4, $5, $6)""",
                tool_name, args_hash, ok,
                (error or "")[:MAX_ERROR_CHARS],
                result_size, latency_ms,
            )
    except Exception:
        pass  # best-effort only


def log_tool_call(tool_name, args, result, error, latency_ms):
    """Fire-and-forget DB write. Never blocks the caller."""
    args_hash = _hash_args(args)
    err = error or ""
    if not err and isinstance(result, dict):
        err = str(result.get("error", ""))
    ok = not err
    result_size = _size_of(result)
    try:
        loop = asyncio.get_event_loop()
        loop.create_task(_write(tool_name, args_hash, ok, err,
                                result_size, latency_ms))
    except Exception:
        pass
