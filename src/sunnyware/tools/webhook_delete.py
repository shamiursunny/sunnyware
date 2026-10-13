# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Delete a webhook endpoint (Part 83)."""


class WebhookDeleteTool:
    name = "webhook_delete"
    description = "Delete a webhook endpoint by token. Also removes its events."
    parameters = {
        "token": {"type": "string", "required": True,
                  "description": "Endpoint token (starts with 'wh_')"},
    }

    async def run(self, args: dict) -> dict:
        from .. import webhook as _wh
        return await _wh.delete(args.get("token", ""))
