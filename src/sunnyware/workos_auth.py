# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 206: WorkOS AuthKit (User Management) client."""

import os
import httpx
from urllib.parse import urlencode


def _client_id() -> str:
    return os.getenv("WORKOS_CLIENT_ID") or ""


def _api_key() -> str:
    return os.getenv("WORKOS_API_KEY") or ""


def _redirect_uri() -> str:
    return os.getenv("WORKOS_REDIRECT_URI") or "https://shamiur-sunnyware.hf.space/auth/callback"


def enabled() -> bool:
    return bool(_client_id() and _api_key())


def get_authorize_url(provider: str = "GoogleOAuth") -> str:
    """Return WorkOS AuthKit authorize URL. Defaults to Google directly."""
    if not enabled():
        return ""
    params = {
        "client_id": _client_id(),
        "redirect_uri": _redirect_uri(),
        "response_type": "code",
        "provider": provider,
    }
    return f"https://api.workos.com/user_management/authorize?{urlencode(params)}"


async def authenticate_with_code(code: str) -> dict:
    """Exchange WorkOS authorization code for user profile."""
    if not enabled():
        return {"ok": False, "error": "WorkOS not configured"}
    if not code:
        return {"ok": False, "error": "code required"}
    try:
        async with httpx.AsyncClient(timeout=15.0) as cli:
            r = await cli.post(
                "https://api.workos.com/user_management/authenticate",
                json={
                    "client_id": _client_id(),
                    "client_secret": _api_key(),
                    "code": code,
                    "grant_type": "authorization_code",
                },
            )
            if r.status_code != 200:
                return {"ok": False, "error": r.text[:300]}
            data = r.json()
            user = data.get("user", {})
            email = (user.get("email") or "").lower().strip()
            if not email:
                return {"ok": False, "error": "no email in WorkOS response"}
            return {"ok": True, "email": email, "user_id": user.get("id", "")}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
