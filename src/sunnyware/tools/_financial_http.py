# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 107: shared HTTP helpers for financial data tools.

Provides:
- get_json()      : JSON fetch with retries + timeout
- env_required()  : raises clean error if API key missing
- cache           : tiny in-memory TTL cache (avoids hammering free tiers)
"""
import os
import time
from typing import Optional

try:
    import httpx
    _HAS_HTTPX = True
except Exception:
    _HAS_HTTPX = False


_CACHE = {}   # key -> (expires_at, value)
_DEFAULT_TTL = 300.0
_MAX_RESPONSE = 1024 * 1024


def cache_get(key: str):
    ent = _CACHE.get(key)
    if not ent:
        return None
    exp, val = ent
    if time.time() > exp:
        _CACHE.pop(key, None)
        return None
    return val


def cache_set(key: str, value, ttl: float = _DEFAULT_TTL):
    _CACHE[key] = (time.time() + ttl, value)


def cache_stats() -> dict:
    """Part 113C: diagnostics snapshot of the in-memory cache."""
    now = time.time()
    total = len(_CACHE)
    live = sum(1 for exp, _ in _CACHE.values() if exp > now)
    return {
        "total_keys": total,
        "live_keys": live,
        "expired_keys": total - live,
        "default_ttl": _DEFAULT_TTL,
    }


def cache_clear() -> int:
    """Part 113C: wipe the in-memory cache. Returns number of keys removed."""
    n = len(_CACHE)
    _CACHE.clear()
    return n


def env_required(name: str) -> Optional[str]:
    """Return env value or None if missing. Caller returns friendly error."""
    v = (os.getenv(name) or "").strip()
    return v or None


async def get_json(
    url: str,
    params: Optional[dict] = None,
    headers: Optional[dict] = None,
    timeout: float = 20.0,
    retries: int = 1,
) -> dict:
    """Fetch JSON. On failure returns {'_http_error': '...', '_status': N}."""
    if not _HAS_HTTPX:
        return {"_http_error": "httpx not installed"}
    last_err = None
    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as cli:
                r = await cli.get(url, params=params, headers=headers or {})
                if r.status_code >= 400:
                    return {
                        "_http_error": f"HTTP {r.status_code}",
                        "_status": r.status_code,
                        "_body": r.text[:400],
                    }
                raw = r.content[:_MAX_RESPONSE]
                try:
                    return r.json() if hasattr(r, "json") else __import__("json").loads(raw)
                except Exception:
                    return {"_http_error": "non-JSON response", "_body": raw[:400].decode("utf-8", "replace")}
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            if attempt < retries:
                time.sleep(0.6)
                continue
    return {"_http_error": last_err or "request failed"}
