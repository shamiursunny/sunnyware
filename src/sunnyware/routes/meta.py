# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Root, about, and health endpoints."""

from fastapi import APIRouter, Request


def _forbidden(role: str, required: str):
    """Part 135: 403 response with role context."""
    return JSONResponse(
        {
            "error": "forbidden",
            "detail": f"requires '{required}' role (you have '{role}')",
            "required_role": required,
            "current_role": role,
        },
        status_code=403,
    )


def _check_admin():
    """Part 135: None if OK, else a 403 JSONResponse.

    Permissive when auth is OFF (preserves pre-135 behavior).
    When auth is ON, requires current role >= admin.
    """
    try:
        from .. import auth as _auth
        from .. import tenant as _tenant
    except Exception:
        return None
    try:
        if not _auth.auth_enabled():
            return None
        cur = _tenant.get_role() or _auth.default_role()
        if not _auth.has_role(cur, "admin"):
            return _forbidden(cur, "admin")
    except Exception:
        return None
    return None
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse

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


@router.get("/api/cache/stats")
async def cache_stats_endpoint():
    """Part 113C: in-memory cache diagnostics + eulerpool hit rates."""
    try:
        from ..tools import _financial_http as _fh
        from .. import metrics as _m
        base = _fh.cache_stats()
        snap = _m.snapshot()
        hits = {k[len("eulerpool_cache_hit_"):]: v
                for k, v in snap.items()
                if k.startswith("eulerpool_cache_hit_")}
        misses = {k[len("eulerpool_cache_miss_"):]: v
                  for k, v in snap.items()
                  if k.startswith("eulerpool_cache_miss_")}
        actions = sorted(set(hits) | set(misses))
        per_action = []
        for a in actions:
            h = int(hits.get(a, 0) or 0)
            ms = int(misses.get(a, 0) or 0)
            total = h + ms
            per_action.append({
                "action": a,
                "hits": h,
                "misses": ms,
                "hit_rate": round(h / total, 3) if total else None,
            })
        return {
            "cache": base,
            "per_action": per_action,
            "eulerpool_api_calls_total": int(snap.get("eulerpool_api_calls_total", 0) or 0),
        }
    except Exception as e:
        return JSONResponse(
            {"error": f"{type(e).__name__}: {e}"},
            status_code=500,
        )


@router.post("/api/cache/clear")
async def cache_clear_endpoint():
    """Part 113C: wipe the in-memory cache. Admin-only escape hatch."""
    try:
        from ..tools import _financial_http as _fh
        n = _fh.cache_clear()
        return {"cleared_keys": n}
    except Exception as e:
        return JSONResponse(
            {"error": f"{type(e).__name__}: {e}"},
            status_code=500,
        )

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

# ═══ Part 106: serve stored image attachments ═══

@router.get("/api/attachments/{att_id}.{ext}")
async def serve_attachment(att_id: str, ext: str):
    """Serve a previously-saved attachment from the /data bucket."""
    try:
        from .. import attachments as _att
        p = _att.resolve_path(att_id, ext)
        if p is None:
            return JSONResponse({"error": "not found"}, status_code=404)
        # Long cache so the browser doesn't refetch on every scroll
        return FileResponse(
            str(p),
            media_type=f"image/{'jpeg' if ext.lower() in ('jpg','jpeg') else ext.lower()}",
            headers={"Cache-Control": "public, max-age=31536000, immutable"},
        )
    except Exception as e:
        return JSONResponse(
            {"error": f"{type(e).__name__}: {e}"},
            status_code=500,
        )


@router.get("/api/attachments/stats")
async def attachments_stats():
    """Diagnostics for the attachments store."""
    try:
        from .. import attachments as _att
        return _att.stats()
    except Exception as e:
        return JSONResponse(
            {"error": f"{type(e).__name__}: {e}"},
            status_code=500,
        )


@router.get("/api/agents/metrics")
async def agents_metrics():
    """Part 119: per-role agent run/success/failure/latency metrics."""
    try:
        from .. import metrics as _m
        from .. import roles as _roles
        snap = _m.snapshot()

        def _bucket(name):
            v = snap.get(name)
            return v if isinstance(v, dict) else {}

        runs = _bucket("agent_runs_total")
        succ = _bucket("agent_success_total")
        fail = _bucket("agent_failure_total")
        lat_sum = _bucket("agent_latency_ms_total")
        lat_cnt = _bucket("agent_latency_ms_count")
        iters = _bucket("agent_iterations_total")

        keys = sorted(set(runs) | set(succ) | set(fail))
        rows = []
        for role in keys:
            r = int(runs.get(role, 0) or 0)
            s = int(succ.get(role, 0) or 0)
            f = int(fail.get(role, 0) or 0)
            total = s + f
            rate = round(s / total, 4) if total else None
            ls = int(lat_sum.get(role, 0) or 0)
            lc = int(lat_cnt.get(role, 0) or 0)
            avg_ms = int(ls / lc) if lc else None
            it = int(iters.get(role, 0) or 0)
            rows.append({
                "role": role,
                "label": (_roles.ROLES.get(role, {}) or {}).get("label", role),
                "runs": r,
                "success": s,
                "failure": f,
                "success_rate": rate,
                "avg_latency_ms": avg_ms,
                "iterations_total": it,
                "avg_iterations": round(it / r, 2) if r else None,
            })

        return {
            "roles": rows,
            "totals": {
                "runs": sum(int(runs.get(k, 0) or 0) for k in keys),
                "success": sum(int(succ.get(k, 0) or 0) for k in keys),
                "failure": sum(int(fail.get(k, 0) or 0) for k in keys),
            },
            "known_roles": _roles.role_names(),
        }
    except Exception as e:
        return JSONResponse(
            {"error": f"{type(e).__name__}: {e}"},
            status_code=500,
        )


@router.get("/api/traces")
async def traces_list(limit: int = 20, role: str = None):
    """Part 132: recent execution traces (newest first)."""
    try:
        from .. import tracing as _tr
        items = _tr.get_recent_traces(limit=limit, role=role)
        return {
            "count": len(items),
            "limit": limit,
            "role_filter": role,
            "traces": items,
        }
    except Exception as e:
        return JSONResponse(
            {"error": f"{type(e).__name__}: {e}"},
            status_code=500,
        )


@router.get("/api/traces/stats")
async def traces_stats():
    """Part 132: trace buffer diagnostics."""
    try:
        from .. import tracing as _tr
        return _tr.stats()
    except Exception as e:
        return JSONResponse(
            {"error": f"{type(e).__name__}: {e}"},
            status_code=500,
        )


@router.get("/api/traces/{trace_id}")
async def traces_detail(trace_id: str):
    """Part 132: full trace with all spans by id."""
    try:
        from .. import tracing as _tr
        t = _tr.get_trace(trace_id)
        if not t:
            return JSONResponse(
                {"error": "trace not found", "trace_id": trace_id},
                status_code=404,
            )
        return t
    except Exception as e:
        return JSONResponse(
            {"error": f"{type(e).__name__}: {e}"},
            status_code=500,
        )


@router.post("/api/traces/clear")
async def traces_clear():
    """Part 132: wipe in-memory trace buffer (admin)."""
    try:
        from .. import tracing as _tr
        n = _tr.clear_traces()
        return {"cleared_traces": n}
    except Exception as e:
        return JSONResponse(
            {"error": f"{type(e).__name__}: {e}"},
            status_code=500,
        )


@router.get("/api/prompts")
async def prompts_list():
    """Part 133: current effective prompt addons for every role."""
    try:
        from .. import roles as _roles
        return {
            "source": _roles._external_status(),
            "roles": {
                k: {
                    "label": _roles.ROLES[k].get("label", k),
                    "addon_length": len(
                        _roles.ROLES[k].get("prompt_addon") or ""
                    ),
                    "prompt_addon": _roles.ROLES[k].get("prompt_addon") or "",
                }
                for k in _roles.role_names()
            },
        }
    except Exception as e:
        return JSONResponse(
            {"error": f"{type(e).__name__}: {e}"},
            status_code=500,
        )


@router.get("/api/prompts/status")
async def prompts_status():
    """Part 133: external-prompt diagnostics (path, version, source)."""
    try:
        from .. import roles as _roles
        return _roles._external_status()
    except Exception as e:
        return JSONResponse(
            {"error": f"{type(e).__name__}: {e}"},
            status_code=500,
        )


