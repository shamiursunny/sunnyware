# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""LLM usage + cost tracking (per-tenant, Neon-persisted)."""

import os
import time
from datetime import datetime, timezone
from typing import Optional


# Cost table in USD per 1M tokens: (input, output)
# Update as pricing changes. Values are estimates.
COST_TABLE = {
    # Google Gemini (as of 2026)
    "gemini-2.5-flash": (0.075, 0.30),
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-2.5-flash-lite": (0.075, 0.30),
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-2.0-flash-lite": (0.075, 0.30),
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-1.5-pro": (1.25, 5.00),
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
    """Part 138: tenant key, fallback to rate-limit key."""
    try:
        from . import tenant
        tk = tenant.get_key() or ""
        if tk:
            return tk
        try:
            return tenant.get_rate_limit_key() or ""
        except Exception:
            return ""
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


async def all_tenants_summary(days: int = 7, limit: int = 100) -> dict:
    """Part 138: cross-tenant rollup."""
    out = {"window_days": days, "tenants": [], "totals": None}
    if not _persist_enabled():
        return out
    pool = await _get_pool()
    if pool is None:
        return out
    try:
        async with pool.acquire() as conn:
            await _ensure_table(conn)
            rows = await conn.fetch(
                "SELECT tenant_key, COUNT(*) AS calls, "
                "COALESCE(SUM(input_tokens),0) AS input_tokens, "
                "COALESCE(SUM(output_tokens),0) AS output_tokens, "
                "COALESCE(SUM(cost_usd),0) AS cost_usd "
                "FROM llm_usage "
                "WHERE created_at > NOW() - make_interval(days => $1) "
                "GROUP BY tenant_key ORDER BY cost_usd DESC LIMIT $2",
                days, limit,
            )
            out["tenants"] = [
                {
                    "tenant_key": r["tenant_key"],
                    "calls": int(r["calls"] or 0),
                    "input_tokens": int(r["input_tokens"] or 0),
                    "output_tokens": int(r["output_tokens"] or 0),
                    "cost_usd": round(float(r["cost_usd"] or 0), 6),
                }
                for r in rows
            ]
            tot = await conn.fetchrow(
                "SELECT COUNT(*) AS calls, "
                "COALESCE(SUM(input_tokens),0) AS input_tokens, "
                "COALESCE(SUM(output_tokens),0) AS output_tokens, "
                "COALESCE(SUM(cost_usd),0) AS cost_usd "
                "FROM llm_usage "
                "WHERE created_at > NOW() - make_interval(days => $1)",
                days,
            )
            out["totals"] = {
                "calls": int(tot["calls"] or 0),
                "input_tokens": int(tot["input_tokens"] or 0),
                "output_tokens": int(tot["output_tokens"] or 0),
                "cost_usd": round(float(tot["cost_usd"] or 0), 6),
            }
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
    return out


async def trends(days: int = 30, bucket: str = "day") -> dict:
    """Part 138: time-bucketed series."""
    if bucket not in ("hour", "day", "week"):
        bucket = "day"
    out = {"bucket": bucket, "window_days": days, "series": []}
    if not _persist_enabled():
        return out
    pool = await _get_pool()
    if pool is None:
        return out
    try:
        async with pool.acquire() as conn:
            await _ensure_table(conn)
            rows = await conn.fetch(
                "SELECT date_trunc($1, created_at) AS bucket_at, "
                "COUNT(*) AS calls, "
                "COALESCE(SUM(input_tokens),0) AS input_tokens, "
                "COALESCE(SUM(output_tokens),0) AS output_tokens, "
                "COALESCE(SUM(cost_usd),0) AS cost_usd "
                "FROM llm_usage "
                "WHERE created_at > NOW() - make_interval(days => $2) "
                "GROUP BY bucket_at ORDER BY bucket_at ASC",
                bucket, days,
            )
            out["series"] = [
                {
                    "bucket_at": r["bucket_at"].isoformat() if r["bucket_at"] else None,
                    "calls": int(r["calls"] or 0),
                    "input_tokens": int(r["input_tokens"] or 0),
                    "output_tokens": int(r["output_tokens"] or 0),
                    "cost_usd": round(float(r["cost_usd"] or 0), 6),
                }
                for r in rows
            ]
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
    return out


async def reset(tenant_key: Optional[str] = None) -> dict:
    """Part 138: delete usage rows (all or one tenant)."""
    if not _persist_enabled():
        return {"reset": False, "reason": "persist disabled"}
    pool = await _get_pool()
    if pool is None:
        return {"reset": False, "reason": "no pool"}
    try:
        async with pool.acquire() as conn:
            await _ensure_table(conn)
            if tenant_key:
                r = await conn.execute(
                    "DELETE FROM llm_usage WHERE tenant_key = $1",
                    tenant_key,
                )
            else:
                r = await conn.execute("DELETE FROM llm_usage")
            n = int(r.split()[1]) if r.startswith("DELETE") else 0
        if not tenant_key:
            _local.update({
                "total_calls": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_cost_usd": 0.0,
            })
            _recent.clear()
        return {"reset": True, "deleted": n, "tenant": tenant_key or "*"}
    except Exception as e:
        return {"reset": False, "error": f"{type(e).__name__}: {e}"}


async def export_rows(days: int = 30, limit: int = 10000) -> list:
    """Part 138: flat rows for CSV export."""
    if not _persist_enabled():
        return []
    pool = await _get_pool()
    if pool is None:
        return []
    try:
        async with pool.acquire() as conn:
            await _ensure_table(conn)
            rows = await conn.fetch(
                "SELECT created_at, tenant_key, model, "
                "input_tokens, output_tokens, cost_usd, latency_ms "
                "FROM llm_usage "
                "WHERE created_at > NOW() - make_interval(days => $1) "
                "ORDER BY created_at DESC LIMIT $2",
                days, limit,
            )
            return [
                {
                    "created_at": r["created_at"].isoformat() if r["created_at"] else "",
                    "tenant_key": r["tenant_key"] or "",
                    "model": r["model"] or "",
                    "input_tokens": int(r["input_tokens"] or 0),
                    "output_tokens": int(r["output_tokens"] or 0),
                    "cost_usd": round(float(r["cost_usd"] or 0), 8),
                    "latency_ms": int(r["latency_ms"] or 0),
                }
                for r in rows
            ]
    except Exception:
        return []


# ── Part 159: budget config + alerts ────────────────────────────

_BUDGET_FIRED: dict = {}   # tenant -> {period_key -> set(fired_pct)}


def _budget_daily() -> float:
    try:
        return float(os.getenv("SUNNYWARE_BUDGET_USD_DAILY", "0") or "0")
    except Exception:
        return 0.0


def _budget_monthly() -> float:
    try:
        return float(os.getenv("SUNNYWARE_BUDGET_USD_MONTHLY", "0") or "0")
    except Exception:
        return 0.0


def _alert_thresholds() -> list:
    raw = os.getenv("SUNNYWARE_BUDGET_ALERT_PCT", "80")
    out = []
    for chunk in (raw or "").split(","):
        try:
            v = int(chunk.strip())
            if 1 <= v <= 100:
                out.append(v)
        except Exception:
            continue
    return sorted(set(out)) or [80]


async def _sum_since(tenant_key: str, since_iso: str) -> dict:
    pool = await _get_pool()
    if pool is None:
        return {"calls": 0, "cost_usd": 0.0}
    try:
        async with pool.acquire() as conn:
            await _ensure_table(conn)
            row = await conn.fetchrow(
                """
                SELECT COUNT(*) AS calls,
                       COALESCE(SUM(cost_usd), 0) AS cost_usd
                FROM llm_usage
                WHERE tenant_key = $1 AND created_at >= $2
                """,
                tenant_key, since_iso,
            )
        return {
            "calls": int(row["calls"] or 0),
            "cost_usd": round(float(row["cost_usd"] or 0), 6),
        }
    except Exception:
        return {"calls": 0, "cost_usd": 0.0}


async def budget_status(tenant_key: Optional[str] = None) -> dict:
    """Return daily + monthly usage vs configured caps."""
    if tenant_key is None:
        tenant_key = _get_tenant()
    tenant_key = tenant_key or ""
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    daily_cap = _budget_daily()
    monthly_cap = _budget_monthly()
    daily = await _sum_since(tenant_key, day_start.isoformat())
    monthly = await _sum_since(tenant_key, month_start.isoformat())

    def _pct(used: float, cap: float) -> float:
        if cap <= 0:
            return 0.0
        return round((used / cap) * 100.0, 2)

    def _pack(u: dict, cap: float) -> dict:
        enabled = cap > 0
        return {
            "used_usd": u["cost_usd"],
            "cap_usd": cap,
            "remaining_usd": (round(max(0.0, cap - u["cost_usd"]), 6)
                              if enabled else -1.0),
            "pct": _pct(u["cost_usd"], cap),
            "calls": u["calls"],
            "enabled": enabled,
        }

    return {
        "tenant_key": tenant_key,
        "daily": _pack(daily, daily_cap),
        "monthly": _pack(monthly, monthly_cap),
        "alert_thresholds_pct": _alert_thresholds(),
        "checked_at": now.isoformat(),
    }


async def check_budget(tenant_key: Optional[str] = None) -> dict:
    """Return {ok, reason?, daily, monthly}. ok=False if over any cap."""
    s = await budget_status(tenant_key)
    d = s["daily"]
    m = s["monthly"]
    if d["enabled"] and d["remaining_usd"] <= 0:
        return {"ok": False, "reason": "daily_budget_exceeded",
                "daily": d, "monthly": m}
    if m["enabled"] and m["remaining_usd"] <= 0:
        return {"ok": False, "reason": "monthly_budget_exceeded",
                "daily": d, "monthly": m}
    return {"ok": True, "daily": d, "monthly": m}


def fire_alerts(tenant_key: str, status: dict) -> list:
    """Return newly crossed alert thresholds (deduped per period)."""
    out = []
    try:
        now = datetime.now(timezone.utc)
        day_key = f"{now.date().isoformat()}:day"
        month_key = f"{now.strftime('%Y-%m')}:month"
        per_tenant = _BUDGET_FIRED.setdefault(tenant_key or "", {})
        for period, key in (("daily", day_key), ("monthly", month_key)):
            p = status.get(period) or {}
            if not p.get("enabled"):
                continue
            fired = per_tenant.setdefault(key, set())
            for t in _alert_thresholds():
                if p.get("pct", 0) >= t and t not in fired:
                    fired.add(t)
                    out.append({
                        "period": period,
                        "threshold_pct": t,
                        "actual_pct": p.get("pct"),
                        "used_usd": p.get("used_usd"),
                        "cap_usd": p.get("cap_usd"),
                    })
    except Exception:
        pass
    return out


async def rollup(tenant_key: Optional[str] = None, days: int = 30,
                 bucket: str = "day") -> dict:
    """Per-tenant bucketed time series (day/week/month)."""
    if tenant_key is None:
        tenant_key = _get_tenant()
    tenant_key = tenant_key or ""
    if bucket not in ("hour", "day", "week", "month"):
        bucket = "day"
    out = {
        "tenant_key": tenant_key,
        "bucket": bucket,
        "window_days": days,
        "series": [],
    }
    pool = await _get_pool()
    if pool is None:
        return out
    try:
        async with pool.acquire() as conn:
            await _ensure_table(conn)
            rows = await conn.fetch(
                """
                SELECT date_trunc($1, created_at) AS bucket_at,
                       COUNT(*) AS calls,
                       COALESCE(SUM(input_tokens), 0) AS input_tokens,
                       COALESCE(SUM(output_tokens), 0) AS output_tokens,
                       COALESCE(SUM(cost_usd), 0) AS cost_usd
                FROM llm_usage
                WHERE tenant_key = $2
                  AND created_at > NOW() - make_interval(days => $3)
                GROUP BY bucket_at
                ORDER BY bucket_at ASC
                """,
                bucket, tenant_key, days,
            )
        out["series"] = [
            {
                "bucket_at": r["bucket_at"].isoformat() if r["bucket_at"] else None,
                "calls": int(r["calls"] or 0),
                "input_tokens": int(r["input_tokens"] or 0),
                "output_tokens": int(r["output_tokens"] or 0),
                "cost_usd": round(float(r["cost_usd"] or 0), 6),
            }
            for r in rows
        ]
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def reset_alerts(tenant_key: Optional[str] = None) -> int:
    """Clear fired-alert state. Returns how many tenant entries cleared."""
    if tenant_key is None:
        n = len(_BUDGET_FIRED)
        _BUDGET_FIRED.clear()
        return n
    existed = tenant_key in _BUDGET_FIRED
    _BUDGET_FIRED.pop(tenant_key, None)
    return 1 if existed else 0


def cost_table_snapshot() -> list:
    return [
        {"model": k, "input_per_million_usd": v[0], "output_per_million_usd": v[1]}
        for k, v in COST_TABLE.items()
    ]
