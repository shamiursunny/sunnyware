# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""MCP (Model Context Protocol) server — JSON-RPC 2.0 handlers."""

import json
from typing import Any, Optional

from . import tools as tools_registry


PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "sunnyware"
SERVER_VERSION = "0.1.0"


def _json_schema_from_params(params: dict) -> dict:
    props = {}
    required = []
    for name, meta in (params or {}).items():
        props[name] = {
            "type": meta.get("type", "string"),
            "description": meta.get("description", ""),
        }
        if meta.get("required"):
            required.append(name)
    return {
        "type": "object",
        "properties": props,
        "required": required,
    }


def list_tools() -> list:
    out = []
    for t in tools_registry.list_tools():
        out.append({
            "name": t["name"],
            "description": t["description"],
            "inputSchema": _json_schema_from_params(t.get("parameters") or {}),
        })
    out.append({
        "name": "agent_query",
        "description": (
            "Ask the sunnyware agent a question. It will plan, call tools, "
            "use memory, and return a final answer. Prefer this for complex queries."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "input": {"type": "string", "description": "The user query or task"},
                "session_id": {"type": "string", "description": "Optional session ID"},
            },
            "required": ["input"],
        },
    })
    return out


async def call_tool(name: str, arguments: dict) -> dict:
    if not isinstance(arguments, dict):
        arguments = {}

    if name == "agent_query":
        try:
            from . import orchestrator
            from . import sessions as sessions_store
            prompt = str(arguments.get("input", "")).strip()
            if not prompt:
                return {"content": [{"type": "text", "text": "error: input is required"}], "isError": True}
            session_id = str(arguments.get("session_id", "mcp-default"))
            session_uuid = await sessions_store.get_or_create(session_id)
            result = await orchestrator.run_agent(prompt, session_uuid=session_uuid)
            text = result.get("answer", "") if result.get("ok") else f"error: {result.get('error')}"
            return {"content": [{"type": "text", "text": text or "(empty)"}], "isError": not result.get("ok", False)}
        except Exception as e:
            return {"content": [{"type": "text", "text": f"{type(e).__name__}: {e}"}], "isError": True}

    tool = tools_registry.get_tool(name)
    if tool is None:
        return {"content": [{"type": "text", "text": f"unknown tool: {name}"}], "isError": True}
    try:
        result = await tool.run(arguments)
    except Exception as e:
        return {"content": [{"type": "text", "text": f"{type(e).__name__}: {e}"}], "isError": True}
    if not isinstance(result, dict):
        result = {"result": result}
    is_err = "error" in result and len(result) <= 2
    text = json.dumps(result, ensure_ascii=False, default=str)
    return {"content": [{"type": "text", "text": text}], "isError": is_err}


async def handle_rpc(method: str, params: dict, req_id: Any) -> Optional[dict]:
    params = params or {}

    if method == "initialize":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        }

    if method in ("notifications/initialized", "initialized"):
        return None

    if method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": list_tools()}}

    if method == "tools/call":
        tool_name = str(params.get("name", ""))
        args = params.get("arguments") or {}
        result = await call_tool(tool_name, args)
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    if method == "resources/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"resources": []}}

    if method == "prompts/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"prompts": []}}

    return {
        "jsonrpc": "2.0", "id": req_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }
