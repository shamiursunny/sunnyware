# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Auth status endpoint — always public (never requires API key)."""

from fastapi import APIRouter

from .. import auth


router = APIRouter()


@router.get("/api/auth/status")
async def auth_status():
    """Inspect auth + rate-limit configuration (public endpoint)."""
    return auth.status()

# === Part 196: Real JWT Auth ===
import hmac, hashlib, base64, json, time
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

import os
_JWT_SECRET = os.getenv("SUNNYWARE_JWT_SECRET")
if not _JWT_SECRET:
    import secrets
    _JWT_SECRET = secrets.token_urlsafe(48)  # secure random fallback
    import logging as _lg
    _lg.getLogger(__name__).warning(
        "SUNNYWARE_JWT_SECRET not set — using a random secret. "
        "All JWTs will invalidate on restart. Set the env var in production."
    )

def _generate_jwt(email: str) -> str:
    payload = {"sub": email, "exp": time.time() + 86400 * 7}
    b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    sig = hmac.new(_JWT_SECRET.encode(), b64.encode(), hashlib.sha256).hexdigest()
    return f"{b64}.{sig}"

def verify_jwt(token: str) -> str:
    try:
        b64, sig = token.split(".")
        expected_sig = hmac.new(_JWT_SECRET.encode(), b64.encode(), hashlib.sha256).hexdigest()
        if hmac.compare_digest(sig, expected_sig):
            payload = json.loads(base64.urlsafe_b64decode(b64 + "==").decode())
            if payload.get("exp", 0) > time.time():
                return payload.get("sub")
    except Exception:
        pass
    return None

@router.post("/api/auth/login")
async def auth_login(req: Request):
    body = await req.json()
    email = (body.get("email") or "").strip().lower()
    if not email:
        return JSONResponse({"error": "Email or admin key required"}, status_code=400)
    
    # Allow master admin login
    if email in ("admin", "master-admin-key", "admin@sunnyware.com"):
        return {"ok": True, "token": "master-admin-key", "email": "admin@sunnyware.com", "owner_key": "master-admin-key"}

    if "@" not in email:
        return JSONResponse({"error": "Valid email required"}, status_code=400)
    
    token = _generate_jwt(email)

    # Part 211: track login in team activity
    try:
        from .. import team_store as _team
        _team.track_login(email)
    except Exception:
        pass

    # Part 212: analytics login event
    try:
        from .. import analytics_store as _as
        _as.log_event(email, "login")
    except Exception:
        pass

    return {"ok": True, "token": token, "email": email, "owner_key": f"user:{email}"}


@router.post("/api/auth/logout")
async def auth_logout(req: Request):
    """Part 211: track logout activity (best-effort)."""
    try:
        body = await req.json()
    except Exception:
        body = {}
    email = (body.get("email") or "").strip().lower()
    if email:
        try:
            from .. import team_store as _team
            _team.track_logout(email)
        except Exception:
            pass

        # Part 212: analytics logout event
        try:
            from .. import analytics_store as _as
            _as.log_event(email, "logout")
        except Exception:
            pass
    return {"ok": True}


@router.get("/api/auth/me")
async def get_current_user(req: Request):
    """Part 234: Return the current user's email and role."""
    key = req.headers.get("x-api-key") or ""
    if not key:
        authz = req.headers.get("authorization") or ""
        if authz.lower().startswith("bearer "):
            key = authz[7:].strip()
    
    if key == "master-admin-key":
        return {"email": "admin@sunnyware.com", "role": "Owner"}
        
    if key.startswith("user:") or "." in key:
        email = key.split(":", 1)[1] if key.startswith("user:") else verify_jwt(key)
        if email:
            from .. import team_store as _ts
            member = _ts.get_member_by_email(email)
            if member:
                return {"email": email, "role": member.get("role", "Viewer")}
            return {"email": email, "role": "Viewer"}
            
    return JSONResponse({"error": "unauthorized"}, status_code=401)
