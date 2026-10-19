# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 222: Two-Factor Authentication store (TOTP + backup codes + trusted devices)."""

import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from typing import Optional

try:
    import pyotp
except ImportError:
    pyotp = None

USERS_FILE = "twofa_users.json"
SESSIONS_FILE = "twofa_sessions.json"
DEVICES_FILE = "twofa_devices.json"

TRUSTED_DEVICE_TTL = 86400 * 30   # 30 days
SESSION_TTL = 86400 * 1           # 1 day


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


def _hash(v: str) -> str:
    return hashlib.sha256(v.encode()).hexdigest()


def _norm_user(user: str) -> str:
    return (user or "").lower().strip()


# ─── USER 2FA CONFIG ───
def get_user(user: str) -> dict:
    key = _norm_user(user)
    users = _load(USERS_FILE)
    u = users.get(key, {})
    return {
        "user": key,
        "enabled": bool(u.get("enabled")),
        "secret": u.get("secret", ""),
        "backup_codes": u.get("backup_codes", []),   # hashed
        "backup_codes_remaining": len(u.get("backup_codes", [])),
        "created_at": u.get("created_at"),
        "enabled_at": u.get("enabled_at"),
    }


def is_enabled(user: str) -> bool:
    return get_user(user).get("enabled", False)


def start_setup(user: str) -> dict:
    """Generate a new secret. User must verify with a code before 2FA is enabled."""
    if pyotp is None:
        return {"ok": False, "error": "pyotp library not installed"}
    key = _norm_user(user)
    users = _load(USERS_FILE)
    cur = users.get(key, {})
    # If already enabled, don't reset — caller must disable first
    if cur.get("enabled"):
        return {"ok": False, "error": "2FA already enabled. Disable first."}
    secret = pyotp.random_base32()
    cur["secret"] = secret
    cur["enabled"] = False
    cur["created_at"] = cur.get("created_at") or time.time()
    users[key] = cur
    _save(USERS_FILE, users)

    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=key or "user", issuer_name="Sunnyware")

    # QR code as base64 PNG
    qr_b64 = ""
    try:
        import qrcode
        import io
        import base64
        img = qrcode.make(uri)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        qr_b64 = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        return {"ok": True, "secret": secret, "uri": uri, "qr_data_url": "", "qr_error": str(e)}
    return {"ok": True, "secret": secret, "uri": uri, "qr_data_url": qr_b64}


def verify_setup(user: str, code: str) -> dict:
    """Verify a TOTP code to finalize setup. Returns backup codes (plaintext, one-time)."""
    if pyotp is None:
        return {"ok": False, "error": "pyotp library not installed"}
    key = _norm_user(user)
    users = _load(USERS_FILE)
    cur = users.get(key)
    if not cur or not cur.get("secret"):
        return {"ok": False, "error": "Start setup first"}
    totp = pyotp.TOTP(cur["secret"])
    if not totp.verify((code or "").strip(), valid_window=1):
        return {"ok": False, "error": "Invalid code"}

    # Enable + generate backup codes
    backup_plain = _generate_backup_codes()
    cur["enabled"] = True
    cur["enabled_at"] = time.time()
    cur["backup_codes"] = [_hash(c) for c in backup_plain]
    users[key] = cur
    _save(USERS_FILE, users)
    return {"ok": True, "backup_codes": backup_plain}


def verify_login(user: str, code: str) -> dict:
    """Verify a TOTP code during login. Returns a session token on success."""
    if pyotp is None:
        return {"ok": False, "error": "pyotp library not installed"}
    key = _norm_user(user)
    users = _load(USERS_FILE)
    cur = users.get(key)
    if not cur or not cur.get("enabled"):
        return {"ok": False, "error": "2FA not enabled for this user"}
    totp = pyotp.TOTP(cur["secret"])
    if not totp.verify((code or "").strip(), valid_window=1):
        return {"ok": False, "error": "Invalid code"}
    return _issue_session(key)


def verify_backup_code(user: str, code: str) -> dict:
    """Consume a backup code. Returns session token on success."""
    key = _norm_user(user)
    users = _load(USERS_FILE)
    cur = users.get(key)
    if not cur or not cur.get("enabled"):
        return {"ok": False, "error": "2FA not enabled for this user"}
    code_norm = (code or "").replace("-", "").replace(" ", "").lower()
    if not code_norm:
        return {"ok": False, "error": "Enter a backup code"}
    target = _hash(code_norm)
    hashes = cur.get("backup_codes", [])
    for h in hashes:
        if hmac.compare_digest(h, target):
            hashes.remove(h)
            cur["backup_codes"] = hashes
            users[key] = cur
            _save(USERS_FILE, users)
            return _issue_session(key)
    return {"ok": False, "error": "Invalid backup code"}


