# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 186: Billing client (Paddle instead of Stripe)."""

import os


def enabled() -> bool:
    return bool((os.getenv("PADDLE_API_KEY") or "").strip())


async def create_checkout_url(org_id: str, plan_id: str,
                              success_url: str, cancel_url: str) -> dict:
    from . import paddle_client as _paddle
    return await _paddle.create_checkout_url(org_id, plan_id, success_url, cancel_url)


def status() -> dict:
    return {
        "enabled": enabled(),
        "provider": "paddle",
        "mode": "live" if enabled() else "simulated",
    }
