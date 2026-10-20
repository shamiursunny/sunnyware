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
from .routes import hitl as hitl_routes
from .routes import meta as meta_routes
from .routes import paddle_webhook as paddle_webhook_routes
from .routes import accounting as accounting_routes
from .routes import billing as billing_routes
from .routes import saas as saas_routes
from .routes import approvals as approvals_routes
from .routes import sso as sso_routes
from .routes import authkit as authkit_routes
from .routes import workos_admin as workos_admin_routes
from .routes import team as team_routes
from .routes import email as email_routes
from .routes import api_keys as api_keys_routes
from .routes import webhooks as webhooks_routes
from .routes import chat_audit as chat_audit_routes
from .routes import scheduled_tasks as scheduled_tasks_routes
from .routes import rag_admin as rag_admin_routes
from .routes import twofa as twofa_routes
from .routes import backup as backup_routes
from .routes import analytics as analytics_routes
from .routes import llm_dashboard as llm_dashboard_routes
from .routes import agent as agent_routes
from .routes import eval as eval_routes
from .routes import mcp as mcp_routes
from .routes import auth as auth_routes
from .routes import schedule as schedule_routes
from .routes import tools as tools_routes
from .routes import sessions as sessions_routes
from .routes import memory_routes
from .routes import rag as rag_routes


async def _preload_local_task():
    """Load the local GGUF model in the background without blocking startup."""
    try:
        from . import local_llm as _local_llm
        result = await _local_llm.preload()
        log.info("local_llm_preload_done", result=result)
    except Exception as e:
        log.error("local_llm_preload_error", err=f"{type(e).__name__}: {e}")


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
    # Part 81: bootstrap dynamic schedules from Neon
    try:
        from . import dynamic_schedule as _dsched
        import asyncio as _aio
        _boot = await _aio.wait_for(_dsched.bootstrap(), timeout=10)
        log.info("dynamic_schedule_bootstrap", result=_boot)
    except Exception as e:
        log.error("dynamic_schedule_bootstrap_error", err=f"{type(e).__name__}: {e}")
    # Part 32: kick off local_llm preload in background (fire-and-forget)
    try:
        from . import local_llm as _local_llm
        if _local_llm.is_enabled():
            import asyncio as _aio
            _aio.create_task(_preload_local_task())
            log.info("local_llm_preload_task_started")
        else:
            log.info("local_llm_disabled")
    except Exception as _e:
        log.error("local_llm_lifespan_error", err=f"{type(_e).__name__}: {_e}")
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
        {"name": "rag", "description": "Local RAG — upload, query, status"},
    ],
    lifespan=lifespan,
)


# Register all routers
app.include_router(meta_routes.router)
app.include_router(paddle_webhook_routes.router)
app.include_router(accounting_routes.router)
app.include_router(billing_routes.router)
app.include_router(saas_routes.router)
app.include_router(approvals_routes.router)
app.include_router(hitl_routes.router)
app.include_router(sso_routes.router)
app.include_router(authkit_routes.router)
app.include_router(workos_admin_routes.router)
app.include_router(team_routes.router)
app.include_router(email_routes.router)
app.include_router(api_keys_routes.router)
app.include_router(webhooks_routes.router)
app.include_router(chat_audit_routes.router)
app.include_router(scheduled_tasks_routes.router)
app.include_router(rag_admin_routes.router)
app.include_router(twofa_routes.router)
app.include_router(backup_routes.router)
app.include_router(analytics_routes.router)
app.include_router(llm_dashboard_routes.router)
app.include_router(agent_routes.router)
app.include_router(tools_routes.router)
app.include_router(sessions_routes.router)
app.include_router(memory_routes.router)
app.include_router(eval_routes.router)
app.include_router(mcp_routes.router)
app.include_router(auth_routes.router)
app.include_router(schedule_routes.router)
app.include_router(rag_routes.router)

# Part 89: serve local static assets (marked.js etc.) - no CDN dependency
from fastapi.staticfiles import StaticFiles as _StaticFiles
_STATIC_DIR = Path(__file__).parent / "static"
if _STATIC_DIR.is_dir():
    app.mount("/static", _StaticFiles(directory=str(_STATIC_DIR)), name="static")




# ── Part 45: flatten _IncludedRouter proxies for OpenAPI schema ──
# FastAPI 0.142+ wraps include_router() calls in a lazy _IncludedRouter
# proxy that doesn't expose the attributes get_openapi() needs. We unwrap
# them into plain APIRoute objects first, then generate the schema.
def _flatten_openapi_routes(routes):
    """Unwrap FastAPI 0.142 _IncludedRouter proxies and drop routes that
    have no response_class (e.g. Gradio's /ui HTML page). FastAPI's OpenAPI
    generator asserts on response_class=None and aborts."""
    out = []
    for r in routes:
        orig = getattr(r, "original_router", None)
        if orig is not None and hasattr(orig, "routes"):
            out.extend(_flatten_openapi_routes(list(orig.routes)))
            continue
        # Skip anything without a response_class (not schema-able)
        rc = getattr(r, "response_class", "MISSING")
        if rc is None:
            continue
        out.append(r)
    return out


