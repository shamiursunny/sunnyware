"""Ensure __version__ is set and follows semver."""
import re
import sunnyware


def test_version_is_semver():
    v = sunnyware.__version__
    assert re.match(r"^\d+\.\d+\.\d+", v), f"Version {v} is not semver"


def test_version_not_zero():
    parts = sunnyware.__version__.split(".")
    major, minor = int(parts[0]), int(parts[1])
    assert (major, minor) >= (1, 0), f"Version {sunnyware.__version__} is below 1.0.0"
