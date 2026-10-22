# src/sunnyware/needle_router.py
import os
os.environ["XDG_CACHE_HOME"] = "/data/.cache"
os.environ["HOME"] = "/data"
os.environ["NEEDLE_TELEMETRY"] = "0"

import json
import needle
from .needle_tool_loader import load_needle_tools

# We no longer use a global singleton because the shortlist changes per request.
# Initializing Needle 3 takes only milliseconds.

async def try_needle_route(prompt: str, shortlist_schemas: list[dict]):
    """
    Attempts to route the prompt using Needle 3.
    Expects a SHORTLIST of tools (e.g., 10-15 max), not the full catalogue.
    """
    if not shortlist_schemas:
        return None
        
    try:
        tools = load_needle_tools(shortlist_schemas)
        schema_size = len(json.dumps(shortlist_schemas))
        
        print(f"[needle] Initializing with {len(tools)} shortlisted tools (size: {schema_size} bytes)", flush=True)
        
        agent = needle.Needle(
            tools=tools,
            tool_index_path="/data/.cache/needle_tool_index.idx",
            stateless=True,
            generation=3,
        )
        
        response = agent.complete(text=prompt, max_new_tokens=256)
        calls = response.get("function_calls", [])
        confidence = response.get("confidence", 0.0)

        if calls and confidence > 0.15:
            call = calls[0]
            print(f"[needle] Selected tool: {call['name']} (confidence={confidence:.2f})", flush=True)
            return {"tool": call["name"], "args": call.get("arguments", {})}
        else:
            print(f"[needle] No confident tool call (calls={len(calls)}, confidence={confidence:.2f})", flush=True)
            return None
            
    except Exception as e:
        print(f"[needle] Routing error: {e}", flush=True)
        return None
