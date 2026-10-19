# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 221b: Chat history audit + flag for review."""

import json
import os
import secrets
import time
from pathlib import Path
from typing import Optional

MESSAGES_FILE = "chat_messages.json"
FLAGS_FILE = "chat_flags.json"


def _base() -> Path:
    data = Path("/data")
    if data.exists() and os.access(str(data), os.W_OK):
        return data
    return Path("data")


def _load(name: str) -> dict:
    p = _base() / name
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(name: str, data: dict) -> bool:
    p = _base() / name
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(p)
        return True
    except Exception:
        return False


def log_message(user: str, role: str, content: str, org_id: str = "", session_id: str = "") -> dict:
    """Log a chat message for audit trail."""
    messages = _load(MESSAGES_FILE)
    mid = "msg_" + secrets.token_hex(6)
    entry = {
        "id": mid,
        "ts": time.time(),
        "user": (user or "").lower().strip(),
        "org_id": org_id,
        "role": role,
        "content": (content or "")[:4000],
        "session_id": session_id or "",
    }
    messages[mid] = entry
    # Keep last 20000 messages
    if len(messages) > 20000:
        items = sorted(messages.items(), key=lambda kv: kv[1].get("ts", 0))
        for k, _ in items[:-20000]:
            del messages[k]
    _save(MESSAGES_FILE, messages)
    return entry


def list_messages(user: str = "", org_id: str = "", search: str = "",
                  since_ts: Optional[float] = None, limit: int = 200) -> list:
    messages = _load(MESSAGES_FILE)
    items = list(messages.values())
    if user:
        items = [m for m in items if m.get("user") == user.lower()]
    if org_id:
        items = [m for m in items if m.get("org_id") == org_id]
    if search:
        s = search.lower()
        items = [m for m in items if s in (m.get("content") or "").lower()]
    if since_ts:
        items = [m for m in items if (m.get("ts", 0) or 0) >= since_ts]
    items.sort(key=lambda x: x.get("ts", 0), reverse=True)
    return items[:limit]


def flag_message(message_id: str, flagged: bool, reason: str = "", reviewer: str = "") -> dict:
    messages = _load(MESSAGES_FILE)
    if message_id not in messages:
        return {"ok": False, "error": "message not found"}
    flags = _load(FLAGS_FILE)
    if flagged:
        flags[message_id] = {
            "message_id": message_id,
            "ts": time.time(),
            "reason": (reason or "")[:300],
            "reviewer": reviewer or "admin",
        }
    else:
        flags.pop(message_id, None)
    _save(FLAGS_FILE, flags)
    return {"ok": True, "flagged": flagged}


def get_flags() -> dict:
    return _load(FLAGS_FILE)


def list_flagged(limit: int = 200) -> list:
    flags = _load(FLAGS_FILE)
    messages = _load(MESSAGES_FILE)
    items = []
    for mid, f in flags.items():
        msg = messages.get(mid)
        if msg:
            m = dict(msg)
            m["flag_reason"] = f.get("reason", "")
            m["flag_reviewer"] = f.get("reviewer", "")
            m["flag_ts"] = f.get("ts", 0)
            items.append(m)
    items.sort(key=lambda x: x.get("flag_ts", 0), reverse=True)
    return items[:limit]


def export_messages(user: str = "", org_id: str = "", limit: int = 5000) -> list:
    """Export for compliance (with option to redact in UI)."""
    return list_messages(user=user, org_id=org_id, limit=limit)


def stats() -> dict:
    messages = _load(MESSAGES_FILE)
    flags = _load(FLAGS_FILE)
    users = set(m.get("user", "") for m in messages.values() if m.get("user"))
    return {
        "total_messages": len(messages),
        "unique_users": len(users),
        "flagged_count": len(flags),
    }
