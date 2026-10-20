# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 224c: Overage billing routes."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from .. import overage_store as _ovg
from .. import usage as _usage
from .. import saas_store as _saas

router = APIRouter(tags=["overage"])


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
    if not _auth.has_role(_auth.role_for_key(key), "admin"):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return None


@router.get("/api/overage/config")
async def get_config(req: Request):
    d = _admin_only(req)
    if d: return d
    return {"config": _ovg.get_config(), "caps": _ovg.get_overage_caps()}


@router.patch("/api/overage/config")
async def update_config(req: Request):
    d = _admin_only(req)
    if d: return d
    try:
        body = await req.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    patch = {}
    if "rate_per_million" in body:
        try:
            patch["rate_per_million"] = float(body["rate_per_million"])
        except Exception:
            return JSONResponse({"error": "invalid rate"}, status_code=400)
    if "enabled" in body:
        patch["enabled"] = bool(body["enabled"])
    if patch:
        _ovg.update_config(patch)
    if "caps" in body and isinstance(body["caps"], dict):
        _ovg.update_overage_caps(body["caps"])
    return {"ok": True, "config": _ovg.get_config(), "caps": _ovg.get_overage_caps()}


@router.get("/api/overage/overview")
async def overview(req: Request):
    """Per-org overage summary for the current month."""
    d = _admin_only(req)
    if d: return d
    orgs = _saas.list_orgs() if hasattr(_saas, "list_orgs") else []
    # Fallback to direct read
    if not orgs:
        try:
            from .. import saas_store as _s
            orgs_data = _s._load("orgs.json", {}) if hasattr(_s, "_load") else {}
            orgs = list(orgs_data.values())
        except Exception:
            orgs = []
    plans = {}
    try:
        plans_data = _saas.list_plans() if hasattr(_saas, "list_plans") else []
        if not plans_data:
            from .. import saas_store as _s2
            plans_data = list(_s2._load("plans.json", {}).values()) if hasattr(_s2, "_load") else []
        for p in plans_data:
            plans[p.get("id")] = p
    except Exception:
        pass

    results = []
    total_overage_cost = 0.0
    total_overage_tokens = 0
    for org in orgs:
        org_id = org.get("id", "")
        plan_id = org.get("plan", "free")
        plan = plans.get(plan_id, {})
        token_limit_m = plan.get("token_limit_millions", 1)
        try:
            tokens_used = _usage.get_tokens(org_id) or 0
        except Exception:
            tokens_used = 0
        summary = _ovg.compute_overage(org_id, plan_id, token_limit_m, tokens_used)
        summary["org_id"] = org_id
        summary["org_name"] = org.get("name", "")
        summary["owner_email"] = org.get("owner_email", "")
        results.append(summary)
        total_overage_cost += summary.get("overage_cost", 0)
        total_overage_tokens += summary.get("overage_tokens", 0)

    results.sort(key=lambda x: x.get("overage_cost", 0), reverse=True)
    return {
        "count": len(results),
        "orgs": results,
        "total_overage_cost": round(total_overage_cost, 2),
        "total_overage_tokens": total_overage_tokens,
    }


@router.get("/api/overage/charges")
async def list_charges(req: Request, org_id: str = "", limit: int = 100):
    d = _admin_only(req)
    if d: return d
    charges = _ovg.list_charges(org_id=org_id, limit=min(limit, 500))
    total = sum(c.get("amount", 0) for c in charges)
    return {"count": len(charges), "charges": charges, "total_amount": round(total, 2)}


@router.delete("/api/overage/charges")
async def clear_charges(req: Request):
    d = _admin_only(req)
    if d: return d
    return {"ok": _ovg.clear_charges()}


@router.post("/api/overage/record-charge")
async def record_charge(req: Request):
    d = _admin_only(req)
    if d: return d
    try:
        body = await req.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    org_id = (body.get("org_id") or "").strip()
    tokens = int(body.get("tokens", 0))
    amount = float(body.get("amount", 0))
    note = (body.get("note") or "").strip()
    if not org_id:
        return JSONResponse({"error": "org_id required"}, status_code=400)
    org = _saas.get_org(org_id) if hasattr(_saas, "get_org") else None
    plan = (org or {}).get("plan", "")
    result = _ovg.record_charge(org_id, plan, tokens, amount, note)
    return {"ok": True, "charge": result}
