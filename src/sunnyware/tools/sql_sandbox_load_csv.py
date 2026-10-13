# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Load CSV into a SQL sandbox (Part 84)."""


class SqlSandboxLoadCsvTool:
    name = "sql_sandbox_load_csv"
    description = (
        "Load a workspace CSV/TSV file into a table inside a sandbox. "
        "Columns are loaded as TEXT; cast in your SQL (e.g. amount::numeric). "
        "Replaces the table if it exists."
    )
    parameters = {
        "name": {"type": "string", "required": True,
                 "description": "Sandbox name"},
        "file": {"type": "string", "required": True,
                 "description": "Workspace CSV/TSV filename"},
        "table": {"type": "string", "required": True,
                  "description": "Target table name"},
    }

    async def run(self, args: dict) -> dict:
        from .. import sql_sandbox as _ss
        return await _ss.load_csv(
            name=args.get("name", ""),
            file=args.get("file", ""),
            table=args.get("table", ""),
        )
