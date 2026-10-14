# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Root, about, and health endpoints."""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse

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


@router.get("/about", response_class=HTMLResponse)
async def about():
    """Part 92: professional HTML about page (was raw JSON)."""
    from pathlib import Path as _Path
    _html_path = _Path(__file__).resolve().parent.parent / "static" / "about.html"
    try:
        html = _html_path.read_text(encoding="utf-8")
    except Exception:
        return HTMLResponse(
            content="<h1>Sunnyware</h1><p>About page unavailable.</p>",
            status_code=200,
        )
    replacements = {
        "%%VERSION%%": meta.PROJECT_VERSION,
        "%%AUTHOR%%": meta.AUTHOR_NAME,
        "%%EMAIL%%": meta.AUTHOR_EMAIL,
        "%%PHONE%%": meta.AUTHOR_PHONE,
        "%%WEBSITE%%": meta.AUTHOR_WEBSITE,
        "%%GITHUB%%": meta.AUTHOR_GITHUB,
        "%%COPYRIGHT%%": meta.COPYRIGHT,
        "%%LICENSE%%": meta.LICENSE_ID,
    }
    for k, v in replacements.items():
        html = html.replace(k, str(v))
    return HTMLResponse(content=html)


@router.get("/health/live")
async def liveness():
    return {"status": "ok"}


@router.get("/api/providers/status")
async def providers_status():
    """Part 32: current multi-provider router state."""
    try:
        from .. import providers as _prov
        from .. import config as _cfg_mod
        cfg = state.get("config") or _cfg_mod.load_config()
        statuses = _prov.provider_statuses()
        return {
            "mode": "multi" if getattr(cfg, "llm_multi_provider", False) else "single",
            "configured": cfg.llm_providers if getattr(cfg, "llm_multi_provider", False) else "legacy",
            "providers": statuses,
        }
    except Exception as e:
        return JSONResponse({"error": f"{type(e).__name__}: {e}"}, status_code=500)


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

    # Part 32: provider router summary
    try:
        from .. import providers as _prov
        _statuses = _prov.provider_statuses()
        if len(_statuses) > 1:
            _live = sum(1 for s in _statuses if not s.get("cooling"))
            checks["providers"] = f"{_live}/{len(_statuses)} live"
        else:
            checks["providers"] = "single"
    except Exception:
        checks["providers"] = "unknown"

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

    # Part 31D: data workbench availability (non-blocking — never degrades)
    try:
        import importlib as _imp
        _required = ["numpy", "pandas"]
        _optional = ["matplotlib", "seaborn", "plotly", "scipy",
                     "sklearn", "statsmodels", "duckdb", "pyarrow",
                     "openpyxl", "xlsxwriter", "tabulate"]
        _missing_core = []
        for m in _required:
            try:
                _imp.import_module(m)
            except Exception:
                _missing_core.append(m)
        _missing_opt = []
        for m in _optional:
            try:
                _imp.import_module(m)
            except Exception:
                _missing_opt.append(m)
        if _missing_core:
            checks["python_eval"] = "unavailable: missing " + ",".join(_missing_core)
        elif _missing_opt:
            checks["python_eval"] = "partial: missing " + ",".join(_missing_opt)
        else:
            checks["python_eval"] = "ok"
    except Exception as e:
        checks["python_eval"] = "error: " + type(e).__name__

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


