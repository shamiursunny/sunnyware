"""Tests for sandboxed file tools (read/write/list/delete/mkdir)."""

import asyncio

import pytest

from sunnyware.tools.read_file import ReadFileTool
from sunnyware.tools.write_file import WriteFileTool
from sunnyware.tools.list_files import ListFilesTool
from sunnyware.tools.delete_file import DeleteFileTool
from sunnyware.tools.mkdir import MkdirTool


def run(tool, args):
    return asyncio.run(tool.run(args))


@pytest.fixture
def tmp_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("SUNNYWARE_WORKSPACE", str(tmp_path))
    return tmp_path


def test_write_read_roundtrip(tmp_workspace):
    assert "error" not in run(WriteFileTool(), {"path": "hello.txt", "content": "hi"})
    r = run(ReadFileTool(), {"path": "hello.txt"})
    assert r["content"] == "hi"
    assert r["size"] == 2


def test_read_missing(tmp_workspace):
    r = run(ReadFileTool(), {"path": "nope.txt"})
    assert "error" in r


def test_mkdir_list_delete(tmp_workspace):
    assert "created" in run(MkdirTool(), {"path": "subdir"})
    names = [e["name"] for e in run(ListFilesTool(), {})["entries"]]
    assert "subdir" in names
    assert "deleted" in run(DeleteFileTool(), {"path": "subdir"})


def test_mkdir_existing(tmp_workspace):
    run(MkdirTool(), {"path": "existing"})
    r = run(MkdirTool(), {"path": "existing"})
    assert r.get("already_existed") is True


def test_path_escape_write_blocked(tmp_workspace):
    r = run(WriteFileTool(), {"path": "../escape.txt", "content": "nope"})
    assert "error" in r


def test_path_escape_mkdir_blocked(tmp_workspace):
    r = run(MkdirTool(), {"path": "../../etc/evil"})
    assert "error" in r


def test_delete_workspace_root_refused(tmp_workspace):
    r = run(DeleteFileTool(), {"path": "."})
    assert "error" in r


def test_delete_nonempty_dir_refused(tmp_workspace):
    run(MkdirTool(), {"path": "outer"})
    run(WriteFileTool(), {"path": "outer/file.txt", "content": "x"})
    r = run(DeleteFileTool(), {"path": "outer"})
    assert "error" in r


def test_list_missing_dir(tmp_workspace):
    r = run(ListFilesTool(), {"path": "does-not-exist"})
    assert "error" in r