@router.post("/api/prompts/reload")
async def prompts_reload():
    """Part 133: re-read static/prompts.json without a restart."""
    try:
        from .. import roles as _roles
        loaded, err = _roles._load_external_prompts()
        return {
            "loaded_roles": loaded,
            "error": err,
            "status": _roles._external_status(),
        }
    except Exception as e:
        return JSONResponse(
            {"error": f"{type(e).__name__}: {e}"},
            status_code=500,
        )


@router.get("/api/rate_limit/status")
async def rate_limit_status(tenant: str = None):
    """Part 134: rate-limit status for the calling tenant.

    Optional ?tenant=<key> to inspect another tenant (admin read).
    """
    try:
        from .. import auth as _auth
        from .. import tenant as _tenant
        if tenant:
            tk = tenant
        else:
            # Part 134c: prefer the rate-limit key set by middleware,
            # fall back to tenant key (API key), then anonymous.
            try:
                tk = _tenant.get_rate_limit_key()
            except Exception:
                tk = ""
            if not tk:
                tk = _tenant.get_key()
            if not tk:
                tk = "anonymous"
        return _auth.tenant_status(tk)
    except Exception as e:
        return JSONResponse(
            {"error": f"{type(e).__name__}: {e}"},
            status_code=500,
        )


@router.get("/api/rate_limit/tenants")
async def rate_limit_tenants():
    """Part 134: snapshot of all active tenants (admin read).

    Part 135: admin-only when auth is enabled.
    """
    _deny = _check_admin()
    if _deny is not None:
        return _deny
    try:
        from .. import auth as _auth
        return {
            "enabled": _auth.rate_limit_enabled(),
            "limit_per_minute": _auth.rate_limit_per_minute(),
            "window_seconds": int(_auth._WINDOW_SEC),
            "tenants": _auth.per_tenant_snapshot(),
        }
    except Exception as e:
        return JSONResponse(
            {"error": f"{type(e).__name__}: {e}"},
            status_code=500,
        )


@router.post("/api/rate_limit/reset")
async def rate_limit_reset(req: Request):
    """Part 134: reset buckets. Body {} = all; {"tenant": "..."} = one.

    Part 135: admin-only when auth is enabled.
    """
    _deny = _check_admin()
    if _deny is not None:
        return _deny
    try:
        from .. import auth as _auth
        try:
            body = await req.json()
        except Exception:
            body = {}
        tk = (body or {}).get("tenant")
        if tk:
            ok = _auth.reset_tenant(str(tk))
            return {"reset": True, "tenant": str(tk), "existed": ok}
        _auth.reset_rate_limits()
        return {"reset": True, "scope": "all"}
    except Exception as e:
        return JSONResponse(
            {"error": f"{type(e).__name__}: {e}"},
            status_code=500,
        )


@router.post("/api/rate_limit/evict")
async def rate_limit_evict():
    """Part 134: force-prune stale buckets, return count pruned.

    Part 135: admin-only when auth is enabled.
    """
    _deny = _check_admin()
    if _deny is not None:
        return _deny
    try:
        from .. import auth as _auth
        n = _auth.evict_stale()
        return {"evicted": n, "remaining": len(_auth._buckets)}
    except Exception as e:
        return JSONResponse(
            {"error": f"{type(e).__name__}: {e}"},
            status_code=500,
        )


@router.get("/api/auth/whoami")
async def auth_whoami(req: Request):
    """Part 135: identify the current caller's key, role, and level."""
    try:
        from .. import auth as _auth
        from .. import tenant as _tenant
        raw = req.headers.get("x-api-key") or ""
        if not raw:
            authz = req.headers.get("authorization") or ""
            if authz.lower().startswith("bearer "):
                raw = authz[7:].strip()
        role = _tenant.get_role() or _auth.role_for_key(raw)
        return {
            "auth_enabled": _auth.auth_enabled(),
            "key_masked": _auth.mask_key(raw) if raw else "",
            "valid_key": _auth.is_valid_key(raw) if raw else False,
            "role": role,
            "role_level": _auth.role_level(role),
            "available_roles": list(_auth._ROLE_HIERARCHY.keys()),
            "default_role": _auth.default_role(),
        }
    except Exception as e:
        return JSONResponse(
            {"error": f"{type(e).__name__}: {e}"},
            status_code=500,
        )
