# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Root, about, and health endpoints."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from .. import meta
from ..runtime import state, ensure_pool
from .. import state as app_state
from .. import sessions as sessions_store
from .. import memory as memory_store
from .. import llm as llm_client
from .. import tools as tools_registry


router = APIRouter()


@router.get("/")
async def root():
    return {
        "name": "sunnyware",
        "version": meta.PROJECT_VERSION,
        "author": {
            "name": meta.AUTHOR_NAME,
            "email": meta.AUTHOR_EMAIL,
            "phone": meta.AUTHOR_PHONE,
            "website": meta.AUTHOR_WEBSITE,
            "github": meta.AUTHOR_GITHUB,
        },
        "copyright": meta.COPYRIGHT,
        "license": meta.LICENSE_ID,
        "architecture": "part-12alt-refactor",
        "endpoints": [
            "/", "/about", "/health/live", "/health/ready",
            "/api/agent/run", "/api/agent/run/stream", "/api/agent/plan",
            "/api/tools", "/api/tools/{name}",
            "/api/sessions", "/api/sessions/{key}",
            "/api/sessions/{key}/history", "/api/sessions/{key}/export",
            "/api/sessions/{key}/rewind",
            "/api/memory/context",
        ],
    }


@router.get("/about")
async def about():
    return {
        "project": "sunnyware",
        "version": meta.PROJECT_VERSION,
        "author": meta.AUTHOR_NAME,
        "email": meta.AUTHOR_EMAIL,
        "phone": meta.AUTHOR_PHONE,
        "website": meta.AUTHOR_WEBSITE,
        "github": meta.AUTHOR_GITHUB,
        "copyright": meta.COPYRIGHT,
        "license": meta.LICENSE_ID,
    }


@router.get("/health/live")
async def liveness():
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness():
    await ensure_pool()
    checks = {}
    all_ok = True

    checks["lifespan_ran"] = state["ready"]
    if not state["ready"]:
        all_ok = False

    checks["config_loaded"] = state["config"] is not None
    if not state["config"]:
        all_ok = False

    if state["config"] and state["config"].neon_database_url:
        neon = await app_state.health_check()
        checks["neon"] = neon.get("status", "unknown")
        if neon.get("status") == "error":
            all_ok = False
    else:
        checks["neon"] = "not_configured"

    if state["config"] and state["config"].llm_base_url:
        llm_health = await llm_client.health_check(timeout=3.0)
        checks["llm"] = llm_health.get("status", "unknown")
        if llm_health.get("status") == "error":
            checks["llm_error"] = llm_health.get("error", "")[:200]
    else:
        checks["llm"] = "not_configured"

    sess_health = await sessions_store.health_check()
    checks["sessions"] = sess_health.get("status", "unknown")
    mem_health = await memory_store.health_check()
    checks["memory"] = mem_health.get("status", "unknown")
    checks["tools"] = len(tools_registry.list_tools())

    # Part 31: persistent storage info
    try:
        from .. import paths as _paths
        checks["workspace_path"] = str(_paths.workspace())
        checks["persistent_storage"] = _paths.using_persistent_storage()
    except Exception:
        checks["workspace_path"] = "unknown"
        checks["persistent_storage"] = False

    try:
        await memory_store.select_relevant_events("health", limit=1)
        checks["memory_context"] = "ok"
    except Exception as e:
        checks["memory_context"] = f"error: {type(e).__name__}"

    return JSONResponse(
        {
            "status": "ok" if all_ok else "degraded",
            "checks": checks,
            "author": meta.AUTHOR_NAME,
        },
        status_code=200 if all_ok else 503,
    )

@router.get("/metrics")
async def metrics_endpoint():
    """In-memory metrics snapshot (requests, tool calls, errors, uptime)."""
    from .. import metrics as _metrics
    return _metrics.snapshot()

@router.post("/api/metrics/flush")
async def metrics_flush():
    """Force-flush dirty counters to persistent storage (Neon)."""
    from .. import metrics as _metrics
    written = await _metrics.flush_now()
    return {
        "flushed_keys": written,
        "status": _metrics.persistence_status(),
    }

@router.get("/ui", response_class=None)
async def web_ui():
    """Minimal chat web UI."""
    from fastapi.responses import HTMLResponse
    from .. import webui
    return HTMLResponse(webui.HTML)

@router.get("/api/firewall/status")
async def firewall_status():
    """Inspect IP allowlist + security header configuration."""
    from .. import firewall as _fw
    return _fw.status()

@router.get("/api/usage")
async def usage_summary(days: int = 7):
    """LLM usage + cost summary for current tenant."""
    from .. import usage as _usage
    return await _usage.summary(days=days)


@router.get("/api/usage/recent")
async def usage_recent(limit: int = 50):
    """Recent LLM calls (in-memory, current process)."""
    from .. import usage as _usage
    return await _usage.recent(limit=limit)


@router.get("/api/usage/pricing")
async def usage_pricing():
    """Cost table (USD per 1M tokens) used for estimates."""
    from .. import usage as _usage
    return {"cost_table": _usage.cost_table_snapshot()}

