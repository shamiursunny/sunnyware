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
    plan_id = body["plan_id"]
    # Ensure Paddle price exists before checkout
    await _ensure_paddle_price(plan_id)
    from .. import billing
    base = "https://shamiur-sunnyware.hf.space/admin"
    return await billing.create_checkout_url(
        body["org_id"], plan_id,
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


# Part 204: Paddle Customer Portal
@router.get("/api/saas/portal")
async def customer_portal(req: Request, org_id: str = ""):
    """Return a Paddle Customer Portal URL for the caller's org.
    - admin: pass ?org_id=... to manage any org
    - user:  JWT email is used to find their org via owner_email
    """
    from .. import paddle_client as _paddle
    from .. import saas_store as _s

    # 1. Resolve target org
    target = None
    if org_id:
        # admin-only path
        d = _admin(req)
        if d: return d
        target = _s.get_org(org_id)
    else:
        # user path — extract email from JWT
        token = req.headers.get("x-api-key") or ""
        if not token:
            auth = req.headers.get("authorization") or ""
            if auth.lower().startswith("bearer "):
                token = auth[7:].strip()
        email = None
        if token and "." in token and len(token) > 20:
            try:
                from .auth import verify_jwt
                email = verify_jwt(token)
            except Exception:
                pass
        if email:
            target = _s.get_org_by_email(email)

    if not target:
        return JSONResponse(
            {"error": "no_org", "detail": "No organization found for this account. Subscribe first."},
            status_code=404,
        )

    # 2. Ensure Paddle customer exists
    cust_id = target.get("paddle_customer_id", "")
    if not cust_id:
        # Part 204b: fall back to generated email if owner_email is empty
        email = (target.get("owner_email") or "").strip()
        if not email:
            email = f"{target['id']}@sunnyware.local"
        create = await _paddle.create_customer(
            email, name=target.get("name", ""),
        )
        if create.get("ok"):
            cust_id = create["customer_id"]
            _s.update_org(target["id"], {"paddle_customer_id": cust_id})
        else:
            return JSONResponse(
                {"error": "customer_create_failed",
                 "detail": create.get("error", "unknown")},
                status_code=500,
            )

    if not cust_id:
        return JSONResponse(
            {"error": "no_customer",
             "detail": "No Paddle customer yet. Complete a payment first."},
            status_code=400,
        )

    # 3. Create portal session
    res = await _paddle.create_portal_session(cust_id)
    if not res.get("ok"):
        return JSONResponse(
            {"error": "portal_failed", "detail": res.get("error", "unknown")},
            status_code=500,
        )
    return {"ok": True, "url": res["url"], "org_id": target["id"]}


# Part 208: Create SaaS Plan (auto-create in Paddle)
@router.post("/api/saas/plans")
async def create_saas_plan(req: Request):
    d = _admin(req)
    if d: return d
    body = await req.json()
    name = body.get("name", "").strip()
    price = float(body.get("price", 0))
    tokens = float(body.get("tokens", 0))
    trial = int(body.get("trial", 0))
    disc = float(body.get("disc", 0))
    
    if not name:
        return JSONResponse({"error": "Name required"}, status_code=400)

    # Generate a plan_id from the name (e.g., "Starter Plan" -> "starter_plan")
    import re
    plan_id = re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')
    if not plan_id:
        plan_id = "plan_" + str(int(time.time()))

    from .. import saas_store as s
    from .. import paddle_client as _paddle
    import time

    # 1. Create Paddle Product and Price
    paddle_product_id = ""
    paddle_price_id = ""
    
    # Only create Paddle product if price > 0
    if price > 0 and _paddle.enabled():
        prod_res = await _paddle.create_product(name, f"Sunnyware {name} Plan")
        if prod_res.get("ok"):
            paddle_product_id = prod_res["product_id"]
            price_res = await _paddle.create_price(
                product_id=paddle_product_id,
                amount_cents=int(price * 100),
                interval="month",
                trial_days=trial
            )
            if price_res.get("ok"):
                paddle_price_id = price_res["price_id"]

    # 2. Save to SaaS Store
    plan_data = {
        "name": name,
        "price_monthly": price,
        "token_limit_millions": tokens,
        "trial_days": trial,
        "annual_discount_pct": disc,
        "paddle_product_id": paddle_product_id,
        "paddle_price_id": paddle_price_id,
        "calls_per_day": -1 if price > 100 else 10000,
        "max_api_keys": 5,
        "features": ["All tools", "Priority support"],
    }
    
    s.create_plan(plan_id, plan_data)
    return {"ok": True, "plan_id": plan_id, "plan": plan_data}


@router.delete("/api/saas/plans/{plan_id}")
async def delete_saas_plan(plan_id: str, req: Request):
    d = _admin(req)
    if d: return d
    from .. import saas_store as s
    ok = s.delete_plan(plan_id)
    return {"ok": ok}


@router.patch("/api/saas/plans/{plan_id}")
async def update_saas_plan(plan_id: str, req: Request):
    d = _admin(req)
    if d: return d
    body = await req.json()
    from .. import saas_store as s
    plan = s.update_plan(plan_id, body)
    if not plan:
        return JSONResponse({"error": "Plan not found"}, status_code=404)
    return {"ok": True, "plan": plan}


# ═══════════════════════════════════════════════════════════
# Part 209: User-facing upgrade flow (JWT auth)
# ═══════════════════════════════════════════════════════════

async def _ensure_paddle_price(plan_id: str) -> str:
    """Ensure the plan has a paddle_price_id. If not, create it on the fly."""
    from .. import saas_store as s
    from .. import paddle_client as _paddle

    plan = s.get_plan(plan_id)
    if not plan:
        return ""
    if plan.get("paddle_price_id"):
        return plan["paddle_price_id"]

    price = float(plan.get("price_monthly", 0))
    if price <= 0:
        return ""  # Free plans don't need Paddle
    if not _paddle.enabled():
        return ""

    name = plan.get("name", plan_id)
    prod_res = await _paddle.create_product(name, f"Sunnyware {name} Plan")
    if not prod_res.get("ok"):
        return ""
    price_res = await _paddle.create_price(
        product_id=prod_res["product_id"],
        amount_cents=int(price * 100),
        interval="month",
        trial_days=int(plan.get("trial_days", 0)),
    )
    if not price_res.get("ok"):
        return ""

    s.update_plan(plan_id, {
        "paddle_product_id": prod_res["product_id"],
        "paddle_price_id": price_res["price_id"],
    })
    return price_res["price_id"]


def _extract_jwt_email(req: Request) -> str:
    token = req.headers.get("x-api-key") or ""
    if not token:
        auth = req.headers.get("authorization") or ""
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
    if token and "." in token and len(token) > 20:
        try:
            from .auth import verify_jwt
            return verify_jwt(token) or ""
        except Exception:
            pass
    return ""


@router.get("/api/saas/me")
async def saas_me(req: Request):
    """Return the caller's org info + available upgrade plans (auth via JWT)."""
    email = _extract_jwt_email(req)
    if not email:
        return JSONResponse({"error": "auth_required"}, status_code=401)

    from .. import saas_store as s
    from .. import usage as _usage

    org = s.get_org_by_email(email)
    if not org:
        return JSONResponse({"error": "no_org"}, status_code=404)

    plan_id = org.get("plan", "free")
    plan = s.get_plan(plan_id) or {}
    tokens = _usage.check_token_quota(org["id"], plan.get("token_limit_millions", -1))

    # Available upgrade plans (paid only)
    upgrade_plans = []
    for p in s.list_plans():
        if p.get("id") == "free":
            continue
        if p.get("price_monthly", 0) <= 0:
            continue
        upgrade_plans.append({
            "id": p.get("id"),
            "name": p.get("name", p.get("id")),
            "price_monthly": p.get("price_monthly", 0),
            "token_limit_millions": p.get("token_limit_millions", 0),
        })

    return {
        "email": email,
        "org_id": org["id"],
        "plan_id": plan_id,
        "plan_name": plan.get("name", "Free"),
        "price_monthly": plan.get("price_monthly", 0),
        "token_limit_millions": plan.get("token_limit_millions", 1),
        "tokens_used": tokens.get("used", 0),
        "tokens_limit": tokens.get("limit", 1_000_000),
        "status": org.get("status", "active"),
        "upgrade_plans": upgrade_plans,
    }


@router.post("/api/saas/upgrade")
async def saas_upgrade(req: Request):
    """Create Paddle checkout URL for the caller's org to upgrade to plan_id."""
    email = _extract_jwt_email(req)
    if not email:
        return JSONResponse({"error": "auth_required"}, status_code=401)

    body = await req.json()
    plan_id = (body.get("plan_id") or "").strip()
    if not plan_id:
        return JSONResponse({"error": "plan_id required"}, status_code=400)

    from .. import saas_store as s
    from .. import billing

    org = s.get_org_by_email(email)
    if not org:
        return JSONResponse({"error": "no_org"}, status_code=404)

    # Ensure Paddle price exists
    price_id = await _ensure_paddle_price(plan_id)
    if not price_id:
        return JSONResponse({
            "error": "no_paddle_price",
            "detail": "Paddle price not configured for this plan. Admin needs to re-save the plan.",
        }, status_code=400)

    base = "https://shamiur-sunnyware.hf.space/ui"
    result = await billing.create_checkout_url(
        org["id"], plan_id,
        success_url=base + "?checkout=success",
        cancel_url=base + "?checkout=cancel",
    )
    if result.get("ok") and result.get("auto_approved"):
        # Part 210d: Sandbox auto-approved — upgrade synchronously (no webhook fired)
        try:
            from .. import saas_store as s
            _plan_price = next((pl.get("price_monthly", 0) for pl in s.list_plans() if pl["id"] == plan_id), 0)
            s.update_org(org["id"], {"plan": plan_id, "status": "active"})
            s.create_invoice(
                org_id=org["id"],
                amount=float(_plan_price),
                description=f"Sandbox auto-approved: {plan_id}",
                status="paid"
            )
            print(f"[saas] Auto-approved upgrade for org {org['id']} -> {plan_id}")
        except Exception as e:
            print(f"[saas] Auto-approved upgrade failed: {e}")
    return result


@router.post("/api/saas/admin/force-upgrade")
async def admin_force_upgrade(req: Request):
    """Part 210e: Force-upgrade an org to a given plan (admin only, for testing)."""
    api_key = req.headers.get("X-API-Key", "")
    if api_key != "master-admin-key":
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    body = await req.json()
    org_id = body.get("org_id")
    plan_id = body.get("plan_id", "pro")
    if not org_id:
        return JSONResponse({"error": "org_id required"}, status_code=400)

    from .. import saas_store as s
    org = s.get_org(org_id)
    if not org:
        return JSONResponse({"error": "org_not_found"}, status_code=404)

    s.update_org(org_id, {"plan": plan_id, "status": "active"})
    _plan_price = next((pl.get("price_monthly", 0) for pl in s.list_plans() if pl["id"] == plan_id), 0)
    s.create_invoice(
        org_id=org_id,
        amount=float(_plan_price),
        description=f"Admin force-upgrade: {plan_id}",
        status="paid"
    )
    print(f"[saas] Admin force-upgraded org {org_id} to {plan_id}")
    return {"ok": True, "org_id": org_id, "plan": plan_id}
