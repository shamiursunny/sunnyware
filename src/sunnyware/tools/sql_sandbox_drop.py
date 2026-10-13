# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Drop a SQL sandbox (Part 84-fix3)."""


class SqlSandboxDropTool:
    name = "sql_sandbox_drop"
    description = (
        "Delete a SQL sandbox and its schema. Removes all tables inside it. "
        "Use when the user asks to clean up or remove a sandbox."
    )
    parameters = {
        "name": {"type": "string", "required": True,
                 "description": "Sandbox name to drop"},
    }

    async def run(self, args: dict) -> dict:
        from .. import sql_sandbox as _ss
        return await _ss.drop(args.get("name", ""))
