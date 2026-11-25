# SPDX-License-Identifier: AGPL-3.0-only
# Module: step_timeout — feature-flagged, zero-token, opt-in
import asyncio, os

def _default():
    v = os.getenv("SUNNYWARE_STEP_TIMEOUT")
    return float(v) if v else None

async def with_timeout(coro, tool_name: str = "", seconds=None):
    if tool_name and tool_name.startswith("browser_"):
        return await coro
    s = seconds if seconds is not None else _default()
    if s is None:
        return await coro
    return await asyncio.wait_for(coro, timeout=s)
