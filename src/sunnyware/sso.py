# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 177: WorkOS SSO client."""

import os
from urllib.parse import urlencode


def _client_id() -> str:
    return os.getenv("WORKOS_CLIENT_ID") or ""


def _api_key() -> str:
    return os.getenv("WORKOS_API_KEY") or ""


def _base_url() -> str:
    return "https://api.workos.com"


def enabled() -> bool:
    return bool(_client_id() and _api_key())


async def get_redirect_url(org_id: str) -> dict:
    if not enabled():
        return {"ok": False, "error": "WorkOS env vars not set"}
    if not org_id:
        return {"ok": False, "error": "organization_id required"}

    params = {
        "client_id": _client_id(),
        "redirect_uri": "https://shamiur-sunnyware.hf.space/sso/callback",
        "response_type": "code",
        "organization": org_id,  # WorkOS requires "organization", not "organization_id"
    }
    url = f"{_base_url()}/sso/authorize?{urlencode(params)}"
    return {"ok": True, "redirect_url": url}


async def redeem(code: str) -> dict:
    if not enabled():
        return {"ok": False, "error": "WorkOS env vars not set"}
    if not code:
        return {"ok": False, "error": "code required"}

    try:
        import httpx
        async with httpx.AsyncClient(timeout=15.0) as cli:
            token_resp = await cli.post(
                f"{_base_url()}/sso/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": _client_id(),
                    "client_secret": _api_key(),
                    "redirect_uri": "https://shamiur-sunnyware.hf.space/sso/callback",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if token_resp.status_code != 200:
                return {"ok": False, "error": f"token error: {token_resp.text}"}

            token_data = token_resp.json()
            # WorkOS returns the profile object directly inside the token response
            profile = token_data.get("profile") or {}
            email = (profile.get("email") or "").lower()
            
            if not email:
                return {"ok": False, "error": "no email in token response"}
                
            org_id = profile.get("organization_id") or ""

            return {"ok": True, "email": email, "org_id": org_id}

    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)}"}


def status() -> dict:
    return {
        "enabled": enabled(),
        "provider": "workos",
        "has_client_id": bool(_client_id()),
        "has_api_key": bool(_api_key()),
    }
