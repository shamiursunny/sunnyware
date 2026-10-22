# src/sunnyware/needle_router.py
import os
os.environ["XDG_CACHE_HOME"] = "/data/.cache"
os.environ["HOME"] = "/data"
os.environ["NEEDLE_TELEMETRY"] = "0"

# Ensure the cache directory exists
os.makedirs("/data/.cache", exist_ok=True)

import json
import needle
from .needle_tool_loader import load_needle_tools

_needle_agent = None

def _get_needle_agent(all_tool_schemas: list[dict]):
    global _needle_agent
    if _needle_agent is None:
        try:
            tools = load_needle_tools(all_tool_schemas)
            total_size = len(json.dumps([s for s in all_tool_schemas]))
            print(f"[needle] Attempting init with {len(tools)} tools, schema size = {total_size} bytes", flush=True)
            
            _needle_agent = needle.Needle(
                tools=tools,
                tool_index_path="/data/.cache/needle_tool_index.idx",  # Use a FILE path, not a directory
                buffer_size=131072,
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

        if calls and confidence > 0.3:  # Lowered threshold to 0.3 for tiny models on many tools
            call = calls[0]
            print(f"[needle] Selected tool: {call['name']} (confidence={confidence:.2f})", flush=True)
            return {"tool": call["name"], "args": call.get("arguments", {})}
        else:
            print(f"[needle] No confident tool call (calls={len(calls)}, confidence={confidence:.2f})", flush=True)
            return None
    except Exception as e:
        print(f"[needle] Routing error: {e}", flush=True)
        return None
