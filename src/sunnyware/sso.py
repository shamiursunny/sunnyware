# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 176: Scalekit SSO client.

Replaces SSOReady (Part 175) with Scalekit's OIDC-based SSO.
The routes and user_store from Part 175 are unchanged.
"""

import os
from typing import Optional
from urllib.parse import urlencode


def _env_url() -> str:
    return (os.getenv("SCALEKIT_ENVIRONMENT_URL") or "").rstrip("/")


def _client_id() -> str:
    return os.getenv("SCALEKIT_CLIENT_ID") or ""


def _client_secret() -> str:
    return os.getenv("SCALEKIT_CLIENT_SECRET") or ""


def _callback() -> str:
    return (os.getenv("SCALEKIT_CALLBACK_URL")
            or "https://shamiur-sunnyware.hf.space/sso/callback")


def enabled() -> bool:
    return bool(_env_url() and _client_id() and _client_secret())


async def get_redirect_url(org_id: str) -> dict:
    """Return {ok, redirect_url?, error?}."""
    if not enabled():
        return {"ok": False, "error": "SCALEKIT env vars not set"}
    if not org_id:
        return {"ok": False, "error": "organization_id required"}
    params = {
        "client_id": _client_id(),
        "redirect_uri": _callback(),
        "response_type": "code",
        "scope": "openid profile email",
        "organization_id": org_id,
        "state": org_id,
    }
    url = _env_url() + "/api/v1/sso/authorize?" + urlencode(params)
    return {"ok": True, "redirect_url": url}


async def redeem(code: str) -> dict:
    """Return {ok, email?, org_id?, error?}."""
    if not enabled():
        return {"ok": False, "error": "SCALEKIT env vars not set"}
    if not code:
        return {"ok": False, "error": "code required"}
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as cli:
            # 1. Exchange authorization code for access token
            token_resp = await cli.post(
                _env_url() + "/api/v1/sso/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": _client_id(),
                    "client_secret": _client_secret(),
                    "redirect_uri": _callback(),
                },
            )
            if token_resp.status_code != 200:
                return {"ok": False,
                        "error": "token error: " + token_resp.text[:200]}
            token = token_resp.json().get("access_token")
            if not token:
                return {"ok": False, "error": "no access_token in response"}

            # 2. Fetch user info
            ui_resp = await cli.get(
                _env_url() + "/api/v1/sso/userinfo",
                headers={"Authorization": "Bearer " + token},
            )
            if ui_resp.status_code != 200:
                return {"ok": False,
                        "error": "userinfo error: " + ui_resp.text[:200]}
            ui = ui_resp.json()
            email = (ui.get("email") or "").lower()
            if not email:
                return {"ok": False, "error": "no email in userinfo"}
            return {
                "ok": True,
                "email": email,
                "org_id": ui.get("organization_id", ""),
            }
    except Exception as e:
        return {"ok": False, "error": type(e).__name__ + ": " + str(e)}


def status() -> dict:
    return {
        "enabled": enabled(),
        "base_url": _env_url(),
        "has_client_id": bool(_client_id()),
        "has_secret": bool(_client_secret()),
    }
