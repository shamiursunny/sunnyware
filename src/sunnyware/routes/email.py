# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 217: Email Routes."""

import os
import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from .. import email_store as _es

router = APIRouter(tags=["email"])

def _admin_only(req: Request):
    from .. import auth as _auth
    key = req.headers.get("x-api-key") or ""
    if not key:
        authz = req.headers.get("authorization") or ""
        if authz.lower().startswith("bearer "):
            key = authz[7:].strip()
    if not _auth.auth_enabled(): return None
    if not key or not _auth.is_valid_key(key):
        return JSONResponse({"error": "auth_required"}, status_code=401)
    if not _auth.has_role(_auth.role_for_key(key), "admin"):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return None

@router.post("/api/email/send")
async def send_email(req: Request):
    d = _admin_only(req)
    if d: return d
    try:
        body = await req.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    to_email = body.get("to", "")
    subject = body.get("subject", "")
    html_content = body.get("html", "")
    if not to_email or not subject:
        return JSONResponse({"error": "Missing to/subject"}, status_code=400)

    api_key = os.getenv("RESEND_API_KEY", "")
    if not api_key:
        _es.log_email(to_email, subject, "failed", "RESEND_API_KEY not configured")
        return JSONResponse({"error": "RESEND_API_KEY not configured on server"}, status_code=500)

    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "from": "Sunnyware <onboarding@resend.dev>",
                    "to": [to_email],
                    "subject": subject,
                    "html": html_content,
                },
            )
            if res.status_code >= 400:
                _es.log_email(to_email, subject, "failed", res.text)
                return JSONResponse({"error": res.text}, status_code=res.status_code)
        _es.log_email(to_email, subject, "sent")
        return {"ok": True}
    except Exception as e:
        _es.log_email(to_email, subject, "failed", str(e))
        return JSONResponse({"error": str(e)}, status_code=500)

@router.get("/api/email/logs")
async def get_logs(req: Request, limit: int = 100):
    d = _admin_only(req)
    if d: return d
    return {"count": len(_es.list_emails(limit)), "logs": _es.list_emails(limit)}

@router.delete("/api/email/logs")
async def clear_logs(req: Request):
    d = _admin_only(req)
    if d: return d
    return {"ok": _es.clear_emails()}