# ── Part 32 Phase 2: local model smoke test ────────────────────
@router.post("/api/local-model/smoke")
async def local_model_smoke():
    """Run a small battery of tests against the local model.

    WARNING: The local model runs in-process on 2 vCPU. During this
    test, the entire Space freezes (GIL held by llama.cpp). The HTTP
    response will only arrive after ALL tests complete (~5-10 min).
    """
    import time as _t
    from .. import local_llm as _lm

    results = []
    t_start = _t.time()

    def _add(name, ok, **extra):
        results.append({"test": name, "ok": ok, **extra})

    # Test 0 — status snapshot
    try:
        _add("status_before", True, status=_lm.status())
    except Exception as e:
        _add("status_before", False, error=str(e))

    # Test 1 — simple greeting
    try:
        t0 = _t.time()
        r = await _lm.chat(prompt="Say hi in one word.", timeout=180.0)
        _add("simple_greeting",
             ok=bool(r.get("ok")),
             answer=(r.get("content") or "")[:100],
             latency_ms=int((_t.time() - t0) * 1000),
             error=r.get("error", ""))
    except Exception as e:
        _add("simple_greeting", False, error=str(e))

    # Test 2 — simple math
    try:
        t0 = _t.time()
        r = await _lm.chat(prompt="What is 7 times 8? Answer with just the number.", timeout=180.0)
        _add("simple_math",
             ok=bool(r.get("ok")),
             answer=(r.get("content") or "")[:100],
             latency_ms=int((_t.time() - t0) * 1000),
             error=r.get("error", ""))
    except Exception as e:
        _add("simple_math", False, error=str(e))

    # Test 3 — memory (2-turn)
    try:
        t0 = _t.time()
        r = await _lm.chat(
            prompt="What is my name?",
            history=[
                {"role": "user", "content": "My name is Ziggy."},
                {"role": "assistant", "content": "Nice to meet you, Ziggy."},
            ],
            timeout=180.0,
        )
        _add("memory_2_turn",
             ok=bool(r.get("ok")),
             answer=(r.get("content") or "")[:100],
             latency_ms=int((_t.time() - t0) * 1000),
             error=r.get("error", ""))
    except Exception as e:
        _add("memory_2_turn", False, error=str(e))

    # Test 4 — tool calling
    try:
        t0 = _t.time()
        tools = [{
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get current weather for a city",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string", "description": "City name"},
                    },
                    "required": ["city"],
                },
            },
        }]
        r = await _lm.chat(
            prompt="What's the weather in Dhaka? Use the get_weather tool.",
            tools=tools,
            timeout=180.0,
        )
        has_call = bool(r.get("tool_calls"))
        _add("tool_calling",
             ok=bool(r.get("ok")),
             tool_calls=has_call,
             raw_tool_calls=str(r.get("tool_calls"))[:200] if has_call else "",
             answer=(r.get("content") or "")[:100],
             latency_ms=int((_t.time() - t0) * 1000),
             error=r.get("error", ""))
    except Exception as e:
        _add("tool_calling", False, error=str(e))

    # Test 5 — status snapshot after
    try:
        _add("status_after", True, status=_lm.status())
    except Exception as e:
        _add("status_after", False, error=str(e))

    total_ms = int((_t.time() - t_start) * 1000)
    passed = sum(1 for r in results if r.get("ok"))
    return {
        "total_tests": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "total_latency_ms": total_ms,
        "results": results,
    }


# ── Part 33: auto model resolver diagnostics ──────────────────
@router.get("/api/models/resolve")
async def models_resolve_status():
    """Return current auto-resolver cache state per provider."""
    try:
        from .. import model_resolver as _mr
        return {"resolvers": _mr.snapshot()}
    except Exception as e:
        return {"error": type(e).__name__ + ": " + str(e)}


@router.post("/api/models/resolve/refresh")
async def models_resolve_refresh():
    """Force invalidate the resolver cache so next call re-probes."""
    try:
        from .. import model_resolver as _mr
        _mr.invalidate()
        return {"ok": True, "cleared": True}
    except Exception as e:
        return {"ok": False, "error": type(e).__name__ + ": " + str(e)}


# ── Part 33: provider smoke test (hits each provider once) ────
@router.post("/api/providers/smoke")
async def providers_smoke():
    """Test each configured HTTP provider with a minimal prompt.

    Runs sequentially so we can isolate failures per provider.
    Returns per-provider {ok, model, latency_ms, error, sample}.
    """
    import time as _t
    from .. import providers as _prov
    from .. import llm as _llm
    from .. import model_resolver as _mr

    out = []
    provs = _prov.load_providers()
    for p in provs:
        if p.provider_type == "local":
            out.append({"provider": p.name, "skipped": "local type"})
            continue

        try:
            r = await _mr.resolve(p.name, p.base_url, p.api_key, p.model)
            resolved = r.get("model") or p.model
            source = r.get("source", "?")
            available = r.get("available", 0)
        except Exception as e:
            resolved = p.model
            source = "resolve_error:" + type(e).__name__
            available = 0

        t0 = _t.time()
        res = await _llm._chat_single(
            prompt="Reply with just the word: OK",
            base_url=p.base_url,
            api_key=p.api_key,
            model=resolved,
            system=None,
            history=None,
            tools=None,
            timeout=90.0,
        )
        latency = int((_t.time() - t0) * 1000)

        out.append({
            "provider": p.name,
            "ok": bool(res.get("ok")),
            "configured_model": p.model,
            "resolved_model": resolved,
            "resolution_source": source,
            "available_count": available,
            "latency_ms": latency,
            "sample": (res.get("content") or "")[:80],
            "error": (res.get("error") or "")[:250],
        })

    passed = sum(1 for r in out if r.get("ok"))
    return {
        "total": len(out),
        "passed": passed,
        "failed": len(out) - passed,
        "results": out,
    }

# ═══ Part 100b: provider limits inspection + admin ═══

