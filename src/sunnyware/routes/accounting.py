# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 188: Accounting / Ledgerly API routes."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["accounting"])


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


# ─── Full State ───
@router.get("/api/acc/state")
async def acc_state(req: Request):
    d = _admin(req)
    if d: return d
    from .. import accounting_store as a
    a.sync_from_saas()
    return a.get_state()


@router.post("/api/acc/sync")
async def acc_sync(req: Request):
    d = _admin(req)
    if d: return d
    from .. import accounting_store as a
    a.sync_from_saas()
    return {"ok": True, "state": a.get_state()}


@router.post("/api/acc/reset")
async def acc_reset(req: Request):
    d = _admin(req)
    if d: return d
    from .. import accounting_store as a
    return {"ok": True, "state": a.reset_empty()}


# ─── Dashboard / P&L ───
@router.get("/api/acc/dashboard")
async def acc_dashboard(req: Request):
    d = _admin(req)
    if d: return d
    from .. import accounting_store as a
    return a.dashboard()


@router.get("/api/acc/pnl")
async def acc_pnl(req: Request):
    d = _admin(req)
    if d: return d
    from .. import accounting_store as a
    return a.pnl()


# ─── Customers ───
@router.get("/api/acc/customers")
async def acc_customers(req: Request):
    d = _admin(req)
    if d: return d
    from .. import accounting_store as a
    return {"customers": a.list_customers()}


@router.post("/api/acc/customers")
async def acc_create_customer(req: Request):
    d = _admin(req)
    if d: return d
    body = await req.json()
    from .. import accounting_store as a
    return {"ok": True, "customer": a.create_customer(
        body["name"], body.get("plan", "starter"), body.get("status", "trial"))}


@router.patch("/api/acc/customers/{cid}")
async def acc_update_customer(cid: int, req: Request):
    d = _admin(req)
    if d: return d
    body = await req.json()
    from .. import accounting_store as a
    c = a.update_customer(cid, body)
    return {"ok": bool(c), "customer": c}


@router.delete("/api/acc/customers/{cid}")
async def acc_delete_customer(cid: int, req: Request):
    d = _admin(req)
    if d: return d
    from .. import accounting_store as a
    return {"ok": a.delete_customer(cid)}


# ─── Plans ───
@router.get("/api/acc/plans")
async def acc_plans(req: Request):
    d = _admin(req)
    if d: return d
    from .. import accounting_store as a
    return {"plans": a.list_plans()}


@router.post("/api/acc/plans")
async def acc_upsert_plan(req: Request):
    d = _admin(req)
    if d: return d
    body = await req.json()
    from .. import accounting_store as a
    return {"ok": True, "plan": a.upsert_plan(body)}


@router.delete("/api/acc/plans/{plan_id}")
async def acc_delete_plan(plan_id: str, req: Request):
    d = _admin(req)
    if d: return d
    from .. import accounting_store as a
    return {"ok": a.delete_plan(plan_id)}


# ─── Invoices ───
@router.get("/api/acc/invoices")
async def acc_invoices(req: Request):
    d = _admin(req)
    if d: return d
    from .. import accounting_store as a
    return {"invoices": a.list_invoices()}


@router.post("/api/acc/invoices")
async def acc_create_invoice(req: Request):
    d = _admin(req)
    if d: return d
    body = await req.json()
    from .. import accounting_store as a
    return {"ok": True, "invoice": a.create_invoice(
        body["customer_id"], float(body["amount"]), float(body.get("tax", 18)),
        body.get("status", "due"), body.get("coupon", ""))}


@router.post("/api/acc/invoices/{inv_no}/paid")
async def acc_invoice_paid(inv_no: str, req: Request):
    d = _admin(req)
    if d: return d
    from .. import accounting_store as a
    return {"ok": True, "invoice": a.mark_invoice_paid(inv_no)}


@router.post("/api/acc/invoices/{inv_no}/refund")
async def acc_invoice_refund(inv_no: str, req: Request):
    d = _admin(req)
    if d: return d
    from .. import accounting_store as a
    return {"ok": True, "invoice": a.refund_invoice(inv_no)}


