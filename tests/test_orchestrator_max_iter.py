"""Part 584: Tests for configurable MAX_ITERATIONS."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from sunnyware.orchestrator import _effective_max_iterations


def test_default():
    assert _effective_max_iterations() == 3


def test_base_override():
    assert _effective_max_iterations(5) == 5
    assert _effective_max_iterations(1) == 1


def test_clamps_high():
    assert _effective_max_iterations(20) == 10


def test_clamps_low():
    assert _effective_max_iterations(0) == 1
    assert _effective_max_iterations(-5) == 1


def test_env_override(monkeypatch):
    monkeypatch.setenv("SUNNYWARE_MAX_ITERATIONS", "7")
    import importlib
    import sunnyware.orchestrator as m
    importlib.reload(m)
    try:
        assert m._effective_max_iterations() == 7
        assert m.MAX_ITERATIONS == 7
    finally:
        monkeypatch.delenv("SUNNYWARE_MAX_ITERATIONS", raising=False)
        importlib.reload(m)


def test_env_invalid(monkeypatch):
    monkeypatch.setenv("SUNNYWARE_MAX_ITERATIONS", "not-a-number")
    import importlib
    import sunnyware.orchestrator as m
    importlib.reload(m)
    try:
        assert m._effective_max_iterations() == 3
    finally:
        monkeypatch.delenv("SUNNYWARE_MAX_ITERATIONS", raising=False)
        importlib.reload(m)
