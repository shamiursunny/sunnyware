# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Tool endpoints: /api/tools, /api/tools/{name}."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .. import tools as tools_registry


router = APIRouter()


@router.get("/api/tools")
async def list_tools_endpoint():
    items = tools_registry.list_tools()
    return {"count": len(items), "tools": items}


@router.post("/api/tools/{tool_name}")
async def call_tool_endpoint(tool_name: str, req: Request):
    tool = tools_registry.get_tool(tool_name)
    if tool is None:
        return JSONResponse(
            {"error": f"unknown tool: {tool_name}", "available": tools_registry.tool_names()},
            status_code=404,
        )
    try:
        args = await req.json()
    except Exception:
        args = {}
    if not isinstance(args, dict):
        args = {}
    try:
        result = await tool.run(args)
    except Exception as e:
        return JSONResponse({"error": f"{type(e).__name__}: {e}"}, status_code=500)
    return {"tool": tool_name, "args": args, "result": result}
