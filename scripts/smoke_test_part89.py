# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 89 smoke test ? self-hosted marked.js.

Verifies:
  1. src/sunnyware/static/marked.min.js exists and is a real marked build
  2. src/sunnyware/static/__init__.py exists (makes static/ a package)
  3. main.py mounts /static via StaticFiles
  4. webui.py references /static/marked.min.js (NOT the CDN)
  5. No jsdelivr CDN references for marked remain
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    flag = "PASS" if ok else "FAIL"
    print(f"  [{flag}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 89: self-hosted marked.js ===")

# 1. marked.min.js
m = SRC / "static" / "marked.min.js"
check("static/marked.min.js exists", m.is_file(), str(m))
if m.is_file():
    size = m.stat().st_size
    check("marked.min.js >= 20 KB", size >= 20_000, f"{size} bytes")
    head = m.read_bytes()[:500].decode("utf-8", errors="ignore").lower()
    check("looks like marked build", "marked" in head)

# 2. __init__.py
init = SRC / "static" / "__init__.py"
check("static/__init__.py exists", init.is_file())

# 3. main.py mount
main_src = (SRC / "main.py").read_text(encoding="utf-8")
check("main.py imports StaticFiles", "from fastapi.staticfiles import StaticFiles" in main_src)
check("main.py mounts /static", 'app.mount("/static"' in main_src)

# 4. webui.py local path
webui_src = (SRC / "webui.py").read_text(encoding="utf-8")
check("webui.py references /static/marked.min.js", "/static/marked.min.js" in webui_src)

# 5. No CDN remaining
check("no jsdelivr marked CDN left", "cdn.jsdelivr.net/npm/marked" not in webui_src)

# Summary
passed = sum(1 for _, ok, _ in checks if ok)
total = len(checks)
print(f"\n{passed}/{total} checks passed")
if passed < total:
    print("\nFAILED CHECKS:")
    for name, ok, detail in checks:
        if not ok:
            print(f"  - {name} {detail}")
    sys.exit(1)
print("ALL PASS")
