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
