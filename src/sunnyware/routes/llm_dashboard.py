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


@router.post("/api/llm-dashboard/reset-cooldown/{provider}")
async def reset_cooldown(provider: str, req: Request):
    d = _admin_only(req)
    if d: return d
    try:
        from .. import provider_limits as _pl
        _pl.reset(provider)
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

