# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Register a webhook endpoint (Part 83)."""


class WebhookAddTool:
    name = "webhook_add"
    description = (
        "Register a webhook endpoint. External services POST to the "
        "returned /webhook/{token} URL. Optionally auto-run an agent "
        "prompt on every received payload. Use for Slack/GitHub/Stripe "
        "events or any external trigger."
    )
    parameters = {
        "name": {"type": "string", "required": True,
                 "description": "Short friendly name (e.g. 'stripe_payments')"},
        "trigger_prompt": {"type": "string", "required": False,
                           "description": "Optional agent prompt to run on each event"},
        "notify_email": {"type": "string", "required": False,
                         "description": "Optional email to notify on every event"},
    }

    async def run(self, args: dict) -> dict:
        from .. import webhook as _wh
        return await _wh.add(
            name=args.get("name", ""),
            trigger_prompt=args.get("trigger_prompt", ""),
            notify_email=args.get("notify_email", ""),
        )
