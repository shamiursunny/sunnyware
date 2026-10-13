# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""List webhook endpoints (Part 83)."""


class WebhookListTool:
    name = "webhook_list"
    description = (
        "List all registered webhook endpoints with their tokens, URLs, "
        "hit counts, and last hit timestamps."
    )
    parameters = {}

    async def run(self, args: dict) -> dict:
        from .. import webhook as _wh
        return await _wh.list_all()
