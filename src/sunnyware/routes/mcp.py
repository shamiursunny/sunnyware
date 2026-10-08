# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""MCP endpoints — JSON-RPC 2.0 over HTTP."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .. import mcp_server


router = APIRouter()


@router.get("/mcp")
async def mcp_info():
    tools = mcp_server.list_tools()
    return {
        "name": mcp_server.SERVER_NAME,
        "version": mcp_server.SERVER_VERSION,
        "protocol": "mcp",
        "protocol_version": mcp_server.PROTOCOL_VERSION,
        "transport": "http-jsonrpc",
        "endpoint": "/mcp/rpc",
        "tools_count": len(tools),
        "tools": [t["name"] for t in tools],
    }


@router.post("/mcp/rpc")
async def mcp_rpc(req: Request):
    try:
        body = await req.json()
    except Exception:
        return JSONResponse(
            {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}},
            status_code=400,
        )

    if isinstance(body, list):
        responses = []
        for item in body:
            if not isinstance(item, dict):
                continue
            r = await mcp_server.handle_rpc(
                str(item.get("method", "")), item.get("params") or {}, item.get("id")
            )
            if r is not None:
                responses.append(r)
        return JSONResponse(responses)

    if not isinstance(body, dict):
        return JSONResponse(
            {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid Request"}},
            status_code=400,
        )

    method = str(body.get("method", ""))
    params = body.get("params") or {}
    req_id = body.get("id")

    r = await mcp_server.handle_rpc(method, params, req_id)
    if r is None:
        return JSONResponse({"jsonrpc": "2.0", "id": req_id, "result": None})
    return JSONResponse(r)
