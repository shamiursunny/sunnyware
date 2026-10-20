# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 221a: User API key management (per-org, hashed)."""

import hashlib
import json
import os
import secrets
import time
from pathlib import Path
from typing import Optional

KEYS_FILE = "api_keys.json"


def _base() -> Path:
    data = Path("/data")
    if data.exists() and os.access(str(data), os.W_OK):
        return data
    return Path("data")


def _load() -> dict:
    p = _base() / KEYS_FILE
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(data: dict) -> bool:
    p = _base() / KEYS_FILE
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(p)
        return True
    except Exception:
        return False


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def create_key(org_id: str, user_email: str, name: str, scopes: list, rate_limit: int) -> dict:
    """Create a new API key. Returns {raw_key, id, ...} — raw key shown ONCE."""
    keys = _load()
    raw = "sk_" + secrets.token_urlsafe(32)
    kid = "key_" + secrets.token_hex(8)
    entry = {
        "id": kid,
        "hash": _hash(raw),
        "prefix": raw[:11],
        "org_id": (org_id or "").strip(),
        "user_email": (user_email or "").lower().strip(),
        "name": (name or "Untitled key").strip()[:80],
        "scopes": list(scopes or ["read"]),
        "rate_limit_per_min": max(1, int(rate_limit or 60)),
        "created_at": time.time(),
        "last_used": None,
        "revoked": False,
        "rpm_limit": 60,  # Part 229: default 60 requests per minute
        "calls": 0,
        "tokens_used": 0,
    }
    keys[kid] = entry
    _save(keys)
    out = dict(entry)
    out.pop("hash", None)
    out["raw_key"] = raw
    return out


def list_keys(org_id: Optional[str] = None, user_email: Optional[str] = None) -> list:
    keys = _load()
    out = []
    for k in keys.values():
        if org_id and k.get("org_id") != org_id:
            continue
        if user_email and k.get("user_email") != user_email.lower():
            continue
        safe = {kk: vv for kk, vv in k.items() if kk != "hash"}
        out.append(safe)
    out.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return out


def revoke_key(key_id: str) -> bool:
    keys = _load()
    if key_id not in keys:
        return False
    keys[key_id]["revoked"] = True
    _save(keys)
    return True


def delete_key(key_id: str) -> bool:
    keys = _load()
    if key_id not in keys:
        return False
    del keys[key_id]
    _save(keys)
    return True


def validate(raw_key: str) -> Optional[dict]:
    """Return key record (no hash) if valid, updating last_used/calls."""
    if not raw_key or not raw_key.startswith("sk_") or len(raw_key) < 20:
        return None
    kh = _hash(raw_key)
    keys = _load()
    for k in keys.values():
        if k.get("revoked"):
            continue
        if k.get("hash") == kh:
            k["last_used"] = time.time()
            k["calls"] = int(k.get("calls", 0)) + 1
            _save(keys)
            return {kk: vv for kk, vv in k.items() if kk != "hash"}
    return None


def record_tokens(key_id: str, tokens: int) -> None:
    keys = _load()
    if key_id in keys:
        keys[key_id]["tokens_used"] = int(keys[key_id].get("tokens_used", 0)) + int(tokens)
        _save(keys)


def update_rpm_limit(key_id: str, rpm_limit: int) -> bool:
    keys = _load(KEYS_FILE)
    if key_id not in keys:
        return False
    keys[key_id]["rpm_limit"] = max(0, rpm_limit)
    _save(KEYS_FILE, keys)
    return True


def update_rate_limit(key_id: str, rate_limit: int) -> bool:
    """Alias for update_rpm_limit, uses the existing rate_limit_per_min field."""
    keys = _load(KEYS_FILE)
    if key_id not in keys:
        return False
    keys[key_id]["rate_limit_per_min"] = max(1, rate_limit)
    _save(KEYS_FILE, keys)
    return True


def regenerate_key(key_id: str) -> dict:
    """Generate a new raw key, update the hash, and return the raw key once."""
    keys = _load()
    if key_id not in keys:
        return None
    
    raw = "sk_" + secrets.token_urlsafe(32)
    keys[key_id]["hash"] = _hash(raw)
    keys[key_id]["prefix"] = raw[:11]
    keys[key_id]["revoked"] = False  # Un-revoke if it was revoked
    keys[key_id]["last_used"] = None  # Reset usage stats
    keys[key_id]["calls"] = 0
    keys[key_id]["tokens_used"] = 0
    _save(keys)
    
    # Return the safe dict (without hash) plus the raw key
    safe = {kk: vv for kk, vv in keys[key_id].items() if kk != "hash"}
    safe["raw_key"] = raw
    return safe
