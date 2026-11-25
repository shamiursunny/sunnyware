# SPDX-License-Identifier: AGPL-3.0-only
# Module: tool_cache — feature-flagged, zero-token, opt-in
import hashlib, json, os, time

_ENABLED = os.getenv("SUNNYWARE_TOOL_CACHE", "0") == "1"
_TTL = int(os.getenv("SUNNYWARE_TOOL_CACHE_TTL", "300"))
_ALLOWED = frozenset(
    x for x in os.getenv(
        "SUNNYWARE_TOOL_CACHE_ALLOW",
        "web_search,fred_economic,weather,url_metadata"
    ).split(",") if x.strip()
)
_store: dict = {}

def _key(tool: str, args: dict) -> str:
    raw = json.dumps({"t": tool, "a": args}, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()

def get(tool: str, args: dict):
    if not _ENABLED or tool not in _ALLOWED:
        return None
    k = _key(tool, args)
    ent = _store.get(k)
    if ent and (time.time() - ent[0]) < _TTL:
        return ent[1]
    _store.pop(k, None)
    return None

def set(tool: str, args: dict, value) -> None:
    if _ENABLED and tool in _ALLOWED:
        _store[_key(tool, args)] = (time.time(), value)
