# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 182: SaaS Control Plane API."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["saas"])

def _admin(req: Request):
    try:
        from .. import auth as _auth
    except Exception:
        return JSONResponse({"error": "auth unavailable"}, status_code=500)
    if not _auth.auth_enabled():
        return None
    key = req.headers.get("x-api-key") or ""
    if not key:
        authz = req.headers.get("authorization") or ""
        if authz.lower().startswith("bearer "):
            key = authz[7:].strip()
    if not key or not _auth.is_valid_key(key):
        return JSONResponse({"error": "auth_required"}, status_code=401)
    if not _auth.has_role(_auth.role_for_key(key), "admin"):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return None

@router.get("/api/saas/dashboard")
async def dashboard(req: Request):
    d = _admin(req)
    if d: return d
    from .. import saas_store as s
    return s.dashboard_stats()

@router.get("/api/saas/orgs")
async def list_orgs(req: Request):
    d = _admin(req)
    if d: return d
    from .. import saas_store as s
    return {"count": len(s.list_orgs()), "orgs": s.list_orgs()}

@router.post("/api/saas/orgs")
async def create_org(req: Request):
    d = _admin(req)
    if d: return d
    body = await req.json()
    from .. import saas_store as s
    org = s.create_org(name=body.get("name", "Untitled"), plan=body.get("plan", "free"), owner_email=body.get("owner_email", ""))
    return {"ok": True, "org": org}

@router.patch("/api/saas/orgs/{org_id}")
async def update_org(org_id: str, req: Request):
    d = _admin(req)
    if d: return d
    body = await req.json()
    from .. import saas_store as s
    org = s.update_org(org_id, body)
    if not org:
        return JSONResponse({"error": "not found"}, status_code=404)
    return {"ok": True, "org": org}

@router.delete("/api/saas/orgs/{org_id}")
async def delete_org(org_id: str, req: Request):
    d = _admin(req)
    if d: return d
    from .. import saas_store as s
    return {"ok": s.delete_org(org_id)}

@router.get("/api/saas/plans")
async def list_plans(req: Request):
    d = _admin(req)
    if d: return d
    from .. import saas_store as s
    return {"plans": s.list_plans()}

@router.get("/api/saas/invoices")
async def list_invoices(req: Request):
    d = _admin(req)
    if d: return d
    from .. import saas_store as s
    return {"count": len(s.list_invoices()), "invoices": s.list_invoices()}

@router.get("/api/saas/notes")
async def list_notes(req: Request, org_id: str = ""):
    d = _admin(req)
    if d: return d
    from .. import saas_store as s
    return {"notes": s.list_notes(org_id or None)}

@router.post("/api/saas/notes")
async def create_note(req: Request):
    d = _admin(req)
    if d: return d
    body = await req.json()
    from .. import saas_store as s
    return {"ok": True, "note": s.create_note(body["org_id"], body["text"])}

@router.get("/api/saas/billing/status")
async def billing_status(req: Request):
    d = _admin(req)
    if d: return d
    from .. import billing
    return billing.status()

@router.post("/api/saas/checkout")
async def checkout(req: Request):
    d = _admin(req)
    if d: return d
    body = await req.json()
    from .. import billing
    base = "https://shamiur-sunnyware.hf.space/admin"
    return await billing.create_checkout_url(
        body["org_id"], body["plan_id"],
        body.get("success_url", base + "?checkout=success"),
        body.get("cancel_url", base + "?checkout=cancel"),
    )


# Part 203: Bulk usage summary for admin dashboard
@router.get("/api/saas/usage/summary")
async def usage_summary(req: Request):
    d = _admin(req)
    if d: return d
    from .. import usage as _usage
    from .. import saas_store as s
    orgs = s.list_orgs()
    plans = {pp["id"]: pp for pp in s.list_plans()}
    out = []
    for org in orgs:
        plan = plans.get(org.get("plan", "free"), {})
        org_id = org["id"]
        calls = _usage.check_quota(org_id, plan.get("calls_per_day", 100))
        tokens = _usage.check_token_quota(org_id, plan.get("token_limit_millions", -1))
        out.append({
            "org_id": org_id,
            "name": org.get("name", ""),
            "plan": org.get("plan", "free"),
            "calls": calls,
            "tokens": tokens,
        })
    return {"orgs": out}
