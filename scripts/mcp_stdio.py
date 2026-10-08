#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""MCP stdio runner — for Claude Desktop / local MCP clients."""

import asyncio
import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sunnyware import mcp_server  # noqa: E402


async def _readline_async() -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, sys.stdin.readline)


async def main():
    log = sys.stderr
    print("[sunnyware-mcp] stdio runner started", file=log)

    while True:
        line = await _readline_async()
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception as e:
            print(f"[sunnyware-mcp] parse error: {e}", file=log)
            continue

        if isinstance(msg, list):
            responses = []
            for item in msg:
                if not isinstance(item, dict):
                    continue
                r = await mcp_server.handle_rpc(
                    str(item.get("method", "")),
                    item.get("params") or {},
                    item.get("id"),
                )
                if r is not None:
                    responses.append(r)
            if responses:
                sys.stdout.write(json.dumps(responses) + "\n")
                sys.stdout.flush()
            continue

        method = msg.get("method")
        params = msg.get("params") or {}
        req_id = msg.get("id")

        try:
            result = await mcp_server.handle_rpc(method, params, req_id)
        except Exception as e:
            result = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32603, "message": f"{type(e).__name__}: {e}"},
            }

        if result is not None:
            sys.stdout.write(json.dumps(result) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
