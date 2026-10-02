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

    body = await req.json()
    prompt = body.get("input", "")
    session_id = body.get("session_id", "default")
    model = body.get("model")
    system = body.get("system")

    if not prompt:
        return JSONResponse({"error": "input required"}, status_code=400)

    # Part 4: get or create session, log user turn
    session_uuid = await sessions_store.get_or_create(session_id)
    if session_uuid:
        await memory_store.log_event(
            session_uuid,
            "user_message",
            {"content": prompt, "model": model or "default"},
        )

    result = await llm_client.chat(prompt, model=model, system=system)

    # Log LLM response (or error) to memory
    if session_uuid:
        if result.get("ok"):
            await memory_store.log_event(
                session_uuid,
                "assistant_message",
                {
                    "content": result["content"],
                    "model": result["model"],
                    "latency_ms": result["latency_ms"],
                },
            )
        else:
            await memory_store.log_event(
                session_uuid,
                "llm_error",
                {"error": result.get("error", "unknown")},
            )

    # Always return 200 (unless request invalid) — graceful degradation.
    if not result.get("ok"):
        return {
            "result": None,
            "error": "LLM call failed",
            "detail": result.get("error"),
            "latency_ms": result.get("latency_ms", 0),
            "served_by": "sunnyware",
            "session_id": session_id,
            "session_uuid": session_uuid,
        }

    return {
        "result": {
            "content": result["content"],
            "model": result["model"],
        },
        "latency_ms": result["latency_ms"],
        "served_by": "sunnyware",
        "session_id": session_id,
        "session_uuid": session_uuid,
    }




# ── Part 4: Session & memory endpoints ──────────────────────────────────────
@app.get("/api/sessions")
async def list_sessions(limit: int = 20):
    """List recent sessions."""
    items = await sessions_store.list_recent(limit=min(limit, 100))
    return {"count": len(items), "sessions": items}


@app.get("/api/sessions/{session_key}")
async def get_session_detail(session_key: str):
    """Get session by key with event history."""
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


# ── Entry point ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "7860")))