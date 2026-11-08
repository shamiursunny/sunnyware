"""Pre-request checks."""
from typing import List
from .models import DiagnosticRecord

def _registry() -> set:
    try:
        from sunnyware.tools import get_all_tool_names as _g
        return set(_g() if callable(_g) else (_g or []))
    except Exception:
        return set()

def run(prompt, route_result, session_id=None) -> List[DiagnosticRecord]:
    records = []
    reg = _registry()
    if not reg: return records
    if isinstance(route_result, dict):
        tool = route_result.get("tool")
        if tool and tool not in reg:
            records.append(DiagnosticRecord(
                cls="routing_anomaly", severity="error", layer="preflight",
                message=f"Router suggested tool '{tool}' not in registry",
                evidence={"tool": tool, "prompt": prompt[:100]},
                session_id=session_id,
                reproducible_cmd=f"python -c \"from sunnyware.tools import get_tool; get_tool('{tool}')\""))
    return records
