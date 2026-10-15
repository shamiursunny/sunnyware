# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 126: persistent text-document library.

Bloomberg Drive-inspired: named documents that persist across
sessions, with tags and keyword search. No LLM, no network.

Storage:
  <data_root>/documents/{name}.txt         # content
  <data_root>/documents/{name}.meta.json   # metadata
"""
import json
import re
import time
from pathlib import Path


_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.\-]{0,63}$")
_MAX_CONTENT_BYTES = 512 * 1024
_MAX_DOCS = 500
_MAX_TAGS = 20
_MAX_TAG_LEN = 32


def _docs_dir() -> Path:
    from .. import paths
    d = paths.data_root() / "documents"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_name(name: str) -> str:
    n = (name or "").strip()
    if not _NAME_RE.match(n):
        raise ValueError(
            "invalid name: start with a letter, then letters/digits/._- "
            "(max 64 chars)"
        )
    if ".." in n or n.startswith("."):
        raise ValueError("invalid name")
    return n


def _paths(name: str):
    d = _docs_dir()
    n = _safe_name(name)
    txt = (d / (n + ".txt")).resolve()
    meta = (d / (n + ".meta.json")).resolve()
    for p in (txt, meta):
        if not str(p).startswith(str(d)):
            raise ValueError("path escapes documents dir")
    return txt, meta


def _clean_tags(tags):
    if not tags:
        return []
    if isinstance(tags, str):
        parts = [t.strip() for t in tags.split(",")]
    elif isinstance(tags, list):
        parts = [str(t).strip() for t in tags]
    else:
        return []
    out = []
    for t in parts:
        if not t:
            continue
        if len(t) > _MAX_TAG_LEN:
            t = t[:_MAX_TAG_LEN]
        if t not in out:
            out.append(t)
        if len(out) >= _MAX_TAGS:
            break
    return out


def list_documents():
    d = _docs_dir()
    out = []
    for meta_p in sorted(d.glob("*.meta.json"))[:_MAX_DOCS]:
        try:
            m = json.loads(meta_p.read_text(encoding="utf-8"))
        except Exception:
            continue
        out.append({
            "name": m.get("name") or meta_p.stem.replace(".meta", ""),
            "description": m.get("description", ""),
            "tags": m.get("tags") or [],
            "size_bytes": m.get("size_bytes"),
            "char_count": m.get("char_count"),
            "created_at": m.get("created_at"),
            "updated_at": m.get("updated_at"),
        })
    return out


def get_document(name: str):
    txt, meta = _paths(name)
    if not txt.exists():
        return None
    content = txt.read_text(encoding="utf-8")
    m = {}
    try:
        if meta.exists():
            m = json.loads(meta.read_text(encoding="utf-8"))
    except Exception:
        m = {}
    return {
        "name": m.get("name") or name,
        "description": m.get("description", ""),
        "tags": m.get("tags") or [],
        "content": content,
        "size_bytes": len(content.encode("utf-8")),
        "char_count": len(content),
        "created_at": m.get("created_at"),
        "updated_at": m.get("updated_at"),
    }


def save_document(name, content, description="", tags=None):
    txt, meta = _paths(name)
    if not isinstance(content, str):
        content = str(content)
    size = len(content.encode("utf-8"))
    if size > _MAX_CONTENT_BYTES:
        raise ValueError("content too large (>512KB)")
    prev = {}
    if meta.exists():
        try:
            prev = json.loads(meta.read_text(encoding="utf-8"))
        except Exception:
            prev = {}
    now = int(time.time())
    txt.write_text(content, encoding="utf-8")
    tags_clean = _clean_tags(tags) or (prev.get("tags") or [])
    meta_obj = {
        "name": _safe_name(name),
        "description": str(description or prev.get("description", "")),
        "tags": tags_clean,
        "size_bytes": size,
        "char_count": len(content),
        "created_at": prev.get("created_at") or now,
        "updated_at": now,
    }
    meta.write_text(json.dumps(meta_obj, indent=2), encoding="utf-8")
    return meta_obj


def delete_document(name):
    txt, meta = _paths(name)
    if not txt.exists():
        return False
    try:
        txt.unlink()
    except Exception:
        pass
    try:
        if meta.exists():
            meta.unlink()
    except Exception:
        pass
    return True


def search_documents(query, limit=10):
    q = (query or "").strip().lower()
    if not q:
        return []
    terms = [t for t in re.split(r"\s+", q) if t]
    d = _docs_dir()
    results = []
    for meta_p in sorted(d.glob("*.meta.json")):
        try:
            m = json.loads(meta_p.read_text(encoding="utf-8"))
        except Exception:
            continue
        name = m.get("name") or meta_p.stem.replace(".meta", "")
        txt_p = d / (name + ".txt")
        content = ""
        if txt_p.exists():
            try:
                content = txt_p.read_text(encoding="utf-8")
            except Exception:
                content = ""
        hay = (name + " " + (m.get("description") or "") + " "
               + " ".join(m.get("tags") or []) + " " + content).lower()
        score = 0
        hits = []
        for t in terms:
            c = hay.count(t)
            if c > 0:
                score += c
                hits.append(t)
        if score == 0:
            continue
        results.append({
            "name": name,
            "description": m.get("description", ""),
            "tags": m.get("tags") or [],
            "score": score,
            "matched_terms": hits,
            "snippet": content[:300] if content else "",
            "updated_at": m.get("updated_at"),
        })
    results.sort(key=lambda r: -r["score"])
    return results[:max(1, limit)]


def stats():
    docs = list_documents()
    total_bytes = sum((doc.get("size_bytes") or 0) for doc in docs)
    tag_counts = {}
    for doc in docs:
        for t in doc.get("tags") or []:
            tag_counts[t] = tag_counts.get(t, 0) + 1
    top_tags = sorted(tag_counts.items(), key=lambda kv: -kv[1])[:10]
    persistent = False
    try:
        from .. import paths
        persistent = paths.using_persistent_storage()
    except Exception:
        persistent = False
    return {
        "count": len(docs),
        "total_bytes": total_bytes,
        "top_tags": top_tags,
        "using_persistent_storage": persistent,
    }


class DocumentLibraryTool:
    name = "document_library"
    description = (
        "Persistent text-document library. Save named documents with "
        "optional description and tags, list them, retrieve content, "
        "keyword-search across name/description/tags/content, and delete. "
        "Documents survive restarts (stored in the persistent data dir). "
        "Use to keep client briefs, reference material, and analyses "
        "available across sessions. No LLM, no network."
    )
    parameters = {
        "action": {
            "type": "string",
            "description": "One of: add, list, get, search, delete, stats",
            "required": True,
        },
        "name": {
            "type": "string",
            "description": "Document name (letter, then letters/digits/._-)",
            "required": False,
        },
        "content": {
            "type": "string",
            "description": "Text content (for action=add)",
            "required": False,
        },
        "description": {
            "type": "string",
            "description": "Short description (for action=add)",
            "required": False,
        },
        "tags": {
            "type": "string",
            "description": "Comma-separated tags, e.g. 'insurance,client' (for action=add)",
            "required": False,
        },
        "query": {
            "type": "string",
            "description": "Keyword query (for action=search)",
            "required": False,
        },
        "limit": {
            "type": "integer",
            "description": "Max results (search, default 10, max 50)",
            "required": False,
        },
    }

    async def run(self, args: dict) -> dict:
        action = (args.get("action") or "").strip().lower()
        if not action:
            return {"error": "action is required",
                    "available": ["add", "list", "get", "search",
                                  "delete", "stats"]}

        if action == "list":
            docs = list_documents()
            return {"count": len(docs), "documents": docs}

        if action == "stats":
            return stats()

        if action == "search":
            q = (args.get("query") or "").strip()
            if not q:
                return {"error": "query is required for search"}
            limit = max(1, min(int(args.get("limit") or 10), 50))
            results = search_documents(q, limit=limit)
            return {"query": q, "count": len(results), "results": results}

        if action not in ("add", "get", "delete"):
            return {"error": "unknown action '" + action + "'",
                    "available": ["add", "list", "get", "search",
                                  "delete", "stats"]}

        name = (args.get("name") or "").strip()
        if not name:
            return {"error": "name is required"}

        if action == "add":
            content = args.get("content")
            if content is None:
                return {"error": "content is required for add"}
            try:
                meta_obj = save_document(
                    name, str(content),
                    description=args.get("description") or "",
                    tags=args.get("tags"),
                )
            except ValueError as e:
                return {"error": str(e)}
            return {"saved": True, "document": {
                "name": meta_obj["name"],
                "description": meta_obj["description"],
                "tags": meta_obj["tags"],
                "size_bytes": meta_obj["size_bytes"],
                "char_count": meta_obj["char_count"],
            }}

        if action == "get":
            try:
                doc = get_document(name)
            except ValueError as e:
                return {"error": str(e)}
            if doc is None:
                return {"error": "document not found: " + name}
            return doc

        if action == "delete":
            try:
                ok = delete_document(name)
            except ValueError as e:
                return {"error": str(e)}
            return {"deleted": ok, "name": name}

        return {"error": "unreachable"}
