#!/usr/bin/env python3
"""Bump the minor version of Sunnyware. Every push = new minor version.

Usage:
  python scripts/bump_version.py             # bump and print
  python scripts/bump_version.py --dry-run   # print without writing
  python scripts/bump_version.py --patch     # bump patch instead of minor
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
INIT_FILE = REPO / "src" / "sunnyware" / "__init__.py"


def read_current():
    t = INIT_FILE.read_text(encoding="utf-8")
    m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', t)
    if not m:
        raise SystemExit(f"Could not parse __version__ from {INIT_FILE}")
    return m.group(1), t


def bump(version, patch=False):
    parts = version.split(".")
    while len(parts) < 3:
        parts.append("0")
    major, minor, ptch = int(parts[0]), int(parts[1]), int(parts[2])
    if patch:
        return f"{major}.{minor}.{ptch + 1}"
    return f"{major}.{minor + 1}.0"


def main():
    dry_run = "--dry-run" in sys.argv
    patch = "--patch" in sys.argv

    old, t = read_current()
    new = bump(old, patch=patch)

    if dry_run:
        print(f"[bump] {old} -> {new} (dry-run, not written)")
        return 0

    t = re.sub(
        r'__version__\s*=\s*["\'][^"\']+["\']',
        f'__version__ = "{new}"',
        t,
        count=1,
    )
    INIT_FILE.write_text(t, encoding="utf-8")
    print(f"[bump] {old} -> {new}")
    # Print just the version for CI to capture
    print(f"NEW_VERSION={new}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
