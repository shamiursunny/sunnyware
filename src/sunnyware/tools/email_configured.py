# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Check email configuration (Part 76)."""


class EmailConfiguredTool:
    name = "email_configured"
    description = (
        "Check whether email sending is configured on the server. Returns "
        "{configured: bool, host, port, from, user_set, password_set}. Use "
        "before attempting email_send to give the user a clear setup hint."
    )
    parameters = {}

    async def run(self, args: dict) -> dict:
        from .. import email_send as _em
        return _em.config_summary()
