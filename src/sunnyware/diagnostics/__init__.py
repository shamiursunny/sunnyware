"""Sunnyware diagnostics – automatic error detection and reporting."""
from .report import (
    record, get_report, write_jsonl, clear_buffer,
    run_startup_checks, preflight, record_call,
    post_response, report_endpoint,
)
from .config import DIAGNOSTICS_ENABLED, DIAGNOSTICS_STRICT

__all__ = [
    "record", "get_report", "write_jsonl", "clear_buffer",
    "run_startup_checks", "preflight", "record_call",
    "post_response", "report_endpoint",
    "DIAGNOSTICS_ENABLED", "DIAGNOSTICS_STRICT",
]
