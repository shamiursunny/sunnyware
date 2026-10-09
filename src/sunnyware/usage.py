# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""LLM usage + cost tracking (per-tenant, Neon-persisted)."""

import os
import time
from typing import Optional


# Cost table in USD per 1M tokens: (input, output)
# Update as pricing changes. Values are estimates.
COST_TABLE = {
    # Groq (as of 2026)
    "openai/gpt-oss-20b": (0.10, 0.50),
    "openai/gpt-oss-120b": (0.30, 1.20),
    "qwen/qwen3.8-27b": (0.20, 0.60),
    "allam-2-7b": (0.05, 0.10),
    # OpenAI
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    # Ollama (local — free)
    "__ollama__": (0.0, 0.0),
}

# In-memory rollup for the current process (also persisted to Neon)
_local = {
    "total_calls": 0,
    "total_input_tokens": 0,
    "total_output_tokens": 0,
    "total_cost_usd": 0.0,
}

_recent = []  # list of last N requests (in-memory only)
_MAX_RECENT = 200


def _persist_enabled() -> bool:
    v = (os.getenv("SUNNYWARE_PERSIST_USAGE", "true") or "").lower()
    return v not in ("false", "0", "no", "off")


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost for a model call."""
    model_l = (model or "").lower()
    # Local models are free
    base_url = (os.getenv("LLM_BASE_URL") or "").lower()
    if "localhost" in base_url or "127.0.0.1" in base_url:
        return 0.0

    pricing = None
    for key, val in COST_TABLE.items():
        if key == "__ollama__":
            continue
        if key.lower() in model_l:
            pricing = val
            break

    if pricing is None:
        # Unknown model — assume cheap
        pricing = (0.10, 0.50)

    in_rate, out_rate = pricing
    return (input_tokens / 1_000_000.0) * in_rate + (output_tokens / 1_000_000.0) * out_rate


def _get_tenant() -> str:
    try:
        from . import tenant
        return tenant.get_key() or ""
    except Exception:
        return ""


async def _get_pool():
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
        CREATE TABLE IF NOT EXISTS llm_usage (
            id BIGSERIAL PRIMARY KEY,
            tenant_key TEXT NOT NULL DEFAULT '',
            model TEXT NOT NULL,
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            cost_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
            latency_ms INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_llm_usage_tenant ON llm_usage (tenant_key, created_at DESC)"
    )


async def record(
    model: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: int = 0,
    tenant_key: Optional[str] = None,
) -> None:
    """Record a single LLM call. Never raises."""
    try:
        tenant_key = tenant_key if tenant_key is not None else _get_tenant()
        input_tokens = max(0, int(input_tokens or 0))
        output_tokens = max(0, int(output_tokens or 0))
        cost = estimate_cost(model or "", input_tokens, output_tokens)
        latency_ms = max(0, int(latency_ms or 0))

        _local["total_calls"] += 1
        _local["total_input_tokens"] += input_tokens
        _local["total_output_tokens"] += output_tokens
        _local["total_cost_usd"] += cost

        entry = {
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": round(cost, 8),
            "latency_ms": latency_ms,
            "created_at": time.time(),
        }
        _recent.append(entry)
        if len(_recent) > _MAX_RECENT:
            del _recent[: len(_recent) - _MAX_RECENT]

        if _persist_enabled():
            pool = await _get_pool()
            if pool is not None:
                async with pool.acquire() as conn:
                    await _ensure_table(conn)
                    await conn.execute(
                        """
                        INSERT INTO llm_usage
                          (tenant_key, model, input_tokens, output_tokens, cost_usd, latency_ms)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        """,
                        tenant_key, model or "unknown",
                        input_tokens, output_tokens, cost, latency_ms,
                    )
    except Exception:
        pass


async def summary(tenant_key: Optional[str] = None, days: int = 7) -> dict:
    """Return usage summary. If tenant_key is None, scopes to current tenant."""
    if tenant_key is None:
        tenant_key = _get_tenant()
    tenant_key = tenant_key or ""

    out = {
        "tenant_key": tenant_key,
        "window_days": days,
        "process_local": dict(_local),
        "persisted": None,
        "by_model": [],
    }

    if not _persist_enabled():
        return out

    pool = await _get_pool()
    if pool is None:
        return out

    try:
        async with pool.acquire() as conn:
            await _ensure_table(conn)
            row = await conn.fetchrow(
                """
                SELECT
                  COUNT(*) AS calls,
                  COALESCE(SUM(input_tokens),0) AS input_tokens,
                  COALESCE(SUM(output_tokens),0) AS output_tokens,
                  COALESCE(SUM(cost_usd),0) AS cost_usd
                FROM llm_usage
                WHERE tenant_key = $1
                  AND created_at > NOW() - make_interval(days => $2)
                """,
                tenant_key, days,
            )
            out["persisted"] = {
                "calls": int(row["calls"] or 0),
                "input_tokens": int(row["input_tokens"] or 0),
                "output_tokens": int(row["output_tokens"] or 0),
                "cost_usd": round(float(row["cost_usd"] or 0), 6),
            }

            rows = await conn.fetch(
                """
                SELECT model,
                       COUNT(*) AS calls,
                       COALESCE(SUM(input_tokens),0) AS input_tokens,
                       COALESCE(SUM(output_tokens),0) AS output_tokens,
                       COALESCE(SUM(cost_usd),0) AS cost_usd
                FROM llm_usage
                WHERE tenant_key = $1
                  AND created_at > NOW() - make_interval(days => $2)
                GROUP BY model
                ORDER BY cost_usd DESC
                """,
                tenant_key, days,
            )
            out["by_model"] = [
                {
                    "model": r["model"],
                    "calls": int(r["calls"] or 0),
                    "input_tokens": int(r["input_tokens"] or 0),
                    "output_tokens": int(r["output_tokens"] or 0),
                    "cost_usd": round(float(r["cost_usd"] or 0), 6),
                }
                for r in rows
            ]
    except Exception:
        pass

    return out


async def recent(limit: int = 50) -> dict:
    """Return recent in-memory usage entries (this process only)."""
    limit = max(1, min(int(limit), _MAX_RECENT))
    items = list(reversed(_recent))[:limit]
    return {"count": len(items), "entries": items}


def cost_table_snapshot() -> list:
    return [
        {"model": k, "input_per_million_usd": v[0], "output_per_million_usd": v[1]}
        for k, v in COST_TABLE.items()
    ]
