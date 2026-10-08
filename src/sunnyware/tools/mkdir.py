# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Create directory in sandboxed workspace."""

import os
from pathlib import Path


def _workspace() -> Path:
    return Path(os.getenv("SUNNYWARE_WORKSPACE", "./data/workspace")).resolve()


def _safe_path(rel: str) -> Path:
    ws = _workspace()
    ws.mkdir(parents=True, exist_ok=True)
    target = (ws / rel).resolve()
    if not str(target).startswith(str(ws)):
        raise ValueError(f"path escapes workspace: {rel}")
    return target



class MkdirTool:
    name = "mkdir"
    description = "Create a directory in the workspace (parents created if needed)."
    parameters = {
        "path": {
            "type": "string",
            "description": "Relative directory path to create",
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

        if target.exists():
            if target.is_dir():
                return {"created": rel, "already_existed": True}
            return {"error": f"path exists and is a file: {rel}"}

        try:
            target.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return {"error": f"mkdir failed: {type(e).__name__}: {e}"}

        return {"created": rel, "already_existed": False}
