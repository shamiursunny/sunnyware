# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 199: HITL config store — per-tool, per-user decisions."""
import json
import os
from contextvars import ContextVar
from pathlib import Path
from typing import Optional

_SAFE_READ_TOOLS = {
    "web_search", "web_fetch", "calculator", "python_eval",
    "current_time", "weather", "pdf_read", "read_file",
    "list_files", "memory_search", "recall_history",
    "rag_search", "rag_list", "csv_query", "date_calc",
    "citation_lookup", "html_to_text", "url_metadata",
    "document_library", "chart_from_data",
}

_CACHE = {"mtime": 0.0, "data": None}
current_user_key: ContextVar[str] = ContextVar("hitl_user_key", default="")


def _path() -> Path:
    env = os.getenv("SUNNYWARE_HITL_CONFIG")
    if env:
        return Path(env)
    data = Path("/data")
    if data.exists() and os.access(str(data), os.W_OK):
        return data / "hitl_config.json"
    return Path("data") / "hitl_config.json"


def _default() -> dict:
    raw = (os.getenv("SUNNYWARE_HITL_TOOLS") or "").strip()
    g = {}
    if raw:
        for t in raw.split(","):
            t = t.strip()
            # Part 199c: skip safe-read tools (they should always auto-approve
            # unless explicitly overridden in the admin UI)
            if t and t not in _SAFE_READ_TOOLS:
                g[t] = "approve"
    return {"global": g, "overrides": {}}


def _load() -> dict:
    p = _path()
    if not p.exists():
        return _default()
    try:
        mtime = p.stat().st_mtime
        if mtime == _CACHE["mtime"] and _CACHE["data"] is not None:
            return _CACHE["data"]
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            data = _default()
        data.setdefault("global", {})
        data.setdefault("overrides", {})
        # Part 199c: one-time cleanup — strip safe-read tools from 'approve'
        # in global config (these were auto-migrated from env var before fix)
        env_raw = (os.getenv("SUNNYWARE_HITL_TOOLS") or "").strip()
        env_set = set(t.strip() for t in env_raw.split(",") if t.strip()) if env_raw else set()
        dirty = False
        for tool in list(data.get("global", {}).keys()):
            if tool in _SAFE_READ_TOOLS and tool in env_set and data["global"][tool] == "approve":
                # Only strip if it's a safe-read tool that's in the env var (probably migration)
                del data["global"][tool]
                dirty = True
        if dirty:
            try:
                p.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
                _CACHE["mtime"] = p.stat().st_mtime
                _CACHE["data"] = data
            except Exception:
                pass
        _CACHE["mtime"] = p.stat().st_mtime
        _CACHE["data"] = data
        return data
    except Exception:
        return _default()


def _save(data: dict) -> bool:
    p = _path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(p)
        _CACHE["mtime"] = p.stat().st_mtime
        _CACHE["data"] = data
        return True
    except Exception:
        return False


def get_decision(tool_name: str, user_key: Optional[str] = None) -> str:
    data = _load()
    if user_key:
        uo = data.get("overrides", {}).get(user_key, {})
        if tool_name in uo:
            return uo[tool_name]
    g = data.get("global", {})
    if tool_name in g:
        return g[tool_name]
    # Part 199b: Safe-read tools ALWAYS default to auto UNLESS explicitly
    # overridden in config (global or per-user). This prevents the legacy
    # SUNNYWARE_HITL_TOOLS env var from causing 120s hangs on read-only tools.
    if tool_name in _SAFE_READ_TOOLS:
        return "auto"
    env_tools = (os.getenv("SUNNYWARE_HITL_TOOLS") or "").strip()
    if env_tools and tool_name in [t.strip() for t in env_tools.split(",")]:
        return "approve"
    return "approve"


def set_global(tool_name: str, decision: str) -> bool:
    if decision not in ("auto", "approve", "deny"):
        return False
    data = _load()
    data.setdefault("global", {})[tool_name] = decision
    return _save(data)


def set_override(user_key: str, tool_name: str, decision: str) -> bool:
    if decision not in ("auto", "approve", "deny"):
        return False
    data = _load()
    data.setdefault("overrides", {}).setdefault(user_key, {})[tool_name] = decision
    return _save(data)


def bulk_set(decision: str, tools=None, user_key: Optional[str] = None) -> bool:
    if decision not in ("auto", "approve", "deny"):
        return False
    data = _load()
    if user_key:
        bucket = data.setdefault("overrides", {}).setdefault(user_key, {})
    else:
        bucket = data.setdefault("global", {})
    if tools:
        for t in tools:
            bucket[t] = decision
    else:
        try:
            from .tools import _TOOLS
            for t in _TOOLS.keys():
                bucket[t] = decision
        except Exception:
            pass
    return _save(data)


def get_full_config() -> dict:
    return _load()


def reset() -> bool:
    return _save({"global": {}, "overrides": {}})
