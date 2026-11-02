import sys
sys.path.insert(0, 'src')
from sunnyware.memory import _summarize_old_events


def _row(event_type, content):
    return {"event_type": event_type, "payload": {"content": content}}


def test_summarize_empty():
    assert _summarize_old_events([]) == ""


def test_summarize_no_user_messages():
    rows = [_row("assistant_message", "hello")]
    assert _summarize_old_events(rows) == ""


def test_summarize_single_user():
    rows = [_row("user_message", "what is AAPL price")]
    result = _summarize_old_events(rows)
    assert "AAPL price" in result
    assert result.startswith("Earlier in this conversation")


def test_summarize_multiple_users():
    rows = [
        _row("user_message", "AAPL price"),
        _row("assistant_message", "$180"),
        _row("user_message", "MSFT price"),
        _row("assistant_message", "$400"),
    ]
    result = _summarize_old_events(rows)
    assert "AAPL" in result
    assert "MSFT" in result
    assert "; " in result


def test_summarize_respects_max_chars():
    rows = [_row("user_message", "question " + str(i) + " " + "x" * 80) for i in range(10)]
    result = _summarize_old_events(rows, max_chars=100)
    assert len(result) < 200
    assert result.endswith("...")


def test_summarize_caps_each_snippet():
    rows = [_row("user_message", "x" * 200)]
    result = _summarize_old_events(rows)
    assert len(result) < 200

import asyncio

def test_build_context_with_summary_no_pool():
    from sunnyware.memory import build_context_with_summary
    result = asyncio.run(build_context_with_summary("", max_turns=4))
    assert result == []

def test_should_skip_message_empty():
    from sunnyware.memory import _should_skip_message
    assert _should_skip_message("") is True
    assert _should_skip_message("   ") is True


def test_should_skip_message_short():
    from sunnyware.memory import _should_skip_message
    assert _should_skip_message("ok") is True
    assert _should_skip_message("yes") is True
    assert _should_skip_message("no") is True


def test_should_skip_message_low_value():
    from sunnyware.memory import _should_skip_message
    assert _should_skip_message("thanks") is True
    assert _should_skip_message("got it") is True
    assert _should_skip_message("sure") is True


def test_should_not_skip_substantive():
    from sunnyware.memory import _should_skip_message
    assert _should_skip_message("what is AAPL price") is False
    assert _should_skip_message("AAPL price") is False
    assert _should_skip_message("MSFT earnings report") is False

def test_pruning_threshold_env_override():
    import os, importlib
    os.environ["SUNNYWARE_MIN_HISTORY_CHARS"] = "10"
    import sunnyware.memory as m
    importlib.reload(m)
    assert m.MIN_HISTORY_CONTENT_CHARS == 10
    assert m._should_skip_message("short") is True
    assert m._should_skip_message("this is long enough") is False
    os.environ.pop("SUNNYWARE_MIN_HISTORY_CHARS", None)
    importlib.reload(m)
    assert m.MIN_HISTORY_CONTENT_CHARS == 4
