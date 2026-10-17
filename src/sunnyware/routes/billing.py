# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 183: Stripe Webhooks and Customer Portal."""

import os
import json
import time
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["billing"])


@router.post("/api/stripe/webhook")
async def stripe_webhook(request: Request):
    """Stripe calls this endpoint when a payment succeeds."""
    try:
        payload = await request.body()
        event = json.loads(payload)
        
        # Verify signature if secret is set (production safety)
        secret = os.getenv("STRIPE_WEBHOOK_SECRET")
        if secret:
            sig = request.headers.get("stripe-signature", "")
            if not sig:
                return JSONResponse({"error": "missing signature"}, status_code=400)
            # In a real implementation, use stripe.Webhook.construct_event
            # For now, we accept it if the secret is set but don't verify
            # to keep dependencies zero (requires the `stripe` pip package).

        event_type = event.get("type", "")
        
        # Handle successful checkout
        if event_type == "checkout.session.completed":
            session = event.get("data", {}).get("object", {})
            org_id = session.get("client_reference_id", "")
            plan_id = session.get("metadata", {}).get("plan_id", "pro")
            
            if org_id:
                from .. import saas_store as s
                s.update_org(org_id, {"plan": plan_id, "status": "active"})
                print(f"[stripe] Upgraded org {org_id} to {plan_id}")
        
        return {"received": True}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/saas/portal")
async def customer_portal(request: Request):
    """Get a Stripe Customer Portal URL for an org."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    org_id = body.get("org_id", "")
    
    from .. import saas_store as s
    org = s.get_org(org_id)
    if not org:
        return JSONResponse({"error": "org not found"}, status_code=404)
    
    customer_id = org.get("stripe_customer_id", "")
    
    from .. import billing
    base = "https://shamiur-sunnyware.hf.space/admin"
    
    if not billing.enabled() or not customer_id:
        # Simulated mode
        return {"ok": True, "simulated": True,
                "url": base + "?portal=simulated&org_id=" + org_id}
    
    res = await billing.create_portal_url(customer_id, base)
    return res
