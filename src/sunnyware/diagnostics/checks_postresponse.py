"""Post-response checks."""
import re
from typing import List
from .models import DiagnosticRecord

def _registry() -> set:
    try:
        from sunnyware.tools import list_tools
        tools = list(list_tools())
        return {t["name"] if isinstance(t, dict) else str(t) for t in tools}
    except Exception:
        return set()

def run(response: str, session_id=None) -> List[DiagnosticRecord]:
    records = []
    reg = _registry()
    if not reg or not response: return records
    pattern = re.compile(
        r"(?:don['\"]?t have|do not have|no|missing|absent)\s+(?:any\s+)?"
        r"([a-zA-Z_][a-zA-Z0-9_]*)", re.IGNORECASE)
    for m in pattern.finditer(response):
        claimed = m.group(1).lower()
        # match exact OR any registry tool that starts with/contains the claimed word
        matched = [name for name in reg if name == claimed or claimed in name]
        if matched:
            records.append(DiagnosticRecord(
                cls="llm_self_report_inconsistency", severity="error",
                layer="post_response",
                message=f"Model claims tool '{claimed}' missing but it exists",
                evidence={"claimed": claimed, "response_snippet": response[:200]},
                session_id=session_id,
                reproducible_cmd=f"python -c \"from sunnyware.tools import get_tool; print(get_tool('{claimed}'))\""))
    return records
