# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""List files in sandboxed workspace."""

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


MAX_ENTRIES = 200


class ListFilesTool:
    name = "list_files"
    description = "List files and directories in the workspace. Optional subpath."
    parameters = {
        "path": {
            "type": "string",
            "description": "Subdirectory path (optional, default root)",
            "required": False,
        }
    }

    async def run(self, args: dict) -> dict:
        rel = str(args.get("path", "")).strip() or "."
        try:
            target = _safe_path(rel)
        except ValueError as e:
            return {"error": str(e)}

        if not target.exists():
            return {"error": f"path not found: {rel}"}
        if not target.is_dir():
            return {"error": f"not a directory: {rel}"}

        entries = []
        try:
            for p in sorted(target.iterdir())[:MAX_ENTRIES]:
                try:
                    stat = p.stat()
                    entries.append({
                        "name": p.name,
                        "type": "dir" if p.is_dir() else "file",
                        "size_bytes": stat.st_size if p.is_file() else None,
                    })
                except Exception:
                    continue
        except Exception as e:
            return {"error": f"list failed: {type(e).__name__}: {e}"}

        return {"path": rel, "count": len(entries), "entries": entries}
