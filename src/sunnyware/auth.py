# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Auth + rate limiting — opt-in via environment variables.

SUNNYWARE_API_KEYS="key1,key2,key3"  (comma-separated; unset = auth disabled)
SUNNYWARE_RATE_LIMIT_PER_MINUTE=60   (default 0 = disabled)

Design: auth is OFF by default so existing deployments/tests don't break.
"""

import os
import time
from collections import defaultdict, deque
from typing import Optional


_KEYS_CACHE: Optional[list] = None
_buckets = defaultdict(deque)
_WINDOW_SEC = 60.0


def _parse_keys() -> list:
    raw = (os.getenv("SUNNYWARE_API_KEYS") or "").strip()
    if not raw:
        return []
    return [k.strip() for k in raw.split(",") if k.strip()]


def load_keys(reload: bool = False) -> list:
    global _KEYS_CACHE
    if _KEYS_CACHE is None or reload:
        _KEYS_CACHE = _parse_keys()
    return _KEYS_CACHE


def auth_enabled() -> bool:
    return len(load_keys()) > 0


def is_valid_key(key: str) -> bool:
    if not key:
        return False
    return key in load_keys()


def mask_key(key: str) -> str:
    if not key or len(key) < 6:
        return "***"
    return key[:3] + "..." + key[-3:]


def rate_limit_enabled() -> bool:
    try:
        return int(os.getenv("SUNNYWARE_RATE_LIMIT_PER_MINUTE", "0") or 0) > 0
    except Exception:
        return False


def rate_limit_per_minute() -> int:
    try:
        return int(os.getenv("SUNNYWARE_RATE_LIMIT_PER_MINUTE", "0") or 0)
    except Exception:
        return 0


def check_rate_limit(key: str) -> dict:
    """Sliding-window rate limit. Returns {ok, limit, remaining, retry_after?}."""
    limit = rate_limit_per_minute()
    if limit <= 0:
        return {"ok": True, "limit": 0, "remaining": -1}

    now = time.time()
    bucket = _buckets[key]
    while bucket and (now - bucket[0]) > _WINDOW_SEC:
        bucket.popleft()

    if len(bucket) >= limit:
        retry_after = int(_WINDOW_SEC - (now - bucket[0])) + 1
        return {
            "ok": False,
            "limit": limit,
            "remaining": 0,
            "retry_after": retry_after,
        }

    bucket.append(now)
    return {"ok": True, "limit": limit, "remaining": limit - len(bucket)}


def reset_rate_limits() -> None:
    _buckets.clear()


def status() -> dict:
    keys = load_keys(reload=True)
    return {
        "auth_enabled": len(keys) > 0,
        "key_count": len(keys),
        "masked_keys": [mask_key(k) for k in keys],
        "rate_limit_enabled": rate_limit_enabled(),
        "rate_limit_per_minute": rate_limit_per_minute(),
        "window_seconds": int(_WINDOW_SEC),
        "protected_prefixes": ["/api/"],
        "public_endpoints": [
            "/", "/about", "/health/live", "/health/ready",
            "/metrics", "/mcp", "/api/auth/status",
        ],
        "auth_header": "X-API-Key (or Authorization: Bearer <key>)",
    }


def extract_key_from_headers(headers: list) -> Optional[str]:
    """Extract API key from ASGI-style headers list [(b'x-api-key', b'...'), ...]."""
    for k, v in headers or []:
        if not isinstance(k, (bytes, bytearray)):
            continue
        lk = k.lower()
        if lk == b"x-api-key":
            try:
                return v.decode("ascii", errors="replace").strip()
            except Exception:
                return None
        if lk == b"authorization":
            try:
                val = v.decode("ascii", errors="replace").strip()
            except Exception:
                continue
            if val.lower().startswith("bearer "):
                return val[7:].strip()
            return val
    return None
