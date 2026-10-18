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

_JWT_SECRET = "sunnyware-jwt-secret-2026"

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
    if not email or "@" not in email:
        return JSONResponse({"error": "Valid email required"}, status_code=400)
    
    token = _generate_jwt(email)
    return {"ok": True, "token": token, "email": email, "owner_key": f"user:{email}"}
