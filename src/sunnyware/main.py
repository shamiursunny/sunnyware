# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""FastAPI entry point — Part 1: minimal server skeleton.

CRITICAL: lifespan=lifespan MUST be passed to Server(...).
Without it, the startup logic never runs and /api/agent/run returns 503.

Uses gradio.Server (FastAPI subclass) so we can deploy on HF free tier
under the Gradio SDK, while keeping full FastAPI custom routes.
"""

import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from gradio import Server                       # ← FastAPI-compatible subclass
from fastapi import Request
from fastapi.responses import JSONResponse
import uvicorn

from .config import load_config
from . import state as app_state
from . import llm as llm_client
from . import sessions as sessions_store
from . import memory as memory_store
from . import orchestrator
from . import tools as tools_registry
from .logging_config import configure_logging


# ── Author metadata ─────────────────────────────────────────────────────────
AUTHOR_NAME = "Shamiur Rashid Sunny"
AUTHOR_EMAIL = "shamiur@engineer.com"
AUTHOR_PHONE = "+880-01737394735"
AUTHOR_WEBSITE = "https://shamiur.com"
AUTHOR_GITHUB = "https://github.com/shamiursunny"
PROJECT_VERSION = "0.1.0"
COPYRIGHT = "Copyright (c) 2026 Shamiur Rashid Sunny"
LICENSE_ID = "AGPL-3.0-only"


# ── Logging setup (stderr fallback if /data not writable) ───────────────────
log = configure_logging("/data/logs" if os.path.exists("/data") else "./data/logs")

async def _ensure_pool():
    """Lazy-init Neon pool if not ready. Idempotent. Called at start of DB-touching endpoints."""
    if app_state.get_pool() is None:
        try:
            await app_state.init_pool()
        except Exception as e:
            log.error("Pool init failed", error=str(e))




# ── Application state ───────────────────────────────────────────────────────
state = {
    "ready": False,
    "started_at": None,
    "config": None,
}


# ── Logging setup ───────────────────────────────────────────────────────────
log = configure_logging("./data/logs")


# ── Application state ───────────────────────────────────────────────────────
state = {
    "ready": False,
    "started_at": None,
    "config": None,
}


# ── Idempotent initialization ───────────────────────────────────────────────
def _init_state() -> None:
    """Initialize application state. Safe to call multiple times.

    Called at module import (fallback for HF Spaces whose Gradio launch
    path skips FastAPI lifespan) AND in lifespan (normal uvicorn path).
    """
    if state["ready"]:
        return

    log.info("sunnyware initializing", version=PROJECT_VERSION)
    state["started_at"] = time.time()

    try:
        cfg = load_config()
        state["config"] = cfg
        log.info("Config loaded", agent_path=cfg.generic_agent_path)

        data_dir = Path("./data")
        (data_dir / "workspace").mkdir(parents=True, exist_ok=True)
        (data_dir / "logs").mkdir(parents=True, exist_ok=True)

        # Neon pool init moved to lazy path (Part 2 fix)
        # See /health/ready — pool created on first request
        # This avoids Windows ProactorEventLoop hang at import time

        state["ready"] = True
        log.info("sunnyware ready", version=PROJECT_VERSION)
    except Exception as e:
        log.error("Startup failed", error=str(e), exc_info=True)
        state["ready"] = False


# ── Lifespan (used when uvicorn / Server.launch() runs) ─────────────────────
@asynccontextmanager
async def lifespan(app):
    _init_state()
    yield
    state["ready"] = False
    log.info("sunnyware shutting down")


# ── Server ──────────────────────────────────────────────────────────────────
app = Server(
    title="sunnyware",
    version=PROJECT_VERSION,
    lifespan=lifespan,
)


# ── FALLBACK: init at import time (HF Spaces skips lifespan) ────────────────
_init_state()


# ── Endpoints ───────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {
        "name": "sunnyware",
        "version": PROJECT_VERSION,
        "author": {
            "name": AUTHOR_NAME,
            "email": AUTHOR_EMAIL,
            "phone": AUTHOR_PHONE,
            "website": AUTHOR_WEBSITE,
            "github": AUTHOR_GITHUB,
        },
        "copyright": COPYRIGHT,
        "license": LICENSE_ID,
        "architecture": "part-1-basic-server",
        "endpoints": ["/", "/about", "/health/live", "/health/ready", "/api/agent/run"],
    }


@app.get("/about")
async def about():
    return {
        "project": "sunnyware",
        "version": PROJECT_VERSION,
        "author": AUTHOR_NAME,
        "email": AUTHOR_EMAIL,
        "phone": AUTHOR_PHONE,
        "website": AUTHOR_WEBSITE,
        "github": AUTHOR_GITHUB,
        "copyright": COPYRIGHT,
        "license": LICENSE_ID,
    }


@app.get("/health/live")
async def liveness():
    """Server is running. Always returns 200 if the process is alive."""
    return {"status": "ok"}


@app.get("/health/ready")
async def readiness():
    """Full readiness check — includes startup state verification."""
    checks = {}
    all_ok = True

    checks["lifespan_ran"] = state["ready"]
    if not state["ready"]:
        all_ok = False

    checks["config_loaded"] = state["config"] is not None
    if not state["config"]:
        all_ok = False

    # Neon check (Part 2) — lazy init on first request
    if state["config"] and state["config"].neon_database_url:
        if app_state.get_pool() is None:
            ok = await app_state.init_pool()
            log.info("Neon pool init", ok=ok)
        neon = await app_state.health_check()
        checks["neon"] = neon.get("status", "unknown")
        if neon.get("status") == "error":
            all_ok = False
            checks["neon_error"] = neon.get("error", "unknown")[:200]
        elif neon.get("status") == "not_initialized":
            checks["neon_error"] = neon.get("error", "unknown")[:200]
    else:
        checks["neon"] = "not_configured"

    # LLM check (Part 3) — non-fatal
    if state["config"] and state["config"].llm_base_url:
        llm_health = await llm_client.health_check(timeout=3.0)
        checks["llm"] = llm_health.get("status", "unknown")
        if llm_health.get("status") == "error":
            checks["llm_error"] = llm_health.get("error", "")[:200]
    else:
        checks["llm"] = "not_configured"

    # Sessions + memory health (Part 4) — non-fatal
    sess_health = await sessions_store.health_check()
    checks["sessions"] = sess_health.get("status", "unknown")
    mem_health = await memory_store.health_check()
    checks["memory"] = mem_health.get("status", "unknown")

    # Tools (Part 6)
    checks["tools"] = len(tools_registry.list_tools())

    return JSONResponse(
        {
            "status": "ok" if all_ok else "degraded",
            "checks": checks,
            "author": AUTHOR_NAME,
        },
        status_code=200 if all_ok else 503,
    )


@app.post("/api/agent/run")
async def run_agent(req: Request):
    """Part 3 — LLM round-trip via OpenAI-compatible endpoint."""
    if not state["ready"]:
        return JSONResponse({"error": "server not ready"}, status_code=503)

    await _ensure_pool()

    body = await req.json()
    prompt = body.get("input", "")
    session_id = body.get("session_id", "default")
    model = body.get("model")
    system = body.get("system")

    if not prompt:
        return JSONResponse({"error": "input required"}, status_code=400)

    # Part 4: get or create session
    session_uuid = await sessions_store.get_or_create(session_id)

    # Part 5A: build conversation context (BEFORE logging current turn)
    history = []
    if session_uuid:
        history = await memory_store.build_context(session_uuid, max_turns=10)

    # Part 4: log current user turn
    if session_uuid:
        await memory_store.log_event(
            session_uuid,
            "user_message",
            {"content": prompt, "model": model or "default"},
        )

    # Part 6: route through orchestrator (agent can call tools)
    import time as _time
    _t0 = _time.time()
    agent_result = await orchestrator.run_agent(
        prompt, session_uuid=session_uuid, model=model, system=system
    )
    total_latency_ms = int((_time.time() - _t0) * 1000)

    # Log assistant turn (or error) to memory
    if session_uuid:
        if agent_result.get("ok"):
            await memory_store.log_event(
                session_uuid,
                "assistant_message",
                {
                    "content": agent_result.get("answer", ""),
                    "steps_count": len(agent_result.get("steps", [])),
                    "iterations": agent_result.get("iterations", 0),
                    "model": model or state["config"].llm_model if state["config"] else "unknown",
                },
            )
        else:
            await memory_store.log_event(
                session_uuid,
                "llm_error",
                {"error": agent_result.get("error", "unknown")},
            )

    # Graceful degradation — always 200 for valid requests
    if not agent_result.get("ok"):
        return {
            "result": None,
            "error": "Agent failed",
            "detail": agent_result.get("error"),
            "latency_ms": total_latency_ms,
            "served_by": "sunnyware",
            "session_id": session_id,
            "session_uuid": session_uuid,
        }

    return {
        "result": {
            "content": agent_result.get("answer", ""),
            "model": (state["config"].llm_model if state["config"] else "unknown"),
            "steps": agent_result.get("steps", []),
            "iterations": agent_result.get("iterations", 1),
        },
        "latency_ms": total_latency_ms,
        "served_by": "sunnyware",
        "session_id": session_id,
        "session_uuid": session_uuid,
    }




# ── Part 4: Session & memory endpoints ──────────────────────────────────────
@app.get("/api/sessions")
async def list_sessions(limit: int = 20):
    """List recent sessions."""
    await _ensure_pool()
    items = await sessions_store.list_recent(limit=min(limit, 100))
    return {"count": len(items), "sessions": items}


@app.get("/api/sessions/{session_key}")
async def get_session_detail(session_key: str):
    """Get session by key with event history."""
    await _ensure_pool()
    sess = await sessions_store.get(session_key)
    if not sess:
        return JSONResponse({"error": "session not found"}, status_code=404)
    history = await memory_store.get_history(sess["id"], limit=50)
    return {"session": sess, "event_count": len(history), "history": history}


@app.delete("/api/sessions/{session_key}")
async def delete_session_endpoint(session_key: str):
    """Delete session (cascades to events)."""
    ok = await sessions_store.delete(session_key)
    return {"deleted": ok, "session_key": session_key}




# ── Part 6: Tool endpoints ──────────────────────────────────────────────────
@app.get("/api/tools")
async def list_tools_endpoint():
    """List all registered tools with metadata."""
    items = tools_registry.list_tools()
    return {"count": len(items), "tools": items}


@app.post("/api/tools/{tool_name}")
async def call_tool_endpoint(tool_name: str, req: Request):
    """Direct tool invocation (bypasses LLM). For testing / integrations."""
    tool = tools_registry.get_tool(tool_name)
    if tool is None:
        return JSONResponse(
            {"error": f"unknown tool: {tool_name}", "available": tools_registry.tool_names()},
            status_code=404,
        )
    try:
        args = await req.json()
    except Exception:
        args = {}
    if not isinstance(args, dict):
        args = {}
    try:
        result = await tool.run(args)
    except Exception as e:
        return JSONResponse(
            {"error": f"{type(e).__name__}: {e}"},
            status_code=500,
        )
    return {"tool": tool_name, "args": args, "result": result}




# ── Part 8: Memory inspection endpoint ──────────────────────────────────────
@app.get("/api/memory/context")
async def memory_context(q: str, session_id: str = None):
    """Show what cross-session memory would be injected for a given query.

    Useful for debugging: "what does the agent remember about X?"
    """
    await _ensure_pool()
    exclude_uuid = None
    if session_id:
        sess = await sessions_store.get(session_id)
        if sess:
            exclude_uuid = sess["id"]

    events = await memory_store.select_relevant_events(
        q, exclude_session_uuid=exclude_uuid, limit=5
    )
    formatted = memory_store.format_context(events)

    return {
        "query": q,
        "exclude_session": session_id,
        "count": len(events),
        "events": events,
        "formatted_context": formatted,
    }




# ── Part 9: Session history API ─────────────────────────────────────────────
@app.get("/api/sessions/{session_key}/history")
async def session_history(session_key: str, limit: int = 200):
    """Full chronological event timeline for a session."""
    await _ensure_pool()
    sess = await sessions_store.get(session_key)
    if not sess:
        return JSONResponse({"error": "session not found"}, status_code=404)
    events = await memory_store.get_all_events(sess["id"], max_limit=min(limit, 1000))
    return {
        "session": sess,
        "count": len(events),
        "events": events,
    }


@app.get("/api/sessions/{session_key}/export")
async def session_export(session_key: str):
    """Full JSON export (session + all events) for backup / portability."""
    await _ensure_pool()
    from datetime import datetime, timezone
    sess = await sessions_store.get(session_key)
    if not sess:
        return JSONResponse({"error": "session not found"}, status_code=404)
    events = await memory_store.get_all_events(sess["id"], max_limit=1000)
    export = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "sunnyware_version": PROJECT_VERSION,
        "session": sess,
        "event_count": len(events),
        "events": events,
    }
    return JSONResponse(
        export,
        headers={
            "Content-Disposition": f'attachment; filename="session-{session_key}.json"'
        },
    )


@app.post("/api/sessions/{session_key}/rewind")
async def session_rewind(session_key: str, req: Request):
    """Soft-truncate: delete all events with id > to_event.

    Body: {"to_event": <event_id>}
    Keeps events up to and including to_event.
    """
    sess = await sessions_store.get(session_key)
    if not sess:
        return JSONResponse({"error": "session not found"}, status_code=404)

    try:
        body = await req.json()
    except Exception:
        body = {}

    to_event = body.get("to_event")
    if to_event is None:
        return JSONResponse(
            {"error": "to_event (event id) required in body"}, status_code=400
        )
    try:
        to_event = int(to_event)
    except Exception:
        return JSONResponse({"error": "to_event must be an integer"}, status_code=400)

    deleted = await memory_store.delete_events_after(sess["id"], to_event)
    return {
        "session_key": session_key,
        "kept_up_to_event_id": to_event,
        "deleted_count": deleted,
    }


# ── Entry point ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "7860")))