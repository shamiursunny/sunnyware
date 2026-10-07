from sunnyware import prompts


def test_compact_prompt_basic():
    p = prompts.compact_prompt()
    assert "Sunnyware" in p
    assert "JSON" in p


def test_compact_prompt_with_context():
    p = prompts.compact_prompt("User said: blue")
    assert "User said: blue" in p


def test_native_prompt_basic():
    p = prompts.native_prompt()
    assert "Sunnyware" in p


def test_planner_constant():
    assert "planner" in prompts.PLANNER_SYSTEM.lower()


def test_synth_constant():
    assert "synthesizer" in prompts.SYNTH_SYSTEM.lower()
