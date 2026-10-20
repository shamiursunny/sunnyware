# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 211: Team management routes."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from .. import team_store as _team
from .. import invite_store as _inv

router = APIRouter(tags=["team"])


def _admin_only(req: Request):
    from .. import auth as _auth
    key = req.headers.get("x-api-key") or ""
    if not key:
        authz = req.headers.get("authorization") or ""
        if authz.lower().startswith("bearer "):
            key = authz[7:].strip()
    if not _auth.auth_enabled():
        return None
    if not key or not _auth.is_valid_key(key):
        return JSONResponse({"error": "auth_required"}, status_code=401)
        
    # Part 234: Allow JWT users if they are in team_store
    if key.startswith("user:"):
        email = key.split(":", 1)[1]
        from .. import team_store as _ts
        member = _ts.get_member_by_email(email)
        if member:
            return None  # Let them pass
            
    role = _auth.role_for_key(key)
    if not _auth.has_role(role, "admin"):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return None
    if not key or not _auth.is_valid_key(key):
        return JSONResponse({"error": "auth_required"}, status_code=401)
    role = _auth.role_for_key(key)
    if not _auth.has_role(role, "admin"):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return None


@router.get("/api/team/members")
async def list_members(req: Request):
    d = _admin_only(req)
    if d: return d
    return {"count": len(_team.list_members()), "members": _team.list_members()}


@router.post("/api/team/members")
async def add_member(req: Request):
    d = _admin_only(req)
    if d: return d
    body = await req.json()
    email = (body.get("email") or "").strip().lower()
    name = (body.get("name") or "").strip()
    role = (body.get("role") or "Viewer").strip()
    if not email or "@" not in email:
        return JSONResponse({"error": "Valid email required"}, status_code=400)
    if _team.get_member_by_email(email):
        return JSONResponse({"error": "Member with this email already exists"}, status_code=400)
    member = _team.add_member(email, name, role, added_by="admin")

    # Part 233: Generate magic link and send email
    invite = _inv.create_invite(email, role)
    base_url = "https://shamiur-sunnyware.hf.space"
    accept_url = f"{base_url}/invite?token={invite['token']}"
    
    html = f"""
    <h2>You've been invited to Sunnyware</h2>
    <p>You have been invited to join the team as a <strong>{role}</strong>.</p>
    <p><a href="{accept_url}" style="display:inline-block;background:#3b82f6;color:#fff;padding:10px 20px;text-decoration:none;border-radius:6px;">Join Team</a></p>
    <p>If the button doesn't work, copy and paste this link:<br><code>{accept_url}</code></p>
    """
    
    return {"ok": True, "member": member, "accept_url": accept_url, "email_sent": False}


@router.patch("/api/team/members/{member_id}")
async def update_member(member_id: str, req: Request):
    d = _admin_only(req)
    if d: return d
    body = await req.json()
    patch = {}
    if "role" in body: patch["role"] = body["role"]
    if "name" in body: patch["name"] = body["name"]
    if "status" in body: patch["status"] = body["status"]
    updated = _team.update_member(member_id, patch)
    if not updated:
        return JSONResponse({"error": "Member not found"}, status_code=404)
    return {"ok": True, "member": updated}


@router.delete("/api/team/members/{member_id}")
async def delete_member(member_id: str, req: Request):
    d = _admin_only(req)
    if d: return d
    ok = _team.delete_member(member_id)
    return {"ok": ok}


@router.get("/api/team/activity")
async def list_activity(req: Request, limit: int = 200, user: str = "", action: str = ""):
    d = _admin_only(req)
    if d: return d
    items = _team.list_activity(limit=limit, user=user, action_filter=action)
    return {"count": len(items), "activity": items}


@router.delete("/api/team/activity")
async def clear_activity(req: Request):
    d = _admin_only(req)
    if d: return d
    ok = _team.clear_activity()
    return {"ok": ok}


@router.get("/invite")
async def accept_invite(token: str):
    invite = _inv.get_invite(token)
    if not invite:
        return JSONResponse({"error": "invalid_or_expired"}, status_code=400)
    
    from ..routes.auth import _generate_jwt
    jwt_token = _generate_jwt(invite["email"])
    
    # Mark invite as used
    _inv.delete_invite(token)
    
    # Redirect to UI with token
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/admin?invite_token={jwt_token}&email={invite['email']}")


# ── Part 237: Explicit Invite Endpoints (completing the API surface) ──

@router.post("/api/team/invite")
async def create_invite(req: Request):
    """Send a magic link invite to an email without adding them as a member immediately."""
    d = _admin_only(req)
    if d: return d
    try:
        body = await req.json()
        email = (body.get("email") or "").strip().lower()
        role = (body.get("role") or "Viewer").strip()
        name = (body.get("name") or "").strip()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    if not email or "@" not in email:
        return JSONResponse({"error": "Valid email required"}, status_code=400)

    from .. import invite_store as _inv
    invite = _inv.create_invite(email, role)
    base_url = "https://shamiur-sunnyware.hf.space"
    accept_url = f"{base_url}/invite?token={invite['token']}"

    return {"ok": True, "accept_url": accept_url, "invite": invite}


@router.get("/api/team/invites")
async def list_invites(req: Request):
    """List all pending invites."""
    d = _admin_only(req)
    if d: return d
    from .. import invite_store as _inv
    # Reuse the existing store
    invites = _inv._load()
    return {"count": len(invites), "invites": list(invites.values())}


@router.get("/api/team/org-members")
async def list_org_members(req: Request, org_id: str = ""):
    """List members filtered by org_id (or all if empty)."""
    d = _admin_only(req)
    if d: return d
    members = _team.list_members()
    if org_id:
        members = [m for m in members if m.get("org_id") == org_id]
    return {"count": len(members), "members": members}


@router.delete("/api/team/org-members/{email}")
async def remove_org_member_by_email(email: str, req: Request):
    """Remove a member by email address."""
    d = _admin_only(req)
    if d: return d
    member = _team.get_member_by_email(email)
    if not member:
        return JSONResponse({"error": "Member not found"}, status_code=404)
    ok = _team.delete_member(member["id"])
    return {"ok": ok}


@router.patch("/api/team/org-members/{email}/role")
async def update_org_member_role_by_email(email: str, req: Request):
    """Update a member's role using their email address."""
    d = _admin_only(req)
    if d: return d
    try:
        body = await req.json()
        role = (body.get("role") or "Viewer").strip()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
        
    member = _team.get_member_by_email(email)
    if not member:
        return JSONResponse({"error": "Member not found"}, status_code=404)
        
    updated = _team.update_member(member["id"], {"role": role})
    return {"ok": True, "member": updated}