@router.get("/api/providers/limits")
async def providers_limits():
    """Show learned provider prompt limits + storage diagnostics."""
    try:
        from .. import provider_limits as _pl
        from .. import providers as _prov
        diag = _pl.debug_info()
        # Also merge live provider values
        live = []
        for p in _prov.load_providers():
            live.append({
                "name": p.name,
                "max_prompt_tokens": p.max_prompt_tokens,
            })
        return {
            "storage": diag,
            "providers_live": live,
        }
    except Exception as e:
        return JSONResponse(
            {"error": f"{type(e).__name__}: {e}"},
            status_code=500,
        )


@router.post("/api/providers/limits/reset")
async def providers_limits_reset(payload: dict = None):
    """Reset learned limits. Body: {"name": "groq"} or {"all": true}."""
    try:
        from .. import provider_limits as _pl
        payload = payload or {}
        if payload.get("all"):
            ok = _pl.reset(None)
            return {"ok": ok, "reset": "all"}
        name = (payload.get("name") or "").strip()
        if not name:
            return JSONResponse(
                {"error": "provide 'name' or 'all': true"},
                status_code=400,
            )
        ok = _pl.reset(name)
        return {"ok": ok, "reset": name}
    except Exception as e:
        return JSONResponse(
            {"error": f"{type(e).__name__}: {e}"},
            status_code=500,
        )

# ═══ Part 103: provider health metrics dashboard ═══

@router.get("/api/providers/metrics")
async def providers_metrics():
    """Part 103: aggregate health dashboard for all providers.

    Combines three sources:
      - In-memory Provider fields (per-process session stats)
      - Persistent metric counters (lifetime, survives restart)
      - Learned limits + storage diagnostics from provider_limits
    """
    try:
        from .. import providers as _prov
        from .. import provider_limits as _pl
        from .. import metrics as _m
        import time as _t

        provs = _prov.load_providers()
        counters = _m.snapshot()
        learned = _pl.snapshot()
        try:
            limits_diag = _pl.debug_info()
        except Exception:
            limits_diag = {}

        def _sum_prefix(prefix):
            total = 0
            per = {}
            for k, v in counters.items():
                if k.startswith(prefix):
                    try:
                        iv = int(v)
                    except Exception:
                        continue
                    total += iv
                    label = k[len(prefix):].lstrip("_")
                    if label:
                        per[label] = iv
            return total, per

        attempts_total, attempts_by = _sum_prefix("llm_provider_attempt")
        empty_total, empty_by = _sum_prefix("llm_provider_empty_response")
        learned_total, learned_by = _sum_prefix("provider_limit_learned")
        retried_total, _ = _sum_prefix("llm_request_retried")

        rows = []
        sess_ok = 0
        sess_fail = 0
        cooling_n = 0
        for p in provs:
            cool = p.is_cooling()
            if cool:
                cooling_n += 1
            sess_ok += p.success_count
            sess_fail += p.fail_count
            total = p.success_count + p.fail_count
            rate = (p.success_count / total) if total else None
            rows.append({
                "name": p.name,
                "model": p.model,
                "type": p.provider_type,
                "cooling": cool,
                "cooldown_remaining_s": round(p.cooldown_remaining(), 1),
                "max_prompt_tokens": p.max_prompt_tokens,
                "learned_limit": learned.get(p.name),
                "session": {
                    "success_count": p.success_count,
                    "fail_count": p.fail_count,
                    "success_rate": round(rate, 4) if rate is not None else None,
                    "last_success_ts": p.last_success_ts,
                },
                "lifetime": {
                    "attempts": attempts_by.get(p.name, 0),
                    "empty_responses": empty_by.get(p.name, 0),
                    "limits_learned": learned_by.get(p.name, 0),
                },
                "last_error": p.last_error,
            })

        sess_total = sess_ok + sess_fail
        overall_rate = (sess_ok / sess_total) if sess_total else None

        return {
            "timestamp": _t.time(),
            "summary": {
                "total_providers": len(provs),
                "ready": len(provs) - cooling_n,
                "cooling": cooling_n,
                "session_success_total": sess_ok,
                "session_fail_total": sess_fail,
                "session_success_rate": (
                    round(overall_rate, 4) if overall_rate is not None else None
                ),
                "lifetime_attempts_total": attempts_total,
                "lifetime_empty_total": empty_total,
                "lifetime_learned_total": learned_total,
                "retries_total": retried_total,
            },
            "providers": rows,
            "storage": {
                "provider_limits": limits_diag,
            },
        }
    except Exception as e:
        return JSONResponse(
            {"error": f"{type(e).__name__}: {e}"},
            status_code=500,
        )

