# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Agent endpoints: /api/agent/run, /run/stream, /plan."""

import json as _json
import time as _time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from ..runtime import state, ensure_pool
from .. import sessions as sessions_store
from .. import memory as memory_store
from .. import llm as llm_client
from .. import orchestrator
from .. import planner


router = APIRouter()


@router.post("/api/agent/run")
async def run_agent(req: Request):
    if not state["ready"]:
        return JSONResponse({"error": "server not ready"}, status_code=503)

    await ensure_pool()

    body = await req.json()
    prompt = body.get("input", "")
    session_id = body.get("session_id", "default")
    model = body.get("model")
    system = body.get("system")

    if not prompt:
        return JSONResponse({"error": "input required"}, status_code=400)

    session_uuid = await sessions_store.get_or_create(session_id)
    if session_uuid:
        await memory_store.log_event(
            session_uuid, "user_message",
            {"content": prompt, "model": model or "default"},
        )

    _t0 = _time.time()
    agent_result = await orchestrator.run_agent(
        prompt, session_uuid=session_uuid, model=model, system=system
    )
    total_latency_ms = int((_time.time() - _t0) * 1000)

    if session_uuid:
        if agent_result.get("ok"):
            await memory_store.log_event(
                session_uuid, "assistant_message",
                {
                    "content": agent_result.get("answer", ""),
                    "steps_count": len(agent_result.get("steps", [])),
                    "iterations": agent_result.get("iterations", 0),
                    "model": model or (state["config"].llm_model if state["config"] else "unknown"),
                },
            )
        else:
            await memory_store.log_event(
                session_uuid, "llm_error",
                {"error": agent_result.get("error", "unknown")},
            )

    if not agent_result.get("ok"):
        return {
            "result": None,
            "error": "Agent failed",
            "detail": agent_result.get("error"),
            "latency_ms": total_latency_ms,
            "served_by": "sunnyware",
            "session_id": session_id,
            "session_uuid": session_uuid,
        }

    return {
        "result": {
            "content": agent_result.get("answer", ""),
            "model": (state["config"].llm_model if state["config"] else "unknown"),
            "steps": agent_result.get("steps", []),
            "iterations": agent_result.get("iterations", 1),
        },
        "latency_ms": total_latency_ms,
        "served_by": "sunnyware",
        "session_id": session_id,
        "session_uuid": session_uuid,
    }


@router.post("/api/agent/run/stream")
async def run_agent_stream(req: Request):
    if not state["ready"]:
        return JSONResponse({"error": "server not ready"}, status_code=503)

    await ensure_pool()

    body = await req.json()
    prompt = body.get("input", "")
    session_id = body.get("session_id", "default")
    model = body.get("model")
    system = body.get("system")

    if not prompt:
        return JSONResponse({"error": "input required"}, status_code=400)

    session_uuid = await sessions_store.get_or_create(session_id)
    history = []
    if session_uuid:
        history = await memory_store.build_context(session_uuid, max_turns=5)
        await memory_store.log_event(
            session_uuid, "user_message",
            {"content": prompt, "model": model or "default", "streaming": True},
        )

    async def event_stream():
        full_text = ""
        try:
            yield f"data: {_json.dumps({'type': 'start', 'session_uuid': session_uuid})}\n\n"
            async for chunk in llm_client.stream_chat(
                prompt, model=model, system=system, history=history
            ):
                full_text += chunk
                yield f"data: {_json.dumps({'type': 'content', 'text': chunk})}\n\n"
            if session_uuid and full_text:
                await memory_store.log_event(
                    session_uuid, "assistant_message",
                    {"content": full_text, "model": model or "default", "streaming": True},
                )
            yield f"data: {_json.dumps({'type': 'done', 'session_uuid': session_uuid})}\n\n"
        except Exception as e:
            err = _json.dumps({"type": "error", "error": f"{type(e).__name__}: {e}"})
            yield f"data: {err}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/api/agent/plan")
async def run_agent_plan(req: Request):
    if not state["ready"]:
        return JSONResponse({"error": "server not ready"}, status_code=503)

    await ensure_pool()

    body = await req.json()
    task = body.get("input", "")
    session_id = body.get("session_id", "plan-default")
    model = body.get("model")
    parallel = bool(body.get("parallel", True))

    if not task:
        return JSONResponse({"error": "input required"}, status_code=400)

    session_uuid = await sessions_store.get_or_create(session_id)
    if session_uuid:
        await memory_store.log_event(
            session_uuid, "user_message",
            {"content": task, "model": model or "default", "mode": "plan", "parallel": parallel},
        )

    result = await planner.plan_and_execute(
        task, session_uuid=session_uuid, model=model, parallel=parallel
    )

    if session_uuid:
        await memory_store.log_event(
            session_uuid, "assistant_message",
            {
                "content": result.get("final_answer", ""),
                "mode": "plan",
                "subtask_count": len(result.get("subtasks", [])),
                "ok": result.get("ok", False),
            },
        )

    return {
        **result,
        "served_by": "sunnyware",
        "session_id": session_id,
        "session_uuid": session_uuid,
    }
