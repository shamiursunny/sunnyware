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
    """Part 1 stub — returns echo response. Orchestrator added in Part 17."""
    if not state["ready"]:
        return JSONResponse(
            {"error": "server not ready — lifespan did not complete"},
            status_code=503,
        )

    body = await req.json()
    prompt = body.get("input", "")
    session_id = body.get("session_id", "default")

    start = time.time()
    result = {"echo": prompt, "note": "Part 1 stub — orchestrator added in Part 17"}
    latency_ms = int((time.time() - start) * 1000)

    return {
        "result": result,
        "latency_ms": latency_ms,
        "served_by": "sunnyware",
        "session_id": session_id,
    }


# ── Entry point ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "7860")))