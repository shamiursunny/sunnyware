# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 224d: Slack bot config + activity log."""

import json
import os
import secrets
import time
from pathlib import Path

CONFIG_FILE = "slack_config.json"
ACTIVITY_FILE = "slack_activity.json"

DEFAULT_CONFIG = {
    "enabled": False,
    "signing_secret": "",
    "bot_token": "",
    "verify_signature": True,
    "bot_name": "Sunnyware",
}


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


# ─── CONFIG ───
def get_config() -> dict:
    cfg = _load(CONFIG_FILE)
    merged = dict(DEFAULT_CONFIG)
    merged.update(cfg)
    return merged


def get_config_sanitized() -> dict:
    """Returns config with secrets masked."""
    cfg = get_config()
    def _mask(s):
        if not s:
            return ""
        if len(s) <= 8:
            return "•" * len(s)
        return s[:4] + "•" * (len(s) - 8) + s[-4:]
    out = dict(cfg)
    out["signing_secret"] = _mask(cfg.get("signing_secret", ""))
    out["bot_token"] = _mask(cfg.get("bot_token", ""))
    out["has_signing_secret"] = bool(cfg.get("signing_secret"))
    out["has_bot_token"] = bool(cfg.get("bot_token"))
    return out


def update_config(patch: dict) -> dict:
    cfg = _load(CONFIG_FILE)
    for k in ("enabled", "signing_secret", "bot_token", "verify_signature", "bot_name"):
        if k in patch:
            cfg[k] = patch[k]
    _save(CONFIG_FILE, cfg)
    return get_config()


# ─── ACTIVITY LOG ───
def log_activity(user: str, channel: str, prompt: str, response: str, latency_ms: int, ok: bool) -> dict:
    activity = _load(ACTIVITY_FILE)
    aid = "act_" + secrets.token_hex(6)
    entry = {
        "id": aid,
        "ts": time.time(),
        "user": (user or "")[:80],
        "channel": (channel or "")[:80],
        "prompt": (prompt or "")[:300],
        "response": (response or "")[:300],
        "latency_ms": int(latency_ms),
        "ok": bool(ok),
    }
    activity[aid] = entry
    if len(activity) > 1000:
        items = sorted(activity.items(), key=lambda kv: kv[1].get("ts", 0))
        for k, _ in items[:-1000]:
            del activity[k]
    _save(ACTIVITY_FILE, activity)
    return entry


def list_activity(limit: int = 50) -> list:
    activity = _load(ACTIVITY_FILE)
    items = list(activity.values())
    items.sort(key=lambda x: x.get("ts", 0), reverse=True)
    return items[:limit]


def clear_activity() -> bool:
    return _save(ACTIVITY_FILE, {})
