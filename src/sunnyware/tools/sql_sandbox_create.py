# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Create SQL sandbox (Part 84)."""


class SqlSandboxCreateTool:
    name = "sql_sandbox_create"
    description = (
        "Create (or ensure) an isolated SQL sandbox. Returns the internal "
        "schema name (sb_<name>). IDEMPOTENT - call ONCE then immediately "
        "proceed to sql_sandbox_execute. Do NOT call this tool more than "
        "once for the same name. If you need to create tables or insert "
        "data, do it via sql_sandbox_execute, not this tool."
    )
    parameters = {
        "name": {"type": "string", "required": True,
                 "description": "Sandbox name ([a-z][a-z0-9_]{0,40})"},
        "description": {"type": "string", "required": False,
                        "description": "Optional description"},
    }

    async def run(self, args: dict) -> dict:
        from .. import sql_sandbox as _ss
        return await _ss.create(args.get("name", ""),
                                args.get("description", ""))
