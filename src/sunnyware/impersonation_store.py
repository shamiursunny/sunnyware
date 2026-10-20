# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 224a: Impersonation session store."""

import json
import os
import secrets
import time
from pathlib import Path

SESSIONS_FILE = "impersonation_sessions.json"
TTL = 3600  # 1 hour


def _base() -> Path:
    data = Path("/data")
    if data.exists() and os.access(str(data), os.W_OK):
        return data
    return Path("data")


def _load() -> dict:
    p = _base() / SESSIONS_FILE
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(data: dict) -> bool:
    p = _base() / SESSIONS_FILE
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(p)
        return True
    except Exception:
        return False


def start(admin_user: str, target_user: str, reason: str = "") -> dict:
    sessions = _load()
    token = "imp_" + secrets.token_urlsafe(32)
    now = time.time()
    sessions[token] = {
        "admin": admin_user,
        "target": target_user,
        "reason": (reason or "")[:200],
        "created": now,
        "expires": now + TTL,
    }
    # Prune expired
    sessions = {k: v for k, v in sessions.items() if v.get("expires", 0) > now}
    _save(sessions)
    return {"ok": True, "token": token, "target": target_user, "expires_in": TTL}


def stop(token: str) -> bool:
    sessions = _load()
    if token in sessions:
        del sessions[token]
        _save(sessions)
        return True
    return False


def verify(token: str) -> dict:
    """Return the session if valid, else None."""
    if not token:
        return None
    sessions = _load()
    entry = sessions.get(token)
    if not entry:
        return None
    if entry.get("expires", 0) < time.time():
        sessions.pop(token, None)
        _save(sessions)
        return None
    return entry
