# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Workspace snapshot tool (Part 60).

Zip the workspace (or a subdirectory) into a retrievable archive.
Returns base64 of the archive + metadata. Stdlib zipfile only.
"""
import base64
import io
import os
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional


_MAX_FILES = 2000
_MAX_TOTAL_BYTES = 50 * 1024 * 1024  # 50 MB hard cap
_MAX_RETURN_BYTES = 100 * 1024       # base64 return cap
_SKIP_DIRS = {".git", "__pycache__", ".venv", "node_modules", ".vs",
              ".pytest_cache", ".mypy_cache", ".ruff_cache"}
_SKIP_EXTS = {".pyc", ".pyo", ".so", ".dylib", ".dll"}


def _workspace_root() -> Path:
    p = os.getenv("SUNNYWARE_WORKSPACE") or os.getenv("WORKSPACE_PATH")
    if p:
        return Path(p).resolve()
    return Path("/data/workspace").resolve()


def _should_skip(p: Path) -> bool:
    if p.is_dir():
        return p.name in _SKIP_DIRS
    if p.suffix.lower() in _SKIP_EXTS:
        return True
    return False


class WorkspaceSnapshotTool:
    name = "workspace_snapshot"
    description = (
        "Create a zip archive of the workspace (or a subdirectory) and "
        "return its contents as base64 + the file path. Useful for "
        "bundling multiple deliverable files (reports, charts, data) into "
        "one downloadable artifact, or archiving evidence for compliance. "
        "Skips .git, __pycache__, .venv, and other noise."
    )
    parameters = {
        "subpath": {
            "type": "string",
            "description": "Subdirectory relative to workspace (default: whole workspace)",
            "required": False,
        },
        "name": {
            "type": "string",
            "description": "Output filename (default snapshot-<UTC timestamp>.zip)",
            "required": False,
        },
        "include_base64": {
            "type": "boolean",
            "description": "Return base64 of the archive (default true, capped at 100 KB)",
            "required": False,
        },
    }

    async def run(self, args: dict) -> dict:
        root = _workspace_root()
        try:
            root.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return {"error": f"workspace not writable: {e}"}

        subpath = (args.get("subpath") or "").strip().strip("/").strip("\\")
        if subpath:
            target = (root / subpath).resolve()
            try:
                target.relative_to(root)
            except ValueError:
                return {"error": "subpath escapes workspace"}
            if not target.exists():
                return {"error": f"subpath not found: {subpath}"}
        else:
            target = root

        name = (args.get("name") or "").strip()
        if not name:
            ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
            name = f"snapshot-{ts}.zip"
        # Sanitize
        name = "".join(c if (c.isalnum() or c in "._-") else "_" for c in name)
        if not name.lower().endswith(".zip"):
            name += ".zip"
        if len(name) > 120:
            name = name[:116] + ".zip"

        out_path = (root / name).resolve()
        try:
            out_path.relative_to(root)
        except ValueError:
            return {"error": "output name escapes workspace"}

        files_added = 0
        total_bytes = 0
        skipped = 0
        truncated = False

        try:
            with zipfile.ZipFile(str(out_path), "w",
                                 compression=zipfile.ZIP_DEFLATED) as zf:
                if target.is_file():
                    arcname = target.name
                    zf.write(str(target), arcname)
                    files_added = 1
                    total_bytes = target.stat().st_size
                else:
                    for p in target.rglob("*"):
                        if files_added >= _MAX_FILES:
                            truncated = True
                            break
                        if _should_skip(p):
                            skipped += 1
                            continue
                        if not p.is_file():
                            continue
                        # Skip our own output file (avoid recursion)
                        if p.resolve() == out_path:
                            continue
                        try:
                            sz = p.stat().st_size
                        except Exception:
                            continue
                        if total_bytes + sz > _MAX_TOTAL_BYTES:
                            truncated = True
                            break
                        arcname = str(p.relative_to(target)) if target != root \
                            else str(p.relative_to(root))
                        try:
                            zf.write(str(p), arcname)
                            files_added += 1
                            total_bytes += sz
                        except Exception:
                            continue
        except Exception as e:
            return {"error": f"zip failed: {type(e).__name__}: {e}"}

        try:
            zip_size = out_path.stat().st_size
        except Exception:
            zip_size = 0

        result = {
            "filename": name,
            "path": str(out_path),
            "files_added": files_added,
            "skipped_entries": skipped,
            "raw_bytes": total_bytes,
            "zip_bytes": zip_size,
            "compression_ratio": round(zip_size / total_bytes, 4) if total_bytes else None,
            "truncated": truncated,
        }

        include_b64 = args.get("include_base64", True)
        if include_b64 and zip_size <= _MAX_RETURN_BYTES:
            try:
                result["base64"] = base64.b64encode(
                    out_path.read_bytes()).decode("ascii")
                result["returned_base64"] = True
            except Exception:
                result["returned_base64"] = False
        else:
            result["returned_base64"] = False
            if include_b64 and zip_size > _MAX_RETURN_BYTES:
                result["note"] = (
                    f"archive is {zip_size} bytes, exceeds {_MAX_RETURN_BYTES} "
                    f"base64 return cap. Use the path instead."
                )

        return result
