# src/sunnyware/needle_router.py
import os
import logging
import needle

logger = logging.getLogger(__name__)

# Disable telemetry to keep logs clean
os.environ["NEEDLE_TELEMETRY"] = "0"

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
            log.info("[needle] Agent initialized successfully")
        except Exception as e:
            log.error(f"[needle] Failed to initialize agent: {e}")
            _needle_agent = "failed"
    return _needle_agent if _needle_agent != "failed" else None

async def try_needle_route(prompt: str):
    """Attempt to route the prompt using Needle 3."""
    agent = _get_needle_agent()
    if agent is None:
        return None

    try:
        response = agent.complete(text=prompt, max_new_tokens=128)
        log.info(f"[needle] Raw response: {response}")
        calls = response.get("function_calls", [])
        confidence = response.get("confidence", 0.0)

        if calls and confidence > 0.5:
            call = calls[0]
            log.info(f"[needle] Selected tool: {call['name']} (confidence={confidence:.2f})")
            return {
                "tool": call["name"],
                "args": call.get("arguments", {}),
            }
        else:
            log.info(f"[needle] No confident tool call (calls={len(calls)}, confidence={confidence:.2f})")
            return None
    except Exception as e:
        log.warning(f"[needle] Routing error: {e}")
        return None
