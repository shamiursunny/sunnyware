# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 186: Paddle Billing webhook handler."""

import json
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["paddle"])


@router.post("/api/paddle/webhook")
async def paddle_webhook(request: Request):
    try:
        raw_body = await request.body()
        signature = request.headers.get("paddle-signature", "")

        from .. import paddle_client as _paddle
        if not _paddle.verify_webhook_signature(raw_body, signature):
            return JSONResponse({"error": "invalid signature"}, status_code=401)

        event = json.loads(raw_body)
        event_type = event.get("event_type", "")

        if event_type == "subscription.created":
            data = event.get("data", {})
            custom_data = data.get("custom_data", {})
            org_id = custom_data.get("org_id", "")
            plan_id = custom_data.get("plan_id", "pro")
            sub_id = data.get("id", "")
            if org_id:
                from .. import saas_store as s
                patch = {"plan": plan_id, "status": "active"}
                if sub_id: patch["paddle_subscription_id"] = sub_id
                s.update_org(org_id, patch)
                print(f"[paddle] Upgraded org {org_id} to {plan_id} (subscription {sub_id})")

        elif event_type == "transaction.completed":
            data = event.get("data", {})
            custom_data = data.get("custom_data", {})
            org_id = custom_data.get("org_id", "")
            plan_id = custom_data.get("plan_id", "pro")
            if org_id:
                from .. import saas_store as s
                s.update_org(org_id, {"plan": plan_id, "status": "active"})
                print(f"[paddle] Transaction completed for org {org_id} -> {plan_id}")

        return {"received": True}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
