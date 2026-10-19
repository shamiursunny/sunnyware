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
            # Part 209h: check multiple possible locations for custom_data
            custom_data = (
                data.get("custom_data", {})
                or data.get("details", {}).get("custom_data", {})
                or data.get("origin", {}).get("custom_data", {})
                or {}
            )
            org_id = custom_data.get("org_id", "")
            plan_id = custom_data.get("plan_id", "pro")
            txn_id = data.get("id", "unknown")

            _cust = data.get("customer_id", "") or data.get("customer", "")
            if isinstance(_cust, dict): _cust = _cust.get("id", "")

            # Fallback: look up by paddle_customer_id
            if not org_id and _cust:
                try:
                    from .. import saas_store as s
                    org = s.get_org_by_paddle_customer(_cust)
                    if org:
                        org_id = org["id"]
                        print(f"[paddle] Resolved org {org_id} from customer {_cust}")
                except Exception as e:
                    print(f"[paddle] Fallback lookup failed: {e}")

            print(f"[paddle] txn.completed: txn={txn_id}, org={org_id}, plan={plan_id}, cust={_cust}")

            totals = data.get("details", {}).get("totals", {})
            amount_str = totals.get("total", "0")
            try:
                amount = float(amount_str) / 100.0
            except Exception:
                amount = 0.0

            if org_id:
                from .. import saas_store as s
                _patch = {"plan": plan_id, "status": "active"}
                if _cust: _patch["paddle_customer_id"] = _cust
                s.update_org(org_id, _patch)
                s.create_invoice(
                    org_id=org_id,
                    amount=amount,
                    description=f"Paddle Checkout (Txn: {txn_id})",
                    status="paid"
                )
                print(f"[paddle] Upgraded org {org_id} to {plan_id}, invoice ${amount:.2f}")
            else:
                print(f"[paddle] WARNING: could not resolve org for txn {txn_id}")

        return {"received": True}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
