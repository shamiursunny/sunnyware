# SPDX-License-Identifier: AGPL-3.0-only
# Module: tool_errors — feature-flagged, zero-token, opt-in
from dataclasses import dataclass
from typing import Any, Optional

@dataclass
class ToolError:
    code: str
    message: str
    retryable: bool = True
    details: Optional[dict] = None
    tool_name: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "ok": False,
            "error": self.message,
            "error_code": self.code,
            "retryable": self.retryable,
            "details": self.details or {},
            "tool_name": self.tool_name,
        }

def normalize_tool_error(tool_name: str, raw: Any) -> dict:
    if not isinstance(raw, dict):
        return ToolError(code="non_dict_result", message=str(raw),
                         retryable=False, tool_name=tool_name).to_dict()
    if raw.get("ok") is not False and not raw.get("error"):
        return raw
    return ToolError(
        code=raw.get("error_code", "tool_error"),
        message=str(raw.get("error") or raw.get("message", "Unknown error")),
        retryable=raw.get("retryable", True),
        details=raw.get("details"),
        tool_name=tool_name,
    ).to_dict()