def _generate_backup_codes() -> list:
    codes = []
    for _ in range(10):
        raw = secrets.token_hex(5)
        formatted = raw[:5] + "-" + raw[5:]
        codes.append(formatted)
    return codes


def regenerate_backup_codes(user: str) -> dict:
    key = _norm_user(user)
    users = _load(USERS_FILE)
    cur = users.get(key)
    if not cur or not cur.get("enabled"):
        return {"ok": False, "error": "2FA not enabled"}
    new_codes = _generate_backup_codes()
    cur["backup_codes"] = [_hash(c) for c in new_codes]
    users[key] = cur
    _save(USERS_FILE, users)
    return {"ok": True, "backup_codes": new_codes}


def disable(user: str, code: str) -> dict:
    """Disable 2FA. Requires a valid TOTP code (or backup code) as proof."""
    if pyotp is None:
        return {"ok": False, "error": "pyotp library not installed"}
    key = _norm_user(user)
    users = _load(USERS_FILE)
    cur = users.get(key)
    if not cur or not cur.get("enabled"):
        return {"ok": False, "error": "2FA not enabled"}
    totp = pyotp.TOTP(cur["secret"])
    code_valid = totp.verify((code or "").strip(), valid_window=1)
    if not code_valid:
        # Try backup code
        code_norm = (code or "").replace("-", "").replace(" ", "").lower()
        target = _hash(code_norm)
        code_valid = any(hmac.compare_digest(h, target) for h in cur.get("backup_codes", []))
    if not code_valid:
        return {"ok": False, "error": "Invalid code"}
    cur["enabled"] = False
    cur["secret"] = ""
    cur["backup_codes"] = []
    users[key] = cur
    _save(USERS_FILE, users)
    # Invalidate all sessions for this user
    sessions = _load(SESSIONS_FILE)
    sessions = {k: v for k, v in sessions.items() if v.get("user") != key}
    _save(SESSIONS_FILE, sessions)
    return {"ok": True}


# ─── SESSIONS ───
def _issue_session(user: str) -> dict:
    sessions = _load(SESSIONS_FILE)
    token = "sess_" + secrets.token_urlsafe(32)
    sessions[_hash(token)] = {
        "user": user,
        "expires": time.time() + SESSION_TTL,
        "created": time.time(),
    }
    # Prune expired
    now = time.time()
    sessions = {k: v for k, v in sessions.items() if v.get("expires", 0) > now}
    _save(SESSIONS_FILE, sessions)
    return {"ok": True, "session_token": token, "expires_in": SESSION_TTL}


def verify_session(user: str, token: str) -> bool:
    if not token:
        return False
    sessions = _load(SESSIONS_FILE)
    entry = sessions.get(_hash(token))
    if not entry:
        return False
    if entry.get("user") != _norm_user(user):
        return False
    if entry.get("expires", 0) < time.time():
        return False
    return True


# ─── TRUSTED DEVICES ───
def trust_device(user: str, device_name: str = "") -> dict:
    key = _norm_user(user)
    devices = _load(DEVICES_FILE)
    token = "trust_" + secrets.token_urlsafe(32)
    did = "dev_" + secrets.token_hex(6)
    devices[_hash(token)] = {
        "id": did,
        "user": key,
        "name": (device_name or "Unknown device")[:100],
        "created": time.time(),
        "expires": time.time() + TRUSTED_DEVICE_TTL,
    }
    _save(DEVICES_FILE, devices)
    return {"ok": True, "trusted_token": token, "device_id": did, "expires_in": TRUSTED_DEVICE_TTL}


def verify_trusted_device(user: str, token: str) -> bool:
    if not token:
        return False
    devices = _load(DEVICES_FILE)
    entry = devices.get(_hash(token))
    if not entry:
        return False
    if entry.get("user") != _norm_user(user):
        return False
    if entry.get("expires", 0) < time.time():
        return False
    return True


def list_devices(user: str) -> list:
    key = _norm_user(user)
    devices = _load(DEVICES_FILE)
    items = []
    now = time.time()
    for h, d in devices.items():
        if d.get("user") == key and d.get("expires", 0) > now:
            items.append({
                "id": d["id"],
                "name": d.get("name", "Unknown"),
                "created": d.get("created"),
                "expires": d.get("expires"),
            })
    items.sort(key=lambda x: x.get("created", 0), reverse=True)
    return items


def remove_device(user: str, device_id: str) -> bool:
    devices = _load(DEVICES_FILE)
    for h, d in list(devices.items()):
        if d.get("user") == _norm_user(user) and d.get("id") == device_id:
            del devices[h]
            _save(DEVICES_FILE, devices)
            return True
    return False


def remove_all_devices(user: str) -> int:
    devices = _load(DEVICES_FILE)
    count = 0
    for h, d in list(devices.items()):
        if d.get("user") == _norm_user(user):
            del devices[h]
            count += 1
    _save(DEVICES_FILE, devices)
    return count
