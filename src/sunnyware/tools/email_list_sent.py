# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""List sent emails (Part 76)."""


class EmailListSentTool:
    name = "email_list_sent"
    description = (
        "List recent emails sent by sunnyware (from Neon log). Returns "
        "recipients, subject, preview, attachments, ok/fail status, and "
        "timestamp. Use to audit past sends or confirm delivery."
    )
    parameters = {
        "limit": {"type": "integer", "required": False,
                  "description": "Max results (default 20, max 100)"},
    }

    async def run(self, args: dict) -> dict:
        from .. import email_send as _em
        return await _em.list_sent(limit=args.get("limit") or 20)