def _collect_refs(obj, out: set):
    """Walk an object and collect every $ref string."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "$ref" and isinstance(v, str):
                out.add(v)
            else:
                _collect_refs(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _collect_refs(v, out)
    return out


def _clean_openapi_schemas(schema: dict) -> dict:
    """Part 77: keep only schemas referenced by our own paths.

    Gradio leaks dozens of internal Pydantic models (PredictBody,
    CancelBody, ConnectBody, EstimationMessage, Body_undo_vibe_edit_*,
    Body_login_login_*, etc.) into components/schemas. Rather than
    blacklisting names, we resolve refs from paths and drop everything
    else — orphaned schemas are exactly the Gradio leftovers.
    """
    try:
        components = schema.get("components") or {}
        schemas = components.get("schemas") or {}
        if not schemas:
            return schema

        # Collect all $refs referenced by paths + responses + requests
        refs = set()
        _collect_refs(schema.get("paths") or {}, refs)
        # Some schemas reference other schemas; iterate to fixpoint
        prefix = "#/components/schemas/"
        keep = set()
        for r in refs:
            if r.startswith(prefix):
                keep.add(r[len(prefix):])
        # Transitive closure
        changed = True
        while changed:
            changed = False
            for name in list(keep):
                body = schemas.get(name)
                if body is None:
                    continue
                sub_refs = set()
                _collect_refs(body, sub_refs)
                for r in sub_refs:
                    if r.startswith(prefix):
                        cand = r[len(prefix):]
                        if cand not in keep:
                            keep.add(cand); changed = True

        dropped = [k for k in schemas if k not in keep]
        components["schemas"] = {k: v for k, v in schemas.items() if k in keep}
        schema["components"] = components
        if dropped:
            print("[openapi] dropped orphan schemas: " + str(len(dropped)))
        return schema
    except Exception:
        return schema


def _patched_openapi():
    # Part 77c: FastAPI caches `openapi_schema`. Something (Gradio init)
    # may have cached an uncleaned schema before we took over. So we
    # clean on EVERY return, and reset the cached attribute once at
    # first invocation.
    cached = getattr(app, "openapi_schema", None)
    if cached is not None:
        return _clean_openapi_schemas(cached)
    from fastapi.openapi.utils import get_openapi as _go
    flat = _flatten_openapi_routes(list(app.routes))
    _raw = _go(
        title=app.title,
        version=app.version,
        openapi_version=getattr(app, "openapi_version", "3.1.0"),
        description=getattr(app, "description", None),
        routes=flat,
        tags=getattr(app, "openapi_tags", None),
    )
    app.openapi_schema = _clean_openapi_schemas(_raw)
    return app.openapi_schema


try:
    app.openapi = _patched_openapi
    app.openapi_schema = None

    # Part 77d: The /openapi.json HTTP route was registered by FastAPI's
    # setup() BEFORE we replaced app.openapi. That route bound the
    # original method reference, so HTTP requests to /openapi.json
    # bypassed our patch. Remove the old route and re-register with a
    # handler that calls our cleaner.
    from fastapi.responses import JSONResponse as _JR
    _default_openapi_path = getattr(app, "openapi_url", "/openapi.json")
    app.router.routes = [
        r for r in app.router.routes
        if getattr(r, "path", None) != _default_openapi_path
    ]

    @app.get(_default_openapi_path, include_in_schema=False)
    async def _openapi_route_override():
        return _JR(_patched_openapi())

except Exception:
    pass


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
        # ── Part 28: IP allowlist check ──
        try:
            from . import firewall as _fw
            if _fw.enabled():
                _ip = _fw.extract_client_ip(scope)
                if not _fw.is_allowed(_ip):
                    body = _json.dumps({
                        "error": "forbidden",
                        "detail": "client IP not in allowlist",
                    }).encode()
                    await send({
                        "type": "http.response.start",
                        "status": 403,
                        "headers": [
                            (b"content-type", b"application/json"),
                            (b"x-request-id", req_id.encode("ascii")),
                        ],
                    })
                    await send({"type": "http.response.body", "body": body})
                    _metrics.incr("errors_total")
                    log.info("firewall_rejected", path=path, rid=req_id, ip=_ip)
                    return
        except Exception as _e:
            try:
                log.error("firewall_error", err=f"{type(_e).__name__}: {_e}")
            except Exception:
                pass

        try:
            from . import auth as _auth
            from . import tenant as _tenant
            _incoming_key = _auth.extract_key_from_headers(scope.get("headers") or []) or ""
            # Only use key as tenant if auth is enabled (else shared namespace)
            _tenant.set_key(_incoming_key if _auth.auth_enabled() else "")
            # Part 135: set the request role from the key's mapping (or default)
            try:
                _role = _auth.role_for_key(_incoming_key) if _auth.auth_enabled() else _auth.default_role()
                _tenant.set_role(_role)
            except Exception:
                pass
            # Part 183: exempt public endpoints from auth
            _public_api = ("/api/auth/status", "/api/auth/login", "/api/stripe/webhook", "/api/paddle/webhook")
            # Attachments are served publicly for <img> tags (random IDs, unguessable)
            is_attachment = path.startswith("/api/attachments/")
            is_protected = path.startswith("/api/") and not is_attachment and path not in _public_api
            
            # Part 134c: auth gate (only when SUNNYWARE_API_KEYS is set).
            if is_protected and _auth.auth_enabled():
                key = _incoming_key
                # Part 196: Check if it's a valid JWT
                if key and "." in key and len(key) > 20:
                    try:
                        from sunnyware.routes.auth import verify_jwt
                        email = verify_jwt(key)
                        if email:
                            key = f"user:{email}" # Multi-tenant isolation!
                    except Exception:
                        pass

                if not _auth.is_valid_key(key or "") and not (key and key.startswith("user:")):
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
            
            # Part 134c: rate-limit gate — runs INDEPENDENTLY of auth.
            # Part 134: richer tenant discriminator so anonymous traffic
            # is isolated per-session / per-IP instead of sharing one
            # empty-string bucket when auth is off.
            if is_protected and _auth.rate_limit_enabled():
                _eff_key = _incoming_key or ""
                if not _eff_key:
                    try:
                        for _k, _v in scope.get("headers", []):
                            if _k.lower() == b"x-session-id":
                                _eff_key = "sess:" + _v.decode(
                                    "ascii", errors="replace"
                                )[:64]
                                break
                    except Exception:
                        pass
                if not _eff_key:
                    try:
                        for _k, _v in scope.get("headers", []):
                            if _k.lower() == b"x-forwarded-for":
                                _ip = _v.decode("ascii", errors="replace").split(",")[0].strip()
                                if _ip:
                                    _eff_key = "ip:" + _ip[:64]
                                break
                    except Exception:
                        pass
                if not _eff_key:
                    try:
                        _cli = scope.get("client") or ()
                        if _cli and _cli[0]:
                            _eff_key = "ip:" + str(_cli[0])[:64]
                    except Exception:
                        pass
                if not _eff_key:
                    _eff_key = "anonymous"
                
                # Part 134c: propagate rate-limit key into dedicated contextvar
                # so route handlers read the SAME key the middleware billed.
                try:
                    _tenant.set_rate_limit_key(_eff_key)
                except Exception:
                    pass
                
                # Part 134d: admin/status endpoints don't consume budget
                if not _auth.is_bypass_path(path):
                    # Part 134: periodic eviction so buckets don't leak
                    try:
                        _auth.evict_stale()
                    except Exception:
                        pass
                
                    rl = _auth.check_rate_limit(_eff_key)
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
                # Part 28: security headers
                try:
                    from . import firewall as _fw
                    if _fw.security_headers_enabled():
                        _existing = {k.lower() for k, _ in headers}
                        _scheme = scope.get("scheme", "https")
                        for hk, hv in _fw.build_security_headers(_scheme):
                            if hk not in _existing:
                                headers.append((hk, hv))
                except Exception:
                    pass
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

# ─── Part 162: recon-path guard middleware ───
try:
    from . import recon_guard as _rg
    try:
        from fastapi.responses import JSONResponse as _JResp
    except Exception:
        _JResp = None

    @app.middleware("http")
    async def _recon_guard_middleware(request, call_next):
        try:
            d = _rg.check(request.url.path)
            if d.get("block"):
                ip = ""
                try:
                    ip = (request.client.host if request.client else "") or ""
                except Exception:
                    pass
                _rg.record(request.url.path, ip, d.get("pattern", ""))
                if _JResp is not None:
                    return _JResp(
                        {"error": "forbidden",
                         "detail": "request blocked by recon guard"},
                        status_code=403,
                    )
        except Exception:
            pass
        return await call_next(request)
except Exception as _e:
    print(f"[recon_guard] middleware not installed: {_e}")

# ─── Part 174: hardware metrics sampler ───
try:
    import asyncio as _asyncio
    _metrics_sampler_started = False

    async def _system_metrics_sampler():
        from . import system_metrics as _sm
        import os as _os
        interval = int(_os.getenv("SUNNYWARE_METRICS_INTERVAL_S", "5"))
        _sm.sample_once()
        while True:
            await _asyncio.sleep(interval)
            try:
                _sm.sample_once()
            except Exception:
                pass

    def _start_metrics_sampler():
        global _metrics_sampler_started
        if _metrics_sampler_started:
            return
        _metrics_sampler_started = True
        try:
            loop = _asyncio.get_event_loop()
            loop.create_task(_system_metrics_sampler())
        except Exception:
            pass
except Exception:
    pass


# ═══════════════════════════════════════════════════════════
# Part 212: analytics context middleware (user tracking)
# ═══════════════════════════════════════════════════════════
@app.middleware("http")
async def _analytics_context_middleware(request, call_next):
    try:
        from . import analytics_store as _as
        _key = request.headers.get("x-api-key") or ""
        _authz = request.headers.get("authorization", "")
        if _authz.lower().startswith("bearer "):
            _key = _authz[7:].strip()
        _user = ""
        _org = ""
        if _key and _key != "master-admin-key":
            # Part 214: custom JWT format: base64(payload).hmac
            try:
                if "." in _key and len(_key) > 20:
                    import base64 as _b64
                    import json as _json
                    b64 = _key.split(".")[0]
                    padded = b64 + "=" * (-len(b64) % 4)
                    payload_bytes = _b64.urlsafe_b64decode(padded)
                    payload = _json.loads(payload_bytes)
                    _user = payload.get("sub") or payload.get("email") or ""
            except Exception:
                pass
            # Fallback: if key is an email format
            if not _user and "@" in _key and "." in _key:
                _user = _key
            if _user:
                try:
                    from . import saas_store as _s
                    _o = _s.get_org_by_email(_user)
                    if _o:
                        _org = _o.get("id", "")
                except Exception:
                    pass
        _as.set_current(_user, _org)
        # Part 220: also set telemetry contextvars in middleware (guaranteed to run)
        _ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else "")
        _ua = request.headers.get("user-agent", "")
        _dev = request.headers.get("x-device-id", "")
        _loc = request.headers.get("x-location", "")
        _as.set_telemetry(ip=_ip, ua=_ua, device=_dev, location=_loc)
        # Part 214c: also store on request.state so it survives across async tasks
        try:
            request.state.analytics_user = _user
            request.state.analytics_org = _org
        except Exception:
            pass
    except Exception:
        pass
    return await call_next(request)

# ═══════════════════════════════════════════════════════════
# Part 212: install analytics hooks (monkey-patch LLM + tools)
# ═══════════════════════════════════════════════════════════
try:
    from . import analytics_hooks as _ah
    _ah_result = _ah.install()
    print(f"[startup] analytics_hooks: {_ah_result}")
except Exception as _ah_e:
    print(f"[startup] analytics_hooks failed: {_ah_e}")


# ═══════════════════════════════════════════════════════════
# Part 222b: Backend enforcement of 2FA on admin routes
# ═══════════════════════════════════════════════════════════
_2FA_WHITELIST = (
    "/api/2fa/",
    "/api/auth/login",
    "/api/auth/logout",
    "/api/saas/me",
    "/api/saas/plans",
    "/api/saas/upgrade",
    "/api/saas/checkout",
    "/api/saas/portal",
    "/api/saas/cancel",
    "/api/chat-audit/log",
    "/ui",
    "/admin",
    "/static/",
    "/api/health",
    "/api/metrics",
)


@app.middleware("http")
async def _twofa_gate_middleware(request, call_next):
    try:
        path = request.url.path
        for prefix in _2FA_WHITELIST:
            if path == prefix or path.startswith(prefix):
                return await call_next(request)
        
        key = request.headers.get("x-api-key") or ""
        if not key:
            authz = request.headers.get("authorization", "")
            if authz.lower().startswith("bearer "):
                key = authz[7:].strip()
        if not key:
            return await call_next(request)
        
        from . import twofa_store as _tfs
        user = ""
        if key == "master-admin-key":
            user = "admin"
        else:
            try:
                import base64 as _b64
                import json as _json
                if "." in key and len(key) > 20:
                    b64 = key.split(".")[0]
                    padded = b64 + "=" * (-len(b64) % 4)
                    payload = _json.loads(_b64.urlsafe_b64decode(padded))
                    user = (payload.get("sub") or payload.get("email") or "").lower()
            except Exception:
                pass
        
        if user and _tfs.is_enabled(user):
            sess = request.headers.get("x-2fa-session", "")
            if not _tfs.verify_session(user, sess):
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    {"error": "2fa_required", "user": user, "detail": "2FA verification required"},
                    status_code=428,
                )
    except Exception:
        pass
    return await call_next(request)

