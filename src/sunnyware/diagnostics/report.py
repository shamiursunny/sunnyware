"""Core reporting, sinks, public API."""
import json, threading
from collections import defaultdict
from pathlib import Path
from typing import List, Dict, Any
from .models import DiagnosticRecord
from .config import DIAGNOSTICS_ENABLED, DIAGNOSTICS_STRICT
from . import checks_startup, checks_preflight, checks_percall, checks_postresponse

_buffer: List[DiagnosticRecord] = []
_lock = threading.Lock()
_JSONL_PATH = Path("data/diagnostics/errors.jsonl")

def record(rec: DiagnosticRecord) -> None:
    if not DIAGNOSTICS_ENABLED: return
    try:
        with _lock:
            _buffer.append(rec)
            if len(_buffer) > 10000: _buffer.pop(0)
        _JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _JSONL_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec.to_dict()) + "\n")
    except Exception:
        pass

def get_report() -> Dict[str, Any]:
    with _lock: buf = list(_buffer)
    grouped = defaultdict(list)
    for r in buf:
        grouped[r.severity].append(r.to_dict())
    return {"summary": {s: len(v) for s, v in grouped.items()},
            "records": dict(grouped)}

def write_jsonl(path: Path = _JSONL_PATH) -> None:
    with _lock: buf = list(_buffer)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in buf: f.write(json.dumps(r.to_dict()) + "\n")

def clear_buffer() -> None:
    with _lock: _buffer.clear()

def run_startup_checks() -> Dict[str, Any]:
    if not DIAGNOSTICS_ENABLED: return {}
    try:
        results = checks_startup.run_all()
        for r in results: record(r)
        if DIAGNOSTICS_STRICT and any(r.severity == "fatal" for r in results):
            raise RuntimeError("DIAGNOSTICS_STRICT: fatal errors found")
        return {"status": "ok", "records": len(results)}
    except Exception as e:
        record(DiagnosticRecord(cls="diagnostics_internal", severity="warn",
                                layer="startup", message=f"{type(e).__name__}: {e}"))
        return {"status": "error", "message": str(e)}

def preflight(prompt, route_result, session_id=None) -> None:
    if not DIAGNOSTICS_ENABLED: return
    try:
        for r in checks_preflight.run(prompt, route_result, session_id): record(r)
    except Exception as e:
        record(DiagnosticRecord(cls="diagnostics_internal", severity="info",
                                layer="preflight", message=f"{type(e).__name__}: {e}"))

def record_call(tool, args, result, duration, session_id=None) -> None:
    if not DIAGNOSTICS_ENABLED: return
    try:
        for r in checks_percall.run(tool, args, result, duration, session_id): record(r)
    except Exception as e:
        record(DiagnosticRecord(cls="diagnostics_internal", severity="info",
                                layer="per_call", message=f"{type(e).__name__}: {e}"))

def post_response(response, session_id=None) -> None:
    if not DIAGNOSTICS_ENABLED: return
    try:
        for r in checks_postresponse.run(response, session_id): record(r)
    except Exception as e:
        record(DiagnosticRecord(cls="diagnostics_internal", severity="info",
                                layer="post_response", message=f"{type(e).__name__}: {e}"))

async def report_endpoint() -> dict:
    return get_report()
