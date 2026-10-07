from sunnyware.planner import _parse_subtasks


def test_valid_json():
    assert _parse_subtasks('{"subtasks": ["a", "b"]}') == ["a", "b"]


def test_markdown_fenced():
    assert _parse_subtasks('```json\n{"subtasks": ["x"]}\n```') == ["x"]


def test_garbage():
    assert _parse_subtasks("not json") == []


def test_caps_at_4():
    r = _parse_subtasks('{"subtasks": ["1","2","3","4","5","6"]}')
    assert len(r) == 4


def test_empty_string():
    assert _parse_subtasks("") == []


def test_bare_list():
    assert _parse_subtasks('["a", "b"]') == ["a", "b"]
