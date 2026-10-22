# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""List SQL sandboxes (Part 84)."""


class SqlSandboxListTool:
    name = "sql_sandbox_list"
    description = "List all SQL sandboxes. Triggers: list SQL sandboxes, show databases, what sandboxes. Returns sandbox names."
    parameters = {}

    async def run(self, args: dict) -> dict:
        from .. import sql_sandbox as _ss
        return await _ss.list_all()
