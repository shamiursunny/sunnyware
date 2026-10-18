# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 199: CFO agent can update HITL config via chat."""


class HitlConfigUpdateTool:
    name = "hitl_config_update"
    description = (
        "Update HITL approval settings for a tool. Use when the user asks to "
        "auto-approve, require approval, or block a tool — globally or for a specific user. "
        "Examples: 'auto-approve web_search', 'require approval for python_eval', "
        "'deny web_search for user:bob@company.com'."
    )
    parameters = {
        "tool_name": {
            "type": "string",
            "description": "Tool name (e.g. web_search, python_eval, write_file)",
            "required": True,
        },
        "decision": {
            "type": "string",
            "description": "One of: auto (run immediately), approve (require HITL), deny (block)",
            "required": True,
        },
        "user_key": {
            "type": "string",
            "description": "Optional: apply only to this user (e.g. user:bob@company.com)",
            "required": False,
        },
    }

    async def run(self, args: dict) -> dict:
        from .. import hitl_config
        tool = (args.get("tool_name") or "").strip()
        decision = (args.get("decision") or "").strip().lower()
        user_key = (args.get("user_key") or "").strip() or None
        if not tool:
            return {"error": "tool_name is required"}
        if decision not in ("auto", "approve", "deny"):
            return {"error": "decision must be auto, approve, or deny"}
        try:
            if user_key:
                ok = hitl_config.set_override(user_key, tool, decision)
            else:
                ok = hitl_config.set_global(tool, decision)
            return {
                "ok": ok,
                "tool": tool,
                "decision": decision,
                "user_key": user_key or "global",
                "message": f"Set {tool} to '{decision}'" + (f" for {user_key}" if user_key else " globally"),
            }
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}
