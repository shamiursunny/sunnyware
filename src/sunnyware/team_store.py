# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 211: Team members + activity log store."""

import json
import os
import secrets
import time
from pathlib import Path
from typing import Optional


def _base() -> Path:
    data = Path("/data")
    if data.exists() and os.access(str(data), os.W_OK):
        return data
    return Path("data")


def _path(name: str) -> Path:
    return _base() / name


def _load(name: str, default: dict) -> dict:
    p = _path(name)
    if not p.exists():
        return dict(default)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return dict(default)


def _save(name: str, data: dict) -> bool:
    p = _path(name)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(p)
        return True
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════
# MEMBERS
# ═══════════════════════════════════════════════════════════
def list_members() -> list:
    members = _load("team_members.json", {})
    return sorted(members.values(), key=lambda m: m.get("added_at", 0), reverse=True)


def get_member(member_id: str) -> Optional[dict]:
    return _load("team_members.json", {}).get(member_id)


def get_member_by_email(email: str) -> Optional[dict]:
    email = (email or "").lower().strip()
    if not email:
        return None
    for m in _load("team_members.json", {}).values():
        if (m.get("email") or "").lower() == email:
            return m
    return None


def add_member(email: str, name: str, role: str, added_by: str = "") -> dict:
    members = _load("team_members.json", {})
    mid = "m_" + secrets.token_hex(6)
    member = {
        "id": mid,
        "email": email.lower().strip(),
        "name": name or email.split("@")[0],
        "role": role or "Viewer",
        "status": "active",
        "added_at": time.time(),
        "added_by": added_by,
        "last_login": None,
        "last_logout": None,
    }
    members[mid] = member
    _save("team_members.json", members)
    log_activity(email, "member_added", f"Role: {role}, Added by: {added_by}")
    return member


def update_member(member_id: str, patch: dict) -> Optional[dict]:
    members = _load("team_members.json", {})
    if member_id not in members:
        return None
    old_role = members[member_id].get("role")
    members[member_id].update(patch)
    _save("team_members.json", members)
    if "role" in patch and patch["role"] != old_role:
        log_activity(members[member_id].get("email", ""), "role_changed", f"{old_role} -> {patch['role']}")
    return members[member_id]


def delete_member(member_id: str) -> bool:
    members = _load("team_members.json", {})
    if member_id not in members:
        return False
    email = members[member_id].get("email", "")
    del members[member_id]
    _save("team_members.json", members)
    log_activity(email, "member_deleted", "")
    return True


# ═══════════════════════════════════════════════════════════
# ACTIVITY
# ═══════════════════════════════════════════════════════════
def log_activity(user: str, action: str, details: str = "") -> dict:
    activity = _load("team_activity.json", {})
    aid = "a_" + secrets.token_hex(6)
    entry = {
        "id": aid,
        "user": (user or "system").lower().strip(),
        "action": action,
        "details": details,
        "ts": time.time(),
    }
    activity[aid] = entry
    # Keep last 1000
    if len(activity) > 1000:
        items = sorted(activity.items(), key=lambda kv: kv[1].get("ts", 0))
        for k, _ in items[:-1000]:
            del activity[k]
    _save("team_activity.json", activity)
    return entry


def list_activity(limit: int = 200, user: str = "", action_filter: str = "") -> list:
    activity = _load("team_activity.json", {})
    items = list(activity.values())
    if user:
        items = [i for i in items if (i.get("user") or "").lower() == user.lower()]
    if action_filter:
        items = [i for i in items if i.get("action") == action_filter]
    return sorted(items, key=lambda x: x.get("ts", 0), reverse=True)[:limit]


def clear_activity() -> bool:
    return _save("team_activity.json", {})


# ═══════════════════════════════════════════════════════════
# AUTH HOOKS
# ═══════════════════════════════════════════════════════════
def track_login(email: str) -> None:
    member = get_member_by_email(email)
    if member:
        update_member(member["id"], {"last_login": time.time()})
    log_activity(email, "login", "")


def track_logout(email: str) -> None:
    member = get_member_by_email(email)
    if member:
        update_member(member["id"], {"last_logout": time.time()})
    log_activity(email, "logout", "")
