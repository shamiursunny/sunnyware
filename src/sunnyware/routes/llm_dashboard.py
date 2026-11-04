# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 212: LLM dashboard routes."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from .. import llm_dashboard_store as _lds

router = APIRouter(tags=["llm_dashboard"])


def _admin_only(req: Request):
    from .. import auth as _auth
    key = req.headers.get("x-api-key") or ""
    if not key:
        authz = req.headers.get("authorization") or ""
        if authz.lower().startswith("bearer "):
            key = authz[7:].strip()
    if not _auth.auth_enabled():
        return None
    if not key or not _auth.is_valid_key(key):
        return JSONResponse({"error": "auth_required"}, status_code=401)
    if not _auth.has_role(_auth.role_for_key(key), "admin"):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return None


@router.get("/api/llm-dashboard/providers")
async def list_providers(req: Request):
    d = _admin_only(req)
    if d: return d
    try:
        from .. import providers as _provs
        statuses = _provs.provider_statuses() or []
    except Exception as e:
        return JSONResponse({"error": f"providers_unavailable: {e}"}, status_code=500)

    priority = _lds.get_priority_order()
    if priority:
        by_name = {s.get("name"): s for s in statuses}
        ordered = [by_name[n] for n in priority if n in by_name]
        for s in statuses:
            if s.get("name") not in priority:
                ordered.append(s)
        statuses = ordered

    result = []
    for p in statuses:
        name = p.get("name", "")
        cfg = _lds.get_provider_config(name)
        cooldown_remaining = p.get("cooldown_remaining") or 0
        result.append({
            "name": name,
            "model": cfg.get("model_override") or p.get("model", ""),
            "provider_type": p.get("provider_type", ""),
            "is_cooling": bool(p.get("is_cooling")),
            "cooldown_remaining": float(cooldown_remaining),
            "config": cfg,
        })
    return {"count": len(result), "providers": result}


@router.post("/api/llm-dashboard/configs/{provider}")
async def update_config(provider: str, req: Request):
    d = _admin_only(req)
    if d: return d
    try:
        body = await req.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    allowed = {"limit_per_min", "limit_per_hour", "limit_per_day", "enabled", "model_override"}
    patch = {k: v for k, v in body.items() if k in allowed}
    cfg = _lds.set_provider_config(provider, patch)
    # Part 609: Invalidate cached providers so the toggle takes effect immediately
    try:
        from .. import providers as _prov
        _prov._PROVIDERS = None
    except Exception:
        pass
    return {"ok": True, "config": cfg}


@router.get("/api/llm-dashboard/logs")
async def get_logs(req: Request, limit: int = 200, provider: str = "", errors_only: bool = False):
    d = _admin_only(req)
    if d: return d
    logs = _lds.list_llm_logs(limit=min(limit, 2000), provider=provider, errors_only=errors_only)
    return {"count": len(logs), "logs": logs}


@router.delete("/api/llm-dashboard/logs")
async def clear_logs(req: Request):
    d = _admin_only(req)
    if d: return d
    return {"ok": _lds.clear_llm_logs()}


@router.post("/api/llm-dashboard/priority")
async def set_priority(req: Request):
    d = _admin_only(req)
    if d: return d
    try:
        body = await req.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    order = body.get("order") or []
    if not isinstance(order, list):
        return JSONResponse({"error": "order must be list"}, status_code=400)
    _lds.set_priority_order([str(x) for x in order])
    return {"ok": True, "order": order}


