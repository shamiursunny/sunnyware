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
from .routes import eval as eval_routes
from .routes import mcp as mcp_routes
from .routes import auth as auth_routes
from .routes import schedule as schedule_routes
from .routes import tools as tools_routes
from .routes import sessions as sessions_routes
from .routes import memory_routes


@asynccontextmanager
async def lifespan(app):
    init_state()
    # Part 26: ensure scheduler running inside the live event loop
    try:
        from . import scheduler as _sched
        _ok = _sched.start()
        log.info("scheduler_lifespan_start", ok=_ok)
    except Exception as e:
        log.error("scheduler_lifespan_error", err=f"{type(e).__name__}: {e}")
    yield
    # Shutdown
    try:
        from . import scheduler as _sched
        _sched.stop()
    except Exception:
        pass
    state["ready"] = False
    log.info("sunnyware shutting down")


app = Server(
    title="sunnyware",
    version=meta.PROJECT_VERSION,
    description=(
        "Production-grade AI agent orchestrator -- 14 tools, cross-session memory, "
        "multi-step planning, MCP interop, SSE streaming, evaluation suite, "
        "auth + rate limiting, persistent metrics."
    ),
    contact={
        "name": meta.AUTHOR_NAME,
        "url": meta.AUTHOR_WEBSITE,
        "email": meta.AUTHOR_EMAIL,
    },
    license_info={"name": meta.LICENSE_ID, "url": "https://www.gnu.org/licenses/agpl-3.0.html"},
    openapi_tags=[
        {"name": "meta", "description": "Info, health, metrics, author"},
        {"name": "agent", "description": "Agent loop, streaming, planning"},
        {"name": "tools", "description": "Tool registry and direct invocation"},
        {"name": "sessions", "description": "Session history, export, rewind"},
        {"name": "memory", "description": "Cross-session memory inspection"},
        {"name": "eval", "description": "Ground-truth evaluation suite"},
        {"name": "mcp", "description": "Model Context Protocol (JSON-RPC 2.0)"},
        {"name": "auth", "description": "Authentication + rate-limit status"},
    ],
    lifespan=lifespan,
)


# Register all routers
app.include_router(meta_routes.router)
app.include_router(agent_routes.router)
app.include_router(tools_routes.router)
app.include_router(sessions_routes.router)
app.include_router(memory_routes.router)
app.include_router(eval_routes.router)
app.include_router(mcp_routes.router)
app.include_router(auth_routes.router)
app.include_router(schedule_routes.router)


# FALLBACK: init state at import time (HF Spaces skips lifespan)
init_state()


# ── Part 17/18: request ID + metrics middleware (ASGI, streaming-safe) ──
class _MetricsMiddleware:
    """Raw ASGI middleware — does NOT buffer streaming responses.

    Adds x-request-id header, structured logs, and metrics counters.
    Safe for SSE / StreamingResponse endpoints.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        import uuid as _uuid
        import time as _time
        import json as _json
        from . import metrics as _metrics

        path = scope.get("path", "")
        method = scope.get("method", "?")
        req_id = str(_uuid.uuid4())[:8]
        start = _time.time()
        status_holder = {"code": 0}

        # ── Part 21: API key auth (opt-in) + rate limit ──
        # ── Part 24: set tenant context from key (empty when auth off) ──
        try:
            from . import auth as _auth
            from . import tenant as _tenant
            _incoming_key = _auth.extract_key_from_headers(scope.get("headers") or []) or ""
            # Only use key as tenant if auth is enabled (else shared namespace)
            _tenant.set_key(_incoming_key if _auth.auth_enabled() else "")
            is_protected = path.startswith("/api/") and path != "/api/auth/status"
            if is_protected and _auth.auth_enabled():
                key = _incoming_key
                if not _auth.is_valid_key(key or ""):
                    body = _json.dumps({
                        "error": "unauthorized",
                        "detail": "valid X-API-Key or Authorization: Bearer <key> required",
                    }).encode()
                    await send({
                        "type": "http.response.start",
                        "status": 401,
                        "headers": [
                            (b"content-type", b"application/json"),
                            (b"x-request-id", req_id.encode("ascii")),
                        ],
                    })
                    await send({"type": "http.response.body", "body": body})
                    _metrics.incr("errors_total")
                    log.info("auth_rejected", path=path, rid=req_id, reason="invalid_key")
                    return
                # Rate limit
                rl = _auth.check_rate_limit(key or "")
                if not rl.get("ok"):
                    body = _json.dumps({
                        "error": "rate_limited",
                        "limit": rl.get("limit"),
                        "retry_after": rl.get("retry_after"),
                    }).encode()
                    await send({
                        "type": "http.response.start",
                        "status": 429,
                        "headers": [
                            (b"content-type", b"application/json"),
                            (b"retry-after", str(rl.get("retry_after", 60)).encode("ascii")),
                            (b"x-request-id", req_id.encode("ascii")),
                        ],
                    })
                    await send({"type": "http.response.body", "body": body})
                    _metrics.incr("errors_total")
                    log.info("rate_limited", path=path, rid=req_id)
                    return
        except Exception as _e:
            # Never break the app if auth code fails
            try:
                log.error("auth_middleware_error", err=f"{type(_e).__name__}: {_e}")
            except Exception:
                pass

        for k, v in scope.get("headers", []):
            if k.lower() == b"x-request-id":
                try:
                    req_id = v.decode("ascii")[:32]
                except Exception:
                    pass
                break

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_holder["code"] = message.get("status", 0)
                headers = list(message.get("headers", []))
                if not any(k.lower() == b"x-request-id" for k, _ in headers):
                    headers.append((b"x-request-id", req_id.encode("ascii")))
                message["headers"] = headers
            await send(message)

        # Part 22: load persisted counters on first request per process
        try:
            await _metrics.ensure_loaded()
        except Exception:
            pass

        # Part 26: lazy-start scheduler on first request (idempotent)
        try:
            from . import scheduler as _sched
            _sched.start()
        except Exception:
            pass

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            _metrics.incr("errors_total")
            log.error("request_failed", rid=req_id, path=path)
            raise
        finally:
            duration_ms = int((_time.time() - start) * 1000)
            if not path.startswith("/health") and not path.startswith("/metrics"):
                _metrics.incr("requests_total")
                _metrics.incr_labeled("requests_by_endpoint", path)
            try:
                log.info(
                    "request",
                    method=method,
                    path=path,
                    status=status_holder["code"],
                    ms=duration_ms,
                    rid=req_id,
                )
            except Exception:
                pass
            # Part 22: flush dirty counters to DB (throttled to once per ~10s)
            try:
                await _metrics.flush_if_due()
            except Exception:
                pass


app.add_middleware(_MetricsMiddleware)





# ── Part 27: CORS (opt-in via SUNNYWARE_CORS_ORIGINS) ──
try:
    import os as _os
    _origins_raw = (_os.getenv("SUNNYWARE_CORS_ORIGINS") or "").strip()
    if _origins_raw:
        from fastapi.middleware.cors import CORSMiddleware
        _origins = [o.strip() for o in _origins_raw.split(",") if o.strip()]
        app.add_middleware(
            CORSMiddleware,
            allow_origins=_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
            allow_headers=["*"],
        )
        log.info("cors_enabled", origins=_origins)
except Exception as _e:
    try:
        log.error("cors_setup_failed", err=f"{type(_e).__name__}: {_e}")
    except Exception:
        pass

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "7860")))
