# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 183: Usage tracking and quota enforcement."""

import json
import os
import time
from pathlib import Path


def _path() -> Path:
    data = Path("/data")
    if data.exists() and os.access(str(data), os.W_OK):
        return data / "usage.json"
    return Path("data") / "usage.json"


def _load() -> dict:
    p = _path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(data: dict) -> None:
    p = _path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True),
                       encoding="utf-8")
        tmp.replace(p)
    except Exception:
        pass


def _today() -> str:
    return time.strftime("%Y-%m-%d")


def increment(org_id: str) -> int:
    """Increment today's call count for the org. Returns new count."""
    if not org_id:
        return 0
    data = _load()
    today = _today()
    key = f"{org_id}:{today}"
    data[key] = data.get(key, 0) + 1
    _save(data)
    return data[key]


def get_usage(org_id: str) -> int:
    """Get today's call count for the org."""
    if not org_id:
        return 0
    data = _load()
    return data.get(f"{org_id}:{_today()}", 0)


def check_quota(org_id: str, limit: int) -> dict:
    """Return {allowed: bool, used: int, limit: int}."""
    if limit < 0:  # -1 means unlimited
        return {"allowed": True, "used": get_usage(org_id),
                "limit": -1, "remaining": -1}
    used = get_usage(org_id)
    return {
        "allowed": used < limit,
        "used": used,
        "limit": limit,
        "remaining": max(0, limit - used),
    }


# ═══════════════════════════════════════════════════════════
# Part 203: Monthly token quota (rolling month, not daily)
# ═══════════════════════════════════════════════════════════
def _this_month() -> str:
    return time.strftime("%Y-%m")


def increment_tokens(org_id: str, count: int) -> int:
    """Add `count` tokens to this month's usage for the org. Returns new total."""
    if not org_id or count <= 0:
        return 0
    data = _load()
    key = f"{org_id}:{_this_month()}:tokens"
    data[key] = data.get(key, 0) + int(count)
    _save(data)
    return data[key]


def get_tokens(org_id: str) -> int:
    """This month's total token usage for the org."""
    if not org_id:
        return 0
    data = _load()
    return data.get(f"{org_id}:{_this_month()}:tokens", 0)


def check_token_quota(org_id: str, limit_millions: int) -> dict:
    """Return {allowed, used, limit, remaining}. -1 limit = unlimited."""
    if limit_millions is None or limit_millions < 0:
        return {"allowed": True, "used": get_tokens(org_id),
                "limit": -1, "remaining": -1}
    limit = int(limit_millions) * 1_000_000
    used = get_tokens(org_id)
    return {
        "allowed": used < limit,
        "used": used,
        "limit": limit,
        "remaining": max(0, limit - used),
    }
