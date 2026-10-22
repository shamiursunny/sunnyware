# src/sunnyware/needle_router.py
import os
os.environ["XDG_CACHE_HOME"] = "/data/.cache"
os.environ["HOME"] = "/data"
os.environ["NEEDLE_TELEMETRY"] = "0"

import needle
from .needle_tool_loader import load_needle_tools

_needle_agent = None

def _get_needle_agent(all_tool_schemas: list[dict]):
    global _needle_agent
    if _needle_agent is None:
        try:
            tools = load_needle_tools(all_tool_schemas)
            _needle_agent = needle.Needle(
                tools=tools,
                tool_index_path="/data/.cache/needle_tool_index",
                stateless=True,
                generation=3,
            )
            print(f"[needle] Agent initialized with {len(tools)} tools", flush=True)
        except Exception as e:
            print(f"[needle] Failed to init: {e}", flush=True)
            _needle_agent = "failed"
    return _needle_agent if _needle_agent != "failed" else None

async def try_needle_route(prompt: str, all_tool_schemas: list[dict]):
    agent = _get_needle_agent(all_tool_schemas)
    if agent is None:
        return None

    try:
        response = agent.complete(text=prompt, max_new_tokens=256)
        calls = response.get("function_calls", [])
        confidence = response.get("confidence", 0.0)

        if calls and confidence > 0.5:
            call = calls[0]
            print(f"[needle] Selected tool: {call['name']} (confidence={confidence:.2f})", flush=True)
            return {"tool": call["name"], "args": call.get("arguments", {})}
        else:
            print(f"[needle] No confident tool call (calls={len(calls)}, confidence={confidence:.2f})", flush=True)
            return None
    except Exception as e:
        print(f"[needle] Routing error: {e}", flush=True)
        return None
