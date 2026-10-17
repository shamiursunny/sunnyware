# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 175: SSOReady client (httpx direct, no SDK dependency).

SSOReady REST API (verify paths against https://docs.ssoready.com if
they ever change — this is the only file that needs updating):

  POST {base}/saml/redirect
       body:   {"organization_external_id": "acme-corp"}
       return: {"redirect_url": "https://idp..."}

  POST {base}/saml/redeem
       body:   {"saml_access_code": "..."}
       return: {"email": "...", "organization_external_id": "...", ...}

Env:
  SSOREADY_API_KEY         (required to enable)
  SSOREADY_BASE_URL        (default https://api.ssoready.com/v1)
  SSOREADY_TIMEOUT_S       (default 10.0)
"""

import os
from typing import Optional


def _api_key() -> Optional[str]:
    k = (os.getenv("SSOREADY_API_KEY") or "").strip()
    return k or None


def _base() -> str:
    return (os.getenv("SSOREADY_BASE_URL")
            or "https://api.ssoready.com/v1").rstrip("/")


def _timeout() -> float:
    try:
        return float(os.getenv("SSOREADY_TIMEOUT_S", "10.0"))
    except Exception:
        return 10.0


def enabled() -> bool:
    return _api_key() is not None


async def get_redirect_url(org_external_id: str) -> dict:
    """Return {ok, redirect_url?, error?}."""
    if not enabled():
        return {"ok": False, "error": "SSOREADY_API_KEY not set"}
    if not org_external_id:
        return {"ok": False, "error": "organization_external_id required"}
    try:
        import httpx
        async with httpx.AsyncClient(timeout=_timeout()) as cli:
            r = await cli.post(
                _base() + "/saml/redirect",
                json={"organization_external_id": org_external_id},
                headers={
                    "Authorization": "Bearer " + _api_key(),
                    "Content-Type": "application/json",
                },
            )
            if r.status_code >= 400:
                return {
                    "ok": False,
                    "error": f"SSOReady HTTP {r.status_code}: "
                             f"{r.text[:200]}",
                }
            data = r.json()
            url = data.get("redirect_url") or data.get("redirectUrl")
            if not url:
                return {"ok": False,
                        "error": "SSOReady response missing redirect_url"}
            return {"ok": True, "redirect_url": url}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


async def redeem(saml_access_code: str) -> dict:
    """Return {ok, email?, org_id?, error?}."""
    if not enabled():
        return {"ok": False, "error": "SSOREADY_API_KEY not set"}
    if not saml_access_code:
        return {"ok": False, "error": "saml_access_code required"}
    try:
        import httpx
        async with httpx.AsyncClient(timeout=_timeout()) as cli:
            r = await cli.post(
                _base() + "/saml/redeem",
                json={"saml_access_code": saml_access_code},
                headers={
                    "Authorization": "Bearer " + _api_key(),
                    "Content-Type": "application/json",
                },
            )
            if r.status_code >= 400:
                return {
                    "ok": False,
                    "error": f"SSOReady HTTP {r.status_code}: "
                             f"{r.text[:200]}",
                }
            data = r.json()
            email = data.get("email") or ""
            org = (data.get("organization_external_id")
                   or data.get("organizationExternalId") or "")
            if not email:
                return {"ok": False,
                        "error": "SSOReady response missing email"}
            return {"ok": True, "email": email.lower(), "org_id": org}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def status() -> dict:
    return {
        "enabled": enabled(),
        "base_url": _base(),
        "has_key": _api_key() is not None,
    }
