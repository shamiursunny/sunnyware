# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 175: SSO user storage.

Simple JSON store mapping email → {api_key, role, org_id, ...}.
Consulted by auth.is_valid_key() and auth.role_for_key() AFTER env
keys, so existing SUNNYWARE_API_KEYS behavior is preserved exactly.

Storage:
  /data/users.json on HF (persistent volume)
  data/users.json locally
  SUNNYWARE_USERS_STORE override for tests

Cache: file mtime based — cheap stat per call, no TTL drift.
"""

import json
import os
import secrets
import time
from pathlib import Path
from typing import Optional


_CACHE = {"mtime": 0.0, "users": {}}


def _path() -> Path:
    env = os.getenv("SUNNYWARE_USERS_STORE")
    if env:
        return Path(env)
    data = Path("/data")
    if data.exists() and os.access(str(data), os.W_OK):
        return data / "users.json"
    return Path("data") / "users.json"


def _load() -> dict:
    p = _path()
    if not p.exists():
        return {}
    try:
        mtime = p.stat().st_mtime
        if mtime == _CACHE["mtime"]:
            return _CACHE["users"]
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            data = {}
        _CACHE["mtime"] = mtime
        _CACHE["users"] = data
        return data
    except Exception:
        return {}


def _save(users: dict) -> bool:
    p = _path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(users, indent=2, sort_keys=True),
                       encoding="utf-8")
        tmp.replace(p)
        _CACHE["mtime"] = p.stat().st_mtime
        _CACHE["users"] = users
        return True
    except Exception:
        return False


def _new_key() -> str:
    return "sk_" + secrets.token_urlsafe(32)


def get(email: str) -> Optional[dict]:
    """Return the user record for an email, or None."""
    if not email:
        return None
    users = _load()
    return users.get(email.strip().lower())


def upsert(email: str, org_id: str = "", role: str = "analyst") -> dict:
    """Create or update a user. Returns the record (with api_key)."""
    email = (email or "").strip().lower()
    if not email:
        return {}
    users = _load()
    now = time.time()
    record = users.get(email)
    if record is None:
        record = {
            "email": email,
            "api_key": _new_key(),
            "role": role,
            "org_id": org_id,
            "created_at": now,
            "last_login": now,
        }
        users[email] = record
    else:
        if org_id and not record.get("org_id"):
            record["org_id"] = org_id
        if role and record.get("role") != role:
            record["role"] = role
        record["last_login"] = now
    _save(users)
    return record


def delete(email: str) -> bool:
    email = (email or "").strip().lower()
    users = _load()
    if email not in users:
        return False
    del users[email]
    _save(users)
    return True


def list_all() -> list:
    """Return list of user records with api_key redacted."""
    users = _load()
    out = []
    for email, rec in users.items():
        copy = dict(rec)
        # Redact the key for list endpoint
        k = copy.get("api_key", "")
        if k:
            copy["api_key_preview"] = k[:6] + "..." + k[-4:]
        copy.pop("api_key", None)
        out.append(copy)
    return sorted(out, key=lambda r: r.get("created_at", 0), reverse=True)


def role_for_api_key(api_key: str) -> Optional[str]:
    """Reverse lookup: given an API key, return the role, or None."""
    if not api_key:
        return None
    users = _load()
    for rec in users.values():
        if rec.get("api_key") == api_key:
            return rec.get("role", "analyst")
    return None


def email_for_api_key(api_key: str) -> Optional[str]:
    """Reverse lookup: given an API key, return the email, or None."""
    if not api_key:
        return None
    users = _load()
    for email, rec in users.items():
        if rec.get("api_key") == api_key:
            return email
    return None


def has_any_users() -> bool:
    return len(_load()) > 0
