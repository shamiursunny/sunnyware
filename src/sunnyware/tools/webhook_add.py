# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Register a webhook endpoint (Part 83)."""


class WebhookAddTool:
    name = "webhook_add"
    description = "Create a webhook that fires on an event. Triggers: create webhook, add webhook, set up webhook. Input: name and callback URL. Returns webhook ID."
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
