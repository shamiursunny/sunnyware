# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Public webhook receiver route (Part 83)."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["webhooks"])


@router.post("/webhook/{token}")
async def receive_webhook(token: str, req: Request):
    """Receive an external webhook POST. Stores event; optionally triggers
    an agent prompt if the endpoint has one configured."""
    from .. import webhook as _wh

    # Try to parse JSON body; fall back to form / raw
    payload = None
    try:
        payload = await req.json()
    except Exception:
        try:
            body = await req.body()
            payload = {"raw": body.decode("utf-8", errors="replace")[:10000]}
        except Exception:
            payload = {}

    headers = dict(req.headers)
    client_ip = req.client.host if req.client else ""

    result = await _wh.fire(token, payload, headers, client_ip)
    status = 200 if result.get("ok") else 404
    return JSONResponse(result, status_code=status)
