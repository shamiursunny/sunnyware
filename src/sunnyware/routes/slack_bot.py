# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 224d: Slack bot routes."""

import asyncio
import hashlib
import hmac
import json
import time
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from .. import slack_store as _slack

router = APIRouter(tags=["slack_bot"])


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


def _verify_slack_signature(request: Request, raw_body: bytes, config: dict) -> bool:
    if not config.get("verify_signature"):
        return True
    secret = config.get("signing_secret", "")
    if not secret:
        return False
    ts = request.headers.get("x-slack-request-timestamp", "")
    sig = request.headers.get("x-slack-signature", "")
    if not ts or not sig:
        return False
    try:
        if abs(time.time() - int(ts)) > 300:
            return False
    except Exception:
        return False
    basestring = b"v0:" + ts.encode() + b":" + raw_body
    computed = "v0=" + hmac.new(secret.encode(), basestring, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, sig)


# ═══════════════════════════════════════════════════════════
# PUBLIC endpoints (verified by Slack signature)
# ═══════════════════════════════════════════════════════════
@router.post("/api/slack/events")
async def handle_events(request: Request):
    """Handles URL verification handshake and future events."""
    raw_body = await request.body()
    config = _slack.get_config()

    if not _verify_slack_signature(request, raw_body, config):
        return JSONResponse({"error": "invalid_signature"}, status_code=401)

    try:
        data = json.loads(raw_body)
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    if data.get("type") == "url_verification":
        return {"challenge": data.get("challenge", "")}

    return {"ok": True}


@router.post("/api/slack/commands")
async def handle_command(request: Request):
    """Handles slash commands like /sunnyware <question>."""
    raw_body = await request.body()
    config = _slack.get_config()

    if not config.get("enabled"):
        return {"response_type": "ephemeral", "text": "Slack bot is disabled. Enable it in Admin → Slack Bot."}

    if not _verify_slack_signature(request, raw_body, config):
        return JSONResponse({"error": "invalid_signature"}, status_code=401)

    # Parse form body
    try:
        from urllib.parse import parse_qs
        form_data = parse_qs(raw_body.decode("utf-8"))
    except Exception:
        return JSONResponse({"error": "invalid_form"}, status_code=400)

    def _get(k):
        return (form_data.get(k, [""])[0] or "").strip()

    text = _get("text")
    user_name = _get("user_name")
    user_id = _get("user_id")
    channel = _get("channel_name") or _get("channel_id")
    response_url = _get("response_url")

    if not text:
        return {"response_type": "ephemeral", "text": "Usage: `/sunnyware <your question>`"}

    # Process in background
    asyncio.create_task(_process_command(user_name or user_id, channel, text, response_url))

    return {"response_type": "in_channel", "text": f"<@{user_id}> asked: _{text}_\n_Processing..._"}


async def _process_command(user: str, channel: str, prompt: str, response_url: str):
    """Runs the LLM in background and posts result to Slack."""
    start = time.time()
    response_text = ""
    ok = False
    try:
        from .. import llm as _llm
        result = await _llm.chat(
            prompt=prompt,
            system="You are Sunnyware, a helpful AI assistant. Keep responses concise and format for Slack (no markdown headers, use bold for emphasis).",
            timeout=60.0,
        )
        if result.get("ok"):
            response_text = result.get("content", "") or "(empty response)"
            ok = True
        else:
            response_text = "⚠️ Error: " + str(result.get("error", "unknown"))
    except Exception as e:
        response_text = "⚠️ Error: " + str(e)[:200]

    latency_ms = int((time.time() - start) * 1000)

    # Log
    try:
        _slack.log_activity(user, channel, prompt, response_text[:500], latency_ms, ok)
    except Exception:
        pass

    # Post to Slack response_url (replaces the "Processing..." message)
    if response_url:
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                await client.post(response_url, json={
                    "replace_original": True,
                    "response_type": "in_channel",
                    "text": response_text[:3900],  # Slack 4000 char limit, leave buffer
                }, timeout=15)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════
# ADMIN endpoints (require X-API-Key + 2FA)
# ═══════════════════════════════════════════════════════════
@router.get("/api/slack/config")
async def get_config(req: Request):
    d = _admin_only(req)
    if d: return d
    return _slack.get_config_sanitized()


@router.patch("/api/slack/config")
async def update_config(req: Request):
    d = _admin_only(req)
    if d: return d
    try:
        body = await req.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    patch = {}
    for k in ("enabled", "verify_signature"):
        if k in body:
            patch[k] = bool(body[k])
    for k in ("signing_secret", "bot_token", "bot_name"):
        if k in body:
            v = (body[k] or "").strip()
            # Don't overwrite if masked dots (unchanged from UI)
            if v and "•" not in v:
                patch[k] = v
    _slack.update_config(patch)
    return {"ok": True, "config": _slack.get_config_sanitized()}


@router.get("/api/slack/activity")
async def list_activity(req: Request, limit: int = 50):
    d = _admin_only(req)
    if d: return d
    items = _slack.list_activity(limit=min(limit, 500))
    return {"count": len(items), "activity": items}


@router.delete("/api/slack/activity")
async def clear_activity(req: Request):
    d = _admin_only(req)
    if d: return d
    return {"ok": _slack.clear_activity()}
