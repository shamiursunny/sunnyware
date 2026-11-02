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

def bulk_write_memory(items: dict, ttl: int = 0) -> int:
    """Write multiple key-value pairs in a single atomic save.

    Args:
        items: dict of key -> value
        ttl: optional TTL applied to all entries
    Returns:
        Number of entries written.
    """
    with _lock:
        data = _load()
        now = time.time()
        for k, v in items.items():
            entry = {"value": v, "ts": now}
            if ttl > 0:
                entry["expires_at"] = now + ttl
            data[k] = entry
        # Cap at 50 entries
        if len(data) > 50:
            keys = list(data.keys())
            for k in keys[:-50]:
                del data[k]
        _save(data)
        return len(items)

def bulk_rename_memory(mapping: dict) -> dict:
    """Rename multiple keys in one atomic save.

    Args:
        mapping: dict of old_key -> new_key
    Returns:
        {"renamed": [...], "missing": [...]}
    """
    with _lock:
        data = _load()
        renamed = []
        missing = []
        for old, new in mapping.items():
            if old not in data:
                missing.append(old)
                continue
            if new in data and new != old:
                # New key already exists — skip to avoid data loss
                missing.append(old)
                continue
            data[new] = data.pop(old)
            renamed.append(old)
        if renamed:
            _save(data)
        return {"renamed": renamed, "missing": missing}

def export_memory(status: str = "live") -> dict:
    """Export memory entries as a dictionary without cleaning up expired keys.

    Args:
        status: 'live' (default), 'expired', or 'all'
    Returns:
        dict of key -> value for the selected status.
    """
    with _lock:
        data = _load()
        now = time.time()
        live = {}
        expired = {}
        for k, entry in data.items():
            if not isinstance(entry, dict) or "value" not in entry:
                live[k] = entry
                continue
            expires = entry.get("expires_at")
            if expires and now > expires:
                expired[k] = entry["value"]
            else:
                live[k] = entry["value"]

    if status == "expired":
        return expired
    if status == "all":
        merged = dict(expired)
        merged.update(live)  # live wins if duplicate
        return merged
    return live

def import_memory(data: dict, ttl: int = 0, overwrite: bool = False) -> dict:
    """Import memory entries idempotently.

    Args:
        data: dict of key -> value to import
        ttl: optional TTL applied to all imported entries
        overwrite: if False (default), skip keys that already exist
    Returns:
        {"imported": int, "skipped": int}
    """
    with _lock:
        existing_data = _load()
        now = time.time()
        imported = 0
        skipped = 0
        for k, v in data.items():
            if not overwrite and k in existing_data:
                skipped += 1
                continue
            entry = {"value": v, "ts": now}
            if ttl > 0:
                entry["expires_at"] = now + ttl
            existing_data[k] = entry
            imported += 1
        # Cap at 50 entries
        if len(existing_data) > 50:
            keys = list(existing_data.keys())
            for k in keys[:-50]:
                del existing_data[k]
        if imported:
            _save(existing_data)
        return {"imported": imported, "skipped": skipped}

def get_memory_stats() -> dict:
    """Return summary statistics about shared memory.

    Returns:
        dict with:
          total_live: count of non-expired entries
          total_expired: count of expired entries
          avg_ttl_seconds: average remaining TTL of live entries with a TTL
          oldest_ts: earliest timestamp among live entries (or None)
          newest_ts: latest timestamp among live entries (or None)
    """
    with _lock:
        data = _load()
        now = time.time()
        live = []
        expired_count = 0
        ttl_values = []
        for k, entry in data.items():
            if not isinstance(entry, dict) or "value" not in entry:
                # Legacy plain value: treat as live with no TTL
                live.append({"ts": None, "expires_at": None})
                continue
            expires = entry.get("expires_at")
            if expires and now > expires:
                expired_count += 1
                continue
            live.append({"ts": entry.get("ts"), "expires_at": expires})
            if expires:
                ttl_values.append(expires - now)

    ts_values = [e["ts"] for e in live if e["ts"] is not None]
    return {
        "total_live": len(live),
        "total_expired": expired_count,
        "avg_ttl_seconds": sum(ttl_values) / len(ttl_values) if ttl_values else 0.0,
        "oldest_ts": min(ts_values) if ts_values else None,
        "newest_ts": max(ts_values) if ts_values else None,
    }

