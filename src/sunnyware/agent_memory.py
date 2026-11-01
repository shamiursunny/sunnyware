# src/sunnyware/agent_memory.py
import json
import os
import threading
import time

MEMORY_FILE = "/data/agent_shared_memory.json"
_lock = threading.Lock()


def _load() -> dict:
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save(data: dict) -> None:
    try:
        with open(MEMORY_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"[agent_memory] Write error: {e}", flush=True)


def write_memory(key: str, value: any, ttl: int = 0):
    """Safely write a key-value pair to the shared agent memory.

    If ttl > 0, the entry expires after ttl seconds.
    """
    with _lock:
        data = _load()
        entry = {"value": value, "ts": time.time()}
        if ttl > 0:
            entry["expires_at"] = time.time() + ttl
        data[key] = entry
        # Keep the file small by limiting history (max 50 entries)
        if len(data) > 50:
            keys = list(data.keys())
            for k in keys[:-50]:
                del data[k]
        _save(data)


def read_memory(key: str) -> any:
    """Read a value from the shared agent memory, honouring TTL."""
    with _lock:
        data = _load()
        entry = data.get(key)
        if entry is None:
            return None
        # Support old format (plain value) and new format (dict with 'value')
        if isinstance(entry, dict) and "value" in entry:
            expires = entry.get("expires_at")
            if expires and time.time() > expires:
                data.pop(key, None)
                _save(data)
                return None
            return entry["value"]
        return entry


def list_memory() -> list:
    """Return all non-expired entries as a list of {key, value, ts, expires_at}."""
    with _lock:
        data = _load()
        now = time.time()
        out = []
        expired_keys = []
        for k, entry in data.items():
            if isinstance(entry, dict) and "value" in entry:
                expires = entry.get("expires_at")
                if expires and now > expires:
                    expired_keys.append(k)
                    continue
                out.append({
                    "key": k,
                    "value": entry["value"],
                    "ts": entry.get("ts"),
                    "expires_at": expires,
                })
            else:
                out.append({"key": k, "value": entry, "ts": None, "expires_at": None})
        if expired_keys:
            for k in expired_keys:
                data.pop(k, None)
            _save(data)
        return out
