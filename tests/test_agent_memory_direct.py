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
