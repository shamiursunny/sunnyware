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

def test_bulk_write_memory():
    import tempfile, os, time
    agent_memory.MEMORY_FILE = os.path.join(tempfile.gettempdir(), "test_agent_mem_bulkwrite.json")
    if os.path.exists(agent_memory.MEMORY_FILE):
        os.remove(agent_memory.MEMORY_FILE)
    written = agent_memory.bulk_write_memory({"a": 1, "b": 2, "c": 3})
    assert written == 3
    assert agent_memory.read_memory("a") == 1
    assert agent_memory.read_memory("b") == 2
    assert agent_memory.read_memory("c") == 3
    agent_memory.bulk_write_memory({"d": 4}, ttl=1)
    assert agent_memory.read_memory("d") == 4
    time.sleep(1.1)
    assert agent_memory.read_memory("d") is None

def test_bulk_rename_memory():
    import tempfile, os
    agent_memory.MEMORY_FILE = os.path.join(tempfile.gettempdir(), "test_agent_mem_bulkrename.json")
    if os.path.exists(agent_memory.MEMORY_FILE):
        os.remove(agent_memory.MEMORY_FILE)
    agent_memory.write_memory("a", 1)
    agent_memory.write_memory("b", 2)
    agent_memory.write_memory("c", 3)
    result = agent_memory.bulk_rename_memory({"a": "x", "c": "z", "missing": "y"})
    assert sorted(result["renamed"]) == ["a", "c"]
    assert result["missing"] == ["missing"]
    assert agent_memory.read_memory("a") is None
    assert agent_memory.read_memory("x") == 1
    assert agent_memory.read_memory("b") == 2
    assert agent_memory.read_memory("c") is None
    assert agent_memory.read_memory("z") == 3

def test_export_memory_status():
    import tempfile, os, time
    agent_memory.MEMORY_FILE = os.path.join(tempfile.gettempdir(), "test_agent_mem_export.json")
    if os.path.exists(agent_memory.MEMORY_FILE):
        os.remove(agent_memory.MEMORY_FILE)
    agent_memory.write_memory("live_key", "live_val", ttl=3600)
    agent_memory.write_memory("dead_key", "dead_val", ttl=1)
    time.sleep(1.1)
    live_data = agent_memory.export_memory("live")
    assert "live_key" in live_data
    assert "dead_key" not in live_data
    expired_data = agent_memory.export_memory("expired")
    assert "dead_key" in expired_data
    assert "live_key" not in expired_data
    all_data = agent_memory.export_memory("all")
    assert "live_key" in all_data
    assert "dead_key" in all_data

def test_import_memory_idempotent():
    import tempfile, os
    agent_memory.MEMORY_FILE = os.path.join(tempfile.gettempdir(), "test_agent_mem_import.json")
    if os.path.exists(agent_memory.MEMORY_FILE):
        os.remove(agent_memory.MEMORY_FILE)
    agent_memory.write_memory("existing", "old_val")
    result = agent_memory.import_memory({"existing": "new_val", "new1": 10, "new2": 20})
    assert result["imported"] == 2
    assert result["skipped"] == 1
    assert agent_memory.read_memory("existing") == "old_val"
    assert agent_memory.read_memory("new1") == 10
    assert agent_memory.read_memory("new2") == 20
    result = agent_memory.import_memory({"existing": "new_val"}, overwrite=True)
    assert result["imported"] == 1
    assert result["skipped"] == 0
    assert agent_memory.read_memory("existing") == "new_val"

def test_get_memory_stats():
    import tempfile, os, time
    agent_memory.MEMORY_FILE = os.path.join(tempfile.gettempdir(), "test_agent_mem_stats.json")
    if os.path.exists(agent_memory.MEMORY_FILE):
        os.remove(agent_memory.MEMORY_FILE)
    agent_memory.write_memory("live1", "v1", ttl=100)
    agent_memory.write_memory("live2", "v2", ttl=200)
    agent_memory.write_memory("live_no_ttl", "v3")
    agent_memory.write_memory("expired", "v4", ttl=1)
    time.sleep(1.1)
    stats = agent_memory.get_memory_stats()
    assert stats["total_live"] == 3
    assert stats["total_expired"] == 1
    assert stats["avg_ttl_seconds"] > 0
    assert stats["oldest_ts"] is not None
    assert stats["newest_ts"] is not None

