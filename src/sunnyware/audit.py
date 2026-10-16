# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 161: tamper-evident audit trail.

Every privileged action gets one line in an append-only JSONL file.
Each entry is signed with HMAC-SHA256 over a canonical JSON form
(prev-hash chained). verify_all() walks the file and reports the
first index whose signature fails.

Design principles:
  - NEVER throws into the request path. All public functions swallow
    exceptions and return safe defaults.
  - Key precedence: SUNNYWARE_AUDIT_KEY -> SUNNYWARE_ADMIN_TOKEN ->
    fixed dev key (with a warning at module import).
  - Storage: /data/audit_log.jsonl when /data exists (HF persistent
    volume); otherwise /tmp/sunnyware_audit_log.jsonl. Override via
    SUNNYWARE_AUDIT_PATH.

Config (opt-in, but on by default):
  SUNNYWARE_AUDIT_ENABLED=1
  SUNNYWARE_AUDIT_KEY=<random hex>      (recommended in prod)
  SUNNYWARE_AUDIT_PATH=<override>
"""

import hashlib
import hmac
import json
import os
import time
from pathlib import Path
from typing import Optional


_DEV_KEY = b"sunnyware-dev-audit-key-DO-NOT-USE-IN-PROD"
_ZERO_HASH = "0" * 64
_KEY_WARNED = False


def _key() -> bytes:
    global _KEY_WARNED
    for name in ("SUNNYWARE_AUDIT_KEY", "SUNNYWARE_ADMIN_TOKEN"):
        v = os.getenv(name)
        if v:
            return v.encode("utf-8")
    if not _KEY_WARNED:
        _KEY_WARNED = True
        print("[audit] WARN: no SUNNYWARE_AUDIT_KEY / SUNNYWARE_ADMIN_TOKEN; "
              "using dev fallback key")
    return _DEV_KEY


def enabled() -> bool:
    v = (os.getenv("SUNNYWARE_AUDIT_ENABLED", "1") or "1").lower()
    return v not in ("0", "false", "no", "off")


def path() -> Path:
    override = os.getenv("SUNNYWARE_AUDIT_PATH")
    if override:
        return Path(override)
    d = Path("/data")
    if d.exists() and os.access(str(d), os.W_OK):
        return d / "audit_log.jsonl"
    return Path("/tmp/sunnyware_audit_log.jsonl")


def _canonical(entry: dict) -> bytes:
    e = {k: v for k, v in entry.items() if k != "sig"}
    return json.dumps(e, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign(entry: dict) -> str:
    return hmac.new(_key(), _canonical(entry), hashlib.sha256).hexdigest()


def _last_hash() -> str:
    p = path()
    if not p.exists():
        return _ZERO_HASH
    last = _ZERO_HASH
    try:
        with p.open("rb") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                    s = e.get("sig")
                    if isinstance(s, str):
                        last = s
                except Exception:
                    pass
    except Exception:
        pass
    return last


def log(action: str, actor: str = "anon", ok: bool = True,
        detail: str = "", **extra) -> Optional[dict]:
    """Append one signed entry. Returns the entry, or None on failure."""
    if not enabled():
        return None
    try:
        entry = {
            "ts": time.time(),
            "action": str(action)[:80],
            "actor": str(actor)[:120],
            "ok": bool(ok),
            "detail": str(detail or "")[:500],
            "prev": _last_hash(),
        }
        for k, v in (extra or {}).items():
            if k in ("sig", "prev", "ts", "action", "actor", "ok", "detail"):
                continue
            # keep values JSON-safe
            try:
                json.dumps(v)
                entry[k] = v
            except Exception:
                entry[k] = str(v)[:200]
        entry["sig"] = sign(entry)
        p = path()
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, sort_keys=True) + "\n")
        return entry
    except Exception:
        return None


def _read_all() -> list:
    p = path()
    if not p.exists():
        return []
    out = []
    try:
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    out.append({"__bad__": True, "__raw__": line[:200]})
    except Exception:
        pass
    return out


def recent(n: int = 50) -> list:
    try:
        n = max(1, min(int(n), 10000))
    except Exception:
        n = 50
    return _read_all()[-n:]


def verify_all() -> dict:
    entries = _read_all()
    bad_index = None
    reason = ""
    expected_prev = _ZERO_HASH
    for i, e in enumerate(entries):
        if e.get("__bad__"):
            bad_index = i; reason = "unparseable line"; break
        sig = e.get("sig")
        if not isinstance(sig, str) or not sig:
            bad_index = i; reason = "missing signature"; break
        if sign(e) != sig:
            bad_index = i; reason = "signature mismatch"; break
        if e.get("prev") != expected_prev:
            bad_index = i; reason = "chain break"; break
        expected_prev = sig
    return {
        "ok": bad_index is None,
        "count": len(entries),
        "first_bad_index": bad_index,
        "reason": reason,
        "path": str(path()),
    }


def stats() -> dict:
    entries = _read_all()
    by_action = {}
    allow = 0
    deny = 0
    first_ts = None
    last_ts = None
    for e in entries:
        a = str(e.get("action") or "unknown")
        by_action[a] = by_action.get(a, 0) + 1
        if e.get("ok"):
            allow += 1
        else:
            deny += 1
        t = e.get("ts")
        if isinstance(t, (int, float)):
            if first_ts is None or t < first_ts: first_ts = t
            if last_ts is None or t > last_ts: last_ts = t
    return {
        "total": len(entries),
        "allow": allow,
        "deny": deny,
        "by_action": by_action,
        "first_ts": first_ts,
        "last_ts": last_ts,
        "path": str(path()),
        "enabled": enabled(),
    }


def clear() -> int:
    """Delete the log file. Returns 0 on success, 1 on failure."""
    p = path()
    try:
        if p.exists():
            p.unlink()
        return 0
    except Exception:
        return 1
