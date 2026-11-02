import sys
sys.path.insert(0, 'src')
from sunnyware import agent_memory
import time
import os
import tempfile

TEMP_FILE = os.path.join(tempfile.gettempdir(), "test_agent_mem.json")


def test_write_and_read():
    agent_memory.MEMORY_FILE = TEMP_FILE
    if os.path.exists(TEMP_FILE):
        os.remove(TEMP_FILE)
    agent_memory.write_memory("foo", "bar")
    assert agent_memory.read_memory("foo") == "bar"


def test_ttl_expiry():
    agent_memory.MEMORY_FILE = TEMP_FILE
    if os.path.exists(TEMP_FILE):
        os.remove(TEMP_FILE)
    agent_memory.write_memory("ttl_key", "ttl_val", ttl=1)
    assert agent_memory.read_memory("ttl_key") == "ttl_val"
    time.sleep(1.1)
    assert agent_memory.read_memory("ttl_key") is None


def test_list_memory():
    agent_memory.MEMORY_FILE = TEMP_FILE
    if os.path.exists(TEMP_FILE):
        os.remove(TEMP_FILE)
    agent_memory.write_memory("a", 1)
    agent_memory.write_memory("b", 2)
    entries = agent_memory.list_memory()
    keys = {e["key"] for e in entries}
    assert "a" in keys and "b" in keys

def test_delete_memory():
    import tempfile, os
    agent_memory.MEMORY_FILE = os.path.join(tempfile.gettempdir(), "test_agent_mem_del.json")
    if os.path.exists(agent_memory.MEMORY_FILE):
        os.remove(agent_memory.MEMORY_FILE)
    agent_memory.write_memory("del_key", "del_val")
    assert agent_memory.read_memory("del_key") == "del_val"
    assert agent_memory.delete_memory("del_key") is True
    assert agent_memory.read_memory("del_key") is None
    assert agent_memory.delete_memory("nonexistent") is False


def test_clear_memory():
    import tempfile, os
    agent_memory.MEMORY_FILE = os.path.join(tempfile.gettempdir(), "test_agent_mem_clear.json")
    if os.path.exists(agent_memory.MEMORY_FILE):
        os.remove(agent_memory.MEMORY_FILE)
    agent_memory.write_memory("a", 1)
    agent_memory.write_memory("b", 2)
    assert len(agent_memory.list_memory()) == 2
    agent_memory.clear_memory()
    assert len(agent_memory.list_memory()) == 0

def test_rename_memory():
    import tempfile, os
    agent_memory.MEMORY_FILE = os.path.join(tempfile.gettempdir(), "test_agent_mem_rename.json")
    if os.path.exists(agent_memory.MEMORY_FILE):
        os.remove(agent_memory.MEMORY_FILE)
    agent_memory.write_memory("old_name", "value123")
    assert agent_memory.rename_memory("old_name", "new_name") is True
    assert agent_memory.read_memory("old_name") is None
    assert agent_memory.read_memory("new_name") == "value123"
    assert agent_memory.rename_memory("nonexistent", "nope") is False

def test_touch_memory():
    import tempfile, os, time
    agent_memory.MEMORY_FILE = os.path.join(tempfile.gettempdir(), "test_agent_mem_touch.json")
    if os.path.exists(agent_memory.MEMORY_FILE):
        os.remove(agent_memory.MEMORY_FILE)
    agent_memory.write_memory("tkey", "tval", ttl=10)
    first = agent_memory.read_memory("tkey")
    assert first == "tval"
    time.sleep(0.05)
    assert agent_memory.touch_memory("tkey", ttl=20) is True
    assert agent_memory.read_memory("tkey") == "tval"
    assert agent_memory.touch_memory("missing", ttl=5) is False

def test_get_memory_entry():
    import tempfile, os
    agent_memory.MEMORY_FILE = os.path.join(tempfile.gettempdir(), "test_agent_mem_get.json")
    if os.path.exists(agent_memory.MEMORY_FILE):
        os.remove(agent_memory.MEMORY_FILE)
    agent_memory.write_memory("gkey", "gval")
    entry = agent_memory.get_memory_entry("gkey")
    assert entry is not None
    assert entry["key"] == "gkey"
    assert entry["value"] == "gval"
    assert entry["ts"] is not None
    assert agent_memory.get_memory_entry("missing") is None

def test_prune_expired_memory():
    import tempfile, os, time
    agent_memory.MEMORY_FILE = os.path.join(tempfile.gettempdir(), "test_agent_mem_prune.json")
    if os.path.exists(agent_memory.MEMORY_FILE):
        os.remove(agent_memory.MEMORY_FILE)
    agent_memory.write_memory("short_ttl", "val1", ttl=1)
    agent_memory.write_memory("no_ttl", "val2")
    agent_memory.write_memory("long_ttl", "val3", ttl=3600)
    time.sleep(1.1)
    removed = agent_memory.prune_expired_memory()
    assert removed == 1
    assert agent_memory.read_memory("short_ttl") is None
    assert agent_memory.read_memory("no_ttl") == "val2"
    assert agent_memory.read_memory("long_ttl") == "val3"

def test_set_memory_ttl():
    import tempfile, os, time
    agent_memory.MEMORY_FILE = os.path.join(tempfile.gettempdir(), "test_agent_mem_ttl.json")
    if os.path.exists(agent_memory.MEMORY_FILE):
        os.remove(agent_memory.MEMORY_FILE)
    agent_memory.write_memory("ttlkey", "ttlval")
    # Add a TTL
    assert agent_memory.set_memory_ttl("ttlkey", ttl=1) is True
    # Expire it
    time.sleep(1.1)
    assert agent_memory.read_memory("ttlkey") is None
    # Re-write and clear TTL
    agent_memory.write_memory("ttlkey2", "val2", ttl=1)
    assert agent_memory.set_memory_ttl("ttlkey2", ttl=0) is True
    time.sleep(1.1)
    assert agent_memory.read_memory("ttlkey2") == "val2"
    # Missing key
    assert agent_memory.set_memory_ttl("missing", ttl=5) is False

def test_list_expired_memory():
    import tempfile, os, time
    agent_memory.MEMORY_FILE = os.path.join(tempfile.gettempdir(), "test_agent_mem_expired.json")
    if os.path.exists(agent_memory.MEMORY_FILE):
        os.remove(agent_memory.MEMORY_FILE)
    agent_memory.write_memory("live_key", "live_val", ttl=3600)
    agent_memory.write_memory("dead_key", "dead_val", ttl=1)
    time.sleep(1.1)
    expired = agent_memory.list_expired_memory()
    assert len(expired) == 1
    assert expired[0]["key"] == "dead_key"
    assert agent_memory.read_memory("live_key") == "live_val"

def test_bulk_delete_memory():
    import tempfile, os
    agent_memory.MEMORY_FILE = os.path.join(tempfile.gettempdir(), "test_agent_mem_bulkdel.json")
    if os.path.exists(agent_memory.MEMORY_FILE):
        os.remove(agent_memory.MEMORY_FILE)
    agent_memory.write_memory("a", 1)
    agent_memory.write_memory("b", 2)
    agent_memory.write_memory("c", 3)
    result = agent_memory.bulk_delete_memory(["a", "c", "missing"])
    assert sorted(result["deleted"]) == ["a", "c"]
    assert result["missing"] == ["missing"]
    assert agent_memory.read_memory("a") is None
    assert agent_memory.read_memory("b") == 2
    assert agent_memory.read_memory("c") is None
