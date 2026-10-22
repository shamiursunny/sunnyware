# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""PDF reader tool (Part 72).

Extract text page-by-page from a PDF in the workspace. Optional table
extraction. Complements pdf_report (writer) with a direct reader —
no RAG indexing needed for one-off reads.
"""
import os
from pathlib import Path


_MAX_CHARS = 400_000
_MAX_PAGES = 500


def _workspace_root() -> Path:
    p = os.getenv("SUNNYWARE_WORKSPACE") or os.getenv("WORKSPACE_PATH")
    if p:
        return Path(p).resolve()
    return Path("/data/workspace").resolve()


class PdfReadTool:
    name = "pdf_read"
    description = "PDF document reader for .pdf files only."
    parameters = {
        "file": {
            "type": "string",
            "description": "Workspace PDF filename (e.g. 'invoice.pdf')",
            "required": True,
        },
        "pages": {
            "type": "array",
            "description": "Optional list of 1-based page numbers. Omit for all.",
            "required": False,
        },
        "max_chars": {
            "type": "integer",
            "description": "Cap total chars returned (default 80000, max 400000)",
            "required": False,
        },
        "extract_tables": {
            "type": "boolean",
            "description": "Attempt table extraction (slower, best-effort)",
            "required": False,
        },
    }

    async def run(self, args: dict) -> dict:
        fname = (args.get("file") or "").strip()
        if not fname:
            return {"error": "file is required"}
        if not fname.lower().endswith(".pdf"):
            return {"error": "only .pdf files are supported"}

        root = _workspace_root()
        candidate = (root / fname).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            return {"error": "file must live inside the workspace"}
        if not candidate.exists():
            return {"error": f"file not found: {fname}"}

        try:
            max_chars = int(args.get("max_chars") or 80000)
        except (TypeError, ValueError):
            max_chars = 80000
        max_chars = max(1000, min(max_chars, _MAX_CHARS))

        page_filter = args.get("pages")
        if page_filter is not None:
            if not isinstance(page_filter, list):
                return {"error": "pages must be a list of integers"}
            try:
                page_filter = [int(p) for p in page_filter]
            except (TypeError, ValueError):
                return {"error": "pages must be integers"}
        else:
            page_filter = None

        extract_tables = bool(args.get("extract_tables", False))

        try:
            from pypdf import PdfReader
        except Exception as e:
            return {"error": f"pypdf not available: {e}"}

        try:
            reader = PdfReader(str(candidate))
            total_pages = len(reader.pages)
        except Exception as e:
            return {"error": f"open failed: {type(e).__name__}: {e}"}

        pages_out = []
        running_chars = 0
        truncated = False

        for i, page in enumerate(reader.pages):
            page_num = i + 1
            if page_filter is not None and page_num not in page_filter:
                continue
            if len(pages_out) >= _MAX_PAGES:
                truncated = True
                break
            try:
                text = page.extract_text() or ""
            except Exception as e:
                text = f"(extract failed: {type(e).__name__}: {e})"
            text = text.strip()
            chars = len(text)
            if running_chars + chars > max_chars:
                allowed = max_chars - running_chars
                text = text[:allowed] + "... [truncated]"
                chars = len(text)
                truncated = True
            running_chars += chars
            entry = {"page": page_num, "text": text, "chars": chars}

            if extract_tables:
                try:
                    tables = page.extract_tables() or []
                    entry["tables"] = [
                        {"rows": len(t), "cols": len(t[0]) if t else 0,
                         "preview": [[c for c in r][:6] for r in t[:5]]}
                        for t in tables
                    ]
                except Exception:
                    entry["tables"] = []

            pages_out.append(entry)
            if truncated and running_chars >= max_chars:
                break

        try:
            size = candidate.stat().st_size
        except Exception:
            size = 0

        return {
            "file": fname,
            "size_bytes": size,
            "total_pages": total_pages,
            "pages_returned": len(pages_out),
            "total_chars": running_chars,
            "truncated": truncated,
            "pages": pages_out,
        }
