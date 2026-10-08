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
app.include_router(eval_routes.router)
app.include_router(mcp_routes.router)
app.include_router(auth_routes.router)


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
        try:
            from . import auth as _auth
            is_protected = path.startswith("/api/") and path != "/api/auth/status"
            if is_protected and _auth.auth_enabled():
                key = _auth.extract_key_from_headers(scope.get("headers") or [])
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


app.add_middleware(_MetricsMiddleware)




if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "7860")))