# ─── Ledger ───
@router.get("/api/acc/ledger")
async def acc_ledger(req: Request):
    d = _admin(req)
    if d: return d
    from .. import accounting_store as a
    return {"entries": a.list_ledger()}


@router.post("/api/acc/ledger")
async def acc_add_ledger(req: Request):
    d = _admin(req)
    if d: return d
    body = await req.json()
    from .. import accounting_store as a
    amt = float(body["amount"])
    if body.get("type") != "Revenue":
        amt = -amt
    return {"ok": True, "entry": a.add_ledger_entry(
        body["type"], body.get("desc", body["type"]), amt)}


# ─── Costs ───
@router.get("/api/acc/costs")
async def acc_costs(req: Request):
    d = _admin(req)
    if d: return d
    from .. import accounting_store as a
    return {"costs": a.list_costs()}


@router.post("/api/acc/costs")
async def acc_create_cost(req: Request):
    d = _admin(req)
    if d: return d
    body = await req.json()
    from .. import accounting_store as a
    return {"ok": True, "cost": a.create_cost(
        body["name"], body.get("cat", "Other"), float(body["amount"]),
        body.get("freq", "month"), body.get("start", ""), int(body.get("life", 0)))}


@router.delete("/api/acc/costs/{cid}")
async def acc_delete_cost(cid: int, req: Request):
    d = _admin(req)
    if d: return d
    from .. import accounting_store as a
    return {"ok": a.delete_cost(cid)}


# ─── Capital ───
@router.get("/api/acc/capital")
async def acc_capital(req: Request):
    d = _admin(req)
    if d: return d
    from .. import accounting_store as a
    return {"entries": a.list_capital()}


@router.post("/api/acc/capital")
async def acc_create_capital(req: Request):
    d = _admin(req)
    if d: return d
    body = await req.json()
    from .. import accounting_store as a
    return {"ok": True, "entry": a.create_capital(
        body["type"], body.get("name", ""), float(body["amount"]),
        body.get("date", ""), float(body.get("rate", 0)))}


@router.delete("/api/acc/capital/{cid}")
async def acc_delete_capital(cid: int, req: Request):
    d = _admin(req)
    if d: return d
    from .. import accounting_store as a
    return {"ok": a.delete_capital(cid)}


# ─── Compliance ───
@router.get("/api/acc/compliance")
async def acc_compliance(req: Request):
    d = _admin(req)
    if d: return d
    from .. import accounting_store as a
    return {"items": a.list_compliance()}


@router.post("/api/acc/compliance")
async def acc_create_compliance(req: Request):
    d = _admin(req)
    if d: return d
    body = await req.json()
    from .. import accounting_store as a
    return {"ok": True, "item": a.create_compliance(
        body["name"], body.get("area", "Tax"), body.get("freq", "year"),
        body["due"])}


@router.post("/api/acc/compliance/{cid}/filed")
async def acc_mark_filed(cid: int, req: Request):
    d = _admin(req)
    if d: return d
    from .. import accounting_store as a
    return {"ok": True, "item": a.mark_compliance_filed(cid)}


@router.delete("/api/acc/compliance/{cid}")
async def acc_delete_compliance(cid: int, req: Request):
    d = _admin(req)
    if d: return d
    from .. import accounting_store as a
    return {"ok": a.delete_compliance(cid)}


# ─── Coupons ───
@router.get("/api/acc/coupons")
async def acc_coupons(req: Request):
    d = _admin(req)
    if d: return d
    from .. import accounting_store as a
    return {"coupons": a.list_coupons()}


@router.post("/api/acc/coupons")
async def acc_create_coupon(req: Request):
    d = _admin(req)
    if d: return d
    body = await req.json()
    from .. import accounting_store as a
    return {"ok": True, "coupon": a.create_coupon(
        body["code"], body.get("type", "pct"), float(body["val"]),
        body.get("plans", []), int(body.get("max", 0)), body.get("exp", ""))}


@router.post("/api/acc/coupons/{code}/toggle")
async def acc_toggle_coupon(code: str, req: Request):
    d = _admin(req)
    if d: return d
    from .. import accounting_store as a
    return {"ok": True, "coupon": a.toggle_coupon(code)}


