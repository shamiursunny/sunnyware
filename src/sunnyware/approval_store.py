# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 180: Human-in-the-Loop Approval Store."""

import json
import os
import secrets
import time
from pathlib import Path
from typing import Optional

_CACHE = {"mtime": 0.0, "items": {}}

def _path() -> Path:
    env = os.getenv("SUNNYWARE_APPROVALS_STORE")
    if env:
        return Path(env)
    data = Path("/data")
    if data.exists() and os.access(str(data), os.W_OK):
        return data / "approvals.json"
    return Path("data") / "approvals.json"

def _load() -> dict:
    p = _path()
    if not p.exists():
        return {}
    try:
        mtime = p.stat().st_mtime
        if mtime == _CACHE["mtime"]:
            return _CACHE["items"]
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            data = {}
        _CACHE["mtime"] = mtime
        _CACHE["items"] = data
        return data
    except Exception:
        return {}

def _save(items: dict) -> bool:
    p = _path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(items, indent=2, sort_keys=True),
                       encoding="utf-8")
        tmp.replace(p)
        _CACHE["mtime"] = p.stat().st_mtime
        _CACHE["items"] = items
        return True
    except Exception:
        return False

def requires_approval(tool_name: str, user_key: str = "") -> bool:
    """Part 199: Delegates to hitl_config for auto/approve/deny decisions."""
    try:
        from . import hitl_config
        return hitl_config.get_decision(tool_name, user_key) == "approve"
    except Exception:
        raw = (os.getenv("SUNNYWARE_HITL_TOOLS") or "").strip()
        if not raw:
            return False
        tools = [t.strip() for t in raw.split(",") if t.strip()]
        return tool_name in tools

def create_request(tool_name: str, args: dict, user_key: str = "") -> dict:
    items = _load()
    req_id = "req_" + secrets.token_hex(8)
    now = time.time()
    req = {
        "id": req_id,
        "tool": tool_name,
        "args": args,
        "user_key": user_key,
        "status": "pending",
        "created_at": now,
        "resolved_at": None,
    }
    items[req_id] = req
    _save(items)
    return req

def get_request(req_id: str) -> Optional[dict]:
    return _load().get(req_id)

def set_status(req_id: str, status: str) -> bool:
    items = _load()
    if req_id not in items:
        return False
    items[req_id]["status"] = status
    items[req_id]["resolved_at"] = time.time()
    _save(items)
    return True

def list_pending() -> list:
    items = _load()
    pending = [r for r in items.values() if r.get("status") == "pending"]
    return sorted(pending, key=lambda r: r["created_at"])
