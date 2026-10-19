# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 206: AuthKit (Google OAuth) routes."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse, RedirectResponse

router = APIRouter(tags=["authkit"])


@router.get("/auth/google")
async def auth_google():
    """Redirect user to WorkOS AuthKit for Google login."""
    from .. import workos_auth
    url = workos_auth.get_authorize_url(provider="GoogleOAuth")
    if not url:
        return JSONResponse({"error": "WorkOS not configured"}, status_code=501)
    return RedirectResponse(url, status_code=302)


@router.get("/auth/callback")
async def auth_callback(code: str = ""):
    """Handle WorkOS redirect, issue JWT, send user to /ui."""
    if not code:
        return JSONResponse({"error": "missing code"}, status_code=400)

    from .. import workos_auth
    result = await workos_auth.authenticate_with_code(code)
    if not result.get("ok"):
        return JSONResponse({"error": result.get("error", "auth_failed")}, status_code=400)

    email = result["email"]

    # 1. Ensure SaaS Org exists for this user (free tier default)
    from .. import saas_store as s
    org = s.get_org_by_email(email)
    if not org:
        org = s.create_org(name=email.split("@")[0], plan="free", owner_email=email)

    # 2. Issue our JWT (uses existing Part 196 _generate_jwt)
    from .auth import _generate_jwt
    token = _generate_jwt(email)

    # 3. Redirect back to UI with token
    return RedirectResponse(url=f"/ui?token={token}", status_code=302)
