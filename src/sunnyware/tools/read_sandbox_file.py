# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Read a file from the agent's Sandbox directory."""

from pathlib import Path
from .. import paths

class ReadSandboxFileTool:
    name = "read_sandbox_file"
    category = "Sandbox"
    description = (
        "Read a file from the Sandbox directory. Use this to inspect "
        "intermediate data, cleaned CSVs, database dumps, or temporary "
        "outputs saved by write_sandbox_file."
    )
    parameters = {
        "file": {
            "type": "string",
            "required": True,
            "description": "Filename to read (e.g. 'cleaned_data.csv')"
        }
    }

    async def run(self, args: dict) -> dict:
        fname = (args.get("file") or "").strip()
        if not fname:
            return {"error": "file is required"}
        fname = Path(fname).name
        target_dir = paths.sandbox()
        target_path = target_dir / fname
        if not target_path.exists():
            return {"error": f"file not found: {fname}"}
        try:
            content = target_path.read_text(encoding="utf-8")
            return {"ok": True, "file": fname, "content": content, "size": target_path.stat().st_size}
        except Exception as e:
            return {"error": f"read failed: {type(e).__name__}: {e}"}
