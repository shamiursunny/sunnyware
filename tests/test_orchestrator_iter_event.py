"""Part 589: Tests for the iteration event builder."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from sunnyware.orchestrator import _build_iteration_event


def test_basic():
    ev = _build_iteration_event(1, 3)
    assert ev == {"type": "iteration", "n": 1, "max": 3}


def test_last_iteration():
    ev = _build_iteration_event(3, 3)
    assert ev["n"] == 3
    assert ev["max"] == 3


def test_coerces_to_int():
    ev = _build_iteration_event("2", "5")
    assert ev["n"] == 2
    assert ev["max"] == 5


def test_type_is_iteration():
    assert _build_iteration_event(1, 1)["type"] == "iteration"
