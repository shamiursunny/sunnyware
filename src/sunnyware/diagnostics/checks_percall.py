"""Per-call checks."""
from typing import Any, List
from .models import DiagnosticRecord

def _classify(result: Any):
    if isinstance(result, dict):
        if result.get("error"):
            msg = str(result["error"]); low = msg.lower()
            if "401" in msg or "unauthorized" in low:
                return ("execution", "error", f"Provider auth failure: {msg[:120]}")
            if "429" in msg or "rate limit" in low:
                return ("execution", "warn", f"Rate limit: {msg[:120]}")
            if "timeout" in low:
                return ("execution", "warn", f"Tool timeout: {msg[:120]}")
            return ("execution", "error", f"Tool error: {msg[:120]}")
        if not result:
            return ("execution", "warn", "Tool returned empty payload")
    return (None, None, None)

def run(tool, args, result, duration, session_id=None) -> List[DiagnosticRecord]:
    records = []
    cls, sev, msg = _classify(result)
    if cls:
        records.append(DiagnosticRecord(
            cls=cls, severity=sev, layer="per_call", message=msg,
            evidence={"tool": tool, "args": args, "duration_ms": round(duration*1000, 1)},
            session_id=session_id,
            reproducible_cmd=f"python -c \"from sunnyware.tools import get_tool; get_tool('{tool}').run({args})\""))
    return records
