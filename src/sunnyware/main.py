# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""FastAPI entry point — thin wrapper mounting route packages."""

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

if sys.platform == "win32":
    try:
        import asyncio
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

from gradio import Server
import uvicorn

from . import meta
from .runtime import state, init_state, log
from . import state as app_state
from .routes import meta as meta_routes
from .routes import agent as agent_routes
from .routes import tools as tools_routes
from .routes import sessions as sessions_routes
from .routes import memory_routes


@asynccontextmanager
async def lifespan(app):
    init_state()
    yield
    state["ready"] = False
    log.info("sunnyware shutting down")


app = Server(
    title="sunnyware",
    version=meta.PROJECT_VERSION,
    lifespan=lifespan,
)


# Register all routers
app.include_router(meta_routes.router)
app.include_router(agent_routes.router)
app.include_router(tools_routes.router)
app.include_router(sessions_routes.router)
app.include_router(memory_routes.router)


# FALLBACK: init state at import time (HF Spaces skips lifespan)
init_state()


# ── Part 17: request ID + metrics middleware ──
@app.middleware("http")
async def _metrics_middleware(request, call_next):
    import uuid as _uuid
    import time as _time
    from . import metrics as _metrics

    req_id = request.headers.get("x-request-id") or str(_uuid.uuid4())[:8]
    start = _time.time()
    try:
        response = await call_next(request)
    except Exception:
        _metrics.incr("errors_total")
        log.error("request_failed", rid=req_id, path=request.url.path)
        raise
    duration_ms = int((_time.time() - start) * 1000)
    path = request.url.path
    if not path.startswith("/health") and not path.startswith("/metrics"):
        _metrics.incr("requests_total")
        _metrics.incr_labeled("requests_by_endpoint", path)
    response.headers["x-request-id"] = req_id
    log.info(
        "request",
        method=request.method,
        path=path,
        status=response.status_code,
        ms=duration_ms,
        rid=req_id,
    )
    return response


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "7860")))
