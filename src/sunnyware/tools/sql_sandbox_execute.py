# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Execute SQL in a sandbox (Part 84)."""


class SqlSandboxExecuteTool:
    name = "sql_sandbox_execute"
    description = (
        "Run SQL in a sandbox. Use $1..$n placeholders for params. "
        "SELECT/WITH return rows (max 5000). DDL/DML return a status "
        "string. Search path is forced to the sandbox; main tables and "
        "cross-schema reads are blocked. 10s statement timeout."
    )
    parameters = {
        "name": {"type": "string", "required": True,
                 "description": "Sandbox name"},
        "sql": {"type": "string", "required": True,
                "description": "SQL statement (SELECT/INSERT/CREATE/etc)"},
        "params": {"type": "array", "required": False,
                   "description": "Optional array of parameter values for $1..$n"},
    }

    async def run(self, args: dict) -> dict:
        from .. import sql_sandbox as _ss
        return await _ss.execute(
            name=args.get("name", ""),
            sql=args.get("sql", ""),
            params=args.get("params"),
        )
