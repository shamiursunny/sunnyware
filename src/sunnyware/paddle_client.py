# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 186: Paddle Billing client (Merchant of Record)."""

import os
import json
import hmac
import hashlib
from urllib.parse import urlencode


def _api_key() -> str:
    return (os.getenv("PADDLE_API_KEY") or "").strip()


def _webhook_secret() -> str:
    return (os.getenv("PADDLE_WEBHOOK_SECRET") or "").strip()


def _environment() -> str:
    return (os.getenv("PADDLE_ENVIRONMENT") or "sandbox").strip().lower()


def _base_url() -> str:
    if _environment() == "live":
        return "https://api.paddle.com"
    return "https://sandbox-api.paddle.com"


def enabled() -> bool:
    return bool(_api_key())


def _price_id(plan_id: str) -> str:
    return {
        "pro": os.getenv("PADDLE_PRICE_PRO") or "",
        "enterprise": os.getenv("PADDLE_PRICE_ENTERPRISE") or "",
    }.get(plan_id, "")


async def create_checkout_url(org_id: str, plan_id: str,
                              success_url: str, cancel_url: str) -> dict:
    if not enabled():
        return {"ok": True, "simulated": True,
                "url": f"{success_url}?simulated=1&org_id={org_id}&plan_id={plan_id}"}

    price_id = _price_id(plan_id)
    if not price_id:
        return {"ok": False, "error": f"No Paddle price ID configured for plan '{plan_id}'"}

    try:
        import httpx
        async with httpx.AsyncClient(timeout=15.0) as cli:
            r = await cli.post(
                _base_url() + "/transactions",
                json={
                    "items": [{"price_id": price_id, "quantity": 1}],
                    "collection_mode": "automatic",
                    "custom_data": {"org_id": org_id, "plan_id": plan_id},
                },
                headers={
                    "Authorization": "Bearer " + _api_key(),
                    "Content-Type": "application/json",
                },
            )
            if r.status_code != 201:
                return {"ok": False, "error": r.text[:300]}

            data = r.json()
            checkout = data.get("data", {}).get("checkout", {})
            url = checkout.get("url", "")
            if not url:
                return {"ok": False, "error": "No checkout URL in Paddle response"}
            return {"ok": True, "simulated": False, "url": url}

    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def verify_webhook_signature(raw_body: bytes, signature_header: str) -> bool:
    secret = _webhook_secret()
    if not secret:
        return False
    try:
        parts = dict(p.split("=", 1) for p in signature_header.split(";"))
        ts = parts.get("ts", "")
        h1 = parts.get("h1", "")
        if not ts or not h1:
            return False
        signed_payload = ts.encode() + b":" + raw_body
        expected = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, h1)
    except Exception:
        return False
