# src/sunnyware/needle_router.py
import os

# CRITICAL: Set XDG_CACHE_HOME to force cactus-needle to use persistent storage
# cactus-needle uses appdirs which reads XDG_CACHE_HOME on Linux
os.environ["XDG_CACHE_HOME"] = "/data/.cache"
os.environ["HOME"] = "/data"
os.environ["NEEDLE_TELEMETRY"] = "0"

# Ensure the directories exist and are writable
os.makedirs("/data/.cache", exist_ok=True)

import needle

@needle.tool
def calculator(expression: str):
    """Evaluate a mathematical expression."""
    return {"expression": expression}

@needle.tool
def current_time(timezone: str = "UTC"):
    """Get the current time for a specific timezone."""
    return {"timezone": timezone}

_needle_agent = None

def _get_needle_agent():
    global _needle_agent
    if _needle_agent is None:
        try:
            _needle_agent = needle.Needle(
                tools=[calculator, current_time],
                generation=3,
            )
            print("[needle] Agent initialized successfully", flush=True)
        except Exception as e:
            print(f"[needle] Failed to initialize agent: {e}", flush=True)
            _needle_agent = "failed"
    return _needle_agent if _needle_agent != "failed" else None

async def try_needle_route(prompt: str):
    """Attempt to route the prompt using Needle 3."""
    agent = _get_needle_agent()
    if agent is None:
        return None

    try:
        response = agent.complete(text=prompt, max_new_tokens=128)
        print(f"[needle] Raw response: {response}", flush=True)
        
        calls = response.get("function_calls", [])
        confidence = response.get("confidence", 0.0)

        if calls and confidence > 0.5:
            call = calls[0]
            print(f"[needle] Selected tool: {call['name']} (confidence={confidence:.2f})", flush=True)
            return {
                "tool": call["name"],
                "args": call.get("arguments", {}),
            }
        else:
            print(f"[needle] No confident tool call (calls={len(calls)}, confidence={confidence:.2f})", flush=True)
            return None
    except Exception as e:
        print(f"[needle] Routing error: {e}", flush=True)
        return None
