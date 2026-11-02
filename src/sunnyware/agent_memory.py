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

def delete_memory(key: str) -> bool:
    """Delete a single key from shared memory.

    Returns True if the key existed and was deleted, False otherwise.
    """
    with _lock:
        data = _load()
        if key not in data:
            return False
        del data[key]
        _save(data)
        return True


def clear_memory() -> None:
    """Delete ALL entries from shared memory."""
    with _lock:
        if os.path.exists(MEMORY_FILE):
            try:
                os.remove(MEMORY_FILE)
            except Exception:
                pass

def rename_memory(old_key: str, new_key: str) -> bool:
    """Rename a key in shared memory. Returns True if successful."""
    with _lock:
        data = _load()
        if old_key not in data:
            return False
        data[new_key] = data.pop(old_key)
        _save(data)
        return True

def touch_memory(key: str, ttl: int = 0) -> bool:
    """Refresh timestamp and optionally extend TTL of an existing key without changing its value."""
    with _lock:
        data = _load()
        entry = data.get(key)
        if entry is None:
            return False
        # Ensure stored format is dict-like
        if not isinstance(entry, dict) or "value" not in entry:
            entry = {"value": entry}
        entry["ts"] = time.time()
        if ttl > 0:
            entry["expires_at"] = time.time() + ttl
        data[key] = entry
        _save(data)
        return True

def get_memory_entry(key: str) -> dict | None:
    """Return a single entry with metadata, or None if missing/expired."""
    with _lock:
        data = _load()
        entry = data.get(key)
        if entry is None:
            return None
        if not isinstance(entry, dict) or "value" not in entry:
            # Legacy plain-value format
            return {"key": key, "value": entry, "ts": None, "expires_at": None}
        expires = entry.get("expires_at")
        if expires and time.time() > expires:
            data.pop(key, None)
            _save(data)
            return None
        return {
            "key": key,
            "value": entry["value"],
            "ts": entry.get("ts"),
            "expires_at": expires,
        }

def prune_expired_memory() -> int:
    """Remove all expired entries from the memory file. Returns count removed."""
    with _lock:
        data = _load()
        now = time.time()
        expired_keys = []
        for k, entry in data.items():
            if isinstance(entry, dict):
                expires = entry.get("expires_at")
                if expires and now > expires:
                    expired_keys.append(k)
        for k in expired_keys:
            data.pop(k, None)
        if expired_keys:
            _save(data)
        return len(expired_keys)

def set_memory_ttl(key: str, ttl: int = 0) -> bool:
    """Set or change the TTL of an existing key without modifying its value.

    ttl=0 removes the expiry (persistent).
    Returns False if the key does not exist.
    """
    with _lock:
        data = _load()
        entry = data.get(key)
        if entry is None:
            return False
        if not isinstance(entry, dict) or "value" not in entry:
            entry = {"value": entry}
        if ttl > 0:
            entry["expires_at"] = time.time() + ttl
        else:
            entry.pop("expires_at", None)
        data[key] = entry
        _save(data)
        return True

def list_expired_memory() -> list:
    """Return entries whose TTL has passed, without removing them."""
    with _lock:
        data = _load()
        now = time.time()
        out = []
        for k, entry in data.items():
            if isinstance(entry, dict):
                expires = entry.get("expires_at")
                if expires and now > expires:
                    out.append({
                        "key": k,
                        "value": entry.get("value"),
                        "ts": entry.get("ts"),
                        "expires_at": expires,
                    })
        return out

def bulk_delete_memory(keys: list) -> dict:
    """Delete multiple keys in one call. Returns {"deleted": [...], "missing": [...]}."""
    with _lock:
        data = _load()
        deleted = []
        missing = []
        for k in keys:
            if k in data:
                data.pop(k)
                deleted.append(k)
            else:
                missing.append(k)
        if deleted:
            _save(data)
        return {"deleted": deleted, "missing": missing}