@router.delete("/api/acc/coupons/{code}")
async def acc_delete_coupon(code: str, req: Request):
    d = _admin(req)
    if d: return d
    from .. import accounting_store as a
    return {"ok": a.delete_coupon(code)}


# ─── Dunning ───
@router.get("/api/acc/dunning")
async def acc_dunning(req: Request):
    d = _admin(req)
    if d: return d
    from .. import accounting_store as a
    return {"failed": a.list_dunning()}


@router.post("/api/acc/dunning/{idx}/retry")
async def acc_dunning_retry(idx: int, req: Request):
    d = _admin(req)
    if d: return d
    from .. import accounting_store as a
    return {"ok": True, "result": a.retry_dunning(idx)}


@router.post("/api/acc/dunning/{idx}/advance")
async def acc_dunning_advance(idx: int, req: Request):
    d = _admin(req)
    if d: return d
    from .. import accounting_store as a
    return {"ok": True, "failed": a.advance_dunning(idx)}


# ─── Entitlements ───
@router.get("/api/acc/entitlements")
async def acc_entitlements(req: Request):
    d = _admin(req)
    if d: return d
    from .. import accounting_store as a
    return {"entitlements": a.get_entitlements()}


@router.post("/api/acc/entitlements")
async def acc_set_entitlement(req: Request):
    d = _admin(req)
    if d: return d
    body = await req.json()
    from .. import accounting_store as a
    return {"ok": a.set_entitlement(body["plan_id"], body["feat_key"], body["value"])}


# ─── Audit ───
@router.get("/api/acc/audit")
async def acc_audit(req: Request):
    d = _admin(req)
    if d: return d
    from .. import accounting_store as a
    return {"audit": a.list_audit()}


@router.post("/api/acc/audit")
async def acc_add_audit(req: Request):
    d = _admin(req)
    if d: return d
    body = await req.json()
    from .. import accounting_store as a
    return {"ok": a.add_audit(body.get("user", "admin"), body["action"])}


# ─── Settings ───
@router.patch("/api/acc/settings")
async def acc_settings(req: Request):
    d = _admin(req)
    if d: return d
    body = await req.json()
    from .. import accounting_store as a
    return {"ok": True, "settings": a.update_settings(body)}


# ============================================================
# Part 191: CFO Chat + Draft Approval
# ============================================================

@router.get("/api/acc/coa")
async def acc_coa(req: Request):
    d = _admin(req)
    if d: return d
    from .. import accounting_store as a
    return {"chart_of_accounts": a.get_chart_of_accounts()}


@router.get("/api/acc/drafts")
async def acc_drafts(req: Request):
    d = _admin(req)
    if d: return d
    from .. import accounting_store as a
    items = a.list_drafts()
    return {"drafts": items, "count": len(items)}


@router.post("/api/acc/drafts/{draft_id}/approve")
async def acc_approve_draft(draft_id: str, req: Request):
    d = _admin(req)
    if d: return d
    from .. import accounting_store as a
    entry = a.post_draft_entry(draft_id, approved_by="admin")
    if not entry:
        return JSONResponse({"error": "draft not found"}, status_code=404)
    return {"ok": True, "entry": entry}


@router.post("/api/acc/drafts/{draft_id}/reject")
async def acc_reject_draft(draft_id: str, req: Request):
    d = _admin(req)
    if d: return d
    from .. import accounting_store as a
    return {"ok": a.reject_draft_entry(draft_id), "draft_id": draft_id}


@router.get("/api/acc/agent/status")
async def acc_agent_status(req: Request):
    d = _admin(req)
    if d: return d
    from .. import cfo_agent
    return cfo_agent.status()


@router.post("/api/acc/chat")
async def acc_chat(req: Request):
    d = _admin(req)
    if d: return d
    body = await req.json()
    message = (body.get("message") or "").strip()
    if not message:
        return JSONResponse({"error": "message required"}, status_code=400)
    history = body.get("history") or []
    from .. import cfo_agent
    try:
        return await cfo_agent.handle_chat(message, history)
    except Exception as e:
        return JSONResponse({"error": f"{type(e).__name__}: {e}"}, status_code=500)
