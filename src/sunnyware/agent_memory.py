# src/sunnyware/agent_memory.py
import json
import os
import threading

MEMORY_FILE = "/data/agent_shared_memory.json"
_lock = threading.Lock()

def write_memory(key: str, value: any):
    """Safely write a key-value pair to the shared agent memory."""
    with _lock:
        data = {}
        if os.path.exists(MEMORY_FILE):
            try:
                with open(MEMORY_FILE, "r") as f:
                    data = json.load(f)
            except Exception:
                pass
        data[key] = value
        # Keep the file small by limiting history
        if len(data) > 10:
            keys = list(data.keys())
            for k in keys[:-10]:
                del data[k]
        try:
            with open(MEMORY_FILE, "w") as f:
                json.dump(data, f)
        except Exception as e:
            print(f"[agent_memory] Write error: {e}", flush=True)

def read_memory(key: str) -> any:
    """Read a value from the shared agent memory."""
    with _lock:
        if os.path.exists(MEMORY_FILE):
            try:
                with open(MEMORY_FILE, "r") as f:
                    data = json.load(f)
                    return data.get(key)
            except Exception:
                pass
    return None
