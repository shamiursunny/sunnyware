# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 222: Two-Factor Authentication routes."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from .. import twofa_store as _tfs

router = APIRouter(tags=["twofa"])


def _resolve_user(req: Request) -> str:
    """Identify the calling user. Master admin → 'admin'. JWT → email."""
    import base64 as _b64
    import json as _json
    key = req.headers.get("x-api-key") or ""
    if not key:
        authz = req.headers.get("authorization") or ""
        if authz.lower().startswith("bearer "):
            key = authz[7:].strip()
    if not key:
        return ""
    if key == "master-admin-key":
        return "admin"
    try:
        if "." in key and len(key) > 20:
            b64 = key.split(".")[0]
            padded = b64 + "=" * (-len(b64) % 4)
            payload = _json.loads(_b64.urlsafe_b64decode(padded))
            return (payload.get("sub") or payload.get("email") or "").lower()
    except Exception:
        pass
    return ""


@router.get("/api/2fa/status")
async def status(req: Request):
    user = _resolve_user(req)
    if not user:
        return JSONResponse({"error": "auth_required"}, status_code=401)
    info = _tfs.get_user(user)
    return {
        "user": user,
        "enabled": info["enabled"],
        "backup_codes_remaining": info["backup_codes_remaining"],
        "enabled_at": info["enabled_at"],
    }


@router.post("/api/2fa/setup")
async def setup(req: Request):
    user = _resolve_user(req)
    if not user:
        return JSONResponse({"error": "auth_required"}, status_code=401)
    return _tfs.start_setup(user)


@router.post("/api/2fa/verify-setup")
async def verify_setup(req: Request):
    user = _resolve_user(req)
    if not user:
        return JSONResponse({"error": "auth_required"}, status_code=401)
    try:
        body = await req.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    return _tfs.verify_setup(user, body.get("code", ""))


@router.post("/api/2fa/verify-login")
async def verify_login(req: Request):
    try:
        body = await req.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    user = (body.get("user") or "").lower().strip()
    code = body.get("code", "")
    trust = bool(body.get("trust_device"))
    if not user:
        return JSONResponse({"error": "user required"}, status_code=400)
    result = _tfs.verify_login(user, code)
    if not result.get("ok"):
        result = _tfs.verify_backup_code(user, code)
    if not result.get("ok"):
        return result
    if trust:
        dev = _tfs.trust_device(user, body.get("device_name", ""))
        if dev.get("ok"):
            result["trusted_token"] = dev["trusted_token"]
    return result


@router.post("/api/2fa/disable")
async def disable(req: Request):
    user = _resolve_user(req)
    if not user:
        return JSONResponse({"error": "auth_required"}, status_code=401)
    try:
        body = await req.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    return _tfs.disable(user, body.get("code", ""))


@router.post("/api/2fa/backup-codes/regenerate")
async def regen_backup(req: Request):
    user = _resolve_user(req)
    if not user:
        return JSONResponse({"error": "auth_required"}, status_code=401)
    return _tfs.regenerate_backup_codes(user)


@router.get("/api/2fa/devices")
async def list_devices(req: Request):
    user = _resolve_user(req)
    if not user:
        return JSONResponse({"error": "auth_required"}, status_code=401)
    devices = _tfs.list_devices(user)
    return {"count": len(devices), "devices": devices}


@router.delete("/api/2fa/devices/{device_id}")
async def remove_device(device_id: str, req: Request):
    user = _resolve_user(req)
    if not user:
        return JSONResponse({"error": "auth_required"}, status_code=401)
    return {"ok": _tfs.remove_device(user, device_id)}


@router.delete("/api/2fa/devices")
async def remove_all_devices(req: Request):
    user = _resolve_user(req)
    if not user:
        return JSONResponse({"error": "auth_required"}, status_code=401)
    count = _tfs.remove_all_devices(user)
    return {"ok": True, "removed": count}


@router.get("/api/2fa/check-session")
async def check_session(req: Request):
    user = _resolve_user(req)
    if not user:
        return JSONResponse({"error": "auth_required"}, status_code=401)
    token = req.headers.get("x-2fa-session", "")
    return {"valid": _tfs.verify_session(user, token)}
