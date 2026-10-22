# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Document diff tool (Part 58).

Compare two documents: workspace files, RAG chunks, or inline text.
Returns unified diff + summary stats + similarity ratio.
Stdlib difflib only — no new dependencies.
"""
import difflib
import os
from pathlib import Path
from typing import Optional

_MAX_LINES = 2000
_MAX_INLINE_CHARS = 200_000


def _workspace_root() -> Path:
    p = os.getenv("SUNNYWARE_WORKSPACE") or os.getenv("WORKSPACE_PATH")
    if p:
        return Path(p).resolve()
    return Path("/data/workspace").resolve()


def _read_workspace_file(name: str) -> tuple:
    root = _workspace_root()
    candidate = (root / name).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None, "file must live inside the workspace"
    if not candidate.exists():
        return None, f"file not found: {name}"
    try:
        text = candidate.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"
    return text, None


def _read_rag_chunk(source: str, chunk_id) -> tuple:
    try:
        from .. import tenant as _tenant
        org_id = _tenant.get_key() or "default"
    except Exception:
        org_id = "default"
    try:
        from ..rag import get_store
    except Exception as e:
        return None, f"rag import failed: {e}"
    try:
        store = get_store(org_id)
        store._ensure_index()  # noqa: SLF001
    except Exception as e:
        return None, f"store load failed: {e}"
    md_list = getattr(store, "_metadata", None) or []
    if not md_list:
        return None, "no documents in store"
    # Normalize source (strip ' (page N)' suffix)
    import re as _re
    norm = _re.compile(r"\s*\(page\s+\d+\)\s*$", _re.IGNORECASE)
    want = norm.sub("", source).strip()
    try:
        cid = int(chunk_id)
    except (TypeError, ValueError):
        return None, "chunk_id must be an integer"
    # Pass 1: exact match (with page suffix)
    for md in md_list:
        if md.get("source") == source and md.get("chunk_id") == cid:
            return md.get("text") or "", None
    # Pass 2: normalized
    for md in md_list:
        if norm.sub("", str(md.get("source") or "")).strip() == want \
                and md.get("chunk_id") == cid:
            return md.get("text") or "", None
    return None, f"chunk not found: source={source} chunk_id={cid}"


def _resolve_side(args: dict, side: str) -> tuple:
    """Return (text, label, error). side is 'left' or 'right'."""
    f = args.get(f"{side}_file")
    if f:
        text, err = _read_workspace_file(f)
        return text, f"file: {f}", err
    src = args.get(f"{side}_source")
    cid = args.get(f"{side}_chunk_id")
    if src and cid is not None:
        text, err = _read_rag_chunk(src, cid)
        return text, f"rag: {src} chunk {cid}", err
    t = args.get(f"{side}_text")
    if isinstance(t, str) and t:
        if len(t) > _MAX_INLINE_CHARS:
            return None, f"{side}_text", f"inline text exceeds {_MAX_INLINE_CHARS} chars"
        return t, f"inline {side}_text", None
    return None, f"{side}_*", (
        f"provide {side}_file, or {side}_source + {side}_chunk_id, or {side}_text"
    )


class DocumentDiffTool:
    name = "document_diff"
    description = "Compare two documents and show differences. Triggers: compare documents, diff files, what changed. Input: doc_a and doc_b. Returns diff."
    parameters = {
        "left_file": {"type": "string", "required": False,
                      "description": "Left workspace file (CSV/TXT/MD/JSON etc.)"},
        "right_file": {"type": "string", "required": False,
                       "description": "Right workspace file"},
        "left_source": {"type": "string", "required": False,
                        "description": "Left RAG source file name"},
        "left_chunk_id": {"type": "integer", "required": False,
                          "description": "Left RAG chunk_id"},
        "right_source": {"type": "string", "required": False,
                         "description": "Right RAG source file name"},
        "right_chunk_id": {"type": "integer", "required": False,
                           "description": "Right RAG chunk_id"},
        "left_text": {"type": "string", "required": False,
                      "description": "Left inline text"},
        "right_text": {"type": "string", "required": False,
                       "description": "Right inline text"},
        "context_lines": {"type": "integer", "required": False,
                          "description": "Unified diff context lines (default 3, max 20)"},
        "ignore_case": {"type": "boolean", "required": False,
                        "description": "Case-insensitive compare"},
        "max_output_lines": {"type": "integer", "required": False,
                             "description": "Cap unified diff lines (default 500, max 2000)"},
    }

    async def run(self, args: dict) -> dict:
        left, left_label, err_l = _resolve_side(args, "left")
        if err_l:
            return {"error": f"left: {err_l}"}
        right, right_label, err_r = _resolve_side(args, "right")
        if err_r:
            return {"error": f"right: {err_r}"}

        try:
            ctx = int(args.get("context_lines") or 3)
        except (TypeError, ValueError):
            ctx = 3
        ctx = max(0, min(ctx, 20))

        try:
            cap = int(args.get("max_output_lines") or 500)
        except (TypeError, ValueError):
            cap = 500
        cap = max(1, min(cap, _MAX_LINES))

        ignore_case = bool(args.get("ignore_case"))

        left_lines = left.splitlines()
        right_lines = right.splitlines()
        # Part 58 fix: stats respect ignore_case; diff display keeps case
        if ignore_case:
            stats_left = [l.lower() for l in left_lines]
            stats_right = [l.lower() for l in right_lines]
        else:
            stats_left = left_lines
            stats_right = right_lines

        sm = difflib.SequenceMatcher(
            None, stats_left, stats_right, autojunk=False
        )
        ratio = round(sm.ratio(), 4)

        add = del_ = same = 0
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                same += (i2 - i1)
            elif tag == "replace":
                del_ += (i2 - i1)
                add += (j2 - j1)
            elif tag == "delete":
                del_ += (i2 - i1)
            elif tag == "insert":
                add += (j2 - j1)

        unified = list(difflib.unified_diff(
            left.splitlines(), right.splitlines(),
            fromfile=left_label, tofile=right_label,
            lineterm="", n=ctx,
        ))
        truncated = False
        if len(unified) > cap:
            unified = unified[:cap]
            truncated = True

        return {
            "left_label": left_label,
            "right_label": right_label,
            "left_chars": len(left),
            "right_chars": len(right),
            "left_lines": len(left.splitlines()),
            "right_lines": len(right.splitlines()),
            "stats": {
                "lines_added": add,
                "lines_removed": del_,
                "lines_same": same,
                "similarity": ratio,  # 0.0 - 1.0
            },
            "identical": ratio == 1.0 and left == right,
            "truncated": truncated,
            "unified_diff": "\n".join(unified),
        }
