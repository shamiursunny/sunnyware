# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Webhook receiver core (Part 83).

External services POST to /webhook/{token}. Events are stored in Neon.
If a trigger_prompt is set on the endpoint, the payload is summarised
and run through the orchestrator; result stored in response_preview and
optionally emailed.
"""
import secrets
import time
from typing import Optional
from . import state as app_state


_MAX_PROMPT = 2000
_MAX_PAYLOAD_PREVIEW = 4000
_TRIGGER_TIMEOUT = 90.0


def _new_token() -> str:
    return "wh_" + secrets.token_urlsafe(24)


async def add(name: str, trigger_prompt: str = "", notify_email: str = "") -> dict:
    name = (name or "").strip()
    if not name or len(name) > 80:
        return {"error": "name must be 1-80 chars"}
    trigger_prompt = (trigger_prompt or "").strip()[: _MAX_PROMPT]
    notify_email = (notify_email or "").strip()

    pool = app_state.get_pool()
    if pool is None:
        return {"error": "database unavailable"}

    token = _new_token()
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO webhook_endpoints
                   (token, name, trigger_prompt, notify_email, enabled)
                   VALUES ($1, $2, $3, $4, TRUE)""",
                token, name, trigger_prompt, notify_email,
            )
    except Exception as e:
        return {"error": type(e).__name__ + ": " + str(e)[:200]}

    return {"ok": True, "token": token, "name": name,
            "url_path": "/webhook/" + token}


async def list_all() -> dict:
    pool = app_state.get_pool()
    if pool is None:
        return {"error": "database unavailable"}
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT token, name, trigger_prompt, notify_email,
                          enabled, hit_count, last_hit_at, created_at
                   FROM webhook_endpoints ORDER BY created_at DESC""")
    except Exception as e:
        return {"error": type(e).__name__ + ": " + str(e)[:200]}
    items = [{
        "token": r["token"],
        "name": r["name"],
        "url_path": "/webhook/" + r["token"],
        "trigger_prompt": r["trigger_prompt"] or "",
        "notify_email": r["notify_email"] or "",
        "enabled": bool(r["enabled"]),
        "hit_count": int(r["hit_count"]),
        "last_hit_at": r["last_hit_at"].isoformat() if r["last_hit_at"] else None,
        "created_at": r["created_at"].isoformat() if r["created_at"] else None,
    } for r in rows]
    return {"count": len(items), "endpoints": items}


async def delete(token: str) -> dict:
    token = (token or "").strip()
    if not token:
        return {"error": "token is required"}
    pool = app_state.get_pool()
    if pool is None:
        return {"error": "database unavailable"}
    try:
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM webhook_endpoints WHERE token = $1", token)
    except Exception as e:
        return {"error": type(e).__name__ + ": " + str(e)[:200]}
    return {"ok": True, "token": token, "result": str(result)}


async def events(token: str, limit: int = 10) -> dict:
    token = (token or "").strip()
    if not token:
        return {"error": "token is required"}
    try:
        limit = max(1, min(int(limit), 50))
    except (TypeError, ValueError):
        limit = 10
    pool = app_state.get_pool()
    if pool is None:
        return {"error": "database unavailable"}
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, source_ip, payload, processed,
                          response_preview, error, received_at
                   FROM webhook_events
                   WHERE endpoint_token = $1
                   ORDER BY received_at DESC LIMIT $2""",
                token, limit)
    except Exception as e:
        return {"error": type(e).__name__ + ": " + str(e)[:200]}
    items = [{
        "id": int(r["id"]),
        "source_ip": r["source_ip"],
        "payload": r["payload"],
        "processed": bool(r["processed"]),
        "response_preview": r["response_preview"],
        "error": r["error"],
        "received_at": r["received_at"].isoformat() if r["received_at"] else None,
    } for r in rows]
    return {"count": len(items), "events": items}


async def fire(token: str, payload, headers: dict, source_ip: str) -> dict:
    """Handle an incoming webhook POST. Stores event, optionally runs prompt."""
    token = (token or "").strip()
    if not token:
        return {"ok": False, "error": "no token"}
    pool = app_state.get_pool()
    if pool is None:
        return {"ok": False, "error": "database unavailable"}
    try:
        async with pool.acquire() as conn:
            ep = await conn.fetchrow(
                "SELECT name, trigger_prompt, notify_email, enabled FROM webhook_endpoints WHERE token = $1",
                token)
    except Exception as e:
        return {"ok": False, "error": type(e).__name__ + ": " + str(e)[:200]}
    if ep is None:
        return {"ok": False, "error": "endpoint not found"}
    if not ep["enabled"]:
        return {"ok": False, "error": "endpoint disabled"}

    # Store raw event
    try:
        import json as _json
        payload_json = _json.dumps(payload)[:100000]
        headers_safe = {k: v for k, v in (headers or {}).items()
                        if k.lower() not in ("authorization", "cookie")}
        headers_json = _json.dumps(headers_safe)[:5000]
        async with pool.acquire() as conn:
            event_id = await conn.fetchval(
                """INSERT INTO webhook_events
                   (endpoint_token, source_ip, headers, payload)
                   VALUES ($1, $2, $3::jsonb, $4::jsonb)
                   RETURNING id""",
                token, source_ip, headers_json, payload_json)
            await conn.execute(
                "UPDATE webhook_endpoints SET hit_count = hit_count + 1, last_hit_at = NOW() WHERE token = $1",
                token)
    except Exception as e:
        return {"ok": False, "error": "storage failed: " + type(e).__name__ + ": " + str(e)[:150]}

    # Optional trigger
    trigger_prompt = (ep["trigger_prompt"] or "").strip()
    response_preview = None
    err = None
    if trigger_prompt:
        try:
            import json as _json
            from . import orchestrator as _orch
            import asyncio as _aio
            # Compose prompt with payload summary
            payload_snippet = _json.dumps(payload)[:_MAX_PAYLOAD_PREVIEW]
            full_prompt = trigger_prompt + "\n\nIncoming event payload:\n" + payload_snippet
            result = await _aio.wait_for(_orch.run_agent(full_prompt), timeout=_TRIGGER_TIMEOUT)
            response_preview = (result.get("answer") or "")[:1000]
            err = None if result.get("ok") else (result.get("error") or "agent error")
        except Exception as e:
            err = type(e).__name__ + ": " + str(e)[:200]

        # Update event
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    """UPDATE webhook_events
                       SET processed = TRUE, response_preview = $1, error = $2
                       WHERE id = $3""",
                    response_preview, err, event_id)
        except Exception:
            pass

        # Optional email
        notify = (ep["notify_email"] or "").strip()
        if notify and response_preview:
            try:
                from . import email_send as _em
                if _em.is_configured():
                    await _em.send_email(
                        to=[notify],
                        subject="[webhook] " + ep["name"],
                        body=("Endpoint: " + ep["name"] + "\n"
                              "Event ID: " + str(event_id) + "\n\n"
                              "Response:\n" + response_preview),
                    )
            except Exception:
                pass

    return {
        "ok": True,
        "event_id": int(event_id),
        "endpoint": ep["name"],
        "triggered": bool(trigger_prompt),
        "response_preview": response_preview,
        "error": err,
    }
