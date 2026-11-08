"""Startup integrity checks."""
import re
from collections import Counter
from typing import List
from .models import DiagnosticRecord

def _tool_names() -> List[str]:
    try:
        from sunnyware.tools import list_tools
        tools = list(list_tools())
        return [t["name"] if isinstance(t, dict) else str(t) for t in tools]
    except Exception:
        return []

def check_registry_integrity() -> List[DiagnosticRecord]:
    records = []
    names = _tool_names()
    seen, dupes = set(), []
    for n in names:
        if n in seen: dupes.append(n)
        else: seen.add(n)
    for name in set(dupes):
        records.append(DiagnosticRecord(
            cls="registry_integrity", severity="error", layer="startup",
            message=f"Duplicate tool name: {name}",
            evidence={"name": name}))
    recursive_pattern = re.compile(r"(_and_\w+){2,}")
    for name in names:
        if recursive_pattern.search(name):
            records.append(DiagnosticRecord(
                cls="registry_integrity", severity="error", layer="startup",
                message=f"Recursive/self-referencing name: {name}",
                evidence={"name": name}))
    return records

def check_wiring_integrity() -> List[DiagnosticRecord]:
    records = []
    try:
        import sunnyware.orchestrator as orch
        for attr in ("run_agent", "_build_tools_schema"):
            if not hasattr(orch, attr):
                records.append(DiagnosticRecord(
                    cls="wiring_integrity", severity="error", layer="startup",
                    message=f"orchestrator.{attr} is missing",
                    evidence={"module": "sunnyware.orchestrator", "missing": attr}))
    except Exception as e:
        records.append(DiagnosticRecord(
            cls="wiring_integrity", severity="warn", layer="startup",
            message=f"Could not import orchestrator: {e}"))
    return records

def check_schema_determinism() -> List[DiagnosticRecord]:
    records = []
    try:
        from sunnyware.orchestrator import _build_tools_schema
        s1 = _build_tools_schema()
        s2 = _build_tools_schema()
        n1 = [t.get("name") for t in s1] if isinstance(s1, list) else list(s1.keys())
        n2 = [t.get("name") for t in s2] if isinstance(s2, list) else list(s2.keys())
        if n1 != n2:
            records.append(DiagnosticRecord(
                cls="schema_integrity", severity="error", layer="startup",
                message="Tool schema is non-deterministic",
                evidence={"first": n1, "second": n2}))
    except Exception as e:
        records.append(DiagnosticRecord(
            cls="schema_integrity", severity="warn", layer="startup",
            message=f"Schema determinism check failed: {e}"))
    return records

def run_all() -> List[DiagnosticRecord]:
    return (check_registry_integrity() + check_wiring_integrity()
            + check_schema_determinism())
