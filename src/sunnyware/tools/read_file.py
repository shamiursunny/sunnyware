# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Read file from sandboxed workspace."""

import os
from pathlib import Path


MAX_BYTES = 256 * 1024  # 256 KB


def _workspace() -> Path:
    from .. import paths
    return paths.workspace()


def _safe_path(rel: str) -> Path:
    """Resolve rel path inside workspace; raise on escape."""
    ws = _workspace()
    ws.mkdir(parents=True, exist_ok=True)
    target = (ws / rel).resolve()
    if not str(target).startswith(str(ws)):
        raise ValueError(f"path escapes workspace: {rel}")
    return target


class ReadFileTool:
    name = "read_file"
    description = "Read a text file from the workspace. Path is relative to the workspace root."
    parameters = {
        "path": {
            "type": "string",
            "description": "Relative path inside the workspace (e.g. 'notes.txt')",
            "required": True,
        }
    }

    async def run(self, args: dict) -> dict:
        rel = str(args.get("path", "")).strip()
        if not rel:
            return {"error": "path is required"}
        try:
            target = _safe_path(rel)
        except ValueError as e:
            return {"error": str(e)}

        if not target.exists():
            return {"error": f"file not found: {rel}"}
        if not target.is_file():
            return {"error": f"not a file: {rel}"}

        size = target.stat().st_size
        if size > MAX_BYTES:
            return {"error": f"file too large: {size} bytes (max {MAX_BYTES})"}

        try:
            content = target.read_text(encoding="utf-8")
        except Exception as e:
            return {"error": f"read failed: {type(e).__name__}: {e}"}

        return {"path": rel, "content": content, "size": size}
