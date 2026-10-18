# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 199: HITL config REST API."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from .. import hitl_config

router = APIRouter()


@router.get("/api/hitl/config")
async def get_config():
    return hitl_config.get_full_config()


@router.get("/api/hitl/tools")
async def list_tools():
    try:
        from ..tools import _TOOLS
        tools = sorted(_TOOLS.keys())
    except Exception:
        tools = []
    cfg = hitl_config.get_full_config()
    decisions = {}
    for t in tools:
        decisions[t] = hitl_config.get_decision(t)
    return {"tools": tools, "global": cfg.get("global", {}),
            "overrides": cfg.get("overrides", {}), "effective": decisions}


@router.post("/api/hitl/config")
async def set_config(req: Request):
    body = await req.json()
    tool = (body.get("tool") or "").strip()
    decision = (body.get("decision") or "").strip()
    user_key = (body.get("user_key") or "").strip() or None
    if not tool or decision not in ("auto", "approve", "deny"):
        return JSONResponse({"error": "tool and decision(auto/approve/deny) required"}, status_code=400)
    if user_key:
        ok = hitl_config.set_override(user_key, tool, decision)
    else:
        ok = hitl_config.set_global(tool, decision)
    return {"ok": ok, "config": hitl_config.get_full_config()}


@router.post("/api/hitl/config/bulk")
async def bulk_config(req: Request):
    body = await req.json()
    decision = (body.get("decision") or "").strip()
    tools = body.get("tools") or None
    user_key = (body.get("user_key") or "").strip() or None
    if decision not in ("auto", "approve", "deny"):
        return JSONResponse({"error": "decision(auto/approve/deny) required"}, status_code=400)
    ok = hitl_config.bulk_set(decision, tools=tools, user_key=user_key)
    return {"ok": ok, "config": hitl_config.get_full_config()}


@router.post("/api/hitl/config/reset")
async def reset_config():
    return {"ok": hitl_config.reset()}
