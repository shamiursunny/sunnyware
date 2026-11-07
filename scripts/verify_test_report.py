#!/usr/bin/env python3
"""Verify SHA-256 integrity of the latest test report."""
import hashlib
import sys
from pathlib import Path

REPORT = Path("test-results/latest.txt")
HASH_FILE = Path("test-results/latest.sha256")

if not REPORT.exists() or not HASH_FILE.exists():
    print("Missing test-results/latest.txt or latest.sha256")
    sys.exit(1)

expected = HASH_FILE.read_text().split()[0].strip()
actual = hashlib.sha256(REPORT.read_bytes()).hexdigest()

if expected == actual:
    print(f"OK Report hash matches: {actual[:32]}...")
    sys.exit(0)
else:
    print("MISMATCH")
    print(f"   Expected: {expected}")
    print(f"   Actual:   {actual}")
    sys.exit(1)