def test_set_all_memory_ttl():
    import tempfile, os, time
    agent_memory.MEMORY_FILE = os.path.join(tempfile.gettempdir(), "test_agent_mem_ttl_all.json")
    if os.path.exists(agent_memory.MEMORY_FILE):
        os.remove(agent_memory.MEMORY_FILE)
    agent_memory.write_memory("a", 1)
    agent_memory.write_memory("b", 2)
    assert agent_memory.set_all_memory_ttl(ttl=1) == 2
    time.sleep(1.1)
    assert agent_memory.read_memory("a") is None
    assert agent_memory.read_memory("b") is None
    agent_memory.write_memory("c", 3, ttl=1)
    assert agent_memory.set_all_memory_ttl(ttl=0) == 1
    time.sleep(1.1)
    assert agent_memory.read_memory("c") == 3

def test_export_memory_mixed_formats():
    import tempfile, os, time, json
    # Simulate a file with both legacy plain values and new dict entries
    agent_memory.MEMORY_FILE = os.path.join(tempfile.gettempdir(), "test_agent_mem_export_mixed.json")
    if os.path.exists(agent_memory.MEMORY_FILE):
        os.remove(agent_memory.MEMORY_FILE)
    now = time.time()
    # legacy_plain -> plain value
    # new_live -> dict with no expiry
    # new_expired -> dict already expired
    with open(agent_memory.MEMORY_FILE, "w") as f:
        json.dump({
            "legacy_plain": "plain_val",
            "new_live": {"value": "live_val", "ts": now},
            "new_expired": {"value": "expired_val", "ts": now - 10, "expires_at": now - 5},
        }, f)
    live_data = agent_memory.export_memory("live")
    assert "legacy_plain" in live_data
    assert live_data["legacy_plain"] == "plain_val"
    assert "new_live" in live_data
    assert live_data["new_live"] == "live_val"
    assert "new_expired" not in live_data
    expired_data = agent_memory.export_memory("expired")
    assert "new_expired" in expired_data
    assert expired_data["new_expired"] == "expired_val"
    assert "legacy_plain" not in expired_data
    assert "new_live" not in expired_data
    all_data = agent_memory.export_memory("all")
    assert "legacy_plain" in all_data
    assert "new_live" in all_data
    assert "new_expired" in all_data

def test_import_memory_edge_cases():
    import tempfile, os, time
    agent_memory.MEMORY_FILE = os.path.join(tempfile.gettempdir(), "test_agent_mem_import_edge.json")
    if os.path.exists(agent_memory.MEMORY_FILE):
        os.remove(agent_memory.MEMORY_FILE)
    # Seed one key
    agent_memory.write_memory("seed", "old")
    # 1) No overwrite: skip existing, import new
    r = agent_memory.import_memory({"seed": "new", "fresh": 1})
    assert r["imported"] == 1
    assert r["skipped"] == 1
    assert agent_memory.read_memory("seed") == "old"
    # 2) Overwrite: replace existing
    r = agent_memory.import_memory({"seed": "new"}, overwrite=True)
    assert r["imported"] == 1
    assert r["skipped"] == 0
    assert agent_memory.read_memory("seed") == "new"
    # 3) Import with TTL
    r = agent_memory.import_memory({"temp": "val"}, ttl=1)
    assert r["imported"] == 1
    assert agent_memory.read_memory("temp") == "val"
    time.sleep(1.1)
    assert agent_memory.read_memory("temp") is None
    # 4) Import empty dict
    r = agent_memory.import_memory({})
    assert r["imported"] == 0
    assert r["skipped"] == 0
