# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Delete file or empty directory in sandboxed workspace."""

import shutil

import os
from pathlib import Path


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



class DeleteFileTool:
    name = "delete_file"
    description = "Delete a file or empty directory in the workspace."
    parameters = {
        "path": {
            "type": "string",
            "description": "Relative path of file or directory to delete",
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
            return {"error": f"not found: {rel}"}
        if target == _workspace():
            return {"error": "cannot delete workspace root"}

        try:
            if target.is_dir():
                # Only delete empty dirs (safety)
                if any(target.iterdir()):
                    return {"error": "directory not empty (refusing to recurse)"}
                target.rmdir()
                return {"deleted": rel, "type": "dir"}
            else:
                target.unlink()
                return {"deleted": rel, "type": "file"}
        except Exception as e:
            return {"error": f"delete failed: {type(e).__name__}: {e}"}