@router.post("/api/llm-dashboard/force-recover/{provider}")
async def force_recover_provider(provider: str):
    try:
        import time as _t
        _lds.set_provider_config(provider, {"force_recover_until": _t.time() + 3600})
        from .. import llm as _llm2
        _llm2._AUTO_DISABLE_CACHE["ts"] = 0
        return {"ok": True, "message": f"Provider {provider} force-recovered for 1 hour"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@router.post("/api/llm-dashboard/reset-cooldown/{provider}")
async def reset_cooldown(provider: str, req: Request):
    d = _admin_only(req)
    if d: return d
    try:
        from .. import provider_limits as _pl
        _pl.reset(provider)
        # Part 663: clear cooldown only, don't override auto-disable
        # Clear cache so next routing decision re-evaluates
        try:
            from .. import llm as _llm2
            _llm2._AUTO_DISABLE_CACHE["ts"] = 0
        except Exception:
            pass
        return {"ok": True, "message": f"Cooldown reset for {provider}"}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@router.get("/api/llm-dashboard/orchestrator")
async def get_orchestrator(req: Request):
    d = _admin_only(req)
    if d: return d
    return _lds.get_orchestrator_config()

@router.post("/api/llm-dashboard/orchestrator")
async def set_orchestrator(req: Request):
    d = _admin_only(req)
    if d: return d
    try:
        body = await req.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    allowed = {"disable_all", "routing_strategy", "global_rate_limit", "max_retries", "system_prompt_addon"}
    patch = {k: v for k, v in body.items() if k in allowed}
    cfg = _lds.set_orchestrator_config(patch)
    return {"ok": True, "config": cfg}

@router.post("/api/llm-dashboard/test-provider/{provider}")
async def test_provider(provider: str, req: Request):
    """Part 630: send a minimal 'Say OK' prompt to a specific provider."""
    d = _admin_only(req)
    if d: return d
    import time as _t
    from .. import providers as _prov
    from .. import llm as _llm

    provs = _prov.load_providers()
    target = next((p for p in provs if p.name == provider), None)
    if not target:
        return JSONResponse({"ok": False, "error": "Provider not found"}, status_code=404)

    start = _t.time()
    try:
        if target.provider_type == "local":
            from .. import local_llm as _local_llm
            res = await _local_llm.chat("Say OK", max_tokens=4, timeout=60.0)
        else:
            res = await _llm._chat_single(
                prompt="Say OK", base_url=target.base_url,
                api_key=target.api_key, model=target.model,
                timeout=15.0, _retry_depth=0,
            )
        latency = int((_t.time() - start) * 1000)
        # Part 658: persist every test result to the health log
        try:
            from .. import llm_dashboard_store as _lds
            _lds.log_llm_call(
                provider=target.name,
                model=target.model or "",
                ok=bool(res.get("ok")),
                tokens=0,
                latency_ms=latency,
                error=(res.get("error") or "")[:200],
                user="test",
            )
        except Exception:
            pass
        if res.get("ok"):
            content = (res.get("content") or "").strip()[:50]
            target.record_success(latency)
            return {"ok": True, "latency_ms": latency, "content": content}
        else:
            err = res.get("error", "Unknown")
            try:
                from .. import llm as _llm2
                cd = _llm2._cooldown_for(target.name, err)
                target.mark_cooldown(cd)
            except Exception:
                pass
            target.record_failure(err)
            return {"ok": False, "error": err, "latency_ms": latency}
    except Exception as e:
        return {"ok": False, "error": str(e), "latency_ms": int((_t.time() - start) * 1000)}

@router.get("/api/llm-dashboard/health")
async def health_summary(req: Request):
    """Part 652: Aggregated per-provider health stats (1h + 24h windows)."""
    d = _admin_only(req)
    if d: return d
    import time as _t
    from collections import defaultdict
    from .. import providers as _prov
    from .. import llm_dashboard_store as _lds

    now = _t.time()
    logs = _lds.list_llm_logs(limit=5000)

    stats = defaultdict(lambda: {
        "ok_1h": 0, "fail_1h": 0, "lat_1h": [],
        "ok_24h": 0, "fail_24h": 0, "lat_24h": [],
        "last_error": "",
    })

    _SKIP_PROVIDERS = {"none", "", "unknown", "__router__", "__all_failed__"}
    for log in logs:
        pname = log.get("provider") or "unknown"
        if pname in _SKIP_PROVIDERS:
            continue  # Part 653: skip router failure aggregates
        ts = log.get("ts", 0)
        age = now - ts
        is_ok = log.get("ok", False)
        lat = log.get("latency_ms", 0)
        s = stats[pname]
        if age <= 3600:
            if is_ok:
                s["ok_1h"] += 1
                if lat > 0: s["lat_1h"].append(lat)
            else:
                s["fail_1h"] += 1
                s["last_error"] = (log.get("error") or "")[:100]
        if age <= 86400:
            if is_ok:
                s["ok_24h"] += 1
                if lat > 0: s["lat_24h"].append(lat)
            else:
                s["fail_24h"] += 1

    provs = _prov.load_providers()
    live = {p.name: p for p in provs}

    def _pct(ok, total):
        return round(100.0 * ok / total, 1) if total > 0 else None

    def _p95(arr):
        if not arr: return 0
        a = sorted(arr)
        idx = max(0, int(len(a) * 0.95) - 1)
        return round(a[idx], 0)

    result = []
    seen = set()
    for name in sorted(stats.keys()):
        s = stats[name]
        lp = live.get(name)
        seen.add(name)
        total_1h = s["ok_1h"] + s["fail_1h"]
        total_24h = s["ok_24h"] + s["fail_24h"]
        avg_1h = round(sum(s["lat_1h"]) / len(s["lat_1h"]), 0) if s["lat_1h"] else 0
        # Part 663: auto-disabled flag (>=5 calls and <50% success)
        _auto = total_1h >= 3 and (s["ok_1h"] / total_1h) < 0.5  # Part 663: lowered from 5 to 3
        result.append({
            "provider": name,
            "live_status": "cooling" if (lp and lp.is_cooling()) else ("active" if lp else "unknown"),
            "cooldown_remaining_s": round(lp.cooldown_remaining(), 1) if lp and lp.is_cooling() else 0,
            "success_pct_1h": _pct(s["ok_1h"], total_1h),
            "avg_latency_1h_ms": avg_1h,
            "p95_latency_1h_ms": _p95(s["lat_1h"]),
            "total_1h": total_1h,
            "success_pct_24h": _pct(s["ok_24h"], total_24h),
            "total_24h": total_24h,
            "last_error": s["last_error"],
            "auto_disabled": _auto,
        })

    for name in live.keys():
        if name in seen: continue
        lp = live[name]
        result.append({
            "provider": name,
            "live_status": "cooling" if lp.is_cooling() else "active",
            "cooldown_remaining_s": round(lp.cooldown_remaining(), 1) if lp.is_cooling() else 0,
            "success_pct_1h": None, "avg_latency_1h_ms": 0, "p95_latency_1h_ms": 0, "total_1h": 0,
            "success_pct_24h": None, "total_24h": 0, "last_error": "",
            "auto_disabled": False,
        })

    return {"count": len(result), "providers": result, "ts": now}

@router.get("/api/llm-dashboard/usage")
async def usage_summary(req: Request):
    """Part 659: Cost & token analytics from LLM call logs."""
    d = _admin_only(req)
    if d: return d
    import time as _t
    from collections import defaultdict
    from .. import llm_dashboard_store as _lds

    now = _t.time()
    logs = _lds.list_llm_logs(limit=5000)

    by_provider = defaultdict(lambda: {"tok_24h": 0, "tok_7d": 0, "calls_7d": 0, "cost_7d_cents": 0.0})
    by_user = defaultdict(lambda: {"tok_24h": 0, "tok_7d": 0, "calls_7d": 0})
    by_model = defaultdict(lambda: {"tok_7d": 0, "calls_7d": 0})
    daily = defaultdict(lambda: {"tokens": 0, "calls": 0})

    day_ago = now - 86400
    week_ago = now - 7 * 86400

    _SKIP = {"none", "", "unknown", "__router__", "__all_failed__"}
    for log in logs:
        ts = log.get("ts", 0)
        if ts < week_ago:
            continue
        prov = log.get("provider") or "unknown"
        if prov in _SKIP:
            continue
        model = log.get("model") or "unknown"
        user = log.get("user") or "anonymous"
        tok = int(log.get("tokens") or 0)

        pp = by_provider[prov]
        pp["tok_7d"] += tok
        pp["calls_7d"] += 1
        if ts >= day_ago:
            pp["tok_24h"] += tok

        uu = by_user[user]
        uu["tok_7d"] += tok
        uu["calls_7d"] += 1
        if ts >= day_ago:
            uu["tok_24h"] += tok

        mm = by_model[model]
        mm["tok_7d"] += tok
        mm["calls_7d"] += 1

        dk = _t.strftime("%Y-%m-%d", _t.gmtime(ts))
        daily[dk]["tokens"] += tok
        daily[dk]["calls"] += 1

    # Cost calc per provider
    for prov, stats in by_provider.items():
        try:
            cfg = _lds.get_provider_config(prov)
            rate = float(cfg.get("cost_per_1k_cents") or 0.0)
        except Exception:
            rate = 0.0
        stats["cost_7d_cents"] = round(stats["tok_7d"] / 1000.0 * rate, 4)

    days_series = []
    for i in range(6, -1, -1):
        dts = now - i * 86400
        key = _t.strftime("%Y-%m-%d", _t.gmtime(dts))
        d_data = daily.get(key, {"tokens": 0, "calls": 0})
        days_series.append({"date": key, "tokens": d_data["tokens"], "calls": d_data["calls"]})

    return {
        "providers": [{"provider": k, **v} for k, v in
                      sorted(by_provider.items(), key=lambda kv: -kv[1]["tok_7d"])],
        "users": [{"user": k, **v} for k, v in
                  sorted(by_user.items(), key=lambda kv: -kv[1]["tok_7d"])][:20],
        "models": [{"model": k, **v} for k, v in
                   sorted(by_model.items(), key=lambda kv: -kv[1]["tok_7d"])],
        "daily": days_series,
        "totals": {
            "tokens_24h": sum(p["tok_24h"] for p in by_provider.values()),
            "tokens_7d": sum(p["tok_7d"] for p in by_provider.values()),
            "calls_7d": sum(p["calls_7d"] for p in by_provider.values()),
        },
    }

