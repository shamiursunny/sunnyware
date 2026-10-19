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

    # Part 221a: fire user.login webhook
    try:
        from .. import webhooks_store as _ws
        _ws.fire_event("user.login", {"email": email})
    except Exception:
        pass

    # 1. Ensure SaaS Org exists for this user (free tier default)
    from .. import saas_store as s
    org = s.get_org_by_email(email)
    if not org:
        org = s.create_org(name=email.split("@")[0], plan="free", owner_email=email)

    # 2. Part 222: if 2FA is enabled, don't issue a full JWT yet.
    from .auth import _generate_jwt
    from .. import twofa_store as _tfs

    if _tfs.is_enabled(email):
        pending_token = _generate_jwt(email)
        return RedirectResponse(
            url=f"/ui?2fa=required&pending={pending_token}",
            status_code=302,
        )

    # 3. Normal flow — issue full JWT
    token = _generate_jwt(email)
    return RedirectResponse(url=f"/ui?token={token}", status_code=302)
