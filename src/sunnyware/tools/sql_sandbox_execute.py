# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Execute SQL in a sandbox (Part 84)."""


class SqlSandboxExecuteTool:
    name = "sql_sandbox_execute"
    description = "Run SQL in an isolated sandbox database. Triggers: run SQL, execute query, SELECT from sandbox. Input: sandbox name and SQL query. Returns query results.". DDL/DML return a status "
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
        name = args.get("name", "")
        sql = args.get("sql", "")
        params = args.get("params")
        
        # First attempt
        res = await _ss.execute(name=name, sql=sql, params=params)
        
        # Part 306: Auto-create sandbox if it doesn't exist
        if res.get("error") and "sandbox not found" in str(res["error"]).lower():
            print(f"[sql_sandbox_execute] Sandbox '{name}' not found. Auto-creating...", flush=True)
            create_res = await _ss.create(name, "")
            if create_res.get("ok"):
                print(f"[sql_sandbox_execute] Auto-created sandbox '{name}'. Retrying query...", flush=True)
                res = await _ss.execute(name=name, sql=sql, params=params)
            else:
                print(f"[sql_sandbox_execute] Auto-create failed: {create_res}", flush=True)
        
        return res
