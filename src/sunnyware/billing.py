# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 182: Stripe billing client (simulated when no key)."""

import os

def _key() -> str:
    return (os.getenv("STRIPE_SECRET_KEY") or "").strip()

def enabled() -> bool:
    return bool(_key())

async def create_checkout_url(org_id: str, plan_id: str, success_url: str, cancel_url: str) -> dict:
    if not enabled():
        return {"ok": True, "simulated": True, "url": f"{success_url}?simulated=1&org_id={org_id}&plan_id={plan_id}"}
    try:
        import httpx
        async with httpx.AsyncClient(timeout=15.0) as cli:
            r = await cli.post(
                "https://api.stripe.com/v1/checkout/sessions",
                auth=(_key(), ""),
                data={
                    "mode": "subscription", "success_url": success_url, "cancel_url": cancel_url,
                    "line_items[0][price_data][currency]": "usd",
                    "line_items[0][price_data][product_data][name]": f"Sunnyware {plan_id.title()}",
                    "line_items[0][price_data][unit_amount]": 4900,
                    "line_items[0][price_data][recurring][interval]": "month",
                    "line_items[0][quantity]": 1,
                },
            )
            if r.status_code != 200:
                return {"ok": False, "error": r.text[:300]}
            return {"ok": True, "simulated": False, "url": r.json().get("url", "")}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}

def status() -> dict:
    return {"enabled": enabled(), "mode": "live" if enabled() else "simulated"}
