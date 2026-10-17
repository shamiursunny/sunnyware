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

# Part 135: RBAC hierarchy. Higher level implies lower.
_ROLE_HIERARCHY = {
    "readonly": 1,
    "analyst": 2,
    "admin": 3,
}
_DEFAULT_ROLE_ENV = "SUNNYWARE_DEFAULT_ROLE"
_DEFAULT_ROLE_FALLBACK = "admin"
_ROLES_CACHE = None
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


def _parse_roles() -> dict:
    """Parse SUNNYWARE_API_ROLES="k1:admin,k2:analyst,k3:readonly"."""
    raw = (os.getenv("SUNNYWARE_API_ROLES") or "").strip()
    if not raw:
        return {}
    out = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair or ":" not in pair:
            continue
        k, _, role = pair.partition(":")
        k = k.strip()
        role = role.strip().lower()
        if not k or role not in _ROLE_HIERARCHY:
            continue
        out[k] = role
    return out


def load_roles(reload: bool = False) -> dict:
    global _ROLES_CACHE
    if _ROLES_CACHE is None or reload:
        _ROLES_CACHE = _parse_roles()
    return _ROLES_CACHE


def default_role() -> str:
    raw = (os.getenv(_DEFAULT_ROLE_ENV) or _DEFAULT_ROLE_FALLBACK).strip().lower()
    if raw not in _ROLE_HIERARCHY:
        return _DEFAULT_ROLE_FALLBACK
    return raw


def role_for_key(key: str) -> str:
    if not key:
        return default_role()
    roles = load_roles() or {}
    if key in roles:
        return roles[key]
    # Part 175: SSO-issued keys (from user_store)
    try:
        from . import user_store as _us
        r = _us.role_for_api_key(key)
        if r:
            return r
    except Exception:
        pass
    return default_role()


def role_level(role: str) -> int:
    return _ROLE_HIERARCHY.get((role or "").lower(), 0)


def has_role(current: str, required: str) -> bool:
    return role_level(current) >= role_level(required)


def auth_enabled() -> bool:
    if len(load_keys()) > 0:
        return True
    # Part 178b: Enable auth if SSO users exist, even without env keys
    try:
        from . import user_store as _us
        return _us.has_any_users()
    except Exception:
        return False


def is_valid_key(key: str) -> bool:
    if not key:
        return False
    # 1. Env-configured keys (existing behavior)
    if key in load_keys():
        return True
    # 2. SSO-issued keys (Part 175)
    try:
        from . import user_store as _us
        return _us.role_for_api_key(key) is not None
    except Exception:
        return False

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


def reset_tenant(tenant_key: str) -> bool:
    """Clear the rate-limit bucket for one tenant. Returns True if it existed."""
    if not tenant_key:
        return False
    existed = tenant_key in _buckets
    if existed:
        try:
            del _buckets[tenant_key]
        except Exception:
            pass
    return existed


def evict_stale(max_age_sec: float = None) -> int:
    """Drop buckets whose newest entry is older than 2x window. Returns
    number of tenants evicted. Cheap; safe to call periodically."""
    if max_age_sec is None:
        max_age_sec = _WINDOW_SEC * 2.0
    now = time.time()
    stale = []
    for tk, bucket in list(_buckets.items()):
        try:
            if not bucket or (now - bucket[-1]) > max_age_sec:
                stale.append(tk)
        except Exception:
            stale.append(tk)
    for tk in stale:
        try:
            del _buckets[tk]
        except Exception:
            pass
    return len(stale)


def per_tenant_snapshot() -> dict:
    """Return current usage per active tenant (within the sliding window)."""
    now = time.time()
    out = {}
    for tk, bucket in _buckets.items():
        try:
            fresh = [t for t in bucket if (now - t) <= _WINDOW_SEC]
            if not fresh:
                continue
            out[tk] = {
                "used": len(fresh),
                "oldest_sec_ago": int(now - fresh[0]),
            }
        except Exception:
            continue
    return out


def tenant_status(tenant_key: str) -> dict:
    """Return rate-limit status for one tenant."""
    limit = rate_limit_per_minute()
    enabled = rate_limit_enabled()
    now = time.time()
    bucket = _buckets.get(tenant_key) if tenant_key else None
    used = 0
    oldest = None
    if bucket:
        fresh = [t for t in bucket if (now - t) <= _WINDOW_SEC]
        used = len(fresh)
        if fresh:
            oldest = int(now - fresh[0])
    remaining = max(0, limit - used) if limit > 0 else -1
    return {
        "tenant_key": tenant_key or "",
        "rate_limit_enabled": enabled,
        "limit_per_minute": limit,
        "window_seconds": int(_WINDOW_SEC),
        "used_in_window": used,
        "remaining_in_window": remaining,
        "oldest_request_sec_ago": oldest,
    }


_BYPASS_PREFIXES_DEFAULT = (
    "/api/rate_limit/status",
    "/api/rate_limit/tenants",
    "/api/rate_limit/reset",
    "/api/rate_limit/evict",
)


def rate_limit_bypass_prefixes() -> tuple:
    """Paths that don't consume rate-limit budget.

    Configurable via SUNNYWARE_RATE_LIMIT_BYPASS (comma-separated).
    Defaults to the admin rate-limit endpoints so operators can
    always inspect/reset the limiter even when they've hit the limit.
    """
    raw = os.getenv("SUNNYWARE_RATE_LIMIT_BYPASS")
    if raw is None:
        return _BYPASS_PREFIXES_DEFAULT
    if not raw.strip():
        return ()
    return tuple(p.strip() for p in raw.split(",") if p.strip())


def is_bypass_path(path: str) -> bool:
    if not path:
        return False
    for prefix in rate_limit_bypass_prefixes():
        if path == prefix or path.startswith(prefix + "/"):
            return True
    return False


def status() -> dict:
    keys = load_keys(reload=True)
    return {
        "auth_enabled": len(keys) > 0,
        "key_count": len(keys),
        "masked_keys": [mask_key(k) for k in keys],
        "rate_limit_enabled": rate_limit_enabled(),
        "rate_limit_per_minute": rate_limit_per_minute(),
        "rate_limit_bypass_prefixes": list(rate_limit_bypass_prefixes()),
        "roles_configured": len(load_roles() or {}),
        "roles_hierarchy": list(_ROLE_HIERARCHY.keys()),
        "default_role": default_role(),
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
