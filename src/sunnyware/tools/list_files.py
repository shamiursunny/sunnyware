# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""List files in sandbox or workspace."""

from pathlib import Path


def _base(kind: str = "workspace") -> Path:
    from .. import paths
    return paths.sandbox() if kind == "sandbox" else paths.workspace()


def _safe_path(rel: str, kind: str = "workspace") -> Path:
    base = _base(kind)
    base.mkdir(parents=True, exist_ok=True)
    rel = (rel or ".").strip()
    if rel in (".", ""):
        target = base
    else:
        target = (base / rel).resolve()
    # Prevent escapes
    try:
        target.relative_to(base.resolve())
    except ValueError:
        raise ValueError(f"path escapes {kind}: {rel}")
    return target


MAX_ENTRIES = 200


class ListFilesTool:
    name = "list_files"
    description = "List files in the workspace or sandbox. Optional path filter."
    parameters = {
        "kind": {
            "type": "string",
            "enum": ["workspace", "sandbox"],
            "description": "Which area to list (default: workspace)",
            "required": False,
        },
        "path": {
            "type": "string",
            "description": "Subdirectory path (optional)",
            "required": False,
        },
    }

    async def run(self, args: dict = None, kind: str = None, path: str = None) -> dict:
        # Support both dict form (args) and kwargs form (kind/path)
        if args is None:
            args = {}
        if kind is None:
            kind = args.get("kind", "workspace")
        if path is None:
            path = args.get("path", "")

        rel = str(path or "").strip() or "."
        try:
            target = _safe_path(rel, kind)
        except ValueError as e:
            return {"error": str(e)}

        if not target.exists():
            return {"error": f"path not found: {kind}/{rel}"}
        if not target.is_dir():
            return {"error": f"not a directory: {kind}/{rel}"}

        entries = []
        try:
            for p in sorted(target.iterdir())[:MAX_ENTRIES]:
                try:
                    stat = p.stat()
                    entries.append({
                        "name": p.name,
                        "type": "dir" if p.is_dir() else "file",
                        "size": stat.st_size if p.is_file() else None,
                    })
                except Exception:
                    continue
        except Exception as e:
            return {"error": f"list failed: {type(e).__name__}: {e}"}

        return {"ok": True, "kind": kind, "path": rel, "count": len(entries), "entries": entries}
