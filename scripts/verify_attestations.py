#!/usr/bin/env python3
"""Verify SHA-256 integrity of every report in reports/latest/."""
import hashlib
import json
import sys
from pathlib import Path

# Force UTF-8 stdout on Windows
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

LATEST = Path("reports/latest")
MANIFEST = LATEST / "MANIFEST.json"

if not MANIFEST.exists():
    print("Missing reports/latest/MANIFEST.json")
    sys.exit(1)

m = json.loads(MANIFEST.read_text())
print("Commit:    " + m["commit_short"])
print("Timestamp: " + m["timestamp_utc"])
print()

ok = True
for name, info in m["reports"].items():
    f = LATEST / info["file"]
    if not f.exists():
        print("  [MISSING]  " + info["file"])
        ok = False
        continue
    actual = hashlib.sha256(f.read_bytes()).hexdigest()
    if actual == info["sha256"]:
        exit_code = info.get("normalized_exit", info["exit_code"])
        tag = "[OK]  " if exit_code == 0 else "[WARN]"
        print("  {} {:<22} {}".format(tag, name, actual[:24] + "..."))
    else:
        print("  [MISMATCH] {}: expected {}, got {}".format(
            name, info["sha256"][:16], actual[:16]))
        ok = False

print()
sys.exit(0 if ok else 1)
