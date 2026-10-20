# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 233: Invite token store for Team Members."""

import json
import os
import secrets
import time
from pathlib import Path

INVITES_FILE = "team_invites.json"

def _base() -> Path:
    data = Path("/data")
    if data.exists() and os.access(str(data), os.W_OK):
        return data
    return Path("data")

def _load() -> dict:
    p = _base() / INVITES_FILE
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _save(data: dict) -> bool:
    p = _base() / INVITES_FILE
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(p)
        return True
    except Exception:
        return False

def create_invite(email: str, role: str) -> dict:
    invites = _load()
    token = "inv_" + secrets.token_urlsafe(32)
    now = time.time()
    entry = {
        "token": token,
        "email": email.lower().strip(),
        "role": role,
        "created_at": now,
        "expires_at": now + 86400 * 7, # 7 days
    }
    invites[token] = entry
    _save(invites)
    return entry

def get_invite(token: str) -> dict:
    invites = _load()
    entry = invites.get(token)
    if not entry:
        return None
    if entry.get("expires_at", 0) < time.time():
        del invites[token]
        _save(invites)
        return None
    return entry

def delete_invite(token: str) -> bool:
    invites = _load()
    if token in invites:
        del invites[token]
        _save(invites)
        return True
    return False
