# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 176: Scalekit SSO client (OIDC).

Uses Scalekit's OAuth 2.0 / OIDC endpoints:
  - Authorization: /oauth/authorize
  - Token exchange: /oauth/token
  - User info: /userinfo
"""

import os
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
        "scope": "openid email profile",
        "state": org_id,
    }

    # Prefer connection_id if configured (highest precedence in Scalekit)
    conn_id = os.getenv("SCALEKIT_CONNECTION_ID")
    if conn_id:
        params["connection_id"] = conn_id
    else:
        params["organization_id"] = org_id
    # Correct endpoint: /oauth/authorize (not /api/v1/sso/authorize)
    url = _env_url() + "/oauth/authorize?" + urlencode(params)
    return {"ok": True, "redirect_url": url}


async def redeem(code: str) -> dict:
    """Return {ok, email?, org_id?, error?}."""
    if not enabled():
        return {"ok": False, "error": "SCALEKIT env vars not set"}
    if not code:
        return {"ok": False, "error": "code required"}

    try:
        import httpx
        async with httpx.AsyncClient(timeout=15.0) as cli:
            # 1. Exchange code for tokens at /oauth/token
            token_resp = await cli.post(
                _env_url() + "/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": _client_id(),
                    "client_secret": _client_secret(),
                    "redirect_uri": _callback(),
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if token_resp.status_code != 200:
                return {"ok": False,
                        "error": "token error: " + token_resp.text[:300]}

            token_data = token_resp.json()
            access_token = token_data.get("access_token")
            if not access_token:
                return {"ok": False, "error": "no access_token in response"}

            # 2. Fetch user info at /userinfo
            ui_resp = await cli.get(
                _env_url() + "/userinfo",
                headers={"Authorization": "Bearer " + access_token},
            )
            if ui_resp.status_code != 200:
                return {"ok": False,
                        "error": "userinfo error: " + ui_resp.text[:300]}

            ui = ui_resp.json()
            email = (ui.get("email") or "").lower()
            if not email:
                return {"ok": False, "error": "no email in userinfo"}

            # Scalekit may return org_id in the userinfo or id_token
            org_id = ui.get("organization_id") or ui.get("org_id") or ""
            return {"ok": True, "email": email, "org_id": org_id}

    except Exception as e:
        return {"ok": False, "error": type(e).__name__ + ": " + str(e)}


def status() -> dict:
    return {
        "enabled": enabled(),
        "base_url": _env_url(),
        "has_client_id": bool(_client_id()),
        "has_secret": bool(_client_secret()),
    }
