# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Write file to sandboxed workspace."""

import os
from pathlib import Path


MAX_BYTES = 256 * 1024  # 256 KB


def _workspace() -> Path:
    from .. import paths
    return paths.workspace()


def _safe_path(rel: str) -> Path:
    ws = _workspace()
    ws.mkdir(parents=True, exist_ok=True)
    target = (ws / rel).resolve()
    if not str(target).startswith(str(ws)):
        raise ValueError(f"path escapes workspace: {rel}")
    return target


class WriteFileTool:
    name = "write_file"
    description = "Write text content to a file in the workspace (creates dirs if needed)."
    parameters = {
        "path": {
            "type": "string",
            "description": "Relative path inside the workspace",
            "required": True,
        },
        "content": {
            "type": "string",
            "description": "Text content to write",
            "required": True,
        },
    }

    async def run(self, args: dict) -> dict:
        rel = str(args.get("path", "")).strip()
        content = args.get("content", "")
        if not rel:
            return {"error": "path is required"}
        if not isinstance(content, str):
            content = str(content)
        if len(content.encode("utf-8")) > MAX_BYTES:
            return {"error": f"content too large (max {MAX_BYTES} bytes)"}

        try:
            target = _safe_path(rel)
        except ValueError as e:
            return {"error": str(e)}

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        except Exception as e:
            return {"error": f"write failed: {type(e).__name__}: {e}"}

        return {
            "path": rel,
            "bytes_written": len(content.encode("utf-8")),
            "absolute": str(target),
        }
