# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Write a file to the agent's Sandbox directory."""

from pathlib import Path
from .. import paths

class WriteSandboxFileTool:
    name = "write_sandbox_file"
    description = (
        "Write a file to the Sandbox directory. Use this for intermediate "
        "data files, cleaned CSVs, database dumps, or temporary outputs. "
        "These files appear in the 'Sandbox' tab in the Library."
    )
    parameters = {
        "file": {
            "type": "string",
            "required": True,
            "description": "Filename to write (e.g. 'cleaned_data.csv')"
        },
        "content": {
            "type": "string",
            "required": True,
            "description": "File content"
        }
    }

    async def run(self, args: dict) -> dict:
        fname = (args.get("file") or "").strip()
        content = args.get("content") or ""
        
        if not fname:
            return {"error": "file is required"}
        if not content:
            return {"error": "content is required"}

        # Prevent directory traversal
        fname = Path(fname).name
        target_dir = paths.sandbox()
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / fname

        import os
        try:
            target_path.write_text(content, encoding="utf-8")
            return {
                "ok": True,
                "file": fname,
                "size": target_path.stat().st_size,
                "path": str(target_path),
                "_debug": {"target_dir": str(target_dir), "cwd": os.getcwd(), "env": os.environ.get("SUNNYWARE_SANDBOX")}
            }
        except Exception as e:
            return {"error": f"write failed: {type(e).__name__}: {e}", "_debug": {"target_dir": str(target_dir), "cwd": os.getcwd()}}
