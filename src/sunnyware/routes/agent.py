import asyncio
# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Agent endpoints: /api/agent/run, /run/stream, /plan."""

import json as _json
import time as _time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from ..runtime import state, ensure_pool, log as _log
from .. import sessions as sessions_store
from .. import memory as memory_store
from .. import llm as llm_client
from .. import orchestrator
from .. import planner
from .. import guardrails as _guard

def _auditor_verdict_or_none(role, content):
    """Part 146b: for the auditor role, extract and return the parsed
    JSON verdict as a structured object; otherwise return None.

    The auditor prompt specifies a strict JSON output contract but
    small models (e.g. Liquid LFM) often wrap the JSON in markdown
    fences or add narrative. This helper normalizes that so API
    consumers get a stable `auditor_verdict` field.

    Never raises.
    """
    try:
        if (role or "").strip().lower() != "auditor":
            return None
        from .. import roles as _roles
        return _roles.extract_auditor_json(content or "")
    except Exception:
        return None


# Part 106c: strip broken base64 markdown before writing to history.
# The LLM tries to embed images as ![...](data:image/...,base64,<data>)
# but base64 is truncated to "[image: N bytes base64]" before reaching
# the model, so the markdown link is unusable. We render images from
# the 'attachments' field instead.
import re as _re
_B64_MD_RE = _re.compile(
    r'!\[[^\]]*\]\(data:image/[^)]*\[image: \d+ bytes base64\]\)'
)


def _strip_broken_b64_md(s: str) -> str:
    if not s:
        return s
    return _B64_MD_RE.sub('', s).strip()



def _guard_check(text: str):
    """Part 136b: run injection guard on user input.

    Returns None (proceed) or JSONResponse 400 (blocked). Never raises.
    In 'off' mode (default) this is a no-op.
    """
    try:
        mode = _guard.guard_mode()
    except Exception:
        return None
    if mode == "off":
        return None
    try:
        result = _guard.scan(text or "")
    except Exception:
        return None

    # Part 136c: log via shared structured logger so hits show up
    # in HF logs alongside the {"event": "request"} stream.
    try:
        if not result.get("clean"):
            _log.info(
                "guardrail_hit",
                mode=mode,
                severity=result.get("highest_severity"),
                findings=len(result.get("findings", [])),
                names=[f.get("name") for f in result.get("findings", [])][:5],
                input_len=result.get("input_length"),
                truncated=result.get("truncated"),
            )
    except Exception:
        pass

    try:
        if _guard.should_block(result):
            return JSONResponse(
                {
                    "error": "input_rejected",
                    "detail": "input triggered prompt-injection guard",
                    "severity": result.get("highest_severity"),
                    "mode": mode,
                    "findings": [
                        {
                            "category": f.get("category"),
                            "severity": f.get("severity"),
                            "name": f.get("name"),
                        }
                        for f in result.get("findings", [])
                    ],
                },
                status_code=400,
            )
    except Exception:
        return None
    return None


async def _auditor_verdict_with_retry(role, content):
    """Part 150: for the auditor role, if the initial extraction fails,
    do ONE forced-JSON retry with a strict instruction.

    Small models (e.g. Liquid LFM 2.6B) sometimes ignore the JSON
    output contract and respond in prose. If the initial parse fails,
    we send the model's own response back asking for the JSON verdict
    only. The retry's response is used if the extraction succeeds.

    Never raises. Returns the parsed dict or None.
    """
    try:
        if (role or "").strip().lower() != "auditor":
            return None
        from .. import roles as _roles
        parsed = _roles.extract_auditor_json(content or "")
        if isinstance(parsed, dict):
            return parsed

        try:
            from .. import orchestrator as _orc
            _required_labels = (
                '"Miscalculated percentage", "Incorrect operator", '
                '"Logic gap", "Incomplete explanation", '
                '"Constraint violation", or the exact no-defect phrase '
                '"No demonstrated defect; no canonical error label applies."'
            )
            retry_prompt = (
                "Your previous response was:\n\n"
                + (content or "")[:1500]
                + "\n\n---\n"
                "Now return ONLY the JSON verdict object. "
                "No prose before or after. No markdown fences. "
                "No explanation. Start with { and end with }. "
                "Required keys: verdict, canonical_label, severity, "
                "defect_confidence, coverage_confidence. "
                "The canonical_label MUST be exactly one of: "
                + _required_labels
            )
            retry_result = await _orc.run_agent(
                retry_prompt,
                session_uuid=None,
                model=None,
                system=None,
            )
            retry_text = (retry_result or {}).get("answer", "") or ""
            parsed2 = _roles.extract_auditor_json(retry_text)
            if isinstance(parsed2, dict):
                return parsed2
        except Exception:
            pass

        return None
    except Exception:
        return None


