# src/sunnyware/needle_router.py
import os
import logging
import needle

logger = logging.getLogger(__name__)

# Disable telemetry to keep logs clean
os.environ["NEEDLE_TELEMETRY"] = "0"
os.environ["HF_HOME"] = "/data/hf_home"

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
        log.info(f"[needle] Raw response: {response}")
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
