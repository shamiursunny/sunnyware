# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""List webhook events (Part 83)."""


class WebhookEventsTool:
    name = "webhook_events"
    description = (
        "List recent events received by a webhook endpoint (payloads, "
        "processed status, agent response preview). Newest first."
    )
    parameters = {
        "token": {"type": "string", "required": True,
                  "description": "Endpoint token"},
        "limit": {"type": "integer", "required": False,
                  "description": "Max events (default 10, max 50)"},
    }

    async def run(self, args: dict) -> dict:
        from .. import webhook as _wh
        return await _wh.events(
            token=args.get("token", ""),
            limit=args.get("limit") or 10,
        )