router = APIRouter()

def _check_quota(req: Request):
    """Check and increment usage quota. Returns a 429 response if exceeded."""
    try:
        from .. import saas_store as _saas
        from .. import usage as _usage
        key = req.headers.get("x-api-key") or ""
        if not key:
            authz = req.headers.get("authorization") or ""
            if authz.lower().startswith("bearer "):
                key = authz[7:].strip()
        org = _saas.get_org_for_api_key(key)
        if not org:
            return None
        org_id = org["id"]
        plan_id = org.get("plan", "free")
        plans = {pp["id"]: pp for pp in _saas.list_plans()}
        plan = plans.get(plan_id, {})
        limit = plan.get("calls_per_day", 100)
        check = _usage.check_quota(org_id, limit)
        if not check["allowed"]:
            return JSONResponse(
                {"error": "quota_exceeded",
                 "detail": f"Daily limit of {limit} calls reached. Please upgrade your plan."},
                status_code=429,
            )
        _usage.increment(org_id)
    except Exception:
        pass
    return None



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
    role = body.get("role")   # Part 112

    if not prompt:
        return JSONResponse({"error": "input required"}, status_code=400)

    # Part 136b: prompt-injection guard (mode=off by default; no-op)
    _g_deny = _guard_check(prompt)
    if _g_deny is not None:
        return _g_deny

    # Part 112: inject role prompt addon for the streaming path
    try:
        from .. import roles as _roles
        _addon = _roles.prompt_addon(role) or ""
        if _addon:
            system = (_addon + "\n\n" + (system or "")).strip()
    except Exception:
        pass

    session_uuid = await sessions_store.get_or_create(session_id)
    # Part 113A: persist role on the session (best-effort, never fatal)
    if session_uuid and role:
        try:
            from .. import roles as _roles
            if _roles.is_valid(role):
                await sessions_store.set_role(
                    session_id, _roles.canonical(role) or role
                )
        except Exception:
            pass
    if session_uuid:
        await memory_store.log_event(
            session_uuid, "user_message",
            {"content": prompt, "model": model or "default",
             "role": role or "general"},
        )

    _t0 = _time.time()
    # Hard wall-clock cap so a looping model cannot freeze the server / laptop.
    # Override via SUNNYWARE_AGENT_TIMEOUT seconds (default 90).
    import os as _os
    try:
        _agent_timeout = float(_os.getenv("SUNNYWARE_AGENT_TIMEOUT", "90"))
    except Exception:
        _agent_timeout = 90.0
    # Part 114: supervisor roles chain sub-agents; allow up to 5 min
    try:
        _role_norm = (role or "general").strip().lower()
        if _role_norm in ("cfo", "cdo"):
            _agent_timeout = max(_agent_timeout, 600.0)
    except Exception:
        pass
    try:
        agent_result = await asyncio.wait_for(
            orchestrator.run_agent(
                prompt, session_uuid=session_uuid, model=model, system=system,
                role=role,
            ),
            timeout=_agent_timeout,
        )
    except asyncio.TimeoutError:
        total_latency_ms = int((_time.time() - _t0) * 1000)
        return JSONResponse(
            {
                "error": "agent_timeout",
                "detail": "agent exceeded " + str(int(_agent_timeout)) + "s wall-clock",
                "latency_ms": total_latency_ms,
            },
            status_code=504,
        )
    total_latency_ms = int((_time.time() - _t0) * 1000)

    if session_uuid:
        if agent_result.get("ok"):
            await memory_store.log_event(
                session_uuid, "assistant_message",
                {
                    "content": _strip_broken_b64_md(agent_result.get("answer", "")),
                    "steps_count": len(agent_result.get("steps", [])),
                    "iterations": agent_result.get("iterations", 0),
                    "model": (agent_result.get("resolved_model") or model or (state["config"].llm_model if state["config"] else "unknown")),
                    "auditor_verdict": await _auditor_verdict_with_retry(role, agent_result.get("answer", "")),
                    "attachments": agent_result.get("attachments") or [],
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
        "provider": agent_result.get("provider"),
            "session_id": session_id,
            "session_uuid": session_uuid,
        }

    return {
        "result": {
            "content": agent_result.get("answer", ""),
            "model": (agent_result.get("resolved_model") or (state["config"].llm_model if state["config"] else "unknown")),
            "auditor_verdict": await _auditor_verdict_with_retry(role, agent_result.get("answer", "")),
            "steps": agent_result.get("steps", []),
            "iterations": agent_result.get("iterations", 1),
            "provider": agent_result.get("provider"),
            "budget_exceeded": agent_result.get("budget_exceeded", False),
            "tokens_used": agent_result.get("tokens_used"),
            "attachments": agent_result.get("attachments") or [],
        },
        "latency_ms": total_latency_ms,
        "served_by": "sunnyware",
        "provider": agent_result.get("provider"),
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
    role = body.get("role")   # Part 112: role persona

    if not prompt:
        return JSONResponse({"error": "input required"}, status_code=400)

    # Part 136b: prompt-injection guard (mode=off by default; no-op)
    _g_deny = _guard_check(prompt)
    if _g_deny is not None:
        return _g_deny

    session_uuid = await sessions_store.get_or_create(session_id)
    # Part 113A: persist role on the session (best-effort, never fatal)
    if session_uuid and role:
        try:
            from .. import roles as _roles
            if _roles.is_valid(role):
                await sessions_store.set_role(
                    session_id, _roles.canonical(role) or role
                )
        except Exception:
            pass
    history = []
    if session_uuid:
        history = await memory_store.build_context(session_uuid, max_turns=5)
        await memory_store.log_event(
            session_uuid, "user_message",
            {"content": prompt, "model": model or "default", "streaming": True},
        )

    async def event_stream():
        full_text = ""
        _prov_name = None
        try:
            _role_meta = {"role": role or "general"}
            try:
                from .. import roles as _roles
                _role_meta["accent"] = _roles.style(role).get("accent", "")
                _role_meta["chip"] = _roles.style(role).get("chip", "")
            except Exception:
                pass
            yield f"data: {_json.dumps({'type': 'start', 'session_uuid': session_uuid, **_role_meta})}\n\n"
            async for chunk in llm_client.stream_chat(
                prompt, model=model, system=system, history=history
            ):
                full_text += chunk
                yield f"data: {_json.dumps({'type': 'content', 'text': chunk})}\n\n"
            if session_uuid and full_text:
                await memory_store.log_event(
                    session_uuid, "assistant_message",
                    {"content": _strip_broken_b64_md(full_text), "model": model or "default", "streaming": True, "attachments": []},
                )
            try:
                from ..llm import get_last_stream_provider as _glp
                _prov_name = _glp()
            except Exception:
                _prov_name = None
            yield f"data: {_json.dumps({'type': 'done', 'session_uuid': session_uuid, 'provider': _prov_name})}\n\n"
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

    # Part 136b: prompt-injection guard (mode=off by default; no-op)
    _g_deny = _guard_check(task)
    if _g_deny is not None:
        return _g_deny

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

@router.post("/api/agent/stream")
async def agent_stream(req: Request):
    deny = _check_quota(req)
    if deny: return deny
    """Tool-aware SSE — reports tool_calls in real time as they happen.

    SSE event types:
      start, iteration, tool_call, tool_result, answer, done, error
    """
    from ..runtime import state, log
    from .. import sessions as _sessions
    from .. import memory as _memory
    from .. import orchestrator as _orch
    from .. import state as _app_state

    if not state.get("ready"):
        return JSONResponse({"error": "server not ready"}, status_code=503)

    # ensure_pool
    if _app_state.get_pool() is None:
        try:
            await _app_state.init_pool()
        except Exception:
            pass

    body = await req.json()
    prompt = body.get("input", "")
    session_id = body.get("session_id", "stream-default")
    model = body.get("model")
    role = body.get("role")   # Part 112/113B: role persona
    attachments = body.get("attachments", [])

    # Part 194b: Process attachments (Files & Images)
    if attachments:
        prompt += "\n\n"
        for att in attachments:
            name = att.get("name", "file")
            att_type = att.get("type", "")
            text_content = att.get("textContent", "")
            data_url = att.get("dataUrl", "")
            
            if att_type == "image" and data_url:
                # Save base64 image to attachments directory so LLM can "see" it
                b64 = data_url.split(",", 1)[-1]
                try:
                    from .. import attachments as _att
                    saved = _att.save_base64(b64, "jpeg")
                    prompt += f"\n![{name}]({saved['url']})\n"
                except Exception as e:
                    from ..runtime import log
                    log.warning(f"Failed to save attachment image: {e}")
            elif text_content:
                # Inject document text directly into the prompt
                prompt += f"\n[Attached File: {name}]\n{text_content}\n"

    if not prompt:
        return JSONResponse({"error": "input required"}, status_code=400)

    # Part 136b: prompt-injection guard (mode=off by default; no-op)
    _g_deny = _guard_check(prompt)
    if _g_deny is not None:
        return _g_deny

    session_uuid = await _sessions.get_or_create(session_id)

    # Part 113A: persist role on session (best-effort, never fatal)
    if session_uuid and role:
        try:
            from .. import roles as _roles_mod
            if _roles_mod.is_valid(role):
                await _sessions.set_role(
                    session_id, _roles_mod.canonical(role) or role
                )
        except Exception:
            pass

    if session_uuid:
        await _memory.log_event(
            session_uuid,
            "user_message",
            {"content": prompt, "model": model or "default",
             "mode": "stream-orch", "role": role or "general"},
        )

    queue: asyncio.Queue = asyncio.Queue()

    async def _cb(ev):
        await queue.put(ev)

    async def _runner():
        try:
            result = await _orch.run_agent(
                prompt, session_uuid=session_uuid, model=model, on_event=_cb,
                role=role,
            )
            if session_uuid:
                if result.get("ok"):
                    await _memory.log_event(
                        session_uuid,
                        "assistant_message",
                        {
                            "content": _strip_broken_b64_md(result.get("answer", "")),
                            "mode": "stream-orch",
                            "steps_count": len(result.get("steps", [])),
                            "attachments": result.get("attachments") or [],
                        },
                    )
                else:
                    await _memory.log_event(
                        session_uuid,
                        "llm_error",
                        {"error": result.get("error", "unknown")},
                    )
            await queue.put({"type": "final", "ok": result.get("ok", False),
                             "answer": result.get("answer", ""),
                             "attachments": result.get("attachments") or [],
                             "error": result.get("error"),
                             "iterations": result.get("iterations", 1),
                             "steps_count": len(result.get("steps", [])),
                             "provider": result.get("provider")})
        except Exception as e:
            await queue.put({"type": "error", "error": f"{type(e).__name__}: {e}"})
        finally:
            await queue.put({"type": "__END__"})

    async def _event_stream():
        runner_task = asyncio.create_task(_runner())
        try:
            _sess_meta = {"type": "session", "session_uuid": session_uuid}
            try:
                from .. import roles as _roles_s
                _st = _roles_s.style(role) or {}
                _sess_meta["role"] = role or "general"
                _sess_meta["accent"] = _st.get("accent", "")
                _sess_meta["chip"] = _st.get("chip", "")
            except Exception:
                pass
            yield f"data: {_json.dumps(_sess_meta)}\n\n"
            while True:
                ev = await queue.get()
                if ev.get("type") == "__END__":
                    break
                yield f"data: {_json.dumps(ev)}\n\n"
            yield f"data: {_json.dumps({'type': 'done'})}\n\n"
        finally:
            if not runner_task.done():
                runner_task.cancel()

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )




@router.get("/api/roles")
async def list_roles():
    """Part 112: return available role personas for the UI selector."""
    try:
        from .. import roles as _roles
        return JSONResponse({
            "roles": [
                {"key": k, "label": v["label"], "icon": v["icon"]}
                for k, v in _roles.ROLES.items()
            ],
            "default": _roles.DEFAULT_ROLE,
        })
    except Exception as e:
        return JSONResponse(
            {"error": type(e).__name__ + ": " + str(e)},
            status_code=500,
        )



@router.get("/api/roles/export")
async def roles_export():
    """Part 116: JSON snapshot of the role registry for sharing."""
    try:
        from .. import roles as _roles
        return JSONResponse(_roles.export_roles())
    except Exception as e:
        return JSONResponse(
            {"error": f"{type(e).__name__}: {e}"},
            status_code=500,
        )


@router.post("/api/roles/import")
async def roles_import(req: Request):
    """Part 116: validate an exported role snapshot (does NOT mutate)."""
    try:
        from .. import roles as _roles
        try:
            body = await req.json()
        except Exception:
            return JSONResponse(
                {"error": "body must be valid JSON"},
                status_code=400,
            )
        ok, errors = _roles.import_roles(body)
        return JSONResponse({
            "valid": ok,
            "errors": errors,
            "roles_in_payload": len(body.get("roles") or []) if isinstance(body, dict) else 0,
        }, status_code=200 if ok else 400)
    except Exception as e:
        return JSONResponse(
            {"error": f"{type(e).__name__}: {e}"},
            status_code=500,
        )
